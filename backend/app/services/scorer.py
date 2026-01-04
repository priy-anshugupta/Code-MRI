import os
import json
from typing import Dict, Any, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.rate_limiter import gemini_limiter
from app.services.analyzer import calculate_metrics, run_static_analysis


def _normalize(value: float, best_is_high: bool = True, cap: float = 100.0) -> float:
    """Normalize a value into 0-100. If best_is_high is False, lower raw values are better.
    This is a simple linear heuristic and can be improved later."""
    # Naive clamp
    try:
        v = float(value)
    except Exception:
        return 0.0

    if best_is_high:
        v = max(0.0, min(v, cap))
        return (v / cap) * 100.0
    else:
        # invert
        v = max(0.0, v)
        # map 0..cap -> 100..0
        return max(0.0, 100.0 - (v / cap) * 100.0)


def compute_file_score(file_path: str) -> Dict[str, Any]:
    """Compute a simple file-level score based on metrics and issues.
    Returns breakdown and numeric score (0-100)."""
    metrics = calculate_metrics(file_path)

    # Basic signals
    loc = metrics.get("loc", 0) or 0
    comments = metrics.get("comments", 0) or 0
    complexity = metrics.get("complexity", 0) or 0

    comment_ratio = (comments / loc) if loc else 0

    readability = min(100.0, max(0.0, comment_ratio * 500))
    complexity_score = min(100.0, max(0.0, 100.0 - (complexity * 5)))

    # Combine equal weights for file-level
    score = (readability * 0.5) + (complexity_score * 0.5)

    return {
        "file": file_path,
        "metrics": metrics,
        "breakdown": {
            "readability": round(readability, 2),
            "complexity": round(complexity_score, 2),
        },
        "score": round(score, 2),
    }


def compute_repo_score(repo_path: str) -> Dict[str, Any]:
    """Compute repository-level scores using configured weights.
    Walks repo files and aggregates metrics. Returns per-category scores and final weighted score."""
    weights = settings.SCORE_WEIGHTS or {}

    total_loc = 0
    total_comments = 0
    complexity_acc = 0.0
    file_count = 0

    file_scores: List[Dict[str, Any]] = []

    # Walk files
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__'}]
        for fn in files:
            if fn.startswith('.'):
                continue
            path = os.path.join(root, fn)
            try:
                m = calculate_metrics(path)
            except Exception:
                continue
            if m.get('loc', 0) <= 0:
                continue
            file_count += 1
            total_loc += m.get('loc', 0)
            total_comments += m.get('comments', 0)
            complexity_acc += m.get('complexity', 0)

            file_scores.append(compute_file_score(path))

    avg_complexity = (complexity_acc / file_count) if file_count else 0.0
    comment_ratio = (total_comments / total_loc) if total_loc else 0.0

    # Category scores (0-100)
    readability_score = min(100.0, max(0.0, 100.0 - (avg_complexity * 3) + (comment_ratio * 50)))
    complexity_score = min(100.0, max(0.0, 100.0 - (avg_complexity * 5)))
    docs_score = min(100.0, max(0.0, comment_ratio * 500))

    # Security signal: number of HIGH issues
    issues = run_static_analysis(repo_path)
    high_issues = sum(1 for i in issues if i.get('severity') == 'HIGH')
    security_score = max(0.0, 100.0 - (high_issues * 10))

    # Apply weights
    w_read = weights.get('readability', 0.25)
    w_comp = weights.get('complexity', 0.2)
    w_docs = weights.get('docs_coverage', 0.2)
    w_sec = weights.get('security', 0.15)

    final = (
        readability_score * w_read +
        complexity_score * w_comp +
        docs_score * w_docs +
        security_score * w_sec
    )

    # Normalize if weights sum < 1, scale to 100
    weight_sum = sum([w_read, w_comp, w_docs, w_sec]) or 1.0
    normalized_final = (final / weight_sum)

    return {
        "repo_path": repo_path,
        "file_count": file_count,
        "total_loc": total_loc,
        "category_scores": {
            "readability": round(readability_score, 2),
            "complexity": round(complexity_score, 2),
            "docs_coverage": round(docs_score, 2),
            "security": round(security_score, 2),
        },
        "final_score": round(normalized_final, 2),
        "files": file_scores,
        "issues_summary": {"total_issues": len(issues), "high_issues": high_issues},
    }


def generate_ai_score_analysis(
    score_data: Dict[str, Any],
    technologies: Optional[List[str]] = None,
    repo_name: Optional[str] = None,
) -> str:
    """Use Gemini AI to generate intelligent analysis of the repository scores.
    
    This is the 'Scoring Agent' - it analyzes the numeric scores and provides
    actionable insights on code quality, strengths, and improvement areas.
    """
    if not settings.GOOGLE_API_KEY:
        return f"Score: {score_data.get('final_score', 0)}/100. AI analysis unavailable (no API key)."

    template = """You are an expert code quality scoring agent. Analyze the following repository metrics and provide a concise, actionable assessment.

Repository: {repo_name}
Technologies: {technologies}

Scoring Breakdown:
{score_json}

Provide a 3-4 sentence analysis that:
1. Highlights the overall quality grade and what it means
2. Identifies the strongest quality aspect
3. Identifies the weakest area that needs improvement
4. Gives one specific, actionable recommendation

Be direct and technical. Focus on actionable insights."""

    try:
        prompt = ChatPromptTemplate.from_template(template)
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.3,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        chain = prompt | llm | StrOutputParser()
        
        # Wait for rate limit
        user_id = f"scoring_{repo_name or 'unknown'}"
        if not gemini_limiter.acquire(timeout=120, user_id=user_id):
            return f"Rate limited. Score: {score_data.get('final_score', 0)}/100. Please wait and refresh for AI analysis."
        
        try:
            analysis = chain.invoke({
                "repo_name": repo_name or "Repository",
                "technologies": ", ".join(technologies or ["Unknown"]),
                "score_json": json.dumps(score_data, indent=2),
            })
            gemini_limiter.record_api_success()
            return analysis.strip()
        except Exception as e:
            gemini_limiter.record_api_failure()
            raise
    except Exception as e:
        print(f"AI Scoring Agent Error: {e}")
        # Fallback to basic analysis
        score = score_data.get('final_score', 0)
        if score >= 80:
            quality = "excellent"
        elif score >= 60:
            quality = "good"
        elif score >= 40:
            quality = "fair"
        else:
            quality = "needs improvement"
        
        return f"Overall code quality is {quality} with a score of {score}/100. Review the category breakdowns for specific improvement areas."
