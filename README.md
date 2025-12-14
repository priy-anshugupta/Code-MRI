# Project Documentation: The "Code MRI" (Open Source Onboarding Engine)

### 1. Executive Summary

**Project Name:** Code MRI (provisional title)

**Tagline:** "From Zero to Contributor in 5 Minutes."

**Concept:** An intelligent static analysis tool that bridges the gap between raw code and human understanding. It provides an automated "health check" and interactive explanation of any public GitHub repository without executing the code, making it the safest way to explore unknown software.

### 2. Problem Statement

The modern open-source ecosystem faces a critical **Onboarding Bottleneck**:

- **Complexity Overload:** New contributors are overwhelmed by massive file structures and undocumented logic.
- **Safety Risks:** Running unknown code (for example, `npm install`) to learn how it works exposes developers to malware.
- **Maintenance Fatigue:** Senior maintainers waste hours answering repetitive "how does this work?" questions.

**Solution:** A web-based platform that treats code as data. It scans, visualizes, and explains the project structure and quality *statically*, acting as an automated mentor for every new developer.

### 3. System Architecture

The system follows a **three-tier microservices architecture** designed for security and scalability.

![System Architecture](attachment:be9e480a-86af-42e5-99fc-8ee001e2554f:image.png)

### A. The Frontend (The Dashboard)

- **Technology:** Next.js (React), Tailwind CSS.
- **Role:** Handles user interaction, visualizations, and displays the "Health Report."
- **Key Components:**
    - **Input Module:** Validates GitHub URLs.
    - **Visualizer:** Renders the interactive file tree and quality charts.
    - **Chat Interface:** Connects user queries to the RAG engine.

### B. The Backend (The Brain)

- **Technology:** Python (FastAPI).
- **Role:** Orchestrates the ingestion, analysis, and API responses.
- **Key Components:**
    - **Ingestion Worker:** Clones repositories to a secure, temporary directory with auto-cleanup (1-hour TTL).
    - **Static Analyzer:** 
        - Uses `radon` for Python complexity metrics (Cyclomatic Complexity).
        - Uses heuristic analysis (indentation, line counts) for other languages.
        - Detects technologies (frameworks, databases) based on file patterns.
        - Scans for secrets (API keys, tokens) using regex patterns.
    - **Orchestrator:** Manages the analysis pipeline and serves API endpoints.

### C. The Intelligence Layer (The AI)

- **Technology:** LangChain, vector database (FAISS), LLM (Google Gemini).
- **Role:** Provides semantic understanding and RAG capabilities.
- **Key Components:**
    - **Embedder:** Uses Google Generative AI Embeddings (`models/embedding-001`) to convert code chunks into vectors.
    - **Vector Store:** FAISS (Facebook AI Similarity Search) for efficient similarity search.
    - **Fallback Search:** A keyword-based retrieval system for when vector search is not applicable.

### 4. End-to-End Workflow

![End-to-End Workflow](attachment:52615367-e882-4897-8d2c-5319c95d296b:image.png)

### Phase 1: Ingestion (The Scan)

1. **User Action:** User pastes a link (for example, `https://github.com/fastapi/fastapi`).
2. **Validation:** System checks if the URL is valid, public, and within size limits (for example, < 500MB).
3. **Secure Cloning:** The backend performs a **shallow clone** (`git clone --depth 1`) into a disposable, isolated directory. Crucially, no install scripts are run.

### Phase 2: Analysis (The Autopsy)

The system runs parallel processes to dissect the codebase:

1.  **Structure Mapping:** Iterates through folders to build a JSON tree of the file hierarchy.
2.  **Metric Calculation:**
    -   **Python:** Calculates Cyclomatic Complexity, LOC, and comments using `radon`.
    -   **Other Languages:** Estimates complexity based on indentation and keywords.
    -   **Secret Scanning:** Identifies potential security risks like API keys and hardcoded secrets.
3.  **AI Indexing:**
    -   Reads high-value files (e.g., `README.md`, `package.json`, `*.py`, `*.ts`).
    -   Splits content into chunks and generates embeddings using Google's model.
    -   Stores vectors in a local FAISS index for fast retrieval during chat.

### Phase 3: Presentation (The Report)

The frontend renders the results:

-   **Health Score:** A calculated grade based on readability, complexity, and documentation coverage.
-   **Interactive Map:** A file tree visualization allowing users to explore the project structure.
-   **Chat:** An AI assistant that answers questions about the codebase using RAG (Retrieval-Augmented Generation).

### 5. Security Threat Model and Mitigation

Since the system handles external code, security is paramount.

![Security Threat Model](attachment:a1d26364-5372-4edf-9e97-4b436ec71d62:image.png)

### Threat Category: System Integrity

- **Specific Risk – Malicious Git Hooks:** A hacked repository executes code upon cloning.
- **Mitigation:** Use `git clone --no-checkout` first, then inspect. Disable all git hooks in the server configuration.

### Threat Category: Resource Attacks

- **Specific Risk – Zip Bomb / Infinite Loop:** A repository expands to petabytes to crash the server.
- **Mitigation:** Strict timeout limits (for example, 30 seconds maximum clone time) and disk usage quotas (for example, 100MB maximum folder size).

### Threat Category: Network Security

- **Specific Risk – SSRF (Server-Side Request Forgery):** User inputs a local IP to scan internal networks.
- **Mitigation:** DNS resolution checks to ensure the URL points to a public IP (for example, GitHub or GitLab) only.

### Threat Category: Data Privacy

- **Specific Risk – Leaking Secrets:** Analyzing a repository that contains accidental API keys.
- **Mitigation:** The tool detects secrets (using regex) and redacts them before showing any code in the UI.

### 6. Key Features and User Benefits

### Feature 1: The "Code Quality Health Card"

- **What it is:** A gamified "Spotify Wrapped" style report for the repository.
- **Metrics:** Readability, modularity, comment density.
- **Benefit:** Instantly tells a user if a project is well maintained or a mess.

### Feature 2: The "Interactive Atlas"

- **What it is:** A visual file tree where every folder has a "Why does this exist?" tooltip.
- **Benefit:** Eliminates the folder fatigue of staring at many directories named `utils` or `helpers`.

### Feature 3: "Chat with the Repository"

- **What it is:** A RAG-based chatbot that answers conceptual questions.
- **Benefit:** Allows users to find specific logic (for example, "Where is the payment gateway?") without manually searching.

### 7. Technology Stack Summary

- **Languages:** Python 3.10+ (Backend), TypeScript (Frontend).
- **Frameworks:** FastAPI (Backend), Next.js 14 (Frontend).
- **AI/ML:** LangChain, Google Gemini API (Embeddings & Chat), FAISS (Vector Store).
- **Frontend Libraries:** Tailwind CSS, Framer Motion, Lucide React.
- **Infrastructure:** Docker (planned), Vercel (Frontend), Railway/AWS (Backend).

### 8. Google Technologies Used

This project leverages the **Google Gemini API** ecosystem for its core intelligence:

-   **Google Gemini Flash (`gemini-2.5-flash`):** The primary LLM used for the "Chat with Repository" feature. It provides fast, context-aware answers by synthesizing information retrieved from the codebase.
-   **Google Generative AI Embeddings (`models/embedding-001`):** Used to convert code files into high-dimensional vectors. This allows the system to perform semantic searches (e.g., finding "login logic" even if the word "login" isn't explicitly used).

### 9. Conclusion

This project moves beyond simple **code completion** (like GitHub Copilot) and focuses on **code comprehension**. By automating the onboarding process and visualizing complexity, it lowers the barrier to entry for open-source contributors and helps developers maintain higher quality standards.
