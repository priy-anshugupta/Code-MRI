"""
Data persistence service for repository intelligence data.
Provides high-level operations for storing and retrieving branch and analysis data.
"""
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

from app.models.database import (
    DatabaseManager, Repository, Branch, Analysis, 
    HistoricalMetric, CacheEntry
)
from app.models.branch import BranchInfo, BranchAnalysisResult
from app.core.config import settings


class DataPersistenceService:
    """Service for persisting and retrieving repository intelligence data."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize data persistence service.
        
        Args:
            database_url: SQLAlchemy database URL. Defaults to SQLite in temp directory.
        """
        if database_url is None:
            # Default to SQLite in the temp directory
            db_path = os.path.join(settings.TEMP_DIR, "code_mri.db")
            database_url = f"sqlite:///{db_path}"
        
        self.db_manager = DatabaseManager(database_url)
        self.db_manager.create_tables()
    
    def _get_session(self) -> Session:
        """Get a new database session."""
        return self.db_manager.get_session()
    
    # Repository operations
    
    def store_repository(self, repo_id: str, url: str, name: Optional[str] = None, 
                        default_branch: Optional[str] = None) -> Repository:
        """
        Store or update repository metadata.
        
        Args:
            repo_id: Repository identifier
            url: Repository URL
            name: Repository name
            default_branch: Default branch name
            
        Returns:
            Repository object
        """
        session = self._get_session()
        try:
            repo = session.query(Repository).filter(Repository.id == repo_id).first()
            
            if repo:
                # Update existing repository
                repo.url = url
                repo.last_accessed = datetime.now()
                if name:
                    repo.name = name
                if default_branch:
                    repo.default_branch = default_branch
            else:
                # Create new repository
                repo = Repository(
                    id=repo_id,
                    url=url,
                    name=name,
                    default_branch=default_branch
                )
                session.add(repo)
            
            session.commit()
            session.refresh(repo)
            return repo
        finally:
            session.close()
    
    def get_repository(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """
        Get repository metadata.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            Dictionary with repository data or None
        """
        session = self._get_session()
        try:
            repo = session.query(Repository).filter(Repository.id == repo_id).first()
            if repo:
                # Update last accessed time
                repo.last_accessed = datetime.now()
                session.commit()
                # Return as dictionary to avoid session issues
                return {
                    "id": repo.id,
                    "url": repo.url,
                    "name": repo.name,
                    "default_branch": repo.default_branch,
                    "created_at": repo.created_at,
                    "last_accessed": repo.last_accessed
                }
            return None
        finally:
            session.close()
    
    def delete_repository(self, repo_id: str) -> bool:
        """
        Delete repository and all associated data.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            True if deleted, False if not found
        """
        session = self._get_session()
        try:
            repo = session.query(Repository).filter(Repository.id == repo_id).first()
            if repo:
                session.delete(repo)
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    # Branch operations
    
    def store_branches(self, repo_id: str, branches: List[BranchInfo]) -> List[Branch]:
        """
        Store or update branch information for a repository.
        
        Args:
            repo_id: Repository identifier
            branches: List of BranchInfo objects
            
        Returns:
            List of Branch objects
        """
        session = self._get_session()
        try:
            stored_branches = []
            
            for branch_info in branches:
                # Check if branch exists
                branch = session.query(Branch).filter(
                    and_(
                        Branch.repo_id == repo_id,
                        Branch.name == branch_info.name
                    )
                ).first()
                
                if branch:
                    # Update existing branch
                    branch.commit_sha = branch_info.commit_sha
                    branch.is_default = branch_info.is_default
                    branch.last_commit_date = branch_info.last_commit_date
                    if branch_info.last_analyzed:
                        branch.last_analyzed = branch_info.last_analyzed
                    branch.updated_at = datetime.now()
                else:
                    # Create new branch
                    branch = Branch(
                        repo_id=repo_id,
                        name=branch_info.name,
                        commit_sha=branch_info.commit_sha,
                        is_default=branch_info.is_default,
                        last_commit_date=branch_info.last_commit_date,
                        last_analyzed=branch_info.last_analyzed
                    )
                    session.add(branch)
                
                stored_branches.append(branch)
            
            session.commit()
            
            # Refresh all branches to get IDs
            for branch in stored_branches:
                session.refresh(branch)
            
            return stored_branches
        finally:
            session.close()
    
    def get_branches(self, repo_id: str) -> List[BranchInfo]:
        """
        Get all branches for a repository.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            List of BranchInfo objects
        """
        session = self._get_session()
        try:
            branches = session.query(Branch).filter(Branch.repo_id == repo_id).all()
            
            return [
                BranchInfo(
                    name=branch.name,
                    commit_sha=branch.commit_sha,
                    is_default=branch.is_default,
                    last_commit_date=branch.last_commit_date,
                    last_analyzed=branch.last_analyzed
                )
                for branch in branches
            ]
        finally:
            session.close()
    
    def get_branch(self, repo_id: str, branch_name: str) -> Optional[Branch]:
        """
        Get a specific branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            
        Returns:
            Branch object or None
        """
        session = self._get_session()
        try:
            branch = session.query(Branch).filter(
                and_(
                    Branch.repo_id == repo_id,
                    Branch.name == branch_name
                )
            ).first()
            if branch:
                # Refresh to load all attributes
                session.refresh(branch)
                # Expunge from session to allow access after session close
                session.expunge(branch)
            return branch
        finally:
            session.close()
    
    def update_branch_analysis_time(self, repo_id: str, branch_name: str, 
                                   analysis_time: datetime) -> bool:
        """
        Update the last analyzed time for a branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            analysis_time: Analysis timestamp
            
        Returns:
            True if updated, False if branch not found
        """
        session = self._get_session()
        try:
            branch = session.query(Branch).filter(
                and_(
                    Branch.repo_id == repo_id,
                    Branch.name == branch_name
                )
            ).first()
            
            if branch:
                branch.last_analyzed = analysis_time
                branch.updated_at = datetime.now()
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    # Analysis operations
    
    def store_analysis(self, analysis_result: BranchAnalysisResult) -> str:
        """
        Store analysis results.
        
        Args:
            analysis_result: BranchAnalysisResult object
            
        Returns:
            Commit SHA of the stored analysis
        """
        session = self._get_session()
        try:
            # Get the branch ID
            branch = session.query(Branch).filter(
                and_(
                    Branch.repo_id == analysis_result.repo_id,
                    Branch.name == analysis_result.branch_name
                )
            ).first()
            
            if not branch:
                # Create branch if it doesn't exist
                branch = Branch(
                    repo_id=analysis_result.repo_id,
                    name=analysis_result.branch_name,
                    commit_sha=analysis_result.commit_sha,
                    is_default=False,
                    last_commit_date=datetime.now(),
                    last_analyzed=analysis_result.analysis_timestamp
                )
                session.add(branch)
                session.flush()
            
            # Extract overall score and grade from detailed_scores
            overall_score = None
            overall_grade = None
            if analysis_result.detailed_scores:
                if hasattr(analysis_result.detailed_scores, 'overall_score'):
                    overall_score = analysis_result.detailed_scores.overall_score
                elif isinstance(analysis_result.detailed_scores, dict):
                    overall_score = analysis_result.detailed_scores.get('overall_score')
                
                if hasattr(analysis_result.detailed_scores, 'overall_grade'):
                    overall_grade = analysis_result.detailed_scores.overall_grade
                elif isinstance(analysis_result.detailed_scores, dict):
                    overall_grade = analysis_result.detailed_scores.get('overall_grade')
            
            # Create analysis record
            analysis = Analysis(
                repo_id=analysis_result.repo_id,
                branch_id=branch.id,
                commit_sha=analysis_result.commit_sha,
                analysis_timestamp=analysis_result.analysis_timestamp,
                file_tree=analysis_result.file_tree if isinstance(analysis_result.file_tree, dict) else {},
                technologies=analysis_result.technologies,
                metrics=analysis_result.metrics if isinstance(analysis_result.metrics, dict) else {},
                issues=analysis_result.issues,
                ai_summary=analysis_result.ai_summary,
                ai_grading_explanation=analysis_result.ai_grading_explanation,
                detailed_scores=analysis_result.detailed_scores.to_dict() if hasattr(analysis_result.detailed_scores, 'to_dict') else analysis_result.detailed_scores,
                overall_score=overall_score,
                overall_grade=overall_grade
            )
            
            session.add(analysis)
            session.commit()
            
            # Update branch last_analyzed time
            branch.last_analyzed = analysis_result.analysis_timestamp
            session.commit()
            
            return analysis_result.commit_sha
        finally:
            session.close()
    
    def get_latest_analysis(self, repo_id: str, branch_name: str, 
                           commit_sha: Optional[str] = None) -> Optional[BranchAnalysisResult]:
        """
        Get the latest analysis for a branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            commit_sha: Optional commit SHA to filter by
            
        Returns:
            BranchAnalysisResult or None
        """
        session = self._get_session()
        try:
            # Get the branch
            branch = session.query(Branch).filter(
                and_(
                    Branch.repo_id == repo_id,
                    Branch.name == branch_name
                )
            ).first()
            
            if not branch:
                return None
            
            # Query for analysis
            query = session.query(Analysis).filter(Analysis.branch_id == branch.id)
            
            if commit_sha:
                query = query.filter(Analysis.commit_sha == commit_sha)
            
            analysis = query.order_by(desc(Analysis.analysis_timestamp)).first()
            
            if not analysis:
                return None
            
            # Convert to BranchAnalysisResult
            return BranchAnalysisResult(
                repo_id=analysis.repo_id,
                branch_name=branch_name,
                commit_sha=analysis.commit_sha,
                analysis_timestamp=analysis.analysis_timestamp,
                file_tree=analysis.file_tree,
                technologies=analysis.technologies,
                metrics=analysis.metrics,
                issues=analysis.issues,
                ai_summary=analysis.ai_summary,
                ai_grading_explanation=analysis.ai_grading_explanation,
                detailed_scores=analysis.detailed_scores
            )
        finally:
            session.close()
    
    def get_analysis_history(self, repo_id: str, branch_name: str, 
                            limit: int = 10) -> List[BranchAnalysisResult]:
        """
        Get analysis history for a branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            limit: Maximum number of results
            
        Returns:
            List of BranchAnalysisResult objects
        """
        session = self._get_session()
        try:
            # Get the branch
            branch = session.query(Branch).filter(
                and_(
                    Branch.repo_id == repo_id,
                    Branch.name == branch_name
                )
            ).first()
            
            if not branch:
                return []
            
            # Query for analyses
            analyses = session.query(Analysis).filter(
                Analysis.branch_id == branch.id
            ).order_by(desc(Analysis.analysis_timestamp)).limit(limit).all()
            
            return [
                BranchAnalysisResult(
                    repo_id=analysis.repo_id,
                    branch_name=branch_name,
                    commit_sha=analysis.commit_sha,
                    analysis_timestamp=analysis.analysis_timestamp,
                    file_tree=analysis.file_tree,
                    technologies=analysis.technologies,
                    metrics=analysis.metrics,
                    issues=analysis.issues,
                    ai_summary=analysis.ai_summary,
                    ai_grading_explanation=analysis.ai_grading_explanation,
                    detailed_scores=analysis.detailed_scores
                )
                for analysis in analyses
            ]
        finally:
            session.close()
    
    # Historical metrics operations
    
    def store_historical_metric(self, repo_id: str, branch_name: str, commit_sha: str,
                               metrics: Dict[str, Any]) -> HistoricalMetric:
        """
        Store historical metrics for trend analysis.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            commit_sha: Commit SHA
            metrics: Dictionary of metric values
            
        Returns:
            HistoricalMetric object
        """
        session = self._get_session()
        try:
            metric = HistoricalMetric(
                repo_id=repo_id,
                branch_name=branch_name,
                commit_sha=commit_sha,
                timestamp=datetime.now(),
                overall_score=metrics.get('overall_score'),
                readability_score=metrics.get('readability_score'),
                complexity_score=metrics.get('complexity_score'),
                maintainability_score=metrics.get('maintainability_score'),
                documentation_score=metrics.get('documentation_score'),
                security_score=metrics.get('security_score'),
                performance_score=metrics.get('performance_score'),
                total_issues=metrics.get('total_issues', 0),
                critical_issues=metrics.get('critical_issues', 0),
                high_issues=metrics.get('high_issues', 0),
                medium_issues=metrics.get('medium_issues', 0),
                low_issues=metrics.get('low_issues', 0),
                total_files=metrics.get('total_files', 0),
                total_lines=metrics.get('total_lines', 0)
            )
            
            session.add(metric)
            session.commit()
            session.refresh(metric)
            return metric
        finally:
            session.close()
    
    def get_historical_metrics(self, repo_id: str, branch_name: str, 
                              days_back: int = 30) -> List[HistoricalMetric]:
        """
        Get historical metrics for trend analysis.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            days_back: Number of days to look back
            
        Returns:
            List of HistoricalMetric objects
        """
        session = self._get_session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            metrics = session.query(HistoricalMetric).filter(
                and_(
                    HistoricalMetric.repo_id == repo_id,
                    HistoricalMetric.branch_name == branch_name,
                    HistoricalMetric.timestamp >= cutoff_date
                )
            ).order_by(HistoricalMetric.timestamp).all()
            
            return metrics
        finally:
            session.close()
    
    # Cache management operations
    
    def register_cache_entry(self, cache_key: str, repo_id: str, branch_name: str,
                            commit_sha: str, file_path: str, size_bytes: int) -> CacheEntry:
        """
        Register a cache entry in the database.
        
        Args:
            cache_key: Cache key
            repo_id: Repository identifier
            branch_name: Branch name
            commit_sha: Commit SHA
            file_path: Path to cached file
            size_bytes: Size of cached file in bytes
            
        Returns:
            CacheEntry object
        """
        session = self._get_session()
        try:
            # Check if entry exists
            entry = session.query(CacheEntry).filter(CacheEntry.cache_key == cache_key).first()
            
            if entry:
                # Update existing entry
                entry.last_accessed = datetime.now()
                entry.access_count += 1
            else:
                # Create new entry
                entry = CacheEntry(
                    cache_key=cache_key,
                    repo_id=repo_id,
                    branch_name=branch_name,
                    commit_sha=commit_sha,
                    file_path=file_path,
                    size_bytes=size_bytes,
                    access_count=1
                )
                session.add(entry)
            
            session.commit()
            session.refresh(entry)
            return entry
        finally:
            session.close()
    
    def get_cache_entry(self, cache_key: str) -> Optional[CacheEntry]:
        """
        Get cache entry metadata.
        
        Args:
            cache_key: Cache key
            
        Returns:
            CacheEntry or None
        """
        session = self._get_session()
        try:
            entry = session.query(CacheEntry).filter(CacheEntry.cache_key == cache_key).first()
            
            if entry:
                # Update access time and count
                entry.last_accessed = datetime.now()
                entry.access_count += 1
                session.commit()
            
            return entry
        finally:
            session.close()
    
    def cleanup_stale_cache_entries(self, max_age_hours: int = 24) -> int:
        """
        Remove stale cache entries from database.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of entries removed
        """
        session = self._get_session()
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            count = session.query(CacheEntry).filter(
                CacheEntry.last_accessed < cutoff_time
            ).delete()
            
            session.commit()
            return count
        finally:
            session.close()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        session = self._get_session()
        try:
            total_entries = session.query(CacheEntry).count()
            total_size = session.query(CacheEntry).with_entities(
                CacheEntry.size_bytes
            ).all()
            
            total_size_bytes = sum(size[0] for size in total_size if size[0])
            
            return {
                "total_entries": total_entries,
                "total_size_bytes": total_size_bytes,
                "total_size_mb": round(total_size_bytes / (1024 * 1024), 2)
            }
        finally:
            session.close()
    
    # Cleanup operations
    
    def cleanup_old_repositories(self, max_age_hours: int = 24) -> int:
        """
        Remove repositories that haven't been accessed recently.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of repositories removed
        """
        session = self._get_session()
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            count = session.query(Repository).filter(
                Repository.last_accessed < cutoff_time
            ).delete()
            
            session.commit()
            return count
        finally:
            session.close()
    
    def cleanup_old_analyses(self, max_age_days: int = 30) -> int:
        """
        Remove old analysis records.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Number of analyses removed
        """
        session = self._get_session()
        try:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            
            count = session.query(Analysis).filter(
                Analysis.analysis_timestamp < cutoff_time
            ).delete()
            
            session.commit()
            return count
        finally:
            session.close()
    
    def close(self):
        """Close database connections."""
        self.db_manager.close()
