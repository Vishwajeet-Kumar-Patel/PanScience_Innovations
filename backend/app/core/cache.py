"""
Redis cache manager for caching expensive operations.
"""
import json
import logging
from typing import Optional, Any
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Cache manager supporting both Redis and in-memory fallback."""
    
    def __init__(self):
        self.redis = None
        self.memory_cache = {}  # Fallback for when Redis is disabled
        
        if settings.ENABLE_REDIS:
            try:
                import redis.asyncio as redis
                self.redis = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                    decode_responses=True
                )
                logger.info("Redis cache initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis, using in-memory cache: {e}")
                self.redis = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if self.redis:
                value = await self.redis.get(key)
                if value:
                    return json.loads(value)
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (default: 1 hour)
        """
        try:
            serialized = json.dumps(value)
            
            if self.redis:
                await self.redis.setex(key, ttl, serialized)
            else:
                # For in-memory cache, we don't implement TTL (would need background task)
                self.memory_cache[key] = value
            
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            if self.redis:
                await self.redis.delete(key)
            else:
                self.memory_cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> bool:
        """Delete all keys matching pattern (Redis only)."""
        try:
            if self.redis:
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
                return True
            else:
                # For in-memory, delete keys that match pattern
                keys_to_delete = [k for k in self.memory_cache.keys() if pattern.replace("*", "") in k]
                for key in keys_to_delete:
                    self.memory_cache.pop(key, None)
                return True
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()


# Global cache instance
cache = CacheManager()


# Helper functions for common caching patterns

async def cache_document_metadata(document_id: str, metadata: dict, ttl: int = 3600):
    """Cache document metadata."""
    key = f"doc:metadata:{document_id}"
    await cache.set(key, metadata, ttl)


async def get_cached_document_metadata(document_id: str) -> Optional[dict]:
    """Get cached document metadata."""
    key = f"doc:metadata:{document_id}"
    return await cache.get(key)


async def cache_search_results(query: str, results: list, ttl: int = 1800):
    """Cache search results (30 min TTL)."""
    key = f"search:{query}"
    await cache.set(key, results, ttl)


async def get_cached_search_results(query: str) -> Optional[list]:
    """Get cached search results."""
    key = f"search:{query}"
    return await cache.get(key)


async def invalidate_document_cache(document_id: str):
    """Invalidate all cache entries for a document."""
    await cache.clear_pattern(f"doc:*:{document_id}")


async def cache_chat_response(query_hash: str, response: dict, ttl: int = 1800):
    """Cache chat response (30 min TTL)."""
    key = f"chat:{query_hash}"
    await cache.set(key, response, ttl)


async def get_cached_chat_response(query_hash: str) -> Optional[dict]:
    """Get cached chat response."""
    key = f"chat:{query_hash}"
    return await cache.get(key)
