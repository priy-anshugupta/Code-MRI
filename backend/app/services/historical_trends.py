"""
Historical Trend Analysis for Repository Intelligence Enhancement

This module provides capabilities for analyzing quality trends across branch history,
storing historical metrics, and preparing visualization data.
"""

import os
import json
import math
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import statistics

from app.models.branch import BranchAnalysisResult


class TrendDirection(Enum):
    """Direction of trend over time."""
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    VOLATILE = "volatile"  # Fluctuating significantly


@dataclass
class HistoricalDataPoint:
    """Single data point in historical analysis."""
    timestamp: datetime
    commit_sha: str
    branch_name: str
    overall_score: float
    category_scores: Dict[str, float]
    total_files: int
    total_loc: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "commit_sha": self.commit_sha,
            "branch_name": self.branch_name,
            "overall_score": self.overall_score,
            "category_scores": self.category_scores,
            "total_files": self.total_files,
            "total_loc": self.total_loc
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoricalDataPoint':
        """Create from dictionary."""
        # Safe datetime parsing with fallback
        try:
            timestamp = datetime.fromisoformat(data["timestamp"])
        except (ValueError, TypeError, KeyError):
            # Fallback to current time if parsing fails
            timestamp = datetime.now()
        
        return cls(
            timestamp=timestamp,
            commit_sha=data.get("commit_sha", ""),
            branch_name=data.get("branch_name", ""),
            overall_score=data.get("overall_score", 0.0),
            category_scores=data.get("category_scores", {}),
            total_files=data.get("total_files", 0),
            total_loc=data.get("total_loc", 0)
        )


@dataclass
class TrendMetrics:
    """Metrics describing a trend over time."""
    direction: TrendDirection
    slope: float  # Rate of change per day
    correlation: float  # Correlation coefficient (-1 to 1)
    volatility: float  # Standard deviation of changes
    confidence: float  # Confidence in trend (0-1)
    start_value: float
    end_value: float
    total_change: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "direction": self.direction.value,
            "slope": round(self.slope, 4),
            "correlation": round(self.correlation, 4),
            "volatility": round(self.volatility, 4),
            "confidence": round(self.confidence, 4),
            "start_value": round(self.start_value, 2),
            "end_value": round(self.end_value, 2),
            "total_change": round(self.total_change, 2)
        }


@dataclass
class CategoryTrend:
    """Trend analysis for a specific quality category."""
    category: str
    metrics: TrendMetrics
    data_points: List[Tuple[datetime, float]]  # (timestamp, score) pairs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category,
            "metrics": self.metrics.to_dict(),
            "data_points": [
                {"timestamp": ts.isoformat(), "score": score}
                for ts, score in self.data_points
            ]
        }


@dataclass
class BranchTrendAnalysis:
    """Complete trend analysis for a branch."""
    repo_id: str
    branch_name: str
    analysis_period: Tuple[datetime, datetime]  # (start, end)
    overall_trend: TrendMetrics
    category_trends: Dict[str, CategoryTrend]
    data_points: List[HistoricalDataPoint]
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "repo_id": self.repo_id,
            "branch_name": self.branch_name,
            "analysis_period": {
                "start": self.analysis_period[0].isoformat(),
                "end": self.analysis_period[1].isoformat()
            },
            "overall_trend": self.overall_trend.to_dict(),
            "category_trends": {k: v.to_dict() for k, v in self.category_trends.items()},
            "data_points": [dp.to_dict() for dp in self.data_points],
            "summary": self.summary
        }


@dataclass
class VisualizationData:
    """Data prepared for frontend visualization."""
    chart_type: str  # "line", "bar", "area"
    title: str
    x_axis_label: str
    y_axis_label: str
    datasets: List[Dict[str, Any]]  # Chart.js compatible format
    annotations: List[Dict[str, Any]]  # Notable events/changes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "chart_type": self.chart_type,
            "title": self.title,
            "x_axis_label": self.x_axis_label,
            "y_axis_label": self.y_axis_label,
            "datasets": self.datasets,
            "annotations": self.annotations
        }


class HistoricalTrendsAnalyzer:
    """
    Analyzer for calculating trends across branch history and preparing visualization data.
    """
    
    def __init__(self, storage_path: str = "backend/temp_clones/historical_data"):
        """Initialize with storage path for historical data."""
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
    
    def store_analysis_result(self, analysis_result: BranchAnalysisResult) -> None:
        """
        Store analysis result for historical tracking.
        
        Args:
            analysis_result: Branch analysis result to store
        """
        if not analysis_result:
            print("Warning: Cannot store None analysis result")
            return
        
        # Safely extract metrics
        metrics = analysis_result.metrics if analysis_result.metrics else {}
        metadata = metrics.get('metadata', {}) if isinstance(metrics, dict) else {}
        
        # Create historical data point with safe defaults
        try:
            data_point = HistoricalDataPoint(
                timestamp=analysis_result.analysis_timestamp if analysis_result.analysis_timestamp else datetime.now(),
                commit_sha=analysis_result.commit_sha if analysis_result.commit_sha else "",
                branch_name=analysis_result.branch_name if analysis_result.branch_name else "",
                overall_score=float(metrics.get('overall_score', 0)),
                category_scores=self._extract_category_scores(metrics),
                total_files=int(metadata.get('total_files_analyzed', 0)) if isinstance(metadata, dict) else 0,
                total_loc=int(metadata.get('total_loc', 0)) if isinstance(metadata, dict) else 0
            )
        except (ValueError, TypeError, AttributeError) as e:
            print(f"Error creating historical data point: {e}")
            return
        
        # Store to file
        file_path = os.path.join(
            self.storage_path, 
            f"{analysis_result.repo_id}_{analysis_result.branch_name}_history.json"
        )
        
        # Load existing data
        historical_data = []
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    historical_data = [HistoricalDataPoint.from_dict(item) for item in data]
            except Exception as e:
                print(f"Error loading historical data: {e}")
        
        # Add new data point (avoid duplicates)
        existing_shas = {dp.commit_sha for dp in historical_data}
        if data_point.commit_sha not in existing_shas:
            historical_data.append(data_point)
            
            # Sort by timestamp
            historical_data.sort(key=lambda x: x.timestamp)
            
            # Keep only last 100 data points to manage storage
            if len(historical_data) > 100:
                historical_data = historical_data[-100:]
            
            # Save updated data
            try:
                with open(file_path, 'w') as f:
                    json.dump([dp.to_dict() for dp in historical_data], f, indent=2)
            except Exception as e:
                print(f"Error saving historical data: {e}")
    
    def calculate_branch_trends(
        self, 
        repo_id: str, 
        branch_name: str, 
        days_back: int = 30
    ) -> Optional[BranchTrendAnalysis]:
        """
        Calculate trend analysis for a specific branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            days_back: Number of days to analyze (default 30)
            
        Returns:
            BranchTrendAnalysis or None if insufficient data
        """
        try:
            # Load historical data
            historical_data = self._load_historical_data(repo_id, branch_name)
            if not historical_data or len(historical_data) < 2:
                return None
            
            # Filter by time period
            end_date = datetime.now()
            start_date = end_date - timedelta(days=max(1, days_back))
            
            filtered_data = [
                dp for dp in historical_data 
                if dp.timestamp and start_date <= dp.timestamp <= end_date
            ]
            
            if len(filtered_data) < 2:
                return None
            
            # Calculate overall trend
            overall_trend = self._calculate_trend_metrics(
                [(dp.timestamp, dp.overall_score) for dp in filtered_data if dp.timestamp]
            )
            
            # Calculate category trends
            category_trends = {}
            all_categories = set()
            for dp in filtered_data:
                if dp.category_scores and isinstance(dp.category_scores, dict):
                    all_categories.update(dp.category_scores.keys())
            
            for category in all_categories:
                category_data = []
                for dp in filtered_data:
                    if dp.category_scores and isinstance(dp.category_scores, dict) and category in dp.category_scores:
                        try:
                            score = float(dp.category_scores[category])
                            if dp.timestamp:
                                category_data.append((dp.timestamp, score))
                        except (ValueError, TypeError):
                            continue
                
                if len(category_data) >= 2:
                    trend_metrics = self._calculate_trend_metrics(category_data)
                    category_trends[category] = CategoryTrend(
                        category=category,
                        metrics=trend_metrics,
                        data_points=category_data
                    )
            
            # Generate summary
            summary = self._generate_trend_summary(overall_trend, category_trends, len(filtered_data))
            
            return BranchTrendAnalysis(
                repo_id=repo_id,
                branch_name=branch_name,
                analysis_period=(start_date, end_date),
                overall_trend=overall_trend,
                category_trends=category_trends,
                data_points=filtered_data,
                summary=summary
            )
        except Exception as e:
            print(f"Error calculating branch trends: {e}")
            return None
    
    def prepare_visualization_data(
        self, 
        trend_analysis: BranchTrendAnalysis,
        chart_type: str = "line"
    ) -> List[VisualizationData]:
        """
        Prepare data for frontend visualization.
        
        Args:
            trend_analysis: Trend analysis results
            chart_type: Type of chart ("line", "bar", "area")
            
        Returns:
            List of visualization data objects
        """
        if not trend_analysis:
            return []
        
        visualizations = []
        
        try:
            # Overall score trend visualization
            overall_viz = self._create_overall_score_visualization(trend_analysis, chart_type)
            visualizations.append(overall_viz)
        except Exception as e:
            print(f"Error creating overall score visualization: {e}")
        
        try:
            # Category trends visualization
            category_viz = self._create_category_trends_visualization(trend_analysis, chart_type)
            visualizations.append(category_viz)
        except Exception as e:
            print(f"Error creating category trends visualization: {e}")
        
        try:
            # Quality metrics comparison
            metrics_viz = self._create_metrics_comparison_visualization(trend_analysis)
            visualizations.append(metrics_viz)
        except Exception as e:
            print(f"Error creating metrics comparison visualization: {e}")
        
        return visualizations
    
    def compare_branch_trends(
        self, 
        repo_id: str, 
        branch1: str, 
        branch2: str,
        days_back: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Compare trends between two branches.
        
        Args:
            repo_id: Repository identifier
            branch1: First branch name
            branch2: Second branch name
            days_back: Number of days to analyze
            
        Returns:
            Comparison data or None if insufficient data
        """
        try:
            trend1 = self.calculate_branch_trends(repo_id, branch1, days_back)
            trend2 = self.calculate_branch_trends(repo_id, branch2, days_back)
            
            if not trend1 or not trend2:
                return None
            
            comparison = {
                "branch1": {
                    "name": branch1,
                    "overall_trend": trend1.overall_trend.to_dict(),
                    "final_score": trend1.overall_trend.end_value
                },
                "branch2": {
                    "name": branch2,
                    "overall_trend": trend2.overall_trend.to_dict(),
                    "final_score": trend2.overall_trend.end_value
                },
                "comparison": {
                    "score_difference": trend2.overall_trend.end_value - trend1.overall_trend.end_value,
                    "trend_difference": trend2.overall_trend.slope - trend1.overall_trend.slope,
                    "better_performing": branch2 if trend2.overall_trend.end_value > trend1.overall_trend.end_value else branch1
                },
                "category_comparisons": {}
            }
            
            # Compare category trends
            common_categories = set(trend1.category_trends.keys()) & set(trend2.category_trends.keys())
            for category in common_categories:
                cat1 = trend1.category_trends[category]
                cat2 = trend2.category_trends[category]
                
                comparison["category_comparisons"][category] = {
                    "branch1_trend": cat1.metrics.direction.value,
                    "branch2_trend": cat2.metrics.direction.value,
                    "score_difference": cat2.metrics.end_value - cat1.metrics.end_value,
                    "better_performing": branch2 if cat2.metrics.end_value > cat1.metrics.end_value else branch1
                }
            
            return comparison
        except Exception as e:
            print(f"Error comparing branch trends: {e}")
            return None
    
    def _extract_category_scores(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """Extract category scores from metrics dictionary."""
        category_scores = {}
        
        if not metrics or not isinstance(metrics, dict):
            return category_scores
        
        # Handle different metrics formats
        if 'category_scores' in metrics:
            cat_scores = metrics['category_scores']
            if isinstance(cat_scores, dict):
                for category, score_data in cat_scores.items():
                    try:
                        if isinstance(score_data, dict) and 'score' in score_data:
                            category_scores[category] = float(score_data['score'])
                        elif isinstance(score_data, (int, float)):
                            category_scores[category] = float(score_data)
                    except (ValueError, TypeError):
                        # Skip invalid score data
                        continue
        
        return category_scores
    
    def _load_historical_data(self, repo_id: str, branch_name: str) -> List[HistoricalDataPoint]:
        """Load historical data for a specific branch."""
        file_path = os.path.join(self.storage_path, f"{repo_id}_{branch_name}_history.json")
        
        if not os.path.exists(file_path):
            return []
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return [HistoricalDataPoint.from_dict(item) for item in data]
        except Exception as e:
            print(f"Error loading historical data: {e}")
            return []
    
    def _calculate_trend_metrics(self, data_points: List[Tuple[datetime, float]]) -> TrendMetrics:
        """
        Calculate trend metrics from time series data.
        
        Args:
            data_points: List of (timestamp, value) tuples
            
        Returns:
            TrendMetrics object
        """
        if len(data_points) < 2:
            return TrendMetrics(
                direction=TrendDirection.STABLE,
                slope=0.0,
                correlation=0.0,
                volatility=0.0,
                confidence=0.0,
                start_value=0.0,
                end_value=0.0,
                total_change=0.0
            )
        
        # Sort by timestamp
        data_points.sort(key=lambda x: x[0])
        
        # Convert timestamps to days since start
        start_time = data_points[0][0]
        x_values = [(dp[0] - start_time).total_seconds() / 86400 for dp in data_points]  # Days
        y_values = [dp[1] for dp in data_points]
        
        # Calculate linear regression
        n = len(data_points)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)
        
        # Slope (rate of change per day)
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator != 0:
            slope = (n * sum_xy - sum_x * sum_y) / denominator
        else:
            slope = 0.0
        
        # Correlation coefficient
        if len(y_values) > 1:
            try:
                correlation = self._calculate_correlation(x_values, y_values)
            except:
                correlation = 0.0
        else:
            correlation = 0.0
        
        # Volatility (standard deviation of changes)
        if len(y_values) > 1:
            changes = [y_values[i] - y_values[i-1] for i in range(1, len(y_values))]
            volatility = statistics.stdev(changes) if len(changes) > 1 else 0.0
        else:
            volatility = 0.0
        
        # Determine trend direction
        abs_correlation = abs(correlation)
        if abs_correlation < 0.3:
            direction = TrendDirection.STABLE
        elif volatility > 10:  # High volatility threshold
            direction = TrendDirection.VOLATILE
        elif slope > 0:
            direction = TrendDirection.IMPROVING
        else:
            direction = TrendDirection.DECLINING
        
        # Confidence based on correlation strength and data points
        confidence = min(1.0, abs_correlation * (min(n, 10) / 10))
        
        start_value = y_values[0]
        end_value = y_values[-1]
        total_change = end_value - start_value
        
        return TrendMetrics(
            direction=direction,
            slope=slope,
            correlation=correlation,
            volatility=volatility,
            confidence=confidence,
            start_value=start_value,
            end_value=end_value,
            total_change=total_change
        )
    
    def _calculate_correlation(self, x_values: List[float], y_values: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = len(x_values)
        if n < 2:
            return 0.0
        
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)
        sum_y2 = sum(y * y for y in y_values)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y))
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    def _generate_trend_summary(
        self, 
        overall_trend: TrendMetrics, 
        category_trends: Dict[str, CategoryTrend],
        data_points_count: int
    ) -> str:
        """Generate human-readable summary of trends."""
        
        # Overall trend description
        if overall_trend.direction == TrendDirection.IMPROVING:
            trend_desc = f"improving at {overall_trend.slope:.2f} points per day"
        elif overall_trend.direction == TrendDirection.DECLINING:
            trend_desc = f"declining at {abs(overall_trend.slope):.2f} points per day"
        elif overall_trend.direction == TrendDirection.VOLATILE:
            trend_desc = "showing volatile patterns with significant fluctuations"
        else:
            trend_desc = "remaining relatively stable"
        
        summary_parts = [
            f"Analysis of {data_points_count} data points shows overall code quality is {trend_desc}",
            f"(total change: {overall_trend.total_change:+.1f} points, confidence: {overall_trend.confidence:.1%})."
        ]
        
        # Category insights
        if category_trends:
            improving_categories = [
                name for name, trend in category_trends.items() 
                if trend.metrics.direction == TrendDirection.IMPROVING
            ]
            declining_categories = [
                name for name, trend in category_trends.items() 
                if trend.metrics.direction == TrendDirection.DECLINING
            ]
            
            if improving_categories:
                summary_parts.append(f"Improving areas: {', '.join(improving_categories)}.")
            
            if declining_categories:
                summary_parts.append(f"Declining areas: {', '.join(declining_categories)}.")
            
            if not improving_categories and not declining_categories:
                summary_parts.append("Most quality categories remain stable.")
        
        return " ".join(summary_parts)
    
    def _create_overall_score_visualization(
        self, 
        trend_analysis: BranchTrendAnalysis,
        chart_type: str
    ) -> VisualizationData:
        """Create visualization for overall score trend."""
        
        # Prepare data points
        data_points = [
            {
                "x": dp.timestamp.isoformat(),
                "y": dp.overall_score
            }
            for dp in trend_analysis.data_points
        ]
        
        # Create dataset
        dataset = {
            "label": f"Overall Quality Score - {trend_analysis.branch_name}",
            "data": data_points,
            "borderColor": "#3B82F6",
            "backgroundColor": "rgba(59, 130, 246, 0.1)",
            "fill": chart_type == "area",
            "tension": 0.4
        }
        
        # Create annotations for significant changes
        annotations = []
        if len(trend_analysis.data_points) > 1:
            max_score = max(dp.overall_score for dp in trend_analysis.data_points)
            min_score = min(dp.overall_score for dp in trend_analysis.data_points)
            
            if max_score - min_score > 10:  # Significant change threshold
                max_point = max(trend_analysis.data_points, key=lambda x: x.overall_score)
                min_point = min(trend_analysis.data_points, key=lambda x: x.overall_score)
                
                annotations.extend([
                    {
                        "type": "point",
                        "xValue": max_point.timestamp.isoformat(),
                        "yValue": max_point.overall_score,
                        "backgroundColor": "#10B981",
                        "label": {
                            "content": f"Peak: {max_point.overall_score:.1f}",
                            "enabled": True
                        }
                    },
                    {
                        "type": "point",
                        "xValue": min_point.timestamp.isoformat(),
                        "yValue": min_point.overall_score,
                        "backgroundColor": "#EF4444",
                        "label": {
                            "content": f"Low: {min_point.overall_score:.1f}",
                            "enabled": True
                        }
                    }
                ])
        
        return VisualizationData(
            chart_type=chart_type,
            title=f"Overall Quality Trend - {trend_analysis.branch_name}",
            x_axis_label="Time",
            y_axis_label="Quality Score",
            datasets=[dataset],
            annotations=annotations
        )
    
    def _create_category_trends_visualization(
        self, 
        trend_analysis: BranchTrendAnalysis,
        chart_type: str
    ) -> VisualizationData:
        """Create visualization for category trends."""
        
        # Color palette for categories
        colors = [
            "#3B82F6", "#10B981", "#F59E0B", "#EF4444", 
            "#8B5CF6", "#06B6D4", "#84CC16", "#F97316"
        ]
        
        datasets = []
        for i, (category, trend) in enumerate(trend_analysis.category_trends.items()):
            color = colors[i % len(colors)]
            
            data_points = [
                {
                    "x": ts.isoformat(),
                    "y": score
                }
                for ts, score in trend.data_points
            ]
            
            dataset = {
                "label": category.title(),
                "data": data_points,
                "borderColor": color,
                "backgroundColor": f"{color}20",  # 20% opacity
                "fill": False,
                "tension": 0.4
            }
            datasets.append(dataset)
        
        return VisualizationData(
            chart_type="line",  # Always use line for multi-category
            title=f"Category Quality Trends - {trend_analysis.branch_name}",
            x_axis_label="Time",
            y_axis_label="Category Score",
            datasets=datasets,
            annotations=[]
        )
    
    def _create_metrics_comparison_visualization(
        self, 
        trend_analysis: BranchTrendAnalysis
    ) -> VisualizationData:
        """Create visualization comparing different metrics over time."""
        
        # Prepare datasets for files and LOC trends
        files_data = [
            {
                "x": dp.timestamp.isoformat(),
                "y": dp.total_files
            }
            for dp in trend_analysis.data_points
        ]
        
        loc_data = [
            {
                "x": dp.timestamp.isoformat(),
                "y": dp.total_loc
            }
            for dp in trend_analysis.data_points
        ]
        
        datasets = [
            {
                "label": "Total Files",
                "data": files_data,
                "borderColor": "#10B981",
                "backgroundColor": "rgba(16, 185, 129, 0.1)",
                "yAxisID": "y",
                "fill": False
            },
            {
                "label": "Lines of Code",
                "data": loc_data,
                "borderColor": "#F59E0B",
                "backgroundColor": "rgba(245, 158, 11, 0.1)",
                "yAxisID": "y1",
                "fill": False
            }
        ]
        
        return VisualizationData(
            chart_type="line",
            title=f"Repository Metrics Trend - {trend_analysis.branch_name}",
            x_axis_label="Time",
            y_axis_label="Count",
            datasets=datasets,
            annotations=[]
        )