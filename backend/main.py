import os
import shutil
import threading
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.core.config import settings
from app.core.rate_limiter import gemini_limiter
from app.services.cloner import clone_repository, clone_repository_with_branches
from app.services.analyzer import (
    analyze_directory_structure,
    detect_technologies,
    run_static_analysis,
    calculate_aggregate_metrics,
    generate_summary,
)
from app.services.rag import index_repository, get_chat_chain, delete_repo_indexes, delete_all_indexes
from app.services.scorer import compute_repo_score, compute_file_score, generate_ai_score_analysis
from app.services.branch_manager import BranchManager
from app.services.analysis_cache import AnalysisCache
from app.services.branch_storage import BranchStorage
from app.services.async_analysis import async_pipeline, AnalysisStatus

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
        # Also remove any persisted indexes for this repo
        delete_repo_indexes(rid)
        # Clean up branch metadata and cache for this repo
        branch_storage.cleanup_repo_metadata(rid)
        # Invalidate cache for all branches of this repo
        cached_branches = analysis_cache.get_cached_branches(rid)
        for branch in cached_branches:
            analysis_cache.invalidate_branch_cache(rid, branch)
        with _cleanup_lock:
            repo_access_times.pop(rid, None)


def _cleanup_loop(stop_event: threading.Event) -> None:
    """Background thread that runs cleanup every 5 minutes."""
    while not stop_event.wait(300):
        _cleanup_expired_repos()


_cleanup_stop = threading.Event()
_cleanup_thread: Optional[threading.Thread] = None


def _cleanup_all_repos() -> None:
    """Delete all cloned repos in any temp_clones folder."""
    print("Starting cleanup of all temporary repositories...")
    repos_cleaned = 0
    
    # 1) Clean temp_clones relative to current working directory (backend/temp_clones when run from backend)
    if os.path.exists(settings.TEMP_DIR):
        for entry in os.listdir(settings.TEMP_DIR):
            entry_path = os.path.join(settings.TEMP_DIR, entry)
            if os.path.isdir(entry_path):
                try:
                    shutil.rmtree(entry_path, ignore_errors=True)
                    repos_cleaned += 1
                except Exception as e:
                    print(f"Error cleaning {entry_path}: {e}")

    # 2) Also clean a temp_clones directory at the project root, if it exists
    try:
        project_root = Path(__file__).resolve().parent.parent
        root_temp = project_root / settings.TEMP_DIR
        if root_temp.exists():
            for entry in os.listdir(root_temp):
                entry_path = root_temp / entry
                if entry_path.is_dir():
                    try:
                        shutil.rmtree(entry_path, ignore_errors=True)
                        repos_cleaned += 1
                    except Exception as e:
                        print(f"Error cleaning {entry_path}: {e}")
    except Exception as e:
        # Best-effort cleanup; log and continue
        print(f"Error cleaning root temp_clones: {e}")
    
    with _cleanup_lock:
        repo_access_times.clear()
    
    # Also wipe all FAISS and fallback indexes
    delete_all_indexes()
    
    # Clean up branch metadata and analysis cache
    analysis_cache.clear_all_cache()
    for repo_id in branch_storage.get_all_repo_ids():
        branch_storage.cleanup_repo_metadata(repo_id)
    
    print(f"Cleanup complete: removed {repos_cleaned} temporary repositories")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cleanup_thread
    # On startup, purge any leftover temp clones and indexes from previous runs
    _cleanup_all_repos()
    _cleanup_thread = threading.Thread(target=_cleanup_loop, args=(_cleanup_stop,), daemon=True)
    _cleanup_thread.start()
    
    # Start async analysis pipeline
    await async_pipeline.start()
    
    # Start enhanced rate limiter queue processor
    gemini_limiter.start_queue_processor()
    
    # Start auto-refresh service
    auto_refresh_service.start()
    
    yield
    
    # Cleanup on shutdown: stop thread and delete all temp repos
    print("Server shutting down - initiating cleanup...")
    _cleanup_stop.set()
    _cleanup_all_repos()
    
    # Stop async analysis pipeline
    await async_pipeline.stop()
    
    # Stop enhanced rate limiter queue processor
    gemini_limiter.stop_queue_processor()
    
    # Stop auto-refresh service
    auto_refresh_service.stop()
    
    # Close database connections
    data_persistence.close()
    
    print("Shutdown complete: all temporary data cleaned up")


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Initialize branch management components
branch_manager = BranchManager()
analysis_cache = AnalysisCache()
branch_storage = BranchStorage()

# Initialize data persistence and synchronization
from app.services.data_persistence import DataPersistenceService
from app.services.data_sync import DataSynchronizationService, DataRefreshManager, ConflictResolutionStrategy
from app.services.auto_refresh import AutoRefreshService, DataRefreshScheduler

data_persistence = DataPersistenceService()
data_sync = DataSynchronizationService(data_persistence, ConflictResolutionStrategy.LATEST_WINS)
data_refresh_manager = DataRefreshManager(data_persistence, stale_threshold_hours=24)
auto_refresh_service = AutoRefreshService(data_persistence, data_refresh_manager, check_interval_minutes=30, auto_refresh_enabled=False)
refresh_scheduler = DataRefreshScheduler(data_persistence)

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
    branch: Optional[str] = None


class ChatRequest(BaseModel):
    repo_id: str
    message: str

@app.get("/")
def read_root():
    return {"status": "online", "service": "Code MRI Backend"}


