import json
import os
from pathlib import Path
from typing import List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, Runnable
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.security import redact_secrets

# High value files to index
HIGH_VALUE_EXTENSIONS = {
    '.md', '.txt', '.py', '.js', '.ts', '.tsx', '.jsx', 
    '.json', '.html', '.css', '.java', '.go', '.rs', '.c', '.cpp'
}
HIGH_VALUE_NAMES = {'Dockerfile', 'Makefile', 'Requirements.txt', 'package.json'}

# Persist indexes at the project root (stable regardless of CWD)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FAISS_ROOT = str(PROJECT_ROOT / "faiss_indexes")

# Fallback (non-vector) index for keyword retrieval
FALLBACK_ROOT = str(PROJECT_ROOT / "fallback_indexes")


def _repo_fallback_path(repo_id: str) -> str:
    return os.path.join(FALLBACK_ROOT, repo_id, "chunks.jsonl")


def _write_fallback_chunks(repo_id: str, splits) -> None:
    os.makedirs(os.path.join(FALLBACK_ROOT, repo_id), exist_ok=True)
    path = _repo_fallback_path(repo_id)
    with open(path, "w", encoding="utf-8") as f:
        for doc in splits:
            payload = {
                "source": doc.metadata.get("source", "unknown"),
                "content": doc.page_content,
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_fallback_chunks(repo_id: str) -> List[dict]:
    path = _repo_fallback_path(repo_id)
    if not os.path.exists(path):
        return []
    chunks: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except Exception:
                continue
    return chunks


def _keyword_retrieve(chunks: List[dict], query: str, k: int = 5) -> List[dict]:
    # Very simple scoring: token overlap; fast and dependency-free.
    q = (query or "").lower()
    q_tokens = {t for t in q.replace("/", " ").replace("_", " ").split() if len(t) >= 3}
    if not q_tokens:
        return chunks[:k]

    scored = []
    for ch in chunks:
        text = (ch.get("content") or "").lower()
        score = 0
        for tok in q_tokens:
            if tok in text:
                score += 1
        if score:
            scored.append((score, ch))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]

def get_embeddings():
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set.")
    return GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=settings.GOOGLE_API_KEY)

def is_high_value_file(file_path: str) -> bool:
    name = os.path.basename(file_path)
    _, ext = os.path.splitext(name)
    return name in HIGH_VALUE_NAMES or ext.lower() in HIGH_VALUE_EXTENSIONS

def index_repository(repo_path: str, repo_id: str):
    """
    Indexes the repository into FAISS.
    """
    documents = []
    
    # 1. Walk and Load
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Simple filter
            if any(p in file_path for p in ['.git', 'node_modules', '__pycache__', 'venv']):
                continue

            if is_high_value_file(file_path):
                try:
                    loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
                    docs = loader.load()
                    
                    for doc in docs:
                        # 2. Redact
                        doc.page_content = redact_secrets(doc.page_content)
                        # Add metadata
                        doc.metadata["source"] = os.path.relpath(file_path, repo_path)
                        doc.metadata["repo_id"] = repo_id
                        
                    documents.extend(docs)
                except Exception as e:
                    # Skip files that fail to load
                    pass

    if not documents:
        return {"indexed": False, "reason": "No indexable documents found."}

    # 3. Chunk
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)

    # Always write fallback chunks so chat can still work without FAISS/embeddings.
    _write_fallback_chunks(repo_id, splits)

    # 4. Upsert to FAISS
    # For FAISS, we typically create a new index for the repo or load existing one
    # Try to build FAISS vector index (optional).
    try:
        embeddings = get_embeddings()
        vectorstore = FAISS.from_documents(splits, embeddings)

        index_path = os.path.join(FAISS_ROOT, repo_id)
        os.makedirs(index_path, exist_ok=True)
        vectorstore.save_local(index_path)
        return {"indexed": True, "vector": True}
    except Exception as e:
        # Fallback chunks already written.
        return {"indexed": True, "vector": False, "warning": str(e)}

def get_chat_chain(repo_id: str) -> Runnable:
    """
    Returns a RAG chain for a specific repository.
    """
    if not settings.GOOGLE_API_KEY:
         raise ValueError("GOOGLE_API_KEY is not set.")

    index_path = os.path.join(FAISS_ROOT, repo_id)
    fallback_chunks = _load_fallback_chunks(repo_id)

    retriever = None
    if os.path.exists(index_path):
        embeddings = get_embeddings()
        vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    elif fallback_chunks:
        # Use keyword retrieval from on-disk chunks.
        def _fallback_retrieve(question: str):
            return _keyword_retrieve(fallback_chunks, question, k=5)

        def format_fallback(docs):
            return "\n\n".join(
                f"Filename: {d.get('source', 'unknown')}\nContent:\n{d.get('content', '')}" for d in docs
            )

        template = """You are an expert developer explaining a codebase.
Answer the question based ONLY on the following context.
Cite filenames when referring to code.
If you don't know the answer, say \"I couldn't find that in the codebase.\"\n\nContext:\n{context}\n\nQuestion: {question}\n"""
        prompt = ChatPromptTemplate.from_template(template)

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=settings.GOOGLE_API_KEY,
        )

        chain = (
            {"context": RunnablePassthrough() | _fallback_retrieve | format_fallback, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        return chain
    else:
        raise ValueError(
            f"Index for repo {repo_id} not found. Run /index/{repo_id} first (or ensure indexing succeeds)."
        )
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2,
        google_api_key=settings.GOOGLE_API_KEY
    )
    
    template = """You are an expert developer explaining a codebase. 
    Answer the question based ONLY on the following context. 
    Cite filenames when referring to code.
    If you don't know the answer, say "I couldn't find that in the codebase."
    
    Context:
    {context}
    
    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(template)

    def format_docs(docs):
        return "\n\n".join(f"Filename: {d.metadata.get('source', 'unknown')}\nContent:\n{d.page_content}" for d in docs)

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain
