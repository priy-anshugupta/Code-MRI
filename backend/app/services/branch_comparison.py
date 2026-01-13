"""
Branch Comparison Engine for Repository Intelligence Enhancement

This module provides comprehensive branch comparison functionality including
side-by-side analysis, quality difference highlighting, and regression/improvement
identification.
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

from app.services.enhanced_grading import (
    DetailedScoreReport, CategoryScore, EnhancedGradingSystem, 
    ChangeType, Priority, EffortLevel
)
from app.models.branch import BranchAnalysisResult


@dataclass
class ScoreDifference:
    """Represents the difference between two scores."""
    category: str
    base_score: float
    compare_score: float
    difference: float  # compare - base
    percentage_change: float
    change_type: ChangeType
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category,
            "base_score": self.base_score,
            "compare_score": self.compare_score,
            "difference": round(self.difference, 2),
            "percentage_change": round(self.percentage_change, 2),
            "change_type": self.change_type.value
        }


@dataclass
class QualityChange:
    """Represents a quality change between branches."""
    category: str
    change_type: ChangeType
    magnitude: float  # Absolute change magnitude
    description: str
    affected_files: List[str]
    impact_level: Priority  # HIGH, MEDIUM, LOW based on magnitude
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category,
            "change_type": self.change_type.value,
            "magnitude": round(self.magnitude, 2),
            "description": self.description,
            "affected_files": self.affected_files,
            "impact_level": self.impact_level.value
        }


@dataclass
class FileChange:
    """Represents changes in a specific file between branches."""
    file_path: str
    change_type: str  # "added", "removed", "modified", "unchanged"
    base_score: Optional[float]
    compare_score: Optional[float]
    score_change: Optional[float]
    metrics_change: Dict[str, float]  # Changes in LOC, complexity, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "base_score": self.base_score,
            "compare_score": self.compare_score,
            "score_change": self.score_change,
            "metrics_change": self.metrics_change
        }


@dataclass
class ComparisonRecommendation:
    """Recommendation based on branch comparison."""
    title: str
    description: str
    priority: Priority
    change_type: ChangeType  # What type of change this addresses
    affected_categories: List[str]
    specific_actions: List[str]
    estimated_impact: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "change_type": self.change_type.value,
            "affected_categories": self.affected_categories,
            "specific_actions": self.specific_actions,
            "estimated_impact": round(self.estimated_impact, 2)
        }


@dataclass
class QualityDiff:
    """Detailed quality differences between two branches."""
    overall_score_diff: float
    overall_grade_change: Tuple[str, str]  # (base_grade, compare_grade)
    category_diffs: Dict[str, ScoreDifference]
    significant_changes: List[QualityChange]  # Changes above threshold
    improvement_areas: List[str]
    regression_areas: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_score_diff": round(self.overall_score_diff, 2),
            "overall_grade_change": self.overall_grade_change,
            "category_diffs": {k: v.to_dict() for k, v in self.category_diffs.items()},
            "significant_changes": [change.to_dict() for change in self.significant_changes],
            "improvement_areas": self.improvement_areas,
            "regression_areas": self.regression_areas
        }


@dataclass
class BranchComparison:
    """Complete comparison between two branches."""
    base_branch: str
    compare_branch: str
    base_commit_sha: str
    compare_commit_sha: str
    comparison_timestamp: datetime
    score_diff: QualityDiff
    quality_changes: List[QualityChange]
    file_changes: List[FileChange]
    recommendations: List[ComparisonRecommendation]
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "base_branch": self.base_branch,
            "compare_branch": self.compare_branch,
            "base_commit_sha": self.base_commit_sha,
            "compare_commit_sha": self.compare_commit_sha,
            "comparison_timestamp": self.comparison_timestamp.isoformat(),
            "score_diff": self.score_diff.to_dict(),
            "quality_changes": [change.to_dict() for change in self.quality_changes],
            "file_changes": [change.to_dict() for change in self.file_changes],
            "recommendations": [rec.to_dict() for rec in self.recommendations],
            "summary": self.summary
        }


class BranchComparisonEngine:
    """
    Engine for comparing analysis results between different branches.
    Provides side-by-side quality comparisons and identifies improvements/regressions.
    """
    
    def __init__(self, significance_threshold: float = 5.0):
        """
        Initialize the comparison engine.
        
        Args:
            significance_threshold: Minimum score difference to consider significant
        """
        self.significance_threshold = significance_threshold
    
    def compare_branches(
        self, 
        base_analysis: BranchAnalysisResult, 
        compare_analysis: BranchAnalysisResult
    ) -> BranchComparison:
        """
        Compare two branch analysis results and generate comprehensive comparison.
        
        Args:
            base_analysis: Analysis result for the base branch
            compare_analysis: Analysis result for the compare branch
            
        Returns:
            BranchComparison: Complete comparison results
        """
        # Validate inputs
        if not base_analysis or not compare_analysis:
            raise ValueError("Both base and compare analysis results are required")
        
        try:
            # Generate quality diff
            quality_diff = self.generate_quality_diff(base_analysis, compare_analysis)
            
            # Identify quality changes
            quality_changes = self._identify_quality_changes(quality_diff)
            
            # Analyze file changes
            file_changes = self._analyze_file_changes(base_analysis, compare_analysis)
            
            # Generate recommendations
            recommendations = self._generate_comparison_recommendations(
                quality_diff, quality_changes, file_changes
            )
            
            # Generate summary
            summary = self._generate_comparison_summary(
                base_analysis.branch_name if base_analysis.branch_name else "unknown", 
                compare_analysis.branch_name if compare_analysis.branch_name else "unknown",
                quality_diff,
                quality_changes
            )
            
            return BranchComparison(
                base_branch=base_analysis.branch_name if base_analysis.branch_name else "unknown",
                compare_branch=compare_analysis.branch_name if compare_analysis.branch_name else "unknown",
                base_commit_sha=base_analysis.commit_sha if base_analysis.commit_sha else "",
                compare_commit_sha=compare_analysis.commit_sha if compare_analysis.commit_sha else "",
                comparison_timestamp=datetime.now(),
                score_diff=quality_diff,
                quality_changes=quality_changes,
                file_changes=file_changes,
                recommendations=recommendations,
                summary=summary
            )
        except Exception as e:
            print(f"Error comparing branches: {e}")
            raise
    
    def generate_quality_diff(
        self, 
        base_analysis: BranchAnalysisResult, 
        compare_analysis: BranchAnalysisResult
    ) -> QualityDiff:
        """
        Generate detailed quality differences between two analyses.
        
        Args:
            base_analysis: Base branch analysis
            compare_analysis: Compare branch analysis
            
        Returns:
            QualityDiff: Detailed quality differences
        """
        # Extract scores from metrics (assuming they contain DetailedScoreReport data)
        base_metrics = base_analysis.metrics if base_analysis.metrics else {}
        compare_metrics = compare_analysis.metrics if compare_analysis.metrics else {}
        
        # Calculate overall score difference
        base_overall = float(base_metrics.get('overall_score', 0))
        compare_overall = float(compare_metrics.get('overall_score', 0))
        overall_diff = compare_overall - base_overall
        
        # Get grade changes
        base_grade = str(base_metrics.get('overall_grade', 'F'))
        compare_grade = str(compare_metrics.get('overall_grade', 'F'))
        
        # Calculate category differences
        category_diffs = {}
        base_categories = base_metrics.get('category_scores', {})
        compare_categories = compare_metrics.get('category_scores', {})
        
        # Ensure both are dictionaries
        if not isinstance(base_categories, dict):
            base_categories = {}
        if not isinstance(compare_categories, dict):
            compare_categories = {}
        
        all_categories = set(base_categories.keys()) | set(compare_categories.keys())
        
        for category in all_categories:
            # Safely extract scores
            try:
                base_cat = base_categories.get(category, {})
                if isinstance(base_cat, dict):
                    base_score = float(base_cat.get('score', 0))
                elif isinstance(base_cat, (int, float)):
                    base_score = float(base_cat)
                else:
                    base_score = 0.0
                    
                compare_cat = compare_categories.get(category, {})
                if isinstance(compare_cat, dict):
                    compare_score = float(compare_cat.get('score', 0))
                elif isinstance(compare_cat, (int, float)):
                    compare_score = float(compare_cat)
                else:
                    compare_score = 0.0
            except (ValueError, TypeError):
                base_score = 0.0
                compare_score = 0.0
            
            difference = compare_score - base_score
            percentage_change = (difference / base_score * 100) if base_score > 0 else 0.0
            
            # Determine change type
            if abs(difference) < self.significance_threshold:
                change_type = ChangeType.NO_CHANGE
            elif difference > 0:
                change_type = ChangeType.IMPROVEMENT
            else:
                change_type = ChangeType.REGRESSION
            
            category_diffs[category] = ScoreDifference(
                category=category,
                base_score=base_score,
                compare_score=compare_score,
                difference=difference,
                percentage_change=percentage_change,
                change_type=change_type
            )
        
        # Identify significant changes
        significant_changes = []
        improvement_areas = []
        regression_areas = []
        
        for category, diff in category_diffs.items():
            if abs(diff.difference) >= self.significance_threshold:
                magnitude = abs(diff.difference)
                
                # Determine impact level
                if magnitude >= 20:
                    impact_level = Priority.HIGH
                elif magnitude >= 10:
                    impact_level = Priority.MEDIUM
                else:
                    impact_level = Priority.LOW
                
                # Create description
                if diff.change_type == ChangeType.IMPROVEMENT:
                    description = f"{category.title()} improved by {diff.difference:.1f} points ({diff.percentage_change:.1f}%)"
                    improvement_areas.append(category)
                elif diff.change_type == ChangeType.REGRESSION:
                    description = f"{category.title()} declined by {abs(diff.difference):.1f} points ({abs(diff.percentage_change):.1f}%)"
                    regression_areas.append(category)
                else:
                    continue
                
                significant_changes.append(QualityChange(
                    category=category,
                    change_type=diff.change_type,
                    magnitude=magnitude,
                    description=description,
                    affected_files=[],  # Will be populated by file analysis
                    impact_level=impact_level
                ))
        
        return QualityDiff(
            overall_score_diff=overall_diff,
            overall_grade_change=(base_grade, compare_grade),
            category_diffs=category_diffs,
            significant_changes=significant_changes,
            improvement_areas=improvement_areas,
            regression_areas=regression_areas
        )
    
    def identify_regressions(self, comparison: BranchComparison) -> List[QualityChange]:
        """
        Identify quality regressions in the comparison.
        
        Args:
            comparison: Branch comparison results
            
        Returns:
            List[QualityChange]: List of identified regressions
        """
        return [
            change for change in comparison.quality_changes 
            if change.change_type == ChangeType.REGRESSION
        ]
    
    def highlight_improvements(self, comparison: BranchComparison) -> List[QualityChange]:
        """
        Highlight quality improvements in the comparison.
        
        Args:
            comparison: Branch comparison results
            
        Returns:
            List[QualityChange]: List of identified improvements
        """
        return [
            change for change in comparison.quality_changes 
            if change.change_type == ChangeType.IMPROVEMENT
        ]
    
    def _identify_quality_changes(self, quality_diff: QualityDiff) -> List[QualityChange]:
        """Identify and categorize quality changes."""
        return quality_diff.significant_changes
    
    def _analyze_file_changes(
        self, 
        base_analysis: BranchAnalysisResult, 
        compare_analysis: BranchAnalysisResult
    ) -> List[FileChange]:
        """
        Analyze changes at the file level between branches.
        
        Args:
            base_analysis: Base branch analysis
            compare_analysis: Compare branch analysis
            
        Returns:
            List[FileChange]: List of file-level changes
        """
        file_changes = []
        
        # Extract file scores from metrics
        base_files = base_analysis.metrics.get('file_level_scores', [])
        compare_files = compare_analysis.metrics.get('file_level_scores', [])
        
        # Create file maps for easier lookup
        base_file_map = {}
        compare_file_map = {}
        
        if isinstance(base_files, list):
            base_file_map = {f.get('file_path', ''): f for f in base_files if isinstance(f, dict)}
        
        if isinstance(compare_files, list):
            compare_file_map = {f.get('file_path', ''): f for f in compare_files if isinstance(f, dict)}
        
        # Get all file paths
        all_files = set(base_file_map.keys()) | set(compare_file_map.keys())
        
        for file_path in all_files:
            base_file = base_file_map.get(file_path)
            compare_file = compare_file_map.get(file_path)
            
            if base_file and compare_file:
                # File exists in both branches - modified or unchanged
                try:
                    base_score = float(base_file.get('overall_score', 0))
                    compare_score = float(compare_file.get('overall_score', 0))
                    score_change = compare_score - base_score
                except (ValueError, TypeError):
                    base_score = 0.0
                    compare_score = 0.0
                    score_change = 0.0
                
                # Calculate metrics changes
                base_metrics = base_file.get('metrics', {})
                compare_metrics = compare_file.get('metrics', {})
                
                # Ensure metrics are dictionaries
                if not isinstance(base_metrics, dict):
                    base_metrics = {}
                if not isinstance(compare_metrics, dict):
                    compare_metrics = {}
                
                metrics_change = {}
                for metric in ['loc', 'complexity', 'comments']:
                    try:
                        base_val = float(base_metrics.get(metric, 0))
                        compare_val = float(compare_metrics.get(metric, 0))
                        metrics_change[metric] = compare_val - base_val
                    except (ValueError, TypeError):
                        metrics_change[metric] = 0.0
                
                change_type = "modified" if abs(score_change) > 1 else "unchanged"
                
                file_changes.append(FileChange(
                    file_path=file_path,
                    change_type=change_type,
                    base_score=base_score,
                    compare_score=compare_score,
                    score_change=score_change,
                    metrics_change=metrics_change
                ))
                
            elif compare_file:
                # File added in compare branch
                file_changes.append(FileChange(
                    file_path=file_path,
                    change_type="added",
                    base_score=None,
                    compare_score=compare_file.get('overall_score', 0),
                    score_change=None,
                    metrics_change={}
                ))
                
            elif base_file:
                # File removed in compare branch
                file_changes.append(FileChange(
                    file_path=file_path,
                    change_type="removed",
                    base_score=base_file.get('overall_score', 0),
                    compare_score=None,
                    score_change=None,
                    metrics_change={}
                ))
        
        return file_changes
    
    def _generate_comparison_recommendations(
        self,
        quality_diff: QualityDiff,
        quality_changes: List[QualityChange],
        file_changes: List[FileChange]
    ) -> List[ComparisonRecommendation]:
        """Generate recommendations based on comparison results."""
        recommendations = []
        
        # Recommendations for regressions
        regressions = [change for change in quality_changes if change.change_type == ChangeType.REGRESSION]
        if regressions:
            high_impact_regressions = [r for r in regressions if r.impact_level == Priority.HIGH]
            
            if high_impact_regressions:
                recommendations.append(ComparisonRecommendation(
                    title="Address High-Impact Quality Regressions",
                    description=f"The compare branch shows significant quality regressions in {len(high_impact_regressions)} areas that need immediate attention.",
                    priority=Priority.HIGH,
                    change_type=ChangeType.REGRESSION,
                    affected_categories=[r.category for r in high_impact_regressions],
                    specific_actions=[
                        f"Review and fix {r.category} issues" for r in high_impact_regressions
                    ],
                    estimated_impact=sum(r.magnitude for r in high_impact_regressions)
                ))
        
        # Recommendations for maintaining improvements
        improvements = [change for change in quality_changes if change.change_type == ChangeType.IMPROVEMENT]
        if improvements:
            recommendations.append(ComparisonRecommendation(
                title="Maintain Quality Improvements",
                description=f"The compare branch shows improvements in {len(improvements)} areas. Ensure these gains are preserved in future development.",
                priority=Priority.MEDIUM,
                change_type=ChangeType.IMPROVEMENT,
                affected_categories=[i.category for i in improvements],
                specific_actions=[
                    "Document improved practices",
                    "Add tests to prevent regression",
                    "Update coding standards"
                ],
                estimated_impact=sum(i.magnitude for i in improvements)
            ))
        
        # Recommendations based on file changes
        added_files = [f for f in file_changes if f.change_type == "added"]
        removed_files = [f for f in file_changes if f.change_type == "removed"]
        
        if len(added_files) > 10:
            recommendations.append(ComparisonRecommendation(
                title="Review Large Number of New Files",
                description=f"{len(added_files)} new files were added. Ensure they follow project standards and are properly tested.",
                priority=Priority.MEDIUM,
                change_type=ChangeType.NO_CHANGE,
                affected_categories=["maintainability", "documentation"],
                specific_actions=[
                    "Review new file structure",
                    "Ensure proper documentation",
                    "Add appropriate tests"
                ],
                estimated_impact=10.0
            ))
        
        if len(removed_files) > 5:
            recommendations.append(ComparisonRecommendation(
                title="Verify Removed Files Impact",
                description=f"{len(removed_files)} files were removed. Verify that functionality is properly migrated or deprecated.",
                priority=Priority.MEDIUM,
                change_type=ChangeType.NO_CHANGE,
                affected_categories=["maintainability"],
                specific_actions=[
                    "Verify functionality migration",
                    "Update documentation",
                    "Check for broken dependencies"
                ],
                estimated_impact=8.0
            ))
        
        return recommendations
    
    def _generate_comparison_summary(
        self,
        base_branch: str,
        compare_branch: str,
        quality_diff: QualityDiff,
        quality_changes: List[QualityChange]
    ) -> str:
        """Generate a summary of the branch comparison."""
        
        # Overall change assessment
        if quality_diff.overall_score_diff > 5:
            overall_trend = "improved significantly"
        elif quality_diff.overall_score_diff > 0:
            overall_trend = "improved slightly"
        elif quality_diff.overall_score_diff < -5:
            overall_trend = "declined significantly"
        elif quality_diff.overall_score_diff < 0:
            overall_trend = "declined slightly"
        else:
            overall_trend = "remained stable"
        
        # Count changes by type
        improvements = len([c for c in quality_changes if c.change_type == ChangeType.IMPROVEMENT])
        regressions = len([c for c in quality_changes if c.change_type == ChangeType.REGRESSION])
        
        # Build summary
        summary_parts = [
            f"Comparison between '{base_branch}' and '{compare_branch}' shows that overall code quality has {overall_trend}",
            f"({quality_diff.overall_score_diff:+.1f} points, from {quality_diff.overall_grade_change[0]} to {quality_diff.overall_grade_change[1]})."
        ]
        
        if improvements > 0 and regressions > 0:
            summary_parts.append(f"The analysis identified {improvements} areas of improvement and {regressions} areas of regression.")
        elif improvements > 0:
            summary_parts.append(f"The analysis identified {improvements} areas of improvement with no significant regressions.")
        elif regressions > 0:
            summary_parts.append(f"The analysis identified {regressions} areas of regression that need attention.")
        else:
            summary_parts.append("No significant quality changes were detected between the branches.")
        
        # Highlight most significant changes
        if quality_changes:
            most_significant = max(quality_changes, key=lambda x: x.magnitude)
            summary_parts.append(f"The most significant change was in {most_significant.category}: {most_significant.description.lower()}.")
        
        return " ".join(summary_parts)