@app.post("/analyze")
async def analyze_repo(request: AnalyzeRequest):
    """
    Clones a repository and returns its directory structure.
    Now supports optional branch parameter for branch-specific analysis.
    """
    try:
        # 1. Clone repository (with branch support if specified)
        if request.branch:
            # Use BranchManager for branch-specific cloning
            repo_path = await branch_manager.clone_branch(request.url, request.branch)
            repo_id = os.path.basename(repo_path)
            
            # Get commit SHA for caching
            commit_sha = await branch_manager.get_branch_commit_sha(request.url, request.branch)
            
            # Check cache first
            cached_analysis = analysis_cache.get_cached_analysis(repo_id, request.branch, commit_sha)
            if cached_analysis:
                return {
                    "message": "Analysis complete (cached)",
                    "repo_id": repo_id,
                    "branch": request.branch,
                    "commit_sha": commit_sha,
                    "tree": cached_analysis.file_tree.to_dict() if hasattr(cached_analysis.file_tree, 'to_dict') else cached_analysis.file_tree,
                    "cached": True
                }
        else:
            # Use existing cloning method for default branch
            repo_path = clone_repository(request.url)
            repo_id = os.path.basename(repo_path)
        
        _touch_repo(repo_id)

        # 2. Analyze
        file_tree = analyze_directory_structure(repo_path)

        response_data = {
            "message": "Analysis complete",
            "repo_id": repo_id,
            "tree": file_tree,
        }
        
        # Add branch info if specified
        if request.branch:
            response_data["branch"] = request.branch
            response_data["commit_sha"] = commit_sha
            response_data["cached"] = False

        return response_data
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/{repo_id}")
async def get_report(repo_id: str, branch: Optional[str] = None):
    """
    Retrieve existing analysis for a repo (or re-analyze if simple).
    Now includes branch awareness, enhanced grading system, and AI-powered scoring analysis.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        # If branch is specified, switch to that branch first
        commit_sha = None
        if branch:
            try:
                # Switch to the specified branch
                branch_context = await branch_manager.switch_branch_context(repo_id, branch)
                commit_sha = branch_context.commit_sha
                
                # Check cache for this specific branch and commit
                cached_analysis = analysis_cache.get_cached_analysis(repo_id, branch, commit_sha)
                if cached_analysis:
                    # Return cached analysis with enhanced grading
                    return {
                        "repo_id": repo_id,
                        "branch": branch,
                        "commit_sha": commit_sha,
                        "tree": cached_analysis.file_tree.to_dict() if hasattr(cached_analysis.file_tree, 'to_dict') else cached_analysis.file_tree,
                        "technologies": cached_analysis.technologies,
                        "metrics": cached_analysis.metrics,
                        "issues": cached_analysis.issues,
                        "summary": cached_analysis.ai_summary,
                        "detailed_scores": cached_analysis.detailed_scores.to_dict() if hasattr(cached_analysis.detailed_scores, 'to_dict') else cached_analysis.detailed_scores,
                        "ai_grading_explanation": cached_analysis.ai_grading_explanation,
                        "analysis_timestamp": cached_analysis.analysis_timestamp.isoformat(),
                        "cached": True
                    }
            except Exception as e:
                print(f"Branch switch error: {e}")
                # Continue with analysis on current branch
                pass

        # Perform fresh analysis
        file_tree = analyze_directory_structure(repo_path)
        technologies = detect_technologies(repo_path)
        metrics = calculate_aggregate_metrics(repo_path)
        issues = run_static_analysis(repo_path)
        summary = generate_summary(repo_path, technologies, metrics, issues)
        
        # Use Enhanced Grading System for detailed scoring
        from app.services.enhanced_grading import EnhancedGradingSystem
        enhanced_grading = EnhancedGradingSystem()
        
        detailed_scores = enhanced_grading.calculate_detailed_scores(repo_path, technologies)
        
        # Generate AI-powered grading explanations
        ai_grading_explanation = ""
        try:
            grading_explanation = await enhanced_grading.explain_grading_decisions(detailed_scores)
            ai_grading_explanation = grading_explanation.overall_explanation
        except Exception as e:
            error_str = str(e)
            if "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                print(f"AI Grading - Quota Exceeded: Continuing without AI explanation")
                ai_grading_explanation = "AI-powered grading explanation is currently unavailable due to API quota limits. The analysis will continue with computed scores."
            else:
                print(f"AI Grading Explanation Error: {e}")
                ai_grading_explanation = "AI explanation temporarily unavailable."
        
        # Compute traditional AI-powered scores for backward compatibility
        score_data = compute_repo_score(repo_path)
        ai_score_analysis = generate_ai_score_analysis(
            score_data, 
            technologies=technologies,
            repo_name=repo_id
        )
        
        # Prepare response data
        response_data = {
            "repo_id": repo_id,
            "tree": file_tree,
            "technologies": technologies,
            "metrics": metrics,
            "issues": issues,
            "summary": summary,
            "score": score_data,  # Legacy scoring for backward compatibility
            "ai_analysis": ai_score_analysis,  # Legacy AI analysis
            "detailed_scores": detailed_scores.to_dict(),  # New enhanced grading
            "ai_grading_explanation": ai_grading_explanation,  # New AI explanations
            "cached": False
        }
        
        # Add branch-specific information if applicable
        if branch and commit_sha:
            response_data["branch"] = branch
            response_data["commit_sha"] = commit_sha
            
            # Cache the analysis result for future use
            from app.models.branch import BranchAnalysisResult
            from datetime import datetime
            
            branch_analysis = BranchAnalysisResult(
                repo_id=repo_id,
                branch_name=branch,
                commit_sha=commit_sha,
                analysis_timestamp=datetime.now(),
                file_tree=file_tree,
                technologies=technologies,
                detailed_scores=detailed_scores,
                issues=issues,
                ai_summary=summary,
                ai_grading_explanation=ai_grading_explanation,
                metrics=detailed_scores.to_dict()  # Store detailed scores in metrics for comparison
            )
            
            # Store in cache
            analysis_cache.store_analysis(repo_id, branch, commit_sha, branch_analysis)
        
        # Store historical data for trend analysis
        try:
            from app.services.historical_trends import HistoricalTrendsAnalyzer
            historical_analyzer = HistoricalTrendsAnalyzer()
            
            if branch and commit_sha:
                # Store the analysis result for historical tracking
                historical_analyzer.store_analysis_result(branch_analysis)
                
                # Also store in database for persistence
                data_sync.sync_analysis_result(branch_analysis)
                
                # Store repository metadata
                import subprocess
                result = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                repo_url = result.stdout.strip()
                data_persistence.store_repository(repo_id, repo_url, default_branch=branch)
                
            else:
                # For default branch analysis, create a basic analysis result
                from app.models.branch import BranchAnalysisResult
                from datetime import datetime
                
                default_analysis = BranchAnalysisResult(
                    repo_id=repo_id,
                    branch_name="main",  # Assume main branch
                    commit_sha="unknown",
                    analysis_timestamp=datetime.now(),
                    file_tree=file_tree,
                    technologies=technologies,
                    detailed_scores=detailed_scores,
                    issues=issues,
                    ai_summary=summary,
                    ai_grading_explanation=ai_grading_explanation,
                    metrics=detailed_scores.to_dict()
                )
                historical_analyzer.store_analysis_result(default_analysis)
                
                # Store in database
                data_sync.sync_analysis_result(default_analysis)
        except Exception as e:
            print(f"Historical data storage error: {e}")
            # Don't fail the request if historical storage fails
        
        return response_data
        
    except Exception as e:
        print(f"Report Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/score/{repo_id}")
def get_score(repo_id: str):
    """Compute and return the repository score and breakdown."""
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        result = compute_repo_score(repo_path)
        return result
    except Exception as e:
        print(f"Scoring Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FileScoreRequest(BaseModel):
    repo_id: str
    file_path: str


@app.post("/score-file")
def score_file_endpoint(request: FileScoreRequest):
    repo_path = os.path.join(settings.TEMP_DIR, request.repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(request.repo_id)

    full_path = os.path.join(repo_path, request.file_path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        result = compute_file_score(full_path)
        return result
    except Exception as e:
        print(f"File Scoring Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FileContentRequest(BaseModel):
    repo_id: str
    file_path: str


@app.post("/file-content")
def get_file_content(request: FileContentRequest):
    """Get the raw content of a file for display."""
    repo_path = os.path.join(settings.TEMP_DIR, request.repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(request.repo_id)

    full_path = os.path.join(repo_path, request.file_path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Detect language from extension
        ext = os.path.splitext(request.file_path)[1].lower()
        language_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.tsx': 'typescript', '.jsx': 'javascript', '.java': 'java',
            '.cpp': 'cpp', '.c': 'c', '.go': 'go', '.rs': 'rust',
            '.html': 'html', '.css': 'css', '.json': 'json',
            '.md': 'markdown', '.yml': 'yaml', '.yaml': 'yaml',
        }
        language = language_map.get(ext, 'text')
        
        return {
            "file_path": request.file_path,
            "content": content,
            "language": language,
            "lines": len(content.splitlines()),
        }
    except Exception as e:
        print(f"File Content Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FileChatRequest(BaseModel):
    repo_id: str
    file_path: str
    message: str


class SwitchBranchRequest(BaseModel):
    repo_id: str
    branch: str


class CompareBranchesRequest(BaseModel):
    repo_id: str
    base_branch: str
    compare_branch: str


class AsyncAnalysisRequest(BaseModel):
    repo_id: str
    branch: str
    priority: int = 1


class ExplainRequest(BaseModel):
    repo_id: str
    explanation_type: str  # 'grading', 'code', 'comparison'
    context: Dict[str, Any] = {}


@app.post("/explain")
async def explain_endpoint(request: ExplainRequest):
    """
    Generate AI-powered explanations for various aspects of the codebase.
    Supports grading explanations, code explanations, and branch comparisons.
    """
    repo_path = os.path.join(settings.TEMP_DIR, request.repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(request.repo_id)

    try:
        # Wait for rate limit before making AI call
        user_id = f"explain_{request.repo_id}"
        if not gemini_limiter.acquire(timeout=120, user_id=user_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment and try again.")
        
        start_time = time.time()
        
        try:
            if request.explanation_type == "grading":
                # Handle grading explanations
                from app.services.enhanced_grading import EnhancedGradingSystem
                enhanced_grading = EnhancedGradingSystem()
                
                # Get or calculate detailed scores
                if "scoreData" in request.context and request.context["scoreData"]:
                    # Use provided score data
                    score_data = request.context["scoreData"]
                    # Convert to DetailedScoreReport if needed
                    detailed_scores = enhanced_grading.calculate_detailed_scores(repo_path, [])
                else:
                    # Calculate fresh scores
                    technologies = detect_technologies(repo_path)
                    detailed_scores = enhanced_grading.calculate_detailed_scores(repo_path, technologies)
                
                # Generate explanation
                explanation_result = await enhanced_grading.explain_grading_decisions(detailed_scores)
                
                response = {
                    "explanation": explanation_result.overall_explanation,
                    "key_insights": explanation_result.key_insights,
                    "recommendations": explanation_result.recommendations,
                    "confidence_level": explanation_result.confidence_level.value,
                    "processing_time": time.time() - start_time,
                    "fallback_used": explanation_result.fallback_used
                }
                
            elif request.explanation_type == "code":
                # Handle code file explanations
                file_path = request.context.get("filePath", "")
                if not file_path:
                    raise ValueError("File path is required for code explanations")
                
                full_path = os.path.join(repo_path, file_path.lstrip("/"))
                if not os.path.exists(full_path) or not os.path.isfile(full_path):
                    raise HTTPException(status_code=404, detail="File not found")
                
                # Use existing file analysis functionality
                from app.services.analyzer import analyze_file_with_ai
                file_analysis = analyze_file_with_ai(full_path, file_path)
                
                response = {
                    "explanation": f"**File Purpose:** {file_analysis.get('purpose', 'Not specified')}\n\n**Summary:** {file_analysis.get('summary', 'No summary available')}\n\n**Quality Notes:** {file_analysis.get('quality_notes', 'No quality notes available')}",
                    "key_insights": [
                        f"File contains {file_analysis.get('metrics', {}).get('loc', 0)} lines of code",
                        f"Complexity score: {file_analysis.get('metrics', {}).get('complexity', 'N/A')}",
                        f"Comment ratio: {file_analysis.get('metrics', {}).get('comments', 0)} comments"
                    ],
                    "recommendations": [],
                    "confidence_level": "medium",
                    "processing_time": time.time() - start_time,
                    "fallback_used": False
                }
                
            elif request.explanation_type == "comparison":
                # Handle branch comparison explanations
                branch_comparison = request.context.get("branchComparison", {})
                base_branch = branch_comparison.get("baseBranch", "")
                compare_branch = branch_comparison.get("compareBranch", "")
                
                if not base_branch or not compare_branch:
                    raise ValueError("Both base and compare branches are required for comparison explanations")
                
                # Get repository URL
                import subprocess
                result = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                repo_url = result.stdout.strip()
                
                # Get commit SHAs and cached analyses
                base_commit_sha = await branch_manager.get_branch_commit_sha(repo_url, base_branch)
                compare_commit_sha = await branch_manager.get_branch_commit_sha(repo_url, compare_branch)
                
                base_analysis = analysis_cache.get_cached_analysis(request.repo_id, base_branch, base_commit_sha)
                compare_analysis = analysis_cache.get_cached_analysis(request.repo_id, compare_branch, compare_commit_sha)
                
                if not base_analysis or not compare_analysis:
                    raise HTTPException(status_code=400, detail="Both branches must be analyzed before comparison explanation")
                
                # Generate comparison explanation using AI
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_core.output_parsers import StrOutputParser
                
                template = """You are an expert code quality analyst with deep expertise in software engineering best practices, code metrics, and branch management. Your role is to provide clear, technical, and actionable insights about code quality differences between branches.

## BRANCH COMPARISON DATA

**Base Branch:** {base_branch}
**Compare Branch:** {compare_branch}

### Base Branch Analysis
- Overall Score: {base_score}/100
- Technologies: {base_technologies}
- Total Issues: {base_issues_count}

### Compare Branch Analysis
- Overall Score: {compare_score}/100
- Technologies: {compare_technologies}
- Total Issues: {compare_issues_count}

---

## YOUR TASK

Provide a comprehensive, structured analysis following this EXACT format:

### 1. QUALITY DELTA SUMMARY
Write 2-3 sentences that:
- State whether the compare branch represents an improvement, regression, or neutral change
- Quantify the score difference (e.g., "+5 points" or "-3 points")
- Highlight the most significant quality change

### 2. CATEGORY-BY-CATEGORY COMPARISON
For each major quality category, provide:
- **[Category Name]**
  - Direction of change: ⬆️ Improved / ⬇️ Regressed / ➡️ Unchanged
  - What specifically changed
  - Impact on overall code quality

### 3. KEY DIFFERENCES
Provide 3-5 bullet points that:
- Highlight the most significant changes between branches
- Note any new issues introduced or resolved
- Identify patterns in the changes (e.g., "complexity increased in module X")

### 4. MERGE RECOMMENDATIONS
Based on the comparison, provide:
1. **Merge Decision:** RECOMMEND / CAUTION / BLOCK with brief justification
2. **Pre-Merge Actions:** List 2-3 specific actions to take before merging (if any)
3. **Post-Merge Monitoring:** What to watch after merging

### 5. RISK ASSESSMENT
- **Risk Level:** LOW / MEDIUM / HIGH
- **Primary Concerns:** List any quality regressions or new issues
- **Mitigation Strategies:** How to address identified risks

---

## GUIDELINES
- Be SPECIFIC about what changed, not generic
- Reference ACTUAL metrics and score differences
- Provide ACTIONABLE recommendations
- Consider the IMPACT on production code
- Focus on changes that affect MAINTAINABILITY and RELIABILITY
- Use concrete examples where possible"""
                
                prompt = ChatPromptTemplate.from_template(template)
                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    temperature=0.3,
                    google_api_key=settings.GOOGLE_API_KEY,
                )
                chain = prompt | llm | StrOutputParser()
                
                explanation_text = chain.invoke({
                    "base_branch": base_branch,
                    "compare_branch": compare_branch,
                    "base_score": getattr(base_analysis.detailed_scores, 'overall_score', 'N/A'),
                    "base_technologies": ', '.join(base_analysis.technologies),
                    "base_issues_count": len(base_analysis.issues),
                    "compare_score": getattr(compare_analysis.detailed_scores, 'overall_score', 'N/A'),
                    "compare_technologies": ', '.join(compare_analysis.technologies),
                    "compare_issues_count": len(compare_analysis.issues),
                })
                
                response = {
                    "explanation": explanation_text,
                    "key_insights": [
                        f"Comparing {base_branch} with {compare_branch}",
                        f"Base branch score: {getattr(base_analysis.detailed_scores, 'overall_score', 'N/A')}/100",
                        f"Compare branch score: {getattr(compare_analysis.detailed_scores, 'overall_score', 'N/A')}/100",
                        f"Base branch has {len(base_analysis.issues)} issues",
                        f"Compare branch has {len(compare_analysis.issues)} issues",
                        f"Issue delta: {len(compare_analysis.issues) - len(base_analysis.issues):+d} issues"
                    ],
                    "recommendations": [
                        "Review all quality changes before merging",
                        "Address any new issues introduced in the compare branch",
                        "Consider the impact on overall code maintainability",
                        "Run comprehensive tests on the compare branch",
                        "Document significant changes for team awareness"
                    ],
                    "confidence_level": "high",
                    "processing_time": time.time() - start_time,
                    "fallback_used": False,
                    "comparison_metadata": {
                        "base_branch": base_branch,
                        "compare_branch": compare_branch,
                        "base_score": getattr(base_analysis.detailed_scores, 'overall_score', None),
                        "compare_score": getattr(compare_analysis.detailed_scores, 'overall_score', None),
                        "score_delta": (getattr(compare_analysis.detailed_scores, 'overall_score', 0) or 0) - (getattr(base_analysis.detailed_scores, 'overall_score', 0) or 0),
                        "issues_delta": len(compare_analysis.issues) - len(base_analysis.issues)
                    }
                }
                
            else:
                raise ValueError(f"Unsupported explanation type: {request.explanation_type}")
            
            gemini_limiter.record_api_success()
            return response
            
        except Exception as e:
            gemini_limiter.record_api_failure()
            
            # Return fallback explanation
            fallback_explanations = {
                "grading": {
                    "explanation": "Your code quality score is calculated based on multiple factors including readability, complexity, maintainability, documentation, security, and performance. Each category is weighted according to industry best practices to provide a comprehensive assessment of your codebase.",
                    "key_insights": [
                        "Scores are calculated using static analysis tools and code metrics",
                        "Higher scores indicate better adherence to coding standards",
                        "Each category contributes proportionally to the overall grade",
                        "Improvement potential is calculated for each category",
                        "Recommendations are prioritized by estimated impact"
                    ],
                    "recommendations": [
                        "Focus on categories with the highest improvement potential",
                        "Address high-priority issues first for maximum impact",
                        "Review the detailed category breakdown for specific guidance"
                    ]
                },
                "code": {
                    "explanation": "This code file has been analyzed for structure, patterns, and quality indicators. The analysis includes complexity metrics, documentation coverage, and potential improvement areas based on static analysis.",
                    "key_insights": [
                        "Code structure directly affects maintainability",
                        "Documentation improves code understanding and onboarding",
                        "Lower complexity generally indicates more maintainable code",
                        "Consistent patterns improve team collaboration"
                    ],
                    "recommendations": [
                        "Add comments to complex logic sections",
                        "Consider breaking down large functions",
                        "Ensure consistent naming conventions"
                    ]
                },
                "comparison": {
                    "explanation": "Branch comparison analyzes differences in code quality metrics between the selected branches. This helps identify improvements or regressions in code quality before merging, ensuring code quality standards are maintained.",
                    "key_insights": [
                        "Quality differences highlight code evolution between branches",
                        "Improvements indicate positive development practices",
                        "Regressions may need attention before merging",
                        "Issue count changes reflect code health trends"
                    ],
                    "recommendations": [
                        "Review all quality regressions before merging",
                        "Address new issues introduced in the compare branch",
                        "Consider the cumulative impact on code maintainability",
                        "Run tests to verify functionality is preserved"
                    ]
                }
            }
            
            fallback = fallback_explanations.get(request.explanation_type, fallback_explanations["grading"])
            
            return {
                "explanation": fallback["explanation"],
                "key_insights": fallback["key_insights"],
                "recommendations": fallback.get("recommendations", []),
                "confidence_level": "low",
                "processing_time": time.time() - start_time,
                "fallback_used": True,
                "error_context": str(e) if str(e) else "AI service temporarily unavailable"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Explain Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat-file")
def chat_file_endpoint(request: FileChatRequest):
    """Chat about a specific file using AI."""
    repo_path = os.path.join(settings.TEMP_DIR, request.repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(request.repo_id)

    full_path = os.path.join(repo_path, request.file_path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")
        
        # Read file content
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Truncate if too large
        max_chars = 20000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n... [truncated for context]"
        
        template = """You are an expert code assistant helping a developer understand a specific file.

