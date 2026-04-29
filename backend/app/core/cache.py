"""简单的内存 TTL 缓存，用于减少高频数据库查询。"""

import time
import asyncio
from typing import Any, Optional
from collections import OrderedDict


class TTLCache:
    """线程安全的内存 TTL 缓存（适合单实例部署）。"""

    def __init__(self, maxsize: int = 128, ttl: float = 60.0):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            value, expire_at = self._cache[key]
            if time.time() > expire_at:
                del self._cache[key]
                return None
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expire_at = time.time() + (ttl or self.ttl)
        async with self._lock:
            self._cache[key] = (value, expire_at)
            self._cache.move_to_end(key)
            # Evict oldest if over maxsize
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def invalidate_prefix(self, prefix: str) -> None:
        """删除所有以指定前缀开头的键（用于批量失效）。"""
        async with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]


# 全局缓存实例
structured_content_cache = TTLCache(maxsize=256, ttl=30.0)
interview_cache = TTLCache(maxsize=128, ttl=60.0)
llm_response_cache = TTLCache(maxsize=512, ttl=300.0)
