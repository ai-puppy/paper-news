"""Utilities for API quota management and error handling."""

import time
from functools import wraps
from typing import Any, Callable
from googleapiclient.errors import HttpError


class YouTubeAPIError(Exception):
    """Custom exception for YouTube API errors."""
    pass


class QuotaExceededError(YouTubeAPIError):
    """Raised when API quota is exceeded."""
    pass


def handle_api_errors(func: Callable) -> Callable:
    """
    Decorator to handle YouTube API errors gracefully.
    
    Handles common API errors including:
    - 403: Quota exceeded
    - 404: Resource not found
    - 400: Bad request
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            error_code = e.resp.status
            error_details = str(e)
            
            if error_code == 403 and "quotaExceeded" in error_details:
                raise QuotaExceededError(
                    "YouTube API quota exceeded. Please try again later or use a different API key."
                )
            elif error_code == 404:
                raise YouTubeAPIError(f"Resource not found: {error_details}")
            elif error_code == 400:
                raise YouTubeAPIError(f"Bad request: {error_details}")
            else:
                raise YouTubeAPIError(f"API error (code {error_code}): {error_details}")
                
    return wrapper


def rate_limit(calls_per_second: float = 10.0):
    """
    Decorator to rate limit API calls.
    
    Args:
        calls_per_second: Maximum number of calls per second
    """
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator


# YouTube API quota costs (in units)
QUOTA_COSTS = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
    "playlists.list": 1,
    "playlistItems.list": 1,
    "comments.list": 1,
    "commentThreads.list": 1,
}


class QuotaTracker:
    """Track API quota usage."""
    
    def __init__(self, daily_limit: int = 10000):
        self.daily_limit = daily_limit
        self.used_quota = 0
        self.operations = []
        
    def track_operation(self, operation: str, count: int = 1):
        """Track an API operation and its quota cost."""
        cost = QUOTA_COSTS.get(operation, 1) * count
        self.used_quota += cost
        self.operations.append({
            "operation": operation,
            "cost": cost,
            "timestamp": time.time()
        })
        
        if self.used_quota >= self.daily_limit:
            raise QuotaExceededError(
                f"Daily quota limit reached: {self.used_quota}/{self.daily_limit} units used"
            )
    
    def get_remaining_quota(self) -> int:
        """Get remaining quota units."""
        return max(0, self.daily_limit - self.used_quota)
    
    def reset(self):
        """Reset quota tracking."""
        self.used_quota = 0
        self.operations = []