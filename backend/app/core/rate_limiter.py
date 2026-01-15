"""
Enhanced rate limiter for API calls to avoid hitting external API limits.
Implements token bucket algorithm with request queuing, fair distribution, and exponential backoff.
"""
import time
import threading
import asyncio
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random
import uuid


class RequestPriority(Enum):
    """Priority levels for API requests."""
    LOW = 3
    NORMAL = 2
    HIGH = 1


@dataclass
class QueuedRequest:
    """A queued API request with metadata."""
    request_id: str
    user_id: Optional[str]
    priority: RequestPriority
    created_at: datetime
    timeout: Optional[float]
    callback: Optional[Callable] = None
    
    def __post_init__(self):
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())


@dataclass
class UserQuota:
    """Per-user quota tracking."""
    user_id: str
    requests_made: int = 0
    last_request_time: datetime = field(default_factory=datetime.now)
    total_wait_time: float = 0.0
    
    def reset_if_needed(self, window_minutes: int = 60):
        """Reset quota if time window has passed."""
        if datetime.now() - self.last_request_time > timedelta(minutes=window_minutes):
            self.requests_made = 0
            self.total_wait_time = 0.0


class ExponentialBackoff:
    """Exponential backoff handler for API errors."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0, max_retries: int = 5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
    
    def should_retry(self) -> bool:
        """Check if we should retry based on failure count."""
        return self.failure_count < self.max_retries
    
    def get_delay(self) -> float:
        """Get the current delay for exponential backoff."""
        if self.failure_count == 0:
            return 0.0
        
        delay = self.base_delay * (2 ** (self.failure_count - 1))
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.1, 0.3) * delay
        return min(delay + jitter, self.max_delay)
    
    def record_failure(self):
        """Record a failure and increment the count."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
    
    def record_success(self):
        """Record a success and reset the failure count."""
        self.failure_count = 0
        self.last_failure_time = None