File: {file_path}

File Content:
```
{content}
```

User Question: {question}

Provide a clear, concise answer based on the file content. If the question is not related to this file, politely redirect the user."""
        
        prompt = ChatPromptTemplate.from_template(template)
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        chain = prompt | llm | StrOutputParser()
        
        # Wait for rate limit with user tracking
        user_id = f"file_chat_{request.repo_id}"  # Simple user identification
        if not gemini_limiter.acquire(timeout=120, user_id=user_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment and try again.")
        
        try:
            response = chain.invoke({
                "file_path": request.file_path,
                "content": content,
                "question": request.message,
            })
            gemini_limiter.record_api_success()
        except Exception as e:
            gemini_limiter.record_api_failure()
            raise
        
        return {"response": response}
    except Exception as e:
        print(f"File Chat Error: {e}")
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
        # Wait for rate limit before making AI call with user tracking
        user_id = f"chat_{request.repo_id}"  # Simple user identification
        if not gemini_limiter.acquire(timeout=120, user_id=user_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait a moment and try again.")
        
        try:
            chain = get_chat_chain(request.repo_id)
            response = chain.invoke(request.message)
            gemini_limiter.record_api_success()
        except Exception as e:
            gemini_limiter.record_api_failure()
            raise
        
        return {"response": response}
    except HTTPException:
        raise
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


@app.get("/branches/{repo_id}")
async def get_repository_branches(repo_id: str):
    """
    Fetch all available branches for a repository from the cloned repo.
    Uses the existing cloned repository instead of creating a new bare clone,
    which fixes Windows compatibility issues.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        # Fetch branches directly from the existing cloned repository
        # This avoids creating bare clones which cause issues on Windows
        branches = await branch_manager.fetch_branches_from_repo(repo_id)
        
        # Try to get repo URL for database storage (optional)
        repo_url = None
        try:
            import subprocess
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo_path
            )
            repo_url = result.stdout.strip()
            
            # Store branches in database if we have the URL
            if repo_url:
                data_persistence.store_repository(repo_id, repo_url)
                data_sync.sync_multiple_branches(repo_id, branches)
        except Exception as db_error:
            # Database storage is optional, don't fail the request
            print(f"Warning: Could not store branch data in database: {db_error}")
        
        return {
            "repo_id": repo_id,
            "branches": [
                {
                    "name": branch.name,
                    "commit_sha": branch.commit_sha,
                    "is_default": branch.is_default,
                    "last_commit_date": branch.last_commit_date.isoformat(),
                    "last_analyzed": branch.last_analyzed.isoformat() if branch.last_analyzed else None
                }
                for branch in branches
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Branch Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/switch-branch")
async def switch_branch(request: SwitchBranchRequest):
    """
    Switch the analysis context to a different branch.
    """
    repo_path = os.path.join(settings.TEMP_DIR, request.repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(request.repo_id)

    try:
        # Switch branch context using BranchManager
        branch_context = await branch_manager.switch_branch_context(request.repo_id, request.branch)
        
        # Check if we have cached analysis for this branch and commit
        cached_analysis = analysis_cache.get_cached_analysis(
            request.repo_id, 
            request.branch, 
            branch_context.commit_sha
        )
        
        response_data = {
            "repo_id": request.repo_id,
            "branch": request.branch,
            "commit_sha": branch_context.commit_sha,
            "analysis_status": branch_context.analysis_status.value,
            "cached_analysis_available": cached_analysis is not None
        }
        
        # If cached analysis is available, include basic info
        if cached_analysis:
            response_data["file_tree"] = cached_analysis.file_tree.to_dict() if hasattr(cached_analysis.file_tree, 'to_dict') else cached_analysis.file_tree
            response_data["technologies"] = cached_analysis.technologies
            response_data["analysis_timestamp"] = cached_analysis.analysis_timestamp.isoformat()
        
        return response_data
        
    except Exception as e:
        print(f"Branch Switch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compare-branches/{repo_id}")
async def compare_branches(
    repo_id: str, 
    base_branch: str, 
    compare_branch: str
):
    """
    Compare analysis results between two branches.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        # Get repository URL for branch operations
        import subprocess
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_path
        )
        repo_url = result.stdout.strip()
        
        # Get commit SHAs for both branches
        base_commit_sha = await branch_manager.get_branch_commit_sha(repo_url, base_branch)
        compare_commit_sha = await branch_manager.get_branch_commit_sha(repo_url, compare_branch)
        
        # Get cached analysis for both branches
        base_analysis = analysis_cache.get_cached_analysis(repo_id, base_branch, base_commit_sha)
        compare_analysis = analysis_cache.get_cached_analysis(repo_id, compare_branch, compare_commit_sha)
        
        if not base_analysis:
            raise HTTPException(
                status_code=404, 
                detail=f"No analysis found for base branch '{base_branch}'. Please analyze this branch first."
            )
        
        if not compare_analysis:
            raise HTTPException(
                status_code=404, 
                detail=f"No analysis found for compare branch '{compare_branch}'. Please analyze this branch first."
            )
        
        # Use BranchComparisonEngine to compare the branches
        from app.services.branch_comparison import BranchComparisonEngine
        comparison_engine = BranchComparisonEngine()
        
        comparison = comparison_engine.compare_branches(base_analysis, compare_analysis)
        
        return {
            "repo_id": repo_id,
            "comparison": comparison.to_dict()
        }
        
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=400, detail="Could not determine repository URL")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Branch Comparison Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-async")
async def analyze_async(request: AsyncAnalysisRequest):
    """
    Submit a repository branch for asynchronous analysis.
    Returns a task ID for tracking progress.
    """
    repo_path = os.path.join(settings.TEMP_DIR, request.repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(request.repo_id)

    try:
        # Get repository URL and commit SHA
        import subprocess
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
            cwd=repo_path
        )
        repo_url = result.stdout.strip()
        
        # Get commit SHA for the branch
        commit_sha = await branch_manager.get_branch_commit_sha(repo_url, request.branch)
        
        # Submit to async pipeline
        task_id = await async_pipeline.submit_analysis(
            repo_id=request.repo_id,
            repo_path=repo_path,
            branch=request.branch,
            commit_sha=commit_sha,
            priority=request.priority
        )
        
        return {
            "task_id": task_id,
            "repo_id": request.repo_id,
            "branch": request.branch,
            "commit_sha": commit_sha,
            "status": "queued",
            "message": "Analysis submitted successfully"
        }
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=400, detail="Could not determine repository URL")
    except Exception as e:
        print(f"Async Analysis Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis-progress/{task_id}")
async def get_analysis_progress(task_id: str):
    """
    Get progress information for an analysis task.
    """
    progress = async_pipeline.get_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": progress.task_id,
        "repo_id": progress.repo_id,
        "branch": progress.branch,
        "commit_sha": progress.commit_sha,
        "status": progress.status.value,
        "current_stage": progress.current_stage.value,
        "progress_percentage": progress.progress_percentage,
        "start_time": progress.start_time.isoformat(),
        "estimated_completion": progress.estimated_completion.isoformat() if progress.estimated_completion else None,
        "error_message": progress.error_message,
        "stages_completed": [stage.value for stage in progress.stages_completed]
    }


@app.get("/analysis-queue-status")
async def get_queue_status():
    """
    Get current analysis queue status and statistics.
    """
    return async_pipeline.get_queue_status()


@app.delete("/analysis-task/{task_id}")
async def cancel_analysis_task(task_id: str):
    """
    Cancel a queued or running analysis task.
    """
    success = async_pipeline.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already completed")
    
    return {"message": "Task cancelled successfully"}


@app.delete("/repo/{repo_id}")
def delete_repo(repo_id: str):
    """
    Manually delete a cloned repo and all its indexes immediately.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)
    # Remove any FAISS and fallback indexes tied to this repo
    delete_repo_indexes(repo_id)
    with _cleanup_lock:
        repo_access_times.pop(repo_id, None)
    return {"message": "Deleted"}


@app.get("/rate-limiter-stats")
async def get_rate_limiter_stats():
    """
    Get rate limiter statistics and current status.
    """
    return gemini_limiter.get_stats()


@app.get("/rate-limiter-user-stats/{user_id}")
async def get_user_rate_limiter_stats(user_id: str):
    """
    Get rate limiter statistics for a specific user.
    """
    return gemini_limiter.get_user_stats(user_id)


@app.get("/historical-trends/{repo_id}/{branch_name}")
async def get_historical_trends(
    repo_id: str,
    branch_name: str,
    days_back: int = 30
):
    """
    Get historical trend analysis for a specific branch.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        from app.services.historical_trends import HistoricalTrendsAnalyzer
        
        analyzer = HistoricalTrendsAnalyzer()
        trend_analysis = analyzer.calculate_branch_trends(repo_id, branch_name, days_back)
        
        if not trend_analysis:
            raise HTTPException(
                status_code=404, 
                detail="Insufficient historical data for trend analysis. At least 2 data points are required."
            )
        
        return {
            "repo_id": repo_id,
            "branch_name": branch_name,
            "analysis": trend_analysis.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Historical Trends Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/historical-trends/{repo_id}/{branch_name}/visualizations")
async def get_trend_visualizations(
    repo_id: str,
    branch_name: str,
    days_back: int = 30,
    chart_type: str = "line"
):
    """
    Get visualization data for historical trends.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        from app.services.historical_trends import HistoricalTrendsAnalyzer
        
        analyzer = HistoricalTrendsAnalyzer()
        trend_analysis = analyzer.calculate_branch_trends(repo_id, branch_name, days_back)
        
        if not trend_analysis:
            raise HTTPException(
                status_code=404, 
                detail="Insufficient historical data for visualization. At least 2 data points are required."
            )
        
        visualizations = analyzer.prepare_visualization_data(trend_analysis, chart_type)
        
        return {
            "repo_id": repo_id,
            "branch_name": branch_name,
            "visualizations": [viz.to_dict() for viz in visualizations]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Trend Visualization Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/historical-trends/{repo_id}/compare")
async def compare_branch_trends(
    repo_id: str,
    branch1: str,
    branch2: str,
    days_back: int = 30
):
    """
    Compare historical trends between two branches.
    """
    repo_path = os.path.join(settings.TEMP_DIR, repo_id)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found")

    _touch_repo(repo_id)

    try:
        from app.services.historical_trends import HistoricalTrendsAnalyzer
        
        analyzer = HistoricalTrendsAnalyzer()
        comparison = analyzer.compare_branch_trends(repo_id, branch1, branch2, days_back)
        
        if not comparison:
            raise HTTPException(
                status_code=404, 
                detail="Insufficient historical data for both branches. At least 2 data points per branch are required."
            )
        
        return {
            "repo_id": repo_id,
            "comparison": comparison
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Branch Trend Comparison Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cleanup")
def cleanup_all():
    """Force-delete all temp_clones, FAISS indexes, and fallback indexes."""
    _cleanup_all_repos()
    return {"message": "All repos and indexes removed"}


# Data persistence and synchronization endpoints

@app.get("/persistence/repository/{repo_id}")
def get_persisted_repository(repo_id: str):
    """Get persisted repository metadata."""
    repo = data_persistence.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found in database")
    
    return {
        "id": repo.id,
        "url": repo.url,
        "name": repo.name,
        "default_branch": repo.default_branch,
        "created_at": repo.created_at.isoformat(),
        "last_accessed": repo.last_accessed.isoformat()
    }


@app.get("/persistence/branches/{repo_id}")
def get_persisted_branches(repo_id: str):
    """Get persisted branch metadata for a repository."""
    branches = data_persistence.get_branches(repo_id)
    
    return {
        "repo_id": repo_id,
        "branches": [
            {
                "name": branch.name,
                "commit_sha": branch.commit_sha,
                "is_default": branch.is_default,
                "last_commit_date": branch.last_commit_date.isoformat() if branch.last_commit_date else None,
                "last_analyzed": branch.last_analyzed.isoformat() if branch.last_analyzed else None
            }
            for branch in branches
        ]
    }


@app.get("/persistence/analysis/{repo_id}/{branch_name}")
def get_persisted_analysis(repo_id: str, branch_name: str, commit_sha: Optional[str] = None):
    """Get persisted analysis for a branch."""
    analysis = data_persistence.get_latest_analysis(repo_id, branch_name, commit_sha)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this branch")
    
    return {
        "repo_id": analysis.repo_id,
        "branch_name": analysis.branch_name,
        "commit_sha": analysis.commit_sha,
        "analysis_timestamp": analysis.analysis_timestamp.isoformat(),
        "technologies": analysis.technologies,
        "metrics": analysis.metrics,
        "issues": analysis.issues,
        "ai_summary": analysis.ai_summary,
        "ai_grading_explanation": analysis.ai_grading_explanation,
        "detailed_scores": analysis.detailed_scores
    }


@app.get("/persistence/analysis-history/{repo_id}/{branch_name}")
def get_persisted_analysis_history(repo_id: str, branch_name: str, limit: int = 10):
    """Get analysis history for a branch."""
    history = data_persistence.get_analysis_history(repo_id, branch_name, limit)
    
    return {
        "repo_id": repo_id,
        "branch_name": branch_name,
        "history": [
            {
                "commit_sha": analysis.commit_sha,
                "analysis_timestamp": analysis.analysis_timestamp.isoformat(),
                "overall_score": analysis.detailed_scores.get('overall_score') if isinstance(analysis.detailed_scores, dict) else None,
                "technologies": analysis.technologies,
                "issue_count": len(analysis.issues)
            }
            for analysis in history
        ]
    }


@app.get("/sync/conflicts")
def get_sync_conflicts():
    """Get list of synchronization conflicts."""
    conflicts = data_sync.get_conflicts()
    
    return {
        "total_conflicts": len(conflicts),
        "conflicts": [conflict.to_dict() for conflict in conflicts]
    }


@app.post("/sync/resolve-conflict/{conflict_index}")
def resolve_sync_conflict(conflict_index: int, use_local: bool = False):
    """Resolve a synchronization conflict."""
    success = data_sync.resolve_conflict(conflict_index, use_local)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resolve conflict")
    
    return {"message": "Conflict resolved successfully"}


@app.get("/sync/stats")
def get_sync_stats():
    """Get synchronization statistics."""
    return data_sync.get_sync_stats()


@app.get("/refresh/staleness/{repo_id}/{branch_name}")
def check_branch_staleness(repo_id: str, branch_name: str):
    """Check if branch data is stale."""
    staleness_info = data_refresh_manager.get_staleness_info(repo_id, branch_name)
    return staleness_info


@app.get("/refresh/stale-branches/{repo_id}")
def get_stale_branches(repo_id: str):
    """Get list of stale branches for a repository."""
    stale_branches = data_refresh_manager.get_stale_branches(repo_id)
    
    return {
        "repo_id": repo_id,
        "stale_branches": stale_branches,
        "count": len(stale_branches)
    }


@app.post("/refresh/mark/{repo_id}/{branch_name}")
def mark_branch_for_refresh(repo_id: str, branch_name: str):
    """Mark a branch for refresh."""
    success = data_refresh_manager.mark_for_refresh(repo_id, branch_name)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to mark branch for refresh")
    
    return {"message": f"Branch {branch_name} marked for refresh"}


@app.get("/persistence/stats")
def get_persistence_stats():
    """Get data persistence statistics."""
    cache_stats = data_persistence.get_cache_stats()
    
    return {
        "cache": cache_stats,
        "sync": data_sync.get_sync_stats()
    }


@app.post("/persistence/cleanup")
def cleanup_persistence_data(
    cleanup_old_repos: bool = False,
    cleanup_old_analyses: bool = False,
    cleanup_cache: bool = False,
    max_age_hours: int = 24,
    max_age_days: int = 30
):
    """Cleanup old persistence data."""
    results = {}
    
    if cleanup_old_repos:
        count = data_persistence.cleanup_old_repositories(max_age_hours)
        results["repositories_removed"] = count
    
    if cleanup_old_analyses:
        count = data_persistence.cleanup_old_analyses(max_age_days)
        results["analyses_removed"] = count
    
    if cleanup_cache:
        count = data_persistence.cleanup_stale_cache_entries(max_age_hours)
        results["cache_entries_removed"] = count
    
    return {
        "message": "Cleanup completed",
        "results": results
    }


# Auto-refresh service endpoints

@app.get("/auto-refresh/status")
def get_auto_refresh_status():
    """Get auto-refresh service status."""
    return auto_refresh_service.get_status()


@app.post("/auto-refresh/enable")
def enable_auto_refresh():
    """Enable automatic refresh of stale data."""
    auto_refresh_service.enable_auto_refresh()
    return {"message": "Auto-refresh enabled", "status": auto_refresh_service.get_status()}


@app.post("/auto-refresh/disable")
def disable_auto_refresh():
    """Disable automatic refresh of stale data."""
    auto_refresh_service.disable_auto_refresh()
    return {"message": "Auto-refresh disabled", "status": auto_refresh_service.get_status()}


# Refresh scheduler endpoints

@app.post("/refresh/schedule/{repo_id}/{branch_name}")
def schedule_branch_refresh(repo_id: str, branch_name: str, delay_minutes: int = 60):
    """Schedule a refresh for a specific branch."""
    task_id = refresh_scheduler.schedule_refresh(repo_id, branch_name, delay_minutes)
    
    return {
        "message": "Refresh scheduled",
        "task_id": task_id,
        "repo_id": repo_id,
        "branch_name": branch_name,
        "delay_minutes": delay_minutes
    }


@app.get("/refresh/scheduled-tasks")
def get_scheduled_refresh_tasks():
    """Get all scheduled refresh tasks."""
    return refresh_scheduler.get_scheduled_tasks()


@app.delete("/refresh/scheduled-tasks/{task_id}")
def cancel_scheduled_refresh(task_id: str):
    """Cancel a scheduled refresh task."""
    success = refresh_scheduler.cancel_refresh(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Scheduled refresh cancelled"}


@app.post("/refresh/cleanup-tasks")
def cleanup_scheduled_tasks(max_age_hours: int = 24):
    """Cleanup completed scheduled tasks."""
    count = refresh_scheduler.cleanup_completed_tasks(max_age_hours)
    
    return {
        "message": "Cleanup completed",
        "tasks_removed": count
    }


