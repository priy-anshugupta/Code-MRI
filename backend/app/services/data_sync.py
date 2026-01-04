"""
Data synchronization service with conflict resolution for concurrent updates.
"""
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from app.models.branch import BranchInfo, BranchAnalysisResult
from app.services.data_persistence import DataPersistenceService


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving data conflicts."""
    LATEST_WINS = "latest_wins"  # Most recent update wins
    MERGE = "merge"  # Attempt to merge changes
    MANUAL = "manual"  # Require manual resolution


class SyncConflict:
    """Represents a data synchronization conflict."""
    
    def __init__(self, entity_type: str, entity_id: str, 
                 local_data: Any, remote_data: Any, conflict_reason: str):
        """
        Initialize sync conflict.
        
        Args:
            entity_type: Type of entity (e.g., 'branch', 'analysis')
            entity_id: Identifier for the entity
            local_data: Local version of data
            remote_data: Remote/incoming version of data
            conflict_reason: Description of the conflict
        """
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.local_data = local_data
        self.remote_data = remote_data
        self.conflict_reason = conflict_reason
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "conflict_reason": self.conflict_reason,
            "timestamp": self.timestamp.isoformat()
        }


class DataSynchronizationService:
    """Service for synchronizing data with conflict resolution."""
    
    def __init__(self, persistence_service: DataPersistenceService,
                 strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LATEST_WINS):
        """
        Initialize data synchronization service.
        
        Args:
            persistence_service: Data persistence service
            strategy: Conflict resolution strategy
        """
        self.persistence = persistence_service
        self.strategy = strategy
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._conflicts: List[SyncConflict] = []
    
    def sync_branch_metadata(self, repo_id: str, branch_info: BranchInfo) -> bool:
        """
        Synchronize branch metadata with conflict resolution.
        
        Args:
            repo_id: Repository identifier
            branch_info: Branch information to sync
            
        Returns:
            True if synced successfully, False if conflict requires manual resolution
        """
        with self._lock:
            # Get existing branch data
            existing_branch = self.persistence.get_branch(repo_id, branch_info.name)
            
            if not existing_branch:
                # No conflict - new branch
                self.persistence.store_branches(repo_id, [branch_info])
                return True
            
            # Check for conflicts
            if existing_branch.commit_sha != branch_info.commit_sha:
                # Commit SHA changed - check timestamps
                if self.strategy == ConflictResolutionStrategy.LATEST_WINS:
                    # Compare timestamps
                    if branch_info.last_commit_date > existing_branch.last_commit_date:
                        # Incoming data is newer
                        self.persistence.store_branches(repo_id, [branch_info])
                        return True
                    else:
                        # Existing data is newer or same - keep it
                        return True
                
                elif self.strategy == ConflictResolutionStrategy.MERGE:
                    # Merge strategy: take the latest commit but preserve analysis time
                    merged_info = BranchInfo(
                        name=branch_info.name,
                        commit_sha=branch_info.commit_sha if branch_info.last_commit_date > existing_branch.last_commit_date else existing_branch.commit_sha,
                        is_default=branch_info.is_default,
                        last_commit_date=max(branch_info.last_commit_date, existing_branch.last_commit_date),
                        last_analyzed=existing_branch.last_analyzed or branch_info.last_analyzed
                    )
                    self.persistence.store_branches(repo_id, [merged_info])
                    return True
                
                else:  # MANUAL
                    # Record conflict for manual resolution
                    conflict = SyncConflict(
                        entity_type="branch",
                        entity_id=f"{repo_id}:{branch_info.name}",
                        local_data=existing_branch,
                        remote_data=branch_info,
                        conflict_reason="Commit SHA mismatch"
                    )
                    self._conflicts.append(conflict)
                    return False
            
            # No conflict - update
            self.persistence.store_branches(repo_id, [branch_info])
            return True
    
    def sync_analysis_result(self, analysis_result: BranchAnalysisResult) -> bool:
        """
        Synchronize analysis result with conflict resolution.
        
        Args:
            analysis_result: Analysis result to sync
            
        Returns:
            True if synced successfully, False if conflict requires manual resolution
        """
        with self._lock:
            # Get existing analysis
            existing_analysis = self.persistence.get_latest_analysis(
                analysis_result.repo_id,
                analysis_result.branch_name,
                analysis_result.commit_sha
            )
            
            if not existing_analysis:
                # No conflict - new analysis
                self.persistence.store_analysis(analysis_result)
                return True
            
            # Check for conflicts
            if existing_analysis.analysis_timestamp != analysis_result.analysis_timestamp:
                if self.strategy == ConflictResolutionStrategy.LATEST_WINS:
                    # Compare timestamps
                    if analysis_result.analysis_timestamp > existing_analysis.analysis_timestamp:
                        # Incoming data is newer
                        self.persistence.store_analysis(analysis_result)
                        return True
                    else:
                        # Existing data is newer or same - keep it
                        return True
                
                elif self.strategy == ConflictResolutionStrategy.MERGE:
                    # For analysis results, we typically don't merge - just take the latest
                    if analysis_result.analysis_timestamp > existing_analysis.analysis_timestamp:
                        self.persistence.store_analysis(analysis_result)
                    return True
                
                else:  # MANUAL
                    # Record conflict for manual resolution
                    conflict = SyncConflict(
                        entity_type="analysis",
                        entity_id=f"{analysis_result.repo_id}:{analysis_result.branch_name}:{analysis_result.commit_sha}",
                        local_data=existing_analysis,
                        remote_data=analysis_result,
                        conflict_reason="Analysis timestamp mismatch"
                    )
                    self._conflicts.append(conflict)
                    return False
            
            # No conflict or same timestamp - update
            self.persistence.store_analysis(analysis_result)
            return True
    
    def sync_multiple_branches(self, repo_id: str, branches: List[BranchInfo]) -> Dict[str, Any]:
        """
        Synchronize multiple branches at once.
        
        Args:
            repo_id: Repository identifier
            branches: List of branch information
            
        Returns:
            Dictionary with sync results
        """
        with self._lock:
            results = {
                "total": len(branches),
                "synced": 0,
                "conflicts": 0,
                "failed": []
            }
            
            for branch_info in branches:
                try:
                    if self.sync_branch_metadata(repo_id, branch_info):
                        results["synced"] += 1
                    else:
                        results["conflicts"] += 1
                except Exception as e:
                    results["failed"].append({
                        "branch": branch_info.name,
                        "error": str(e)
                    })
            
            return results
    
    def get_conflicts(self) -> List[SyncConflict]:
        """
        Get list of unresolved conflicts.
        
        Returns:
            List of SyncConflict objects
        """
        with self._lock:
            return self._conflicts.copy()
    
    def resolve_conflict(self, conflict_index: int, use_local: bool = False) -> bool:
        """
        Manually resolve a conflict.
        
        Args:
            conflict_index: Index of conflict in conflicts list
            use_local: If True, keep local data; if False, use remote data
            
        Returns:
            True if resolved successfully
        """
        with self._lock:
            if conflict_index < 0 or conflict_index >= len(self._conflicts):
                return False
            
            conflict = self._conflicts[conflict_index]
            
            try:
                if conflict.entity_type == "branch":
                    data_to_use = conflict.local_data if use_local else conflict.remote_data
                    # Extract repo_id from entity_id
                    repo_id = conflict.entity_id.split(':')[0]
                    
                    # Convert to BranchInfo if needed
                    if not isinstance(data_to_use, BranchInfo):
                        branch_info = BranchInfo(
                            name=data_to_use.name,
                            commit_sha=data_to_use.commit_sha,
                            is_default=data_to_use.is_default,
                            last_commit_date=data_to_use.last_commit_date,
                            last_analyzed=data_to_use.last_analyzed
                        )
                    else:
                        branch_info = data_to_use
                    
                    self.persistence.store_branches(repo_id, [branch_info])
                
                elif conflict.entity_type == "analysis":
                    data_to_use = conflict.local_data if use_local else conflict.remote_data
                    self.persistence.store_analysis(data_to_use)
                
                # Remove resolved conflict
                self._conflicts.pop(conflict_index)
                return True
                
            except Exception as e:
                print(f"Error resolving conflict: {e}")
                return False
    
    def clear_conflicts(self):
        """Clear all recorded conflicts."""
        with self._lock:
            self._conflicts.clear()
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """
        Get synchronization statistics.
        
        Returns:
            Dictionary with sync statistics
        """
        with self._lock:
            return {
                "strategy": self.strategy.value,
                "pending_conflicts": len(self._conflicts),
                "conflicts": [conflict.to_dict() for conflict in self._conflicts]
            }


class DataRefreshManager:
    """Manages data refresh and staleness detection."""
    
    def __init__(self, persistence_service: DataPersistenceService,
                 stale_threshold_hours: int = 24):
        """
        Initialize data refresh manager.
        
        Args:
            persistence_service: Data persistence service
            stale_threshold_hours: Hours after which data is considered stale
        """
        self.persistence = persistence_service
        self.stale_threshold_hours = stale_threshold_hours
    
    def is_branch_stale(self, repo_id: str, branch_name: str) -> bool:
        """
        Check if branch data is stale.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            
        Returns:
            True if stale, False otherwise
        """
        branch = self.persistence.get_branch(repo_id, branch_name)
        if not branch:
            return True  # No data means stale
        
        if not branch.last_analyzed:
            return True  # Never analyzed means stale
        
        # Check if last analysis is older than threshold
        age = datetime.now() - branch.last_analyzed
        return age.total_seconds() > (self.stale_threshold_hours * 3600)
    
    def is_analysis_stale(self, repo_id: str, branch_name: str, commit_sha: str) -> bool:
        """
        Check if analysis data is stale.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            commit_sha: Commit SHA
            
        Returns:
            True if stale, False otherwise
        """
        analysis = self.persistence.get_latest_analysis(repo_id, branch_name, commit_sha)
        if not analysis:
            return True  # No data means stale
        
        # Check if analysis is older than threshold
        age = datetime.now() - analysis.analysis_timestamp
        return age.total_seconds() > (self.stale_threshold_hours * 3600)
    
    def get_stale_branches(self, repo_id: str) -> List[str]:
        """
        Get list of stale branches for a repository.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            List of branch names that are stale
        """
        branches = self.persistence.get_branches(repo_id)
        stale_branches = []
        
        for branch in branches:
            if self.is_branch_stale(repo_id, branch.name):
                stale_branches.append(branch.name)
        
        return stale_branches
    
    def mark_for_refresh(self, repo_id: str, branch_name: str) -> bool:
        """
        Mark a branch for refresh by clearing its last_analyzed timestamp.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            
        Returns:
            True if marked successfully
        """
        # This is a placeholder - in a real system, you might have a separate
        # refresh queue or flag. For now, we just return True to indicate
        # the branch should be refreshed
        return True
    
    def get_staleness_info(self, repo_id: str, branch_name: str) -> Dict[str, Any]:
        """
        Get detailed staleness information for a branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            
        Returns:
            Dictionary with staleness information
        """
        branch = self.persistence.get_branch(repo_id, branch_name)
        
        if not branch:
            return {
                "exists": False,
                "is_stale": True,
                "reason": "Branch not found in database"
            }
        
        if not branch.last_analyzed:
            return {
                "exists": True,
                "is_stale": True,
                "reason": "Branch has never been analyzed",
                "last_analyzed": None
            }
        
        age = datetime.now() - branch.last_analyzed
        age_hours = age.total_seconds() / 3600
        is_stale = age_hours > self.stale_threshold_hours
        
        return {
            "exists": True,
            "is_stale": is_stale,
            "last_analyzed": branch.last_analyzed.isoformat(),
            "age_hours": round(age_hours, 2),
            "threshold_hours": self.stale_threshold_hours,
            "reason": f"Data is {round(age_hours, 1)} hours old" if is_stale else "Data is fresh"
        }
