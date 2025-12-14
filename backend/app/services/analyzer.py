import os
import re
import json
from typing import List, Dict, Any, Tuple, Set, Optional

import radon.raw
import radon.complexity
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings

IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', '.idea', '.vscode', 'venv', 'env', 'dist', 'build', 'coverage'}
IGNORE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.mp4', '.mov', '.mp3', '.wav', '.pdf', '.zip', '.tar', '.gz', '.pyc'}

# Technology detection patterns
TECH_PATTERNS: Dict[str, List[str]] = {
    "Python": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile", "*.py"],
    "FastAPI": ["fastapi"],  # in requirements
    "Flask": ["flask"],
    "Django": ["django"],
    "React": ["react"],  # in package.json
    "Next.js": ["next"],
    "Vue": ["vue"],
    "Angular": ["@angular/core"],
    "Node.js": ["package.json"],
    "TypeScript": ["tsconfig.json", "*.ts", "*.tsx"],
    "PostgreSQL": ["psycopg2", "asyncpg", "postgresql"],
    "MongoDB": ["pymongo", "mongodb", "mongoose"],
    "Redis": ["redis"],
    "Docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"],
    "Kubernetes": ["*.yaml"],  # with kind: Deployment etc
    "GraphQL": ["graphql", "apollo"],
    "REST API": ["fastapi", "flask", "express", "django-rest-framework"],
    "SQLAlchemy": ["sqlalchemy"],
    "Prisma": ["prisma"],
}

# Secret patterns for static analysis
SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[\w\-]{20,}', "API Key"),
    (r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{8,}', "Hardcoded Secret"),
    (r'sk-[a-zA-Z0-9]{32,}', "OpenAI API Key"),
    (r'sk_live_[a-zA-Z0-9]{24,}', "Stripe Live Key"),
    (r'ghp_[a-zA-Z0-9]{36,}', "GitHub Token"),
    (r'-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----', "Private Key"),
    (r'(?i)bearer\s+[a-zA-Z0-9\-_.]+', "Bearer Token"),
]