class EnhancedRateLimiter:
    """
    Enhanced rate limiter with request queuing, fair distribution, and exponential backoff.
    Enforces 5 requests per minute for Gemini API free tier.
    """
    
    def __init__(self, requests_per_minute: int = 5, burst_size: Optional[int] = None):
        """
        Initialize the enhanced rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute
            burst_size: Maximum burst size (defaults to requests_per_minute)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or requests_per_minute
        self.tokens = float(self.burst_size)
        self.last_update = time.time()
        self.lock = threading.Lock()
        
        # Calculate refill rate (tokens per second)
        self.refill_rate = requests_per_minute / 60.0
        
        # Request queue with priority support
        self.request_queue: List[QueuedRequest] = []
        self.queue_lock = threading.Lock()
        
        # User quota tracking for fair distribution
        self.user_quotas: Dict[str, UserQuota] = {}
        self.quota_lock = threading.Lock()
        
        # Exponential backoff for API errors
        self.backoff = ExponentialBackoff()
        
        # Queue processing
        self.queue_processor_running = False
        self.queue_processor_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "queue_timeouts": 0,
            "average_wait_time": 0.0
        }
        self.stats_lock = threading.Lock()
    
    def start_queue_processor(self):
        """Start the background queue processor."""
        if not self.queue_processor_running:
            self.queue_processor_running = True
            self.shutdown_event.clear()
            self.queue_processor_thread = threading.Thread(
                target=self._process_queue,
                daemon=True
            )
            self.queue_processor_thread.start()
    
    def stop_queue_processor(self):
        """Stop the background queue processor."""
        if self.queue_processor_running:
            self.queue_processor_running = False
            self.shutdown_event.set()
            if self.queue_processor_thread:
                self.queue_processor_thread.join(timeout=5.0)
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.burst_size, self.tokens + elapsed * self.refill_rate)
        self.last_update = now
    
    def _update_user_quota(self, user_id: str, wait_time: float = 0.0):
        """Update quota tracking for a user."""
        with self.quota_lock:
            if user_id not in self.user_quotas:
                self.user_quotas[user_id] = UserQuota(user_id)
            
            quota = self.user_quotas[user_id]
            quota.reset_if_needed()
            quota.requests_made += 1
            quota.last_request_time = datetime.now()
            quota.total_wait_time += wait_time
    
    def _get_user_priority_adjustment(self, user_id: str) -> float:
        """Get priority adjustment based on user's recent usage."""
        if not user_id:
            return 0.0
        
        with self.quota_lock:
            if user_id not in self.user_quotas:
                return 0.0  # New user gets normal priority
            
            quota = self.user_quotas[user_id]
            quota.reset_if_needed()
            
            # Users who have made fewer requests get higher priority
            # This implements fair distribution
            if quota.requests_made == 0:
                return -1.0  # Higher priority (lower sort value)
            elif quota.requests_made < 3:
                return 0.0   # Normal priority
            else:
                return 1.0   # Lower priority
    
    def acquire(self, timeout: Optional[float] = None, user_id: Optional[str] = None) -> bool:
        """
        Acquire a token, blocking if necessary.
        
        Args:
            timeout: Maximum time to wait in seconds
            user_id: User identifier for fair distribution
        
        Returns:
            True if token was acquired, False if timed out
        """
        start_time = time.time()
        
        # Check if we need to wait due to exponential backoff
        backoff_delay = self.backoff.get_delay()
        if backoff_delay > 0:
            if timeout and backoff_delay > timeout:
                return False
            time.sleep(backoff_delay)
            if timeout:
                timeout -= backoff_delay
        
        while True:
            with self.lock:
                self._refill()
                
                if self.tokens >= 1:
                    self.tokens -= 1
                    wait_time = time.time() - start_time
                    if user_id:
                        self._update_user_quota(user_id, wait_time)
                    
                    with self.stats_lock:
                        self.stats["total_requests"] += 1
                        # Update average wait time
                        total_wait = self.stats["average_wait_time"] * (self.stats["total_requests"] - 1)
                        self.stats["average_wait_time"] = (total_wait + wait_time) / self.stats["total_requests"]
                    
                    return True
                
                # Calculate wait time for next token
                wait_time = (1 - self.tokens) / self.refill_rate
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    with self.stats_lock:
                        self.stats["queue_timeouts"] += 1
                    return False
            
            # Wait for tokens to refill
            time.sleep(min(wait_time, 1.0))
    
    def acquire_async(
        self,
        priority: RequestPriority = RequestPriority.NORMAL,
        timeout: Optional[float] = None,
        user_id: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """
        Queue a request for asynchronous processing.
        
        Args:
            priority: Request priority level
            timeout: Maximum time to wait in seconds
            user_id: User identifier for fair distribution
            callback: Callback function to call when token is acquired
        
        Returns:
            Request ID for tracking
        """
        request = QueuedRequest(
            request_id=str(uuid.uuid4()),
            user_id=user_id,
            priority=priority,
            created_at=datetime.now(),
            timeout=timeout,
            callback=callback
        )
        
        with self.queue_lock:
            self.request_queue.append(request)
            # Sort by priority and fair distribution
            self.request_queue.sort(key=lambda r: (
                r.priority.value,
                self._get_user_priority_adjustment(r.user_id),
                r.created_at
            ))
        
        # Start queue processor if not running
        self.start_queue_processor()
        
        return request.request_id
    
    def _process_queue(self):
        """Background thread that processes the request queue."""
        while self.queue_processor_running and not self.shutdown_event.is_set():
            try:
                request = None
                
                # Get next request from queue
                with self.queue_lock:
                    if self.request_queue:
                        request = self.request_queue.pop(0)
                
                if request is None:
                    time.sleep(0.1)
                    continue
                
                # Check if request has timed out
                if request.timeout:
                    elapsed = (datetime.now() - request.created_at).total_seconds()
                    if elapsed > request.timeout:
                        with self.stats_lock:
                            self.stats["queue_timeouts"] += 1
                        continue
                
                # Try to acquire token
                remaining_timeout = None
                if request.timeout:
                    elapsed = (datetime.now() - request.created_at).total_seconds()
                    remaining_timeout = max(0, request.timeout - elapsed)
                
                success = self.acquire(timeout=remaining_timeout, user_id=request.user_id)
                
                if success and request.callback:
                    try:
                        request.callback()
                    except Exception as e:
                        print(f"Error in rate limiter callback: {e}")
                
            except Exception as e:
                print(f"Error in queue processor: {e}")
                time.sleep(1.0)
    
    def try_acquire(self, user_id: Optional[str] = None) -> bool:
        """
        Try to acquire a token without blocking.
        
        Args:
            user_id: User identifier for fair distribution
        
        Returns:
            True if token was acquired, False otherwise
        """
        # Check exponential backoff
        if self.backoff.get_delay() > 0:
            return False
        
        with self.lock:
            self._refill()
            
            if self.tokens >= 1:
                self.tokens -= 1
                if user_id:
                    self._update_user_quota(user_id)
                
                with self.stats_lock:
                    self.stats["total_requests"] += 1
                
                return True
            
            return False
    
    def wait_time(self) -> float:
        """
        Get the estimated wait time for the next available token.
        
        Returns:
            Wait time in seconds
        """
        backoff_delay = self.backoff.get_delay()
        
        with self.lock:
            self._refill()
            
            if self.tokens >= 1 and backoff_delay == 0:
                return 0.0
            
            token_wait = (1 - self.tokens) / self.refill_rate if self.tokens < 1 else 0.0
            return max(backoff_delay, token_wait)
    
    def record_api_success(self):
        """Record a successful API call."""
        self.backoff.record_success()
        with self.stats_lock:
            self.stats["successful_requests"] += 1
    
    def record_api_failure(self):
        """Record a failed API call for exponential backoff."""
        self.backoff.record_failure()
        with self.stats_lock:
            self.stats["failed_requests"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self.stats_lock:
            stats = self.stats.copy()
        
        with self.quota_lock:
            user_stats = {
                user_id: {
                    "requests_made": quota.requests_made,
                    "total_wait_time": quota.total_wait_time,
                    "last_request": quota.last_request_time.isoformat()
                }
                for user_id, quota in self.user_quotas.items()
            }
        
        with self.queue_lock:
            queue_size = len(self.request_queue)
        
        return {
            **stats,
            "current_tokens": self.tokens,
            "queue_size": queue_size,
            "backoff_delay": self.backoff.get_delay(),
            "failure_count": self.backoff.failure_count,
            "user_quotas": user_stats
        }
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for a specific user."""
        with self.quota_lock:
            if user_id not in self.user_quotas:
                return {"requests_made": 0, "total_wait_time": 0.0}
            
            quota = self.user_quotas[user_id]
            quota.reset_if_needed()
            
            return {
                "requests_made": quota.requests_made,
                "total_wait_time": quota.total_wait_time,
                "last_request": quota.last_request_time.isoformat(),
                "estimated_wait_time": self.wait_time()
            }


# Global enhanced rate limiter instance for Gemini API calls
# Free tier limits: 15 requests per minute, 1500 per day
# Conservative setting: 2 requests per minute to avoid hitting limits
gemini_limiter = EnhancedRateLimiter(requests_per_minute=2, burst_size=1)


def rate_limited_call(func, *args, timeout: float = 120.0, user_id: Optional[str] = None, **kwargs):
    """
    Execute a function with enhanced rate limiting.
    
    Args:
        func: The function to call
        *args: Arguments to pass to the function
        timeout: Maximum time to wait for rate limit
        user_id: User identifier for fair distribution
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        The result of the function call
    
    Raises:
        TimeoutError: If rate limit timeout is exceeded
    """
    if not gemini_limiter.acquire(timeout=timeout, user_id=user_id):
        raise TimeoutError(f"Rate limit timeout exceeded ({timeout}s). Try again later.")
    
    try:
        result = func(*args, **kwargs)
        gemini_limiter.record_api_success()
        return result
    except Exception as e:
        gemini_limiter.record_api_failure()
        raise


# Legacy compatibility
RateLimiter = EnhancedRateLimiter
