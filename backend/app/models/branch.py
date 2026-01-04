"""
Branch management data models for repository intelligence enhancement.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class AnalysisStatus(Enum):
    """Status of branch analysis."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BranchInfo:
    """Information about a repository branch."""
    name: str
    commit_sha: str
    is_default: bool
    last_commit_date: datetime
    last_analyzed: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "commit_sha": self.commit_sha,
            "is_default": self.is_default,
            "last_commit_date": self.last_commit_date.isoformat() if self.last_commit_date else None,
            "last_analyzed": self.last_analyzed.isoformat() if self.last_analyzed else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BranchInfo':
        """Create from dictionary."""
        return cls(
            name=data["name"],
            commit_sha=data["commit_sha"],
            is_default=data["is_default"],
            last_commit_date=datetime.fromisoformat(data["last_commit_date"]) if data.get("last_commit_date") else datetime.now(),
            last_analyzed=datetime.fromisoformat(data["last_analyzed"]) if data.get("last_analyzed") else None,
        )


@dataclass
class BranchContext:
    """Context information for a specific branch analysis."""
    repo_id: str
    branch_name: str
    commit_sha: str
    analysis_status: AnalysisStatus
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "repo_id": self.repo_id,
            "branch_name": self.branch_name,
            "commit_sha": self.commit_sha,
            "analysis_status": self.analysis_status.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BranchContext':
        """Create from dictionary."""
        return cls(
            repo_id=data["repo_id"],
            branch_name=data["branch_name"],
            commit_sha=data["commit_sha"],
            analysis_status=AnalysisStatus(data["analysis_status"]),
        )


@dataclass
class BranchAnalysisResult:
    """Complete analysis result for a branch."""
    repo_id: str
    branch_name: str
    commit_sha: str
    analysis_timestamp: datetime
    file_tree: Dict[str, Any]
    technologies: List[str]
    metrics: Dict[str, Any]
    issues: List[Dict[str, Any]]
    ai_summary: str
    ai_grading_explanation: str = ""
    detailed_scores: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "repo_id": self.repo_id,
            "branch_name": self.branch_name,
            "commit_sha": self.commit_sha,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "file_tree": self.file_tree,
            "technologies": self.technologies,
            "metrics": self.metrics,
            "issues": self.issues,
            "ai_summary": self.ai_summary,
            "ai_grading_explanation": self.ai_grading_explanation,
            "detailed_scores": self.detailed_scores,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BranchAnalysisResult':
        """Create from dictionary."""
        return cls(
            repo_id=data["repo_id"],
            branch_name=data["branch_name"],
            commit_sha=data["commit_sha"],
            analysis_timestamp=datetime.fromisoformat(data["analysis_timestamp"]),
            file_tree=data["file_tree"],
            technologies=data["technologies"],
            metrics=data["metrics"],
            issues=data["issues"],
            ai_summary=data["ai_summary"],
            ai_grading_explanation=data.get("ai_grading_explanation", ""),
            detailed_scores=data.get("detailed_scores"),
        )