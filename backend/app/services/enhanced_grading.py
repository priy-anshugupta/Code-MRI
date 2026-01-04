"""
Enhanced Grading System for Repository Intelligence Enhancement

This module provides detailed code quality scoring with configurable weights,
comprehensive recommendations, and AI-powered explanations.
"""

import os
import json
import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.rate_limiter import gemini_limiter
from app.services.analyzer import calculate_metrics, run_static_analysis


class Priority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class EffortLevel(Enum):
    EASY = "EASY"
    MODERATE = "MODERATE"
    HARD = "HARD"


class ChangeType(Enum):
    IMPROVEMENT = "IMPROVEMENT"
    REGRESSION = "REGRESSION"
    NO_CHANGE = "NO_CHANGE"


@dataclass
class CategoryScore:
    name: str
    score: float  # 0-100
    weight: float  # 0-1
    contributing_factors: List[str]
    improvement_potential: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "score": self.score,
            "weight": self.weight,
            "contributing_factors": self.contributing_factors,
            "improvement_potential": self.improvement_potential
        }


@dataclass
class Recommendation:
    category: str
    priority: Priority
    title: str
    description: str
    estimated_impact: float
    effort_level: EffortLevel
    specific_files: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "estimated_impact": self.estimated_impact,
            "effort_level": self.effort_level.value,
            "specific_files": self.specific_files
        }


@dataclass
class FileScore:
    file_path: str
    overall_score: float
    category_scores: Dict[str, float]
    issues_count: int
    loc: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "overall_score": self.overall_score,
            "category_scores": self.category_scores,
            "issues_count": self.issues_count,
            "loc": self.loc
        }


@dataclass
class ScoreMetadata:
    analysis_timestamp: datetime
    total_files_analyzed: int
    total_loc: int
    repository_type: Optional[str]
    technologies: List[str]
    repo_name: Optional[str] = None  # Optional repo name for identification
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "total_files_analyzed": self.total_files_analyzed,
            "total_loc": self.total_loc,
            "repository_type": self.repository_type,
            "technologies": self.technologies,
            "repo_name": self.repo_name
        }


@dataclass
class ScoreTrends:
    previous_score: Optional[float]
    score_change: Optional[float]
    trend_direction: Optional[str]  # "improving", "declining", "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "previous_score": self.previous_score,
            "score_change": self.score_change,
            "trend_direction": self.trend_direction
        }


@dataclass
class DetailedScoreReport:
    overall_grade: str  # A+, A, A-, B+, etc.
    overall_score: float  # 0-100
    category_scores: Dict[str, CategoryScore]
    file_level_scores: List[FileScore]
    recommendations: List[Recommendation]
    trends: Optional[ScoreTrends]
    metadata: ScoreMetadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_grade": self.overall_grade,
            "overall_score": self.overall_score,
            "category_scores": {k: v.to_dict() for k, v in self.category_scores.items()},
            "file_level_scores": [f.to_dict() for f in self.file_level_scores],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "trends": self.trends.to_dict() if self.trends else None,
            "metadata": self.metadata.to_dict()
        }


class ConfidenceLevel(Enum):
    """Confidence level for AI-generated explanations."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class GradingExplanation:
    overall_explanation: str
    category_explanations: Dict[str, str]
    key_insights: List[str]
    improvement_priorities: List[str]
    recommendations: List[str] = None  # Specific actionable recommendations
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM  # Confidence in the explanation
    fallback_used: bool = False  # Whether AI failed and fallback was used
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_explanation": self.overall_explanation,
            "category_explanations": self.category_explanations,
            "key_insights": self.key_insights,
            "improvement_priorities": self.improvement_priorities,
            "recommendations": self.recommendations,
            "confidence_level": self.confidence_level.value,
            "fallback_used": self.fallback_used
        }


class EnhancedGradingSystem:
    """
    Enhanced grading system that provides detailed code quality scoring
    with configurable weights and AI-powered explanations.
    """
    
    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        """Initialize with optional custom weights for different repository types."""
        self.default_weights = {
            "readability": 0.25,
            "complexity": 0.20,
            "maintainability": 0.20,
            "documentation": 0.15,
            "security": 0.10,
            "performance": 0.10
        }
        self.weights = custom_weights or settings.SCORE_WEIGHTS or self.default_weights
        self._normalize_weights()
    
    def _normalize_weights(self):
        """Ensure weights sum to 1.0."""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
    
    def calculate_detailed_scores(self, repo_path: str, technologies: Optional[List[str]] = None) -> DetailedScoreReport:
        """
        Calculate comprehensive scores for all categories with detailed breakdowns.
        """
        # Collect repository metrics
        file_scores = []
        total_loc = 0
        total_files = 0
        total_complexity = 0
        total_comments = 0
        security_issues = []
        
        # Walk through repository files
        for root, dirs, files in os.walk(repo_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build'}]
            
            for filename in files:
                if filename.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, filename)
                try:
                    metrics = calculate_metrics(file_path)
                    if metrics.get('loc', 0) <= 0:
                        continue
                    
                    file_score = self._calculate_file_score(file_path, metrics)
                    file_scores.append(file_score)
                    
                    total_files += 1
                    total_loc += metrics.get('loc', 0)
                    total_complexity += metrics.get('complexity', 0)
                    total_comments += metrics.get('comments', 0)
                    
                except Exception as e:
                    print(f"Error analyzing file {file_path}: {e}")
                    continue
        
        # Run security analysis
        try:
            security_issues = run_static_analysis(repo_path)
        except Exception as e:
            print(f"Error running security analysis: {e}")
            security_issues = []
        
        # Calculate category scores
        category_scores = self._calculate_category_scores(
            file_scores, total_loc, total_files, total_complexity, 
            total_comments, security_issues, technologies
        )
        
        # Calculate overall score
        overall_score = sum(
            score.score * score.weight 
            for score in category_scores.values()
        )
        
        # Generate grade
        overall_grade = self._score_to_grade(overall_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(category_scores, file_scores, security_issues)
        
        # Create metadata
        metadata = ScoreMetadata(
            analysis_timestamp=datetime.now(),
            total_files_analyzed=total_files,
            total_loc=total_loc,
            repository_type=self._detect_repository_type(technologies),
            technologies=technologies or []
        )
        
        return DetailedScoreReport(
            overall_grade=overall_grade,
            overall_score=round(overall_score, 2),
            category_scores=category_scores,
            file_level_scores=file_scores,
            recommendations=recommendations,
            trends=None,  # Will be populated by comparison engine
            metadata=metadata
        )
    
    def _calculate_file_score(self, file_path: str, metrics: Dict[str, Any]) -> FileScore:
        """Calculate score for individual file."""
        loc = metrics.get('loc', 0)
        comments = metrics.get('comments', 0)
        complexity = metrics.get('complexity', 0)
        
        # Calculate category scores for this file
        readability_score = self._calculate_file_readability(loc, comments, complexity)
        complexity_score = self._calculate_file_complexity(complexity, loc)
        maintainability_score = self._calculate_file_maintainability(complexity, loc)
        documentation_score = self._calculate_file_documentation(comments, loc)
        
        category_scores = {
            'readability': readability_score,
            'complexity': complexity_score,
            'maintainability': maintainability_score,
            'documentation': documentation_score
        }
        
        # Calculate overall file score
        overall_score = sum(
            score * self.weights.get(category, 0) 
            for category, score in category_scores.items()
        )
        
        return FileScore(
            file_path=file_path,
            overall_score=round(overall_score, 2),
            category_scores=category_scores,
            issues_count=0,  # Will be populated by security analysis
            loc=loc
        )
    
    def _calculate_category_scores(
        self, 
        file_scores: List[FileScore], 
        total_loc: int, 
        total_files: int,
        total_complexity: int,
        total_comments: int,
        security_issues: List[Dict],
        technologies: Optional[List[str]]
    ) -> Dict[str, CategoryScore]:
        """Calculate scores for each category."""
        
        if not file_scores:
            # Return default scores if no files analyzed
            return {
                category: CategoryScore(
                    name=category,
                    score=0.0,
                    weight=weight,
                    contributing_factors=["No files analyzed"],
                    improvement_potential=100.0
                )
                for category, weight in self.weights.items()
            }
        
        # Calculate readability score
        avg_complexity = total_complexity / total_files if total_files > 0 else 0
        comment_ratio = total_comments / total_loc if total_loc > 0 else 0
        
        readability_score = self._calculate_readability_score(avg_complexity, comment_ratio, file_scores)
        complexity_score = self._calculate_complexity_score(avg_complexity, file_scores)
        maintainability_score = self._calculate_maintainability_score(avg_complexity, total_files, file_scores)
        documentation_score = self._calculate_documentation_score(comment_ratio, total_files)
        security_score = self._calculate_security_score(security_issues, total_files)
        performance_score = self._calculate_performance_score(file_scores, technologies)
        
        return {
            'readability': readability_score,
            'complexity': complexity_score,
            'maintainability': maintainability_score,
            'documentation': documentation_score,
            'security': security_score,
            'performance': performance_score
        }
    
    def _calculate_readability_score(self, avg_complexity: float, comment_ratio: float, file_scores: List[FileScore]) -> CategoryScore:
        """Calculate readability score based on complexity and comments."""
        # Base score from complexity (lower is better)
        complexity_factor = max(0, 100 - (avg_complexity * 8))
        
        # Comment factor (higher is better)
        comment_factor = min(100, comment_ratio * 300)
        
        # File consistency factor
        readability_scores = [fs.category_scores.get('readability', 0) for fs in file_scores]
        consistency_factor = 100 - (self._calculate_variance(readability_scores) * 2)
        
        score = (complexity_factor * 0.4 + comment_factor * 0.4 + consistency_factor * 0.2)
        
        contributing_factors = []
        if avg_complexity > 10:
            contributing_factors.append("High average complexity")
        if comment_ratio < 0.1:
            contributing_factors.append("Low comment density")
        if consistency_factor < 70:
            contributing_factors.append("Inconsistent readability across files")
        
        improvement_potential = max(0, 100 - score)
        
        return CategoryScore(
            name="readability",
            score=round(score, 2),
            weight=self.weights.get('readability', 0.25),
            contributing_factors=contributing_factors or ["Good readability practices"],
            improvement_potential=round(improvement_potential, 2)
        )
    
    def _calculate_complexity_score(self, avg_complexity: float, file_scores: List[FileScore]) -> CategoryScore:
        """Calculate complexity score."""
        # Exponential penalty for high complexity
        base_score = max(0, 100 - (avg_complexity * 6))
        
        # Penalty for files with very high complexity
        high_complexity_files = sum(1 for fs in file_scores if fs.category_scores.get('complexity', 100) < 50)
        high_complexity_penalty = min(30, high_complexity_files * 5)
        
        score = max(0, base_score - high_complexity_penalty)
        
        contributing_factors = []
        if avg_complexity > 15:
            contributing_factors.append("Very high average complexity")
        elif avg_complexity > 10:
            contributing_factors.append("High average complexity")
        if high_complexity_files > 0:
            contributing_factors.append(f"{high_complexity_files} files with high complexity")
        
        improvement_potential = max(0, 100 - score)
        
        return CategoryScore(
            name="complexity",
            score=round(score, 2),
            weight=self.weights.get('complexity', 0.20),
            contributing_factors=contributing_factors or ["Well-managed complexity"],
            improvement_potential=round(improvement_potential, 2)
        )
    
    def _calculate_maintainability_score(self, avg_complexity: float, total_files: int, file_scores: List[FileScore]) -> CategoryScore:
        """Calculate maintainability score."""
        # Base score from complexity
        complexity_factor = max(0, 100 - (avg_complexity * 5))
        
        # File size factor (prefer smaller files)
        avg_loc_per_file = sum(fs.loc for fs in file_scores) / len(file_scores) if file_scores else 0
        size_factor = max(0, 100 - (avg_loc_per_file / 10))  # Penalty starts at 1000 LOC per file
        
        # Modularity factor (more files generally better for maintainability)
        modularity_factor = min(100, total_files * 2)  # Bonus for having multiple files
        
        score = (complexity_factor * 0.5 + size_factor * 0.3 + modularity_factor * 0.2)
        
        contributing_factors = []
        if avg_complexity > 12:
            contributing_factors.append("High complexity reduces maintainability")
        if avg_loc_per_file > 500:
            contributing_factors.append("Large files reduce maintainability")
        if total_files < 5:
            contributing_factors.append("Low modularity")
        
        improvement_potential = max(0, 100 - score)
        
        return CategoryScore(
            name="maintainability",
            score=round(score, 2),
            weight=self.weights.get('maintainability', 0.20),
            contributing_factors=contributing_factors or ["Good maintainability practices"],
            improvement_potential=round(improvement_potential, 2)
        )
    
    def _calculate_documentation_score(self, comment_ratio: float, total_files: int) -> CategoryScore:
        """Calculate documentation score."""
        # Comment density score
        comment_score = min(100, comment_ratio * 400)
        
        # Assume README exists if this is a real repository
        readme_bonus = 20  # Simplified assumption
        
        score = min(100, comment_score + readme_bonus)
        
        contributing_factors = []
        if comment_ratio < 0.05:
            contributing_factors.append("Very low comment density")
        elif comment_ratio < 0.1:
            contributing_factors.append("Low comment density")
        
        improvement_potential = max(0, 100 - score)
        
        return CategoryScore(
            name="documentation",
            score=round(score, 2),
            weight=self.weights.get('documentation', 0.15),
            contributing_factors=contributing_factors or ["Good documentation practices"],
            improvement_potential=round(improvement_potential, 2)
        )
    
    def _calculate_security_score(self, security_issues: List[Dict], total_files: int) -> CategoryScore:
        """Calculate security score based on static analysis results."""
        if not security_issues:
            return CategoryScore(
                name="security",
                score=100.0,
                weight=self.weights.get('security', 0.10),
                contributing_factors=["No security issues detected"],
                improvement_potential=0.0
            )
        
        # Count issues by severity
        high_issues = sum(1 for issue in security_issues if issue.get('severity') == 'HIGH')
        medium_issues = sum(1 for issue in security_issues if issue.get('severity') == 'MEDIUM')
        low_issues = sum(1 for issue in security_issues if issue.get('severity') == 'LOW')
        
        # Calculate penalty
        penalty = (high_issues * 20) + (medium_issues * 10) + (low_issues * 5)
        score = max(0, 100 - penalty)
        
        contributing_factors = []
        if high_issues > 0:
            contributing_factors.append(f"{high_issues} high-severity security issues")
        if medium_issues > 0:
            contributing_factors.append(f"{medium_issues} medium-severity security issues")
        if low_issues > 0:
            contributing_factors.append(f"{low_issues} low-severity security issues")
        
        improvement_potential = max(0, 100 - score)
        
        return CategoryScore(
            name="security",
            score=round(score, 2),
            weight=self.weights.get('security', 0.10),
            contributing_factors=contributing_factors,
            improvement_potential=round(improvement_potential, 2)
        )
    
    def _calculate_performance_score(self, file_scores: List[FileScore], technologies: Optional[List[str]]) -> CategoryScore:
        """Calculate performance score based on code patterns."""
        # This is a simplified implementation
        # In a real system, this would analyze performance patterns
        
        # Base score from complexity (lower complexity often means better performance)
        avg_complexity = sum(fs.category_scores.get('complexity', 0) for fs in file_scores) / len(file_scores) if file_scores else 0
        complexity_factor = max(0, 100 - (avg_complexity * 0.5))
        
        # File size factor (very large files might have performance issues)
        avg_loc = sum(fs.loc for fs in file_scores) / len(file_scores) if file_scores else 0
        size_factor = max(0, 100 - (avg_loc / 20))  # Penalty starts at 2000 LOC per file
        
        score = (complexity_factor * 0.6 + size_factor * 0.4)
        
        contributing_factors = []
        if avg_complexity > 20:
            contributing_factors.append("High complexity may impact performance")
        if avg_loc > 1000:
            contributing_factors.append("Large files may impact performance")
        
        improvement_potential = max(0, 100 - score)
        
        return CategoryScore(
            name="performance",
            score=round(score, 2),
            weight=self.weights.get('performance', 0.10),
            contributing_factors=contributing_factors or ["Good performance indicators"],
            improvement_potential=round(improvement_potential, 2)
        )
    
    def _calculate_file_readability(self, loc: int, comments: int, complexity: int) -> float:
        """Calculate readability score for a single file."""
        comment_ratio = comments / loc if loc > 0 else 0
        comment_score = min(100, comment_ratio * 300)
        complexity_score = max(0, 100 - (complexity * 8))
        return (comment_score * 0.6 + complexity_score * 0.4)
    
    def _calculate_file_complexity(self, complexity: int, loc: int) -> float:
        """Calculate complexity score for a single file."""
        return max(0, 100 - (complexity * 6))
    
    def _calculate_file_maintainability(self, complexity: int, loc: int) -> float:
        """Calculate maintainability score for a single file."""
        complexity_factor = max(0, 100 - (complexity * 5))
        size_factor = max(0, 100 - (loc / 10))  # Penalty for very large files
        return (complexity_factor * 0.7 + size_factor * 0.3)
    
    def _calculate_file_documentation(self, comments: int, loc: int) -> float:
        """Calculate documentation score for a single file."""
        comment_ratio = comments / loc if loc > 0 else 0
        return min(100, comment_ratio * 400)
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if not values:
            return 0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 97:
            return "A+"
        elif score >= 93:
            return "A"
        elif score >= 90:
            return "A-"
        elif score >= 87:
            return "B+"
        elif score >= 83:
            return "B"
        elif score >= 80:
            return "B-"
        elif score >= 77:
            return "C+"
        elif score >= 73:
            return "C"
        elif score >= 70:
            return "C-"
        elif score >= 67:
            return "D+"
        elif score >= 63:
            return "D"
        elif score >= 60:
            return "D-"
        else:
            return "F"
    
    def _detect_repository_type(self, technologies: Optional[List[str]]) -> Optional[str]:
        """Detect repository type based on technologies."""
        if not technologies:
            return None
        
        tech_lower = [t.lower() for t in technologies]
        
        if any(t in tech_lower for t in ['react', 'vue', 'angular', 'svelte']):
            return "frontend"
        elif any(t in tech_lower for t in ['django', 'flask', 'fastapi', 'express']):
            return "backend"
        elif any(t in tech_lower for t in ['tensorflow', 'pytorch', 'scikit-learn']):
            return "ml"
        elif any(t in tech_lower for t in ['docker', 'kubernetes', 'terraform']):
            return "devops"
        else:
            return "general"
    
    def generate_improvement_recommendations(self, scores: DetailedScoreReport) -> List[Recommendation]:
        """Generate specific, actionable recommendations based on scores."""
        return self._generate_recommendations(scores.category_scores, scores.file_level_scores, [])
    
    def _generate_recommendations(
        self, 
        category_scores: Dict[str, CategoryScore], 
        file_scores: List[FileScore],
        security_issues: List[Dict]
    ) -> List[Recommendation]:
        """Generate recommendations based on analysis results."""
        recommendations = []
        
        # Sort categories by improvement potential
        sorted_categories = sorted(
            category_scores.items(), 
            key=lambda x: x[1].improvement_potential, 
            reverse=True
        )
        
        for category_name, category_score in sorted_categories[:3]:  # Top 3 improvement areas
            if category_score.improvement_potential < 10:
                continue  # Skip if already good
            
            if category_name == "readability":
                recommendations.extend(self._generate_readability_recommendations(category_score, file_scores))
            elif category_name == "complexity":
                recommendations.extend(self._generate_complexity_recommendations(category_score, file_scores))
            elif category_name == "maintainability":
                recommendations.extend(self._generate_maintainability_recommendations(category_score, file_scores))
            elif category_name == "documentation":
                recommendations.extend(self._generate_documentation_recommendations(category_score, file_scores))
            elif category_name == "security":
                recommendations.extend(self._generate_security_recommendations(category_score, security_issues))
            elif category_name == "performance":
                recommendations.extend(self._generate_performance_recommendations(category_score, file_scores))
        
        return recommendations
    
    def _generate_readability_recommendations(self, category_score: CategoryScore, file_scores: List[FileScore]) -> List[Recommendation]:
        """Generate readability-specific recommendations."""
        recommendations = []
        
        # Find files with low readability scores
        low_readability_files = [
            fs for fs in file_scores 
            if fs.category_scores.get('readability', 100) < 60
        ]
        
        if low_readability_files:
            recommendations.append(Recommendation(
                category="readability",
                priority=Priority.HIGH,
                title="Improve code readability in low-scoring files",
                description="Add meaningful comments, improve variable naming, and reduce complexity in files with poor readability scores.",
                estimated_impact=category_score.improvement_potential * 0.6,
                effort_level=EffortLevel.MODERATE,
                specific_files=[fs.file_path for fs in low_readability_files[:5]]
            ))
        
        if "Low comment density" in category_score.contributing_factors:
            recommendations.append(Recommendation(
                category="readability",
                priority=Priority.MEDIUM,
                title="Increase comment density across the codebase",
                description="Add explanatory comments for complex logic, document function purposes, and explain non-obvious code sections.",
                estimated_impact=category_score.improvement_potential * 0.4,
                effort_level=EffortLevel.EASY,
                specific_files=[]
            ))
        
        return recommendations
    
    def _generate_complexity_recommendations(self, category_score: CategoryScore, file_scores: List[FileScore]) -> List[Recommendation]:
        """Generate complexity-specific recommendations."""
        recommendations = []
        
        # Find files with high complexity
        high_complexity_files = [
            fs for fs in file_scores 
            if fs.category_scores.get('complexity', 100) < 50
        ]
        
        if high_complexity_files:
            recommendations.append(Recommendation(
                category="complexity",
                priority=Priority.HIGH,
                title="Refactor high-complexity functions",
                description="Break down complex functions into smaller, more manageable pieces. Consider extracting helper functions and reducing nesting levels.",
                estimated_impact=category_score.improvement_potential * 0.7,
                effort_level=EffortLevel.HARD,
                specific_files=[fs.file_path for fs in high_complexity_files[:3]]
            ))
        
        return recommendations
    
    def _generate_maintainability_recommendations(self, category_score: CategoryScore, file_scores: List[FileScore]) -> List[Recommendation]:
        """Generate maintainability-specific recommendations."""
        recommendations = []
        
        # Find very large files
        large_files = [fs for fs in file_scores if fs.loc > 500]
        
        if large_files:
            recommendations.append(Recommendation(
                category="maintainability",
                priority=Priority.MEDIUM,
                title="Split large files into smaller modules",
                description="Consider breaking large files into smaller, focused modules to improve maintainability and testability.",
                estimated_impact=category_score.improvement_potential * 0.5,
                effort_level=EffortLevel.MODERATE,
                specific_files=[fs.file_path for fs in large_files[:3]]
            ))
        
        return recommendations
    
    def _generate_documentation_recommendations(self, category_score: CategoryScore, file_scores: List[FileScore]) -> List[Recommendation]:
        """Generate documentation-specific recommendations."""
        recommendations = []
        
        if category_score.score < 70:
            recommendations.append(Recommendation(
                category="documentation",
                priority=Priority.MEDIUM,
                title="Improve code documentation",
                description="Add docstrings to functions and classes, create or update README files, and document complex algorithms.",
                estimated_impact=category_score.improvement_potential * 0.6,
                effort_level=EffortLevel.EASY,
                specific_files=[]
            ))
        
        return recommendations
    
    def _generate_security_recommendations(self, category_score: CategoryScore, security_issues: List[Dict]) -> List[Recommendation]:
        """Generate security-specific recommendations."""
        recommendations = []
        
        if security_issues:
            high_issues = [issue for issue in security_issues if issue.get('severity') == 'HIGH']
            if high_issues:
                recommendations.append(Recommendation(
                    category="security",
                    priority=Priority.HIGH,
                    title="Address high-severity security issues",
                    description="Fix critical security vulnerabilities that could compromise system security.",
                    estimated_impact=category_score.improvement_potential * 0.8,
                    effort_level=EffortLevel.MODERATE,
                    specific_files=list(set(issue.get('file', '') for issue in high_issues if issue.get('file')))
                ))
        
        return recommendations
    
    def _generate_performance_recommendations(self, category_score: CategoryScore, file_scores: List[FileScore]) -> List[Recommendation]:
        """Generate performance-specific recommendations."""
        recommendations = []
        
        if category_score.score < 70:
            recommendations.append(Recommendation(
                category="performance",
                priority=Priority.LOW,
                title="Review code for performance optimizations",
                description="Look for opportunities to optimize algorithms, reduce complexity, and improve resource usage.",
                estimated_impact=category_score.improvement_potential * 0.3,
                effort_level=EffortLevel.MODERATE,
                specific_files=[]
            ))
        
        return recommendations
    
    async def explain_grading_decisions(self, scores: DetailedScoreReport) -> GradingExplanation:
        """
        Generate AI-powered explanations for grading decisions.
        Integrates with existing Gemini API setup.
        """
        if not settings.GOOGLE_API_KEY:
            return self._generate_fallback_explanation(scores)
        
        try:
            # Wait for rate limit - use repo_name, repository_type, or 'unknown' as fallback
            identifier = scores.metadata.repo_name or scores.metadata.repository_type or 'unknown'
            user_id = f"grading_{identifier}"
            if not gemini_limiter.acquire(timeout=120, user_id=user_id):
                return self._generate_fallback_explanation(scores, "Rate limited")
            
            template = """You are an expert code quality analyst with deep expertise in software engineering best practices, code metrics, and maintainability assessment. Your role is to provide clear, technical, and actionable insights about code quality.

## REPOSITORY ANALYSIS RESULTS

**Overall Grade:** {overall_grade} ({overall_score}/100)
**Repository Type:** {repo_type}
**Technologies:** {technologies}

### Metrics Summary
- Total files analyzed: {total_files}
- Total lines of code: {total_loc}

### Category Scores (Detailed Breakdown)
{category_breakdown}

### Contributing Factors
{contributing_factors}

### Current Recommendations
{recommendations}

---

## YOUR TASK

Provide a comprehensive, structured analysis following this EXACT format:

### 1. EXECUTIVE SUMMARY
Write 2-3 sentences that:
- State the overall code quality assessment in plain terms
- Highlight the most significant strength
- Identify the most critical area needing improvement

### 2. CATEGORY ANALYSIS
For EACH scoring category, provide:
- **[Category Name]** (Score: X/100)
  - What this score means in practical terms
  - Key factors that influenced this score
  - One specific, actionable improvement suggestion

### 3. KEY INSIGHTS
Provide 3-5 bullet points that:
- Highlight patterns or issues that stand out
- Reference specific metrics that support your insights
- Note any correlations between categories (e.g., high complexity often correlates with low maintainability)

### 4. PRIORITY ACTIONS
List the THREE most impactful improvements in order:
1. **[Highest Impact]** - Description and expected benefit (e.g., "could improve score by X points")
2. **[Medium Impact]** - Description and expected benefit
3. **[Quick Win]** - Something that can be done quickly with good results

