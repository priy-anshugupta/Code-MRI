"""
Automatic refresh service for stale data.
"""
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional, Set
import time

from app.services.data_persistence import DataPersistenceService
from app.services.data_sync import DataRefreshManager


class AutoRefreshService:
    """Service for automatically refreshing stale data."""
    
    def __init__(self, persistence_service: DataPersistenceService,
                 refresh_manager: DataRefreshManager,
                 check_interval_minutes: int = 30,
                 auto_refresh_enabled: bool = False):
        """
        Initialize auto-refresh service.
        
        Args:
            persistence_service: Data persistence service
            refresh_manager: Data refresh manager
            check_interval_minutes: How often to check for stale data
            auto_refresh_enabled: Whether to automatically trigger refresh
        """
        self.persistence = persistence_service
        self.refresh_manager = refresh_manager
        self.check_interval_minutes = check_interval_minutes
        self.auto_refresh_enabled = auto_refresh_enabled
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._refreshing_branches: Set[str] = set()
        self._lock = threading.Lock()
    
    def start(self):
        """Start the auto-refresh service."""
        if self._thread and self._thread.is_alive():
            return  # Already running
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._thread.start()
        print(f"Auto-refresh service started (check interval: {self.check_interval_minutes} minutes)")
    
    def stop(self):
        """Stop the auto-refresh service."""
        if not self._thread or not self._thread.is_alive():
            return
        
        self._stop_event.set()
        self._thread.join(timeout=5)
        print("Auto-refresh service stopped")
    
    def _refresh_loop(self):
        """Background loop that checks for stale data."""
        while not self._stop_event.wait(self.check_interval_minutes * 60):
            try:
                self._check_and_refresh_stale_data()
            except Exception as e:
                print(f"Error in auto-refresh loop: {e}")
    
    def _check_and_refresh_stale_data(self):
        """Check for stale data and optionally trigger refresh."""
        # Get all repositories
        session = self.persistence._get_session()
        try:
            from app.models.database import Repository
            repos = session.query(Repository).all()
            
            for repo in repos:
                # Get stale branches for this repository
                stale_branches = self.refresh_manager.get_stale_branches(repo.id)
                
                if stale_branches:
                    print(f"Found {len(stale_branches)} stale branches for repo {repo.id}")
                    
                    if self.auto_refresh_enabled:
                        # Trigger refresh for stale branches
                        for branch_name in stale_branches:
                            branch_key = f"{repo.id}:{branch_name}"
                            
                            with self._lock:
                                if branch_key in self._refreshing_branches:
                                    continue  # Already refreshing
                                
                                self._refreshing_branches.add(branch_key)
                            
                            try:
                                # Mark for refresh
                                self.refresh_manager.mark_for_refresh(repo.id, branch_name)
                                print(f"Marked {branch_name} for refresh in repo {repo.id}")
                                
                                # Note: Actual analysis would need to be triggered by the
                                # async analysis pipeline. This just marks it as needing refresh.
                                
                            except Exception as e:
                                print(f"Error refreshing {branch_name} in repo {repo.id}: {e}")
                            finally:
                                with self._lock:
                                    self._refreshing_branches.discard(branch_key)
                    else:
                        # Just log the stale branches
                        print(f"Stale branches in repo {repo.id}: {', '.join(stale_branches)}")
        finally:
            session.close()
    
    def enable_auto_refresh(self):
        """Enable automatic refresh of stale data."""
        self.auto_refresh_enabled = True
        print("Auto-refresh enabled")
    
    def disable_auto_refresh(self):
        """Disable automatic refresh of stale data."""
        self.auto_refresh_enabled = False
        print("Auto-refresh disabled")
    
    def get_status(self) -> dict:
        """Get auto-refresh service status."""
        with self._lock:
            return {
                "running": self._thread and self._thread.is_alive(),
                "auto_refresh_enabled": self.auto_refresh_enabled,
                "check_interval_minutes": self.check_interval_minutes,
                "currently_refreshing": len(self._refreshing_branches),
                "refreshing_branches": list(self._refreshing_branches)
            }


class DataRefreshScheduler:
    """Scheduler for periodic data refresh tasks."""
    
    def __init__(self, persistence_service: DataPersistenceService):
        """
        Initialize refresh scheduler.
        
        Args:
            persistence_service: Data persistence service
        """
        self.persistence = persistence_service
        self._scheduled_tasks: dict = {}
        self._lock = threading.Lock()
    
    def schedule_refresh(self, repo_id: str, branch_name: str, 
                        delay_minutes: int = 60) -> str:
        """
        Schedule a refresh for a specific branch.
        
        Args:
            repo_id: Repository identifier
            branch_name: Branch name
            delay_minutes: Delay before refresh in minutes
            
        Returns:
            Task ID
        """
        task_id = f"{repo_id}:{branch_name}:{int(time.time())}"
        scheduled_time = datetime.now() + timedelta(minutes=delay_minutes)
        
        with self._lock:
            self._scheduled_tasks[task_id] = {
                "repo_id": repo_id,
                "branch_name": branch_name,
                "scheduled_time": scheduled_time,
                "status": "scheduled"
            }
        
        # Start a thread to execute the refresh
        thread = threading.Thread(
            target=self._execute_scheduled_refresh,
            args=(task_id, delay_minutes * 60),
            daemon=True
        )
        thread.start()
        
        return task_id
    
    def _execute_scheduled_refresh(self, task_id: str, delay_seconds: int):
        """Execute a scheduled refresh after delay."""
        time.sleep(delay_seconds)
        
        with self._lock:
            if task_id not in self._scheduled_tasks:
                return  # Task was cancelled
            
            task = self._scheduled_tasks[task_id]
            task["status"] = "executing"
        
        try:
            # Mark for refresh
            repo_id = task["repo_id"]
            branch_name = task["branch_name"]
            
            # Update branch to trigger refresh
            self.persistence.update_branch_analysis_time(
                repo_id, 
                branch_name, 
                datetime.now() - timedelta(days=2)  # Set to old time to trigger refresh
            )
            
            with self._lock:
                task["status"] = "completed"
                task["completed_time"] = datetime.now()
            
            print(f"Scheduled refresh completed for {repo_id}:{branch_name}")
            
        except Exception as e:
            print(f"Error executing scheduled refresh: {e}")
            with self._lock:
                task["status"] = "failed"
                task["error"] = str(e)
    
    def cancel_refresh(self, task_id: str) -> bool:
        """
        Cancel a scheduled refresh.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if cancelled, False if not found
        """
        with self._lock:
            if task_id in self._scheduled_tasks:
                del self._scheduled_tasks[task_id]
                return True
            return False
    
    def get_scheduled_tasks(self) -> dict:
        """Get all scheduled tasks."""
        with self._lock:
            return {
                task_id: {
                    "repo_id": task["repo_id"],
                    "branch_name": task["branch_name"],
                    "scheduled_time": task["scheduled_time"].isoformat(),
                    "status": task["status"]
                }
                for task_id, task in self._scheduled_tasks.items()
            }
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """
        Remove completed tasks older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            tasks_to_remove = []
            for task_id, task in self._scheduled_tasks.items():
                if task["status"] in ["completed", "failed"]:
                    completed_time = task.get("completed_time")
                    if completed_time and completed_time < cutoff_time:
                        tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self._scheduled_tasks[task_id]
            
            return len(tasks_to_remove)
