"""
Branch-aware analysis cache system for repository intelligence enhancement.
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from app.models.branch import BranchAnalysisResult
from app.core.config import settings


class AnalysisCache:
    """Branch-aware caching system with composite keys."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the analysis cache.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to temp_clones/cache
        """
        self.cache_dir = cache_dir or os.path.join(settings.TEMP_DIR, "cache")
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _generate_cache_key(self, repo_id: str, branch: str, commit_sha: str) -> str:
        """
        Generate a composite cache key for repository, branch, and commit.
        
        Args:
            repo_id: Repository identifier
            branch: Branch name
            commit_sha: Commit SHA
            
        Returns:
            Composite cache key string
        """
        # Create composite key: repo_id:branch:commit_sha
        composite_key = f"{repo_id}:{branch}:{commit_sha}"
        
        # Hash the key to ensure filesystem compatibility and consistent length
        key_hash = hashlib.sha256(composite_key.encode()).hexdigest()
        
        return f"{repo_id}_{branch}_{key_hash[:16]}"
    
    def _get_cache_file_path(self, cache_key: str) -> str:
        """Get the full path to a cache file."""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get_cached_analysis(self, repo_id: str, branch: str, commit_sha: str) -> Optional[BranchAnalysisResult]:
        """
        Retrieve cached analysis results for a specific repository, branch, and commit.
        
        Args:
            repo_id: Repository identifier
            branch: Branch name
            commit_sha: Commit SHA
            
        Returns:
            BranchAnalysisResult if cached data exists, None otherwise
        """
        cache_key = self._generate_cache_key(repo_id, branch, commit_sha)
        cache_file = self._get_cache_file_path(cache_key)
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate that the cached data matches the request
            if (data.get("repo_id") != repo_id or 
                data.get("branch_name") != branch or 
                data.get("commit_sha") != commit_sha):
                # Cache key collision or corrupted data, remove it
                os.remove(cache_file)
                return None
            
            return BranchAnalysisResult.from_dict(data)
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Corrupted cache file, remove it
            try:
                os.remove(cache_file)
            except OSError:
                pass
            return None
    
    def store_analysis(self, repo_id: str, branch: str, commit_sha: str, result: BranchAnalysisResult) -> None:
        """
        Store analysis results in the cache.
        
        Args:
            repo_id: Repository identifier
            branch: Branch name
            commit_sha: Commit SHA
            result: Analysis result to cache
        """
        cache_key = self._generate_cache_key(repo_id, branch, commit_sha)
        cache_file = self._get_cache_file_path(cache_key)
        
        try:
            # Ensure the result has the correct metadata
            result.repo_id = repo_id
            result.branch_name = branch
            result.commit_sha = commit_sha
            result.analysis_timestamp = datetime.now()
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
                
        except (OSError, TypeError) as e:
            # Log error but don't fail the analysis
            print(f"Warning: Failed to cache analysis for {repo_id}:{branch}:{commit_sha[:8]}: {e}")
    
    def invalidate_branch_cache(self, repo_id: str, branch: str) -> None:
        """
        Invalidate all cached entries for a specific repository and branch.
        
        Args:
            repo_id: Repository identifier
            branch: Branch name
        """
        if not os.path.exists(self.cache_dir):
            return
        
        # Find all cache files that match the repo_id and branch pattern
        pattern_prefix = f"{repo_id}_{branch}_"
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.startswith(pattern_prefix) and filename.endswith('.json'):
                    cache_file = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(cache_file)
                    except OSError:
                        pass  # File might have been removed by another process
        except OSError:
            pass  # Directory might not exist or be accessible
    
    def cleanup_stale_entries(self, max_age: timedelta = timedelta(hours=24)) -> int:
        """
        Remove cache entries older than the specified age.
        
        Args:
            max_age: Maximum age for cache entries
            
        Returns:
            Number of entries removed
        """
        if not os.path.exists(self.cache_dir):
            return 0
        
        removed_count = 0
        cutoff_time = datetime.now() - max_age
        
        try:
            for filename in os.listdir(self.cache_dir):
                if not filename.endswith('.json'):
                    continue
                
                cache_file = os.path.join(self.cache_dir, filename)
                
                try:
                    # Check file modification time
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                    
                    if file_mtime < cutoff_time:
                        os.remove(cache_file)
                        removed_count += 1
                        
                except OSError:
                    # File might have been removed by another process
                    pass
                    
        except OSError:
            pass  # Directory might not exist or be accessible
        
        return removed_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        if not os.path.exists(self.cache_dir):
            return {
                "total_entries": 0,
                "total_size_bytes": 0,
                "cache_dir": self.cache_dir,
                "cache_exists": False
            }
        
        total_entries = 0
        total_size = 0
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    cache_file = os.path.join(self.cache_dir, filename)
                    try:
                        total_entries += 1
                        total_size += os.path.getsize(cache_file)
                    except OSError:
                        pass
        except OSError:
            pass
        
        return {
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "cache_dir": self.cache_dir,
            "cache_exists": True
        }
    
    def clear_all_cache(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries removed
        """
        if not os.path.exists(self.cache_dir):
            return 0
        
        removed_count = 0
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    cache_file = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(cache_file)
                        removed_count += 1
                    except OSError:
                        pass
        except OSError:
            pass
        
        return removed_count
    
    def get_cached_branches(self, repo_id: str) -> List[str]:
        """
        Get list of branches that have cached analysis data.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            List of branch names with cached data
        """
        if not os.path.exists(self.cache_dir):
            return []
        
        branches = set()
        pattern_prefix = f"{repo_id}_"
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.startswith(pattern_prefix) and filename.endswith('.json'):
                    # Extract branch name from filename pattern: repo_id_branch_hash.json
                    parts = filename[len(pattern_prefix):].split('_')
                    if len(parts) >= 2:
                        # Branch name is everything except the last part (hash) and .json
                        branch_name = '_'.join(parts[:-1])
                        branches.add(branch_name)
        except OSError:
            pass
        
        return sorted(list(branches))