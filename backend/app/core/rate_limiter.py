"""
Rate limiter for API calls to avoid hitting external API limits.
Implements a simple token bucket algorithm with configurable rate.
"""
import time
import threading
from typing import Optional


class RateLimiter:
    """
    A thread-safe rate limiter using token bucket algorithm.
    Default: 5 requests per minute (matching Gemini free tier limits).
    """
    
    def __init__(self, requests_per_minute: int = 5, burst_size: Optional[int] = None):
        """
        Initialize the rate limiter.
        
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
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.burst_size, self.tokens + elapsed * self.refill_rate)
        self.last_update = now
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a token, blocking if necessary.
        
        Args:
            timeout: Maximum time to wait in seconds. None means wait indefinitely.
        
        Returns:
            True if token was acquired, False if timed out.
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                self._refill()
                
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
                
                # Calculate wait time for next token
                wait_time = (1 - self.tokens) / self.refill_rate
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
            
            # Wait for tokens to refill
            time.sleep(min(wait_time, 1.0))  # Sleep in 1-second intervals max
    
    def try_acquire(self) -> bool:
        """
        Try to acquire a token without blocking.
        
        Returns:
            True if token was acquired, False otherwise.
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            return False
    
    def wait_time(self) -> float:
        """
        Get the estimated wait time for the next available token.
        
        Returns:
            Wait time in seconds.
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= 1:
                return 0.0
            
            return (1 - self.tokens) / self.refill_rate


# Global rate limiter instance for Gemini API calls
# 5 requests per minute with burst of 2
gemini_limiter = RateLimiter(requests_per_minute=5, burst_size=2)


def rate_limited_call(func, *args, timeout: float = 120.0, **kwargs):
    """
    Execute a function with rate limiting.
    
    Args:
        func: The function to call
        *args: Arguments to pass to the function
        timeout: Maximum time to wait for rate limit
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        The result of the function call
    
    Raises:
        TimeoutError: If rate limit timeout is exceeded
    """
    if not gemini_limiter.acquire(timeout=timeout):
        raise TimeoutError(f"Rate limit timeout exceeded ({timeout}s). Try again later.")
    
    return func(*args, **kwargs)