def calculate_metrics(file_path: str) -> Dict[str, Any]:
    """
    Calculates LOC, Comment Density, and Complexity for a file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        metrics = {
            "loc": 0,
            "comments": 0,
            "complexity": 0
        }

        if file_path.endswith('.py'):
            # Use Radon for Python
            try:
                raw_metrics = radon.raw.analyze(content)
                metrics["loc"] = raw_metrics.loc
                metrics["comments"] = raw_metrics.comments
                
                # Complexity (Cyclomatic)
                # radon.complexity.cc_visit returns a list of blocks. We take the average or max.
                # Simplification: Sum of complexity of all blocks or just 1 if empty
                blocks = radon.complexity.cc_visit(content)
                if blocks:
                    metrics["complexity"] = sum(b.complexity for b in blocks) / len(blocks)
                else:
                    metrics["complexity"] = 1
            except Exception:
                # Fallback if syntax error
                metrics["loc"] = len(content.splitlines())
        
        else:
            # Generic Fallback
            lines = content.splitlines()
            metrics["loc"] = len(lines)
            
            # Simple heuristic for comments
            comments = 0
            complexity = 0
            
            # Very basic complexity proxy: indentation depth + keywords
            max_indent = 0
            
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                
                # Comments
                if stripped.startswith('//') or stripped.startswith('#') or stripped.startswith('/*'):
                    comments += 1
                
                # Complexity proxy: Indentation
                # Count leading spaces
                indent = len(line) - len(line.lstrip(' '))
                if indent > max_indent:
                    max_indent = indent
                    
                # Complexity proxy: keywords (simple check)
                if any(kw in stripped for kw in ['if ', 'for ', 'while ', 'case ', 'catch ']):
                    complexity += 1
            
            metrics["comments"] = comments
            # Normalize indentation to a rough "depth" (assuming 4 spaces per level)
            metrics["complexity"] = max(1, (max_indent // 4) + (complexity // 2))

        return metrics

    except Exception as e:
        print(f"Error calculating metrics for {file_path}: {e}")
        return {"loc": 0, "comments": 0, "complexity": 0}

def analyze_directory_structure(path: str) -> Dict[str, Any]:
    """
    Walks the directory structure and returns a JSON tree.
    """
    name = os.path.basename(path)
    if not name: 
        name = path
        
    item = {
        "name": name,
        "type": "folder",
        "children": []
    }

    try:
        with os.scandir(path) as entries:
            entries = sorted(list(entries), key=lambda e: (not e.is_dir(), e.name.lower()))
            
            for entry in entries:
                if entry.name in IGNORE_DIRS or entry.name.startswith('.'):
                    continue
                
                if entry.is_dir():
                    item["children"].append(analyze_directory_structure(entry.path))
                else:
                    _, ext = os.path.splitext(entry.name)
                    if ext.lower() in IGNORE_EXTS:
                        continue
                    
                    # Calculate metrics for the file
                    # Note: In a real large repo we might want to do this lazily or async
                    # For MVP we do it inline
                    metrics = calculate_metrics(entry.path)
                    
                    item["children"].append({
                        "name": entry.name,
                        "type": "file",
                        "metrics": metrics
                    })
    except PermissionError:
        pass

    return item


def detect_technologies(repo_path: str) -> List[str]:
    """Detect technologies/frameworks used in the repository."""
    detected: Set[str] = set()
    
    # Check for config files
    for tech, patterns in TECH_PATTERNS.items():
        for pattern in patterns:
            if pattern.startswith("*"):
                # File extension pattern - skip for now, check content below
                continue
            # Check if file exists
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
                if pattern in files:
                    detected.add(tech)
                    break
    
    # Check requirements.txt for Python packages
    req_file = os.path.join(repo_path, "requirements.txt")
    if os.path.exists(req_file):
        try:
            with open(req_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                if "fastapi" in content:
                    detected.add("FastAPI")
                if "flask" in content:
                    detected.add("Flask")
                if "django" in content:
                    detected.add("Django")
                if "sqlalchemy" in content:
                    detected.add("SQLAlchemy")
                if "psycopg2" in content or "asyncpg" in content:
                    detected.add("PostgreSQL")
                if "pymongo" in content:
                    detected.add("MongoDB")
                if "redis" in content:
                    detected.add("Redis")
        except:
            pass
    
    # Check package.json for JS frameworks
    pkg_file = os.path.join(repo_path, "package.json")
    if os.path.exists(pkg_file):
        try:
            with open(pkg_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()
                if '"react"' in content:
                    detected.add("React")
                if '"next"' in content:
                    detected.add("Next.js")
                if '"vue"' in content:
                    detected.add("Vue")
                if '"@angular/core"' in content:
                    detected.add("Angular")
                if '"express"' in content:
                    detected.add("Express")
                if '"typescript"' in content:
                    detected.add("TypeScript")
                if '"prisma"' in content:
                    detected.add("Prisma")
        except:
            pass
    
    # Check for Python files
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        if any(f.endswith('.py') for f in files):
            detected.add("Python")
            break
    
    return sorted(list(detected))


def run_static_analysis(repo_path: str) -> List[Dict[str, Any]]:
    """Run static analysis and return list of issues found."""
    issues: List[Dict[str, Any]] = []
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        rel_root = os.path.relpath(root, repo_path)
        
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in IGNORE_EXTS:
                continue
            
            file_path = os.path.join(root, filename)
            rel_path = os.path.join(rel_root, filename) if rel_root != "." else filename
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Check for secrets
                for line_num, line in enumerate(lines, 1):
                    for pattern, secret_type in SECRET_PATTERNS:
                        if re.search(pattern, line):
                            issues.append({
                                "severity": "HIGH",
                                "title": f"Hardcoded {secret_type} Detected",
                                "file": rel_path.replace("\\", "/"),
                                "line": line_num,
                                "type": "security",
                            })
                            break  # One issue per line max
                
                # Check Python complexity
                if filename.endswith('.py'):
                    content = ''.join(lines)
                    try:
                        blocks = radon.complexity.cc_visit(content)
                        for block in blocks:
                            if block.complexity > 15:
                                issues.append({
                                    "severity": "MEDIUM",
                                    "title": f"Cyclomatic Complexity > 15 ({block.complexity})",
                                    "file": rel_path.replace("\\", "/"),
                                    "line": block.lineno,
                                    "type": "complexity",
                                    "function": block.name,
                                })
                    except:
                        pass
                
                # Check for TODO/FIXME
                for line_num, line in enumerate(lines, 1):
                    if re.search(r'\b(TODO|FIXME|HACK|XXX)\b', line, re.IGNORECASE):
                        issues.append({
                            "severity": "LOW",
                            "title": "TODO/FIXME Comment",
                            "file": rel_path.replace("\\", "/"),
                            "line": line_num,
                            "type": "maintenance",
                        })
                
            except Exception as e:
                continue
    
    # Sort by severity
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 3))
    
    return issues[:50]  # Limit to 50 issues


def calculate_aggregate_metrics(repo_path: str) -> Dict[str, Any]:
    """Calculate aggregate quality metrics for the entire repository."""
    total_loc = 0
    total_comments = 0
    total_complexity = 0
    file_count = 0
    high_complexity_count = 0
    
    all_complexities = []
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in IGNORE_EXTS:
                continue
            
            file_path = os.path.join(root, filename)
            metrics = calculate_metrics(file_path)
            
            if metrics["loc"] > 0:
                file_count += 1
                total_loc += metrics["loc"]
                total_comments += metrics["comments"]
                total_complexity += metrics["complexity"]
                all_complexities.append(metrics["complexity"])
                
                if metrics["complexity"] > 10:
                    high_complexity_count += 1
    
    if file_count == 0:
        return {
            "readability": 0,
            "complexity": 0,
            "maintainability": 0,
            "docs_coverage": 0,
            "grade": "N/A",
            "total_files": 0,
            "total_loc": 0,
        }
    
    # Calculate scores (0-100)
    avg_complexity = total_complexity / file_count if file_count else 0
    comment_ratio = total_comments / total_loc if total_loc else 0
    
    # Readability: based on comment ratio and avg line length (simplified)
    readability = min(100, max(0, 100 - (avg_complexity * 3) + (comment_ratio * 50)))
    
    # Complexity score: inverse of average complexity (lower is better)
    complexity_score = min(100, max(0, 100 - (avg_complexity * 5)))
    
    # Maintainability: based on file sizes and complexity
    maintainability = min(100, max(0, 100 - (high_complexity_count / file_count * 100) if file_count else 0))
    
    # Docs coverage: based on comment ratio
    docs_coverage = min(100, max(0, comment_ratio * 500))
    
    # Overall grade
    overall_score = (readability + complexity_score + maintainability + docs_coverage) / 4
    
    if overall_score >= 90:
        grade = "A+"
    elif overall_score >= 85:
        grade = "A"
    elif overall_score >= 80:
        grade = "A-"
    elif overall_score >= 75:
        grade = "B+"
    elif overall_score >= 70:
        grade = "B"
    elif overall_score >= 65:
        grade = "B-"
    elif overall_score >= 60:
        grade = "C+"
    elif overall_score >= 55:
        grade = "C"
    elif overall_score >= 50:
        grade = "C-"
    elif overall_score >= 40:
        grade = "D"
    else:
        grade = "F"
    
    return {
        "readability": round(readability),
        "complexity": round(complexity_score),
        "maintainability": round(maintainability),
        "docs_coverage": round(docs_coverage),
        "grade": grade,
        "total_files": file_count,
        "total_loc": total_loc,
    }


def generate_summary(
    repo_path: str,
    technologies: List[str],
    metrics: Optional[Dict[str, Any]] = None,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate a brief natural-language summary of the repository.

    If a GOOGLE_API_KEY is configured, this uses Gemini to produce a
    richer AI-generated description. Otherwise it falls back to a
    deterministic summary based on technology detection and basic
    file statistics.
    """
    # Count files by type
    py_files = 0
    js_files = 0
    ts_files = 0
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            if f.endswith('.py'):
                py_files += 1
            elif f.endswith('.js') or f.endswith('.jsx'):
                js_files += 1
            elif f.endswith('.ts') or f.endswith('.tsx'):
                ts_files += 1
    
    # Basic deterministic summary text used as a fallback or prompt seed.
    parts = []

    # Determine project type
    if "FastAPI" in technologies or "Flask" in technologies or "Django" in technologies:
        parts.append("Python web API")
    elif "React" in technologies or "Next.js" in technologies:
        parts.append("React application")
    elif "Vue" in technologies:
        parts.append("Vue.js application")
    elif py_files > 0:
        parts.append("Python project")
    elif js_files > 0 or ts_files > 0:
        parts.append("JavaScript/TypeScript project")
    else:
        parts.append("Software project")

    # Add backend framework
    if "FastAPI" in technologies:
        parts.append("with FastAPI backend")
    elif "Flask" in technologies:
        parts.append("with Flask backend")
    elif "Django" in technologies:
        parts.append("with Django backend")
    elif "Express" in technologies:
        parts.append("with Express.js backend")

    # Add frontend
    if "Next.js" in technologies:
        parts.append("and Next.js frontend")
    elif "React" in technologies:
        parts.append("and React frontend")

    # Add database
    if "PostgreSQL" in technologies:
        parts.append("using PostgreSQL")
    elif "MongoDB" in technologies:
        parts.append("using MongoDB")

    # Add ORM
    if "SQLAlchemy" in technologies:
        parts.append("with SQLAlchemy ORM")
    elif "Prisma" in technologies:
        parts.append("with Prisma ORM")

    base_summary = " ".join(parts) + "."

    # If no LLM configured, return the deterministic summary.
    if not settings.GOOGLE_API_KEY:
        return base_summary

    # Prepare additional context for the model.
    metrics_payload: Dict[str, Any] = metrics or {}
    issues_payload = (issues or [])[:10]

    context = {
        "technologies": technologies,
        "file_stats": {
            "python_files": py_files,
            "javascript_files": js_files,
            "typescript_files": ts_files,
        },
        "metrics": metrics_payload,
        "issues": issues_payload,
        "baseline": base_summary,
    }

    template = """You are an expert software architect.
Given structured analysis data about a code repository, write a concise
3-5 sentence execution summary that would help a new engineer quickly
understand what this project does and how it is built.

- Start with what the project is and its main purpose.
- Mention the primary technologies and notable architectural choices.
- Briefly comment on overall code quality using the metrics.
- Optionally highlight any significant risks or smells if present.
- Do not speculate beyond what the data suggests.

Here is the structured analysis JSON:
{analysis_json}
"""

    try:
        prompt = ChatPromptTemplate.from_template(template)
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        chain = prompt | llm | StrOutputParser()
        summary = chain.invoke({"analysis_json": json.dumps(context, ensure_ascii=False)})
        return summary.strip() or base_summary
    except Exception:
        # Any failure should fall back to the deterministic summary to
        # keep the endpoint stable.
        return base_summary
