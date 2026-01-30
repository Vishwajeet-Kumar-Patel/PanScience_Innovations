"""
Rate limiting middleware using Redis or in-memory storage.
"""
import time
import logging
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """Simple in-memory rate limiter (not production-ready for multi-instance)."""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, key: str, max_requests: int, window: int) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            key: Unique identifier (e.g., IP address or user ID)
            max_requests: Maximum requests allowed in window
            window: Time window in seconds
        """
        current_time = time.time()
        
        # Get or create request history for this key
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the window
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if current_time - req_time < window
        ]
        
        # Check if limit exceeded
        if len(self.requests[key]) >= max_requests:
            return False
        
        # Add current request
        self.requests[key].append(current_time)
        return True
    
    def get_retry_after(self, key: str, window: int) -> int:
        """Get seconds until rate limit resets."""
        if key not in self.requests or not self.requests[key]:
            return 0
        
        oldest_request = min(self.requests[key])
        retry_after = int(window - (time.time() - oldest_request))
        return max(0, retry_after)


class RedisRateLimiter:
    """Redis-based rate limiter for production use."""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def is_allowed(self, key: str, max_requests: int, window: int) -> bool:
        """Check if request is allowed using Redis."""
        try:
            # Use Redis sliding window
            current_time = time.time()
            window_start = current_time - window
            
            # Remove old requests
            await self.redis.zremrangebyscore(key, 0, window_start)
            
            # Count requests in window
            count = await self.redis.zcard(key)
            
            if count >= max_requests:
                return False
            
            # Add current request
            await self.redis.zadd(key, {str(current_time): current_time})
            await self.redis.expire(key, window)
            
            return True
            
        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            # Fail open (allow request) if Redis is down
            return True
    
    async def get_retry_after(self, key: str, window: int) -> int:
        """Get seconds until rate limit resets."""
        try:
            scores = await self.redis.zrange(key, 0, 0, withscores=True)
            if scores:
                oldest_time = scores[0][1]
                retry_after = int(window - (time.time() - oldest_time))
                return max(0, retry_after)
            return 0
        except Exception:
            return 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting on API requests."""
    
    def __init__(self, app, limiter: Optional[InMemoryRateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter()
        self.max_requests = settings.RATE_LIMIT_CALLS
        self.window = settings.RATE_LIMIT_PERIOD
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        
        # Skip rate limiting if disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Skip for health check and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get client identifier (IP address or user ID from token)
        client_id = request.client.host if request.client else "unknown"
        
        # Try to get user ID from Authorization header for better tracking
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            from app.core.auth import decode_access_token
            token = auth_header.replace("Bearer ", "")
            token_data = decode_access_token(token)
            if token_data and token_data.user_id:
                client_id = f"user:{token_data.user_id}"
        
        # Check rate limit
        is_allowed = self.limiter.is_allowed(
            client_id,
            self.max_requests,
            self.window
        )
        
        if not is_allowed:
            retry_after = self.limiter.get_retry_after(client_id, self.window)
            
            logger.warning(f"Rate limit exceeded for {client_id}")
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)}
            )
        
        response = await call_next(request)
        return response