---

## GUIDELINES
- Be SPECIFIC and TECHNICAL, not generic
- Reference ACTUAL metrics and scores in your explanations
- Provide ACTIONABLE recommendations, not vague suggestions
- Consider the TECHNOLOGY STACK when making recommendations
- Focus on improvements that will have MEASURABLE impact
- Use concrete examples where possible (e.g., "functions with complexity > 10 should be refactored")
- Avoid generic advice like "write better code" - be specific about what "better" means"""

            # Prepare detailed data for the prompt
            category_breakdown = "\n".join([
                f"- **{name.title()}**: {score.score}/100 (Weight: {score.weight:.0%}, Improvement Potential: {score.improvement_potential:.1f}%)"
                for name, score in scores.category_scores.items()
            ])
            
            # Include contributing factors for more context
            contributing_factors = "\n".join([
                f"- **{name.title()}**: {', '.join(score.contributing_factors)}"
                for name, score in scores.category_scores.items()
                if score.contributing_factors
            ])
            
            recommendations_text = "\n".join([
                f"- **{rec.title}** (Priority: {rec.priority.value}, Effort: {rec.effort_level.value})\n  {rec.description}"
                for rec in scores.recommendations[:5]
            ])
            
            prompt = ChatPromptTemplate.from_template(template)
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0.3,
                google_api_key=settings.GOOGLE_API_KEY,
            )
            chain = prompt | llm | StrOutputParser()
            
            try:
                explanation_text = chain.invoke({
                    "overall_grade": scores.overall_grade,
                    "overall_score": scores.overall_score,
                    "repo_type": scores.metadata.repository_type or "General",
                    "category_breakdown": category_breakdown,
                    "contributing_factors": contributing_factors or "No specific factors identified",
                    "total_files": scores.metadata.total_files_analyzed,
                    "total_loc": scores.metadata.total_loc,
                    "technologies": ", ".join(scores.metadata.technologies) or "Unknown",
                    "recommendations": recommendations_text or "No recommendations generated"
                })
                gemini_limiter.record_api_success()
                return self._parse_ai_explanation(explanation_text, scores)
            except Exception as e:
                gemini_limiter.record_api_failure()
                raise
            
        except Exception as e:
            print(f"AI Grading Explanation Error: {e}")
            return self._generate_fallback_explanation(scores, str(e))
    
    def _parse_ai_explanation(self, explanation_text: str, scores: DetailedScoreReport) -> GradingExplanation:
        """Parse AI explanation into structured format."""
        lines = explanation_text.strip().split('\n')
        
        # Extract sections (simplified parsing)
        overall_explanation = explanation_text[:200] + "..." if len(explanation_text) > 200 else explanation_text
        
        # Generate category explanations based on scores
        category_explanations = {}
        for category, score in scores.category_scores.items():
            if score.score >= 80:
                category_explanations[category] = f"Excellent {category} with strong practices in place."
            elif score.score >= 60:
                category_explanations[category] = f"Good {category} with room for improvement."
            else:
                category_explanations[category] = f"Poor {category} requiring immediate attention."
        
        # Extract key insights (simplified)
        key_insights = [
            f"Overall code quality is {scores.overall_grade} level",
            f"Analyzed {scores.metadata.total_files_analyzed} files with {scores.metadata.total_loc} lines of code",
            f"Primary improvement area: {max(scores.category_scores.items(), key=lambda x: x[1].improvement_potential)[0]}"
        ]
        
        # Top improvement priorities
        improvement_priorities = [
            rec.title for rec in sorted(scores.recommendations, key=lambda x: x.estimated_impact, reverse=True)[:3]
        ]
        
        # Extract recommendations
        recommendations = [
            rec.description for rec in scores.recommendations[:3]
        ]
        
        return GradingExplanation(
            overall_explanation=overall_explanation,
            category_explanations=category_explanations,
            key_insights=key_insights,
            improvement_priorities=improvement_priorities,
            recommendations=recommendations,
            confidence_level=ConfidenceLevel.HIGH,
            fallback_used=False
        )
    
    def _generate_fallback_explanation(self, scores: DetailedScoreReport, error_msg: str = "") -> GradingExplanation:
        """Generate fallback explanation when AI is unavailable."""
        error_prefix = f"AI explanation unavailable ({error_msg}). " if error_msg else "AI explanation unavailable. "
        
        # Generate basic explanation
        if scores.overall_score >= 80:
            quality_assessment = "excellent"
        elif scores.overall_score >= 60:
            quality_assessment = "good"
        elif scores.overall_score >= 40:
            quality_assessment = "fair"
        else:
            quality_assessment = "poor"
        
        overall_explanation = (
            f"{error_prefix}The repository shows {quality_assessment} code quality "
            f"with an overall grade of {scores.overall_grade} ({scores.overall_score}/100). "
            f"Analysis covered {scores.metadata.total_files_analyzed} files with "
            f"{scores.metadata.total_loc} lines of code."
        )
        
        # Generate category explanations
        category_explanations = {}
        for category, score in scores.category_scores.items():
            if score.score >= 80:
                category_explanations[category] = f"Strong {category} practices with score of {score.score}/100."
            elif score.score >= 60:
                category_explanations[category] = f"Adequate {category} with score of {score.score}/100, some improvements possible."
            else:
                category_explanations[category] = f"Weak {category} with score of {score.score}/100, significant improvements needed."
        
        # Key insights
        lowest_category = min(scores.category_scores.items(), key=lambda x: x[1].score)
        highest_category = max(scores.category_scores.items(), key=lambda x: x[1].score)
        
        key_insights = [
            f"Strongest area: {highest_category[0]} ({highest_category[1].score}/100)",
            f"Weakest area: {lowest_category[0]} ({lowest_category[1].score}/100)",
            f"Total recommendations generated: {len(scores.recommendations)}"
        ]
        
        # Improvement priorities
        improvement_priorities = [
            rec.title for rec in sorted(scores.recommendations, key=lambda x: x.estimated_impact, reverse=True)[:3]
        ]
        
        # Generate fallback recommendations
        recommendations = [
            f"Focus on improving {lowest_category[0]} which has the lowest score",
            "Review the detailed recommendations for specific action items",
            "Consider addressing high-priority issues first for maximum impact"
        ]
        
        return GradingExplanation(
            overall_explanation=overall_explanation,
            category_explanations=category_explanations,
            key_insights=key_insights,
            improvement_priorities=improvement_priorities,
            recommendations=recommendations,
            confidence_level=ConfidenceLevel.LOW,
            fallback_used=True
        )