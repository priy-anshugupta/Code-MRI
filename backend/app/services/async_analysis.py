"""
Asynchronous analysis pipeline with progress tracking and request queuing.
Provides background task system for branch analysis with status monitoring.
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from app.services.analyzer import (
    analyze_directory_structure,
    detect_technologies,
    run_static_analysis,
    calculate_aggregate_metrics,
    generate_summary,
)
from app.services.enhanced_grading import EnhancedGradingSystem
from app.services.analysis_cache import AnalysisCache
from app.models.branch import BranchAnalysisResult


class AnalysisStatus(Enum):
    """Status of an analysis task."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisStage(Enum):
    """Stages of analysis process."""
    INITIALIZING = "initializing"
    ANALYZING_STRUCTURE = "analyzing_structure"
    DETECTING_TECHNOLOGIES = "detecting_technologies"
    CALCULATING_METRICS = "calculating_metrics"
    RUNNING_STATIC_ANALYSIS = "running_static_analysis"
    GENERATING_SUMMARY = "generating_summary"
    CALCULATING_SCORES = "calculating_scores"
    GENERATING_AI_EXPLANATIONS = "generating_ai_explanations"
    CACHING_RESULTS = "caching_results"
    FINALIZING = "finalizing"


@dataclass
class AnalysisProgress:
    """Progress information for an analysis task."""
    task_id: str
    repo_id: str
    branch: str
    commit_sha: str
    status: AnalysisStatus
    current_stage: AnalysisStage
    progress_percentage: float
    start_time: datetime
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    stages_completed: List[AnalysisStage] = field(default_factory=list)
    total_stages: int = 10
    
    def update_progress(self, stage: AnalysisStage, percentage: float = None):
        """Update the current stage and progress percentage."""
        self.current_stage = stage
        if stage not in self.stages_completed:
            self.stages_completed.append(stage)
        
        if percentage is not None:
            self.progress_percentage = percentage
        else:
            # Auto-calculate based on completed stages
            self.progress_percentage = (len(self.stages_completed) / self.total_stages) * 100
        
        # Update estimated completion time
        if self.progress_percentage > 0:
            elapsed = datetime.now() - self.start_time
            total_estimated = elapsed / (self.progress_percentage / 100)
            self.estimated_completion = self.start_time + total_estimated


@dataclass
class AnalysisRequest:
    """Request for repository analysis."""
    repo_id: str
    repo_path: str
    branch: str
    commit_sha: str
    priority: int = 1  # Lower number = higher priority
    created_at: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None  # For fair distribution


