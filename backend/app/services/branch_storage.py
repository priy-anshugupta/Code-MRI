"""
Branch metadata storage system using JSON files.
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from app.models.branch import BranchInfo, BranchContext
from app.core.config import settings


class BranchStorage:
    """JSON-based storage for branch metadata."""
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize branch storage.
        
        Args:
            storage_dir: Directory to store branch metadata files
        """
        self.storage_dir = storage_dir or os.path.join(settings.TEMP_DIR, "branch_metadata")
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def _get_repo_metadata_file(self, repo_id: str) -> str:
        """Get the path to a repository's metadata file."""
        return os.path.join(self.storage_dir, f"{repo_id}_branches.json")
    
    def store_branches(self, repo_id: str, branches: List[BranchInfo]) -> None:
        """
        Store branch information for a repository.
        
        Args:
            repo_id: Repository identifier
            branches: List of branch information to store
        """
        metadata_file = self._get_repo_metadata_file(repo_id)
        
        try:
            data = {
                "repo_id": repo_id,
                "last_updated": datetime.now().isoformat(),
                "branches": [branch.to_dict() for branch in branches]
            }
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except (OSError, json.JSONEncodeError) as e:
            print(f"Warning: Failed to store branch metadata for {repo_id}: {e}")
    
    def get_branches(self, repo_id: str) -> Optional[List[BranchInfo]]:
        """
        Retrieve stored branch information for a repository.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            List of BranchInfo objects, or None if not found
        """
        metadata_file = self._get_repo_metadata_file(repo_id)
        
        if not os.path.exists(metadata_file):
            return None
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get("repo_id") != repo_id:
                return None
            
            branches = []
            for branch_data in data.get("branches", []):
                branches.append(BranchInfo.from_dict(branch_data))
            
            return branches
            
        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted metadata file
            try:
                os.remove(metadata_file)
            except OSError:
                pass
            return None
    
    def update_branch_analysis_time(self, repo_id: str, branch_name: str, analysis_time: datetime) -> None:
        """
        Update the last analyzed time for a specific branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            analysis_time: Time when analysis was completed
        """
        branches = self.get_branches(repo_id)
        if not branches:
            return
        
        # Update the specific branch
        for branch in branches:
            if branch.name == branch_name:
                branch.last_analyzed = analysis_time
                break
        
        # Store the updated branches
        self.store_branches(repo_id, branches)
    
    def get_branch_info(self, repo_id: str, branch_name: str) -> Optional[BranchInfo]:
        """
        Get information for a specific branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            
        Returns:
            BranchInfo object or None if not found
        """
        branches = self.get_branches(repo_id)
        if not branches:
            return None
        
        for branch in branches:
            if branch.name == branch_name:
                return branch
        
        return None
    
    def store_branch_context(self, context: BranchContext) -> None:
        """
        Store branch context information.
        
        Args:
            context: BranchContext to store
        """
        context_file = os.path.join(self.storage_dir, f"{context.repo_id}_context.json")
        
        try:
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(context.to_dict(), f, indent=2, ensure_ascii=False)
        except (OSError, json.JSONEncodeError) as e:
            print(f"Warning: Failed to store branch context for {context.repo_id}: {e}")
    
    def get_branch_context(self, repo_id: str) -> Optional[BranchContext]:
        """
        Retrieve stored branch context.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            BranchContext object or None if not found
        """
        context_file = os.path.join(self.storage_dir, f"{repo_id}_context.json")
        
        if not os.path.exists(context_file):
            return None
        
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return BranchContext.from_dict(data)
            
        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted context file
            try:
                os.remove(context_file)
            except OSError:
                pass
            return None
    
    def cleanup_repo_metadata(self, repo_id: str) -> None:
        """
        Remove all stored metadata for a repository.
        
        Args:
            repo_id: Repository identifier
        """
        files_to_remove = [
            self._get_repo_metadata_file(repo_id),
            os.path.join(self.storage_dir, f"{repo_id}_context.json")
        ]
        
        for file_path in files_to_remove:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
    
    def get_all_repo_ids(self) -> List[str]:
        """
        Get list of all repository IDs with stored metadata.
        
        Returns:
            List of repository IDs
        """
        if not os.path.exists(self.storage_dir):
            return []
        
        repo_ids = set()
        
        try:
            for filename in os.listdir(self.storage_dir):
                if filename.endswith('_branches.json'):
                    repo_id = filename[:-13]  # Remove '_branches.json'
                    repo_ids.add(repo_id)
        except OSError:
            pass
        
        return sorted(list(repo_ids))
    
    def cleanup_stale_metadata(self, max_age_hours: int = 24) -> int:
        """
        Remove metadata files older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of files removed
        """
        if not os.path.exists(self.storage_dir):
            return 0
        
        removed_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        try:
            for filename in os.listdir(self.storage_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.storage_dir, filename)
                    try:
                        if os.path.getmtime(file_path) < cutoff_time:
                            os.remove(file_path)
                            removed_count += 1
                    except OSError:
                        pass
        except OSError:
            pass
        
        return removed_count