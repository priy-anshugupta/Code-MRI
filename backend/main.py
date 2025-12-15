import os
import shutil
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.core.config import settings
from app.services.cloner import clone_repository
from app.services.analyzer import (
    analyze_directory_structure,
    detect_technologies,
    run_static_analysis,
    calculate_aggregate_metrics,
    generate_summary,
)
from app.services.rag import index_repository, get_chat_chain

# ---------------------------------------------------------------------------
# Auto-cleanup: track repo last-access time and delete after TTL (1 hour)
# ---------------------------------------------------------------------------
REPO_TTL_SECONDS = 60 * 60  # 1 hour
repo_access_times: Dict[str, float] = {}
_cleanup_lock = threading.Lock()


def _touch_repo(repo_id: str) -> None:
    """Update last-access timestamp for a repo."""
    with _cleanup_lock:
        repo_access_times[repo_id] = time.time()


def _cleanup_expired_repos() -> None:
    """Delete repos that haven't been accessed within TTL."""
    now = time.time()
    with _cleanup_lock:
        expired = [rid for rid, ts in repo_access_times.items() if now - ts > REPO_TTL_SECONDS]
    for rid in expired:
        repo_path = os.path.join(settings.TEMP_DIR, rid)
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
        with _cleanup_lock:
            repo_access_times.pop(rid, None)


def _cleanup_loop(stop_event: threading.Event) -> None:
    """Background thread that runs cleanup every 5 minutes."""
    while not stop_event.wait(300):
        _cleanup_expired_repos()


_cleanup_stop = threading.Event()
_cleanup_thread: Optional[threading.Thread] = None


def _cleanup_all_repos() -> None:
    """Delete all cloned repos in temp_clones folder."""
    if os.path.exists(settings.TEMP_DIR):
        for entry in os.listdir(settings.TEMP_DIR):
            entry_path = os.path.join(settings.TEMP_DIR, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)
    with _cleanup_lock:
        repo_access_times.clear()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cleanup_thread
    _cleanup_thread = threading.Thread(target=_cleanup_loop, args=(_cleanup_stop,), daemon=True)
    _cleanup_thread.start()
    yield
    # Cleanup on shutdown: stop thread and delete all temp repos
    _cleanup_stop.set()
    _cleanup_all_repos()
    print("Shutdown: cleaned up all temp_clones")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    url: str


class ChatRequest(BaseModel):
    repo_id: str
    message: str

@app.get("/")
def read_root():
    return {"status": "online", "service": "Code MRI Backend"}


@app.post("/analyze")
def analyze_repo(request: AnalyzeRequest):
    """
    Clones a repository and returns its directory structure.
    """
    try:
        # 1. Clone
        repo_path = clone_repository(request.url)
        repo_id = os.path.basename(repo_path)
        _touch_repo(repo_id)

        # 2. Analyze
        file_tree = analyze_directory_structure(repo_path)

        return {
            "message": "Analysis complete",
            "repo_id": repo_id,
            "tree": file_tree,
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/{repo_id}")
def get_report(repo_id: str):
    """
    Retrieve existing analysis for a repo (or re-analyze if simple).
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        file_tree = analyze_directory_structure(repo_path)
        technologies = detect_technologies(repo_path)
        metrics = calculate_aggregate_metrics(repo_path)
        issues = run_static_analysis(repo_path)
        summary = generate_summary(repo_path, technologies, metrics, issues)
        
        return {
            "repo_id": repo_id,
            "tree": file_tree,
            "technologies": technologies,
            "metrics": metrics,
            "issues": issues,
            "summary": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/{repo_id}")
def index_repo_endpoint(repo_id: str):
    """
    Trigger indexing for a cloned repo.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        result = index_repository(repo_path, repo_id)
        return {"message": "Indexing complete", "result": result}
    except Exception as e:
        print(f"Index Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """
    Chat with the codebase.
    """
    _touch_repo(request.repo_id)

    try:
        chain = get_chat_chain(request.repo_id)
        response = chain.invoke(request.message)
        return {"response": response}
    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FileAnalyzeRequest(BaseModel):
    repo_id: str
    file_path: str


@app.post("/analyze-file")
def analyze_file_endpoint(request: FileAnalyzeRequest):
    """
    Analyze a specific file and return AI-generated explanation of what it does.
    """
    from app.services.analyzer import analyze_file_with_ai

    repo_path = os.path.join(settings.TEMP_DIR, request.repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(request.repo_id)

    # Construct full file path
    full_path = os.path.join(repo_path, request.file_path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        result = analyze_file_with_ai(full_path, request.file_path)
        return result
    except Exception as e:
        print(f"File Analysis Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/repo/{repo_id}")
def delete_repo(repo_id: str):
    """
    Manually delete a cloned repo immediately.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)
    with _cleanup_lock:
        repo_access_times.pop(repo_id, None)
    return {"message": "Deleted"}