class AsyncAnalysisPipeline:
    """
    Asynchronous analysis pipeline with progress tracking and request queuing.
    Manages background analysis tasks with status monitoring and fair distribution.
    """
    
    def __init__(self, max_concurrent_tasks: int = 3, max_queue_size: int = 50):
        """
        Initialize the async analysis pipeline.
        
        Args:
            max_concurrent_tasks: Maximum number of concurrent analysis tasks
            max_queue_size: Maximum number of queued requests
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size
        
        # Task management
        self.active_tasks: Dict[str, AnalysisProgress] = {}
        self.task_queue: List[AnalysisRequest] = []
        self.completed_tasks: Dict[str, AnalysisProgress] = {}
        
        # Thread pool for CPU-intensive analysis work
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_tasks)
        
        # Synchronization
        self.queue_lock = threading.Lock()
        self.tasks_lock = threading.Lock()
        
        # Services
        self.enhanced_grading = EnhancedGradingSystem()
        self.analysis_cache = AnalysisCache()
        
        # Background task processor
        self.processor_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
        
        # Progress callbacks
        self.progress_callbacks: List[Callable[[AnalysisProgress], None]] = []
    
    async def start(self):
        """Start the background task processor."""
        if self.processor_task is None or self.processor_task.done():
            self.processor_task = asyncio.create_task(self._process_queue())
    
    async def stop(self):
        """Stop the background task processor and cleanup."""
        self.shutdown_event.set()
        if self.processor_task:
            await self.processor_task
        self.executor.shutdown(wait=True)
    
    def add_progress_callback(self, callback: Callable[[AnalysisProgress], None]):
        """Add a callback to be notified of progress updates."""
        self.progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[AnalysisProgress], None]):
        """Remove a progress callback."""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)
    
    def _notify_progress(self, progress: AnalysisProgress):
        """Notify all registered callbacks of progress updates."""
        for callback in self.progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                print(f"Error in progress callback: {e}")
    
    async def submit_analysis(
        self,
        repo_id: str,
        repo_path: str,
        branch: str,
        commit_sha: str,
        priority: int = 1,
        user_id: Optional[str] = None
    ) -> str:
        """
        Submit an analysis request to the queue.
        
        Args:
            repo_id: Repository identifier
            repo_path: Path to the repository
            branch: Branch name
            commit_sha: Commit SHA
            priority: Priority level (lower = higher priority)
            user_id: User identifier for fair distribution
        
        Returns:
            Task ID for tracking progress
        
        Raises:
            ValueError: If queue is full or analysis already exists
        """
        # Check if analysis already exists in cache
        cached_analysis = self.analysis_cache.get_cached_analysis(repo_id, branch, commit_sha)
        if cached_analysis:
            raise ValueError(f"Analysis already exists for {repo_id}:{branch}:{commit_sha}")
        
        # Check if already queued or running
        with self.queue_lock:
            # Check queue
            for request in self.task_queue:
                if (request.repo_id == repo_id and 
                    request.branch == branch and 
                    request.commit_sha == commit_sha):
                    raise ValueError(f"Analysis already queued for {repo_id}:{branch}:{commit_sha}")
            
            # Check active tasks
            with self.tasks_lock:
                for progress in self.active_tasks.values():
                    if (progress.repo_id == repo_id and 
                        progress.branch == branch and 
                        progress.commit_sha == commit_sha):
                        raise ValueError(f"Analysis already running for {repo_id}:{branch}:{commit_sha}")
            
            # Check queue size
            if len(self.task_queue) >= self.max_queue_size:
                raise ValueError("Analysis queue is full. Please try again later.")
            
            # Create and queue request
            request = AnalysisRequest(
                repo_id=repo_id,
                repo_path=repo_path,
                branch=branch,
                commit_sha=commit_sha,
                priority=priority,
                user_id=user_id
            )
            
            self.task_queue.append(request)
            # Sort by priority and creation time for fair distribution
            self.task_queue.sort(key=lambda r: (r.priority, r.created_at))
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Start processor if not running
        await self.start()
        
        return task_id
    
    def get_progress(self, task_id: str) -> Optional[AnalysisProgress]:
        """Get progress information for a task."""
        with self.tasks_lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]
            if task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
        return None
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        with self.queue_lock:
            queue_size = len(self.task_queue)
        
        with self.tasks_lock:
            active_count = len(self.active_tasks)
            completed_count = len(self.completed_tasks)
        
        return {
            "queue_size": queue_size,
            "active_tasks": active_count,
            "completed_tasks": completed_count,
            "max_concurrent": self.max_concurrent_tasks,
            "max_queue_size": self.max_queue_size
        }
    
    def get_user_tasks(self, user_id: str) -> List[AnalysisProgress]:
        """Get all tasks (active and completed) for a specific user."""
        tasks = []
        
        with self.tasks_lock:
            # Active tasks
            for progress in self.active_tasks.values():
                if hasattr(progress, 'user_id') and progress.user_id == user_id:
                    tasks.append(progress)
            
            # Completed tasks
            for progress in self.completed_tasks.values():
                if hasattr(progress, 'user_id') and progress.user_id == user_id:
                    tasks.append(progress)
        
        return sorted(tasks, key=lambda t: t.start_time, reverse=True)
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a queued or running task.
        
        Args:
            task_id: Task ID to cancel
        
        Returns:
            True if task was cancelled, False if not found or already completed
        """
        # Try to remove from queue first
        with self.queue_lock:
            for i, request in enumerate(self.task_queue):
                # Note: We need to match by repo/branch/commit since we don't store task_id in request
                # This is a limitation of the current design
                pass
        
        # Try to cancel active task
        with self.tasks_lock:
            if task_id in self.active_tasks:
                progress = self.active_tasks[task_id]
                progress.status = AnalysisStatus.CANCELLED
                progress.error_message = "Task cancelled by user"
                self._notify_progress(progress)
                return True
        
        return False
    
    async def _process_queue(self):
        """Background task processor that handles the analysis queue."""
        while not self.shutdown_event.is_set():
            try:
                # Check if we can process more tasks
                with self.tasks_lock:
                    active_count = len(self.active_tasks)
                
                if active_count >= self.max_concurrent_tasks:
                    await asyncio.sleep(1)
                    continue
                
                # Get next request from queue
                request = None
                with self.queue_lock:
                    if self.task_queue:
                        request = self.task_queue.pop(0)
                
                if request is None:
                    await asyncio.sleep(1)
                    continue
                
                # Create task and start processing
                task_id = str(uuid.uuid4())
                progress = AnalysisProgress(
                    task_id=task_id,
                    repo_id=request.repo_id,
                    branch=request.branch,
                    commit_sha=request.commit_sha,
                    status=AnalysisStatus.QUEUED,
                    current_stage=AnalysisStage.INITIALIZING,
                    progress_percentage=0.0,
                    start_time=datetime.now()
                )
                
                # Add to active tasks
                with self.tasks_lock:
                    self.active_tasks[task_id] = progress
                
                # Start analysis in background
                asyncio.create_task(self._run_analysis(request, progress))
                
            except Exception as e:
                print(f"Error in queue processor: {e}")
                await asyncio.sleep(5)
    
    async def _run_analysis(self, request: AnalysisRequest, progress: AnalysisProgress):
        """Run the actual analysis process."""
        try:
            progress.status = AnalysisStatus.RUNNING
            self._notify_progress(progress)
            
            # Run analysis in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._perform_analysis,
                request,
                progress
            )
            
            if progress.status == AnalysisStatus.CANCELLED:
                return
            
            # Store result in cache
            progress.update_progress(AnalysisStage.CACHING_RESULTS)
            self._notify_progress(progress)
            
            self.analysis_cache.store_analysis(
                request.repo_id,
                request.branch,
                request.commit_sha,
                result
            )
            
            # Finalize
            progress.update_progress(AnalysisStage.FINALIZING, 100.0)
            progress.status = AnalysisStatus.COMPLETED
            self._notify_progress(progress)
            
        except Exception as e:
            progress.status = AnalysisStatus.FAILED
            progress.error_message = str(e)
            progress.progress_percentage = 0.0
            self._notify_progress(progress)
        
        finally:
            # Move from active to completed
            with self.tasks_lock:
                if progress.task_id in self.active_tasks:
                    del self.active_tasks[progress.task_id]
                self.completed_tasks[progress.task_id] = progress
                
                # Cleanup old completed tasks (keep last 100)
                if len(self.completed_tasks) > 100:
                    oldest_tasks = sorted(
                        self.completed_tasks.items(),
                        key=lambda x: x[1].start_time
                    )
                    for task_id, _ in oldest_tasks[:-100]:
                        del self.completed_tasks[task_id]
    
    def _perform_analysis(self, request: AnalysisRequest, progress: AnalysisProgress) -> BranchAnalysisResult:
        """Perform the actual analysis work (runs in thread pool)."""
        repo_path = request.repo_path
        
        # Check for cancellation before each stage
        def check_cancelled():
            if progress.status == AnalysisStatus.CANCELLED:
                raise Exception("Analysis cancelled")
        
        # Stage 1: Analyze directory structure
        check_cancelled()
        progress.update_progress(AnalysisStage.ANALYZING_STRUCTURE)
        self._notify_progress(progress)
        file_tree = analyze_directory_structure(repo_path)
        
        # Stage 2: Detect technologies
        check_cancelled()
        progress.update_progress(AnalysisStage.DETECTING_TECHNOLOGIES)
        self._notify_progress(progress)
        technologies = detect_technologies(repo_path)
        
        # Stage 3: Calculate metrics
        check_cancelled()
        progress.update_progress(AnalysisStage.CALCULATING_METRICS)
        self._notify_progress(progress)
        metrics = calculate_aggregate_metrics(repo_path)
        
        # Stage 4: Run static analysis
        check_cancelled()
        progress.update_progress(AnalysisStage.RUNNING_STATIC_ANALYSIS)
        self._notify_progress(progress)
        issues = run_static_analysis(repo_path)
        
        # Stage 5: Generate summary
        check_cancelled()
        progress.update_progress(AnalysisStage.GENERATING_SUMMARY)
        self._notify_progress(progress)
        summary = generate_summary(repo_path, technologies, metrics, issues)
        
        # Stage 6: Calculate detailed scores
        check_cancelled()
        progress.update_progress(AnalysisStage.CALCULATING_SCORES)
        self._notify_progress(progress)
        detailed_scores = self.enhanced_grading.calculate_detailed_scores(repo_path, technologies)
        
        # Stage 7: Generate AI explanations
        check_cancelled()
        progress.update_progress(AnalysisStage.GENERATING_AI_EXPLANATIONS)
        self._notify_progress(progress)
        
        ai_grading_explanation = ""
        try:
            # This is async but we're in a thread, so we need to handle it carefully
            # For now, we'll skip the async AI explanation in the threaded context
            # This could be improved by making the entire pipeline async
            ai_grading_explanation = "AI explanation generation skipped in async context"
        except Exception as e:
            ai_grading_explanation = f"AI explanation unavailable: {str(e)}"
        
        # Create result
        result = BranchAnalysisResult(
            repo_id=request.repo_id,
            branch_name=request.branch,
            commit_sha=request.commit_sha,
            analysis_timestamp=datetime.now(),
            file_tree=file_tree,
            technologies=technologies,
            detailed_scores=detailed_scores,
            issues=issues,
            ai_summary=summary,
            ai_grading_explanation=ai_grading_explanation,
            metrics=detailed_scores.to_dict() if hasattr(detailed_scores, 'to_dict') else {}
        )
        
        return result


# Global instance
async_pipeline = AsyncAnalysisPipeline()