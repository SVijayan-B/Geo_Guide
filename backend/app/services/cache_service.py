from __future__ import annotations

import json
import os
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class CacheService:
    def __init__(self):
        self._memory_store: dict[str, tuple[float, str]] = {}
        self._redis_client = None

        host = os.getenv("REDIS_HOST")
        port = os.getenv("REDIS_PORT")
        if not host or not port:
            return

        try:
            import redis

            client = redis.Redis(host=host, port=int(port), decode_responses=True)
            client.ping()
            self._redis_client = client
        except Exception:
            self._redis_client = None

    def get(self, key: str) -> Any:
        if self._redis_client is not None:
            try:
                payload = self._redis_client.get(key)
                return json.loads(payload) if payload else None
            except Exception:
                pass

        cached = self._memory_store.get(key)
        if not cached:
            return None
        expires_at, payload = cached
        if time.time() > expires_at:
            self._memory_store.pop(key, None)
            return None
        try:
            return json.loads(payload)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        serialized = json.dumps(value)

        if self._redis_client is not None:
            try:
                self._redis_client.setex(key, ttl, serialized)
                return
            except Exception:
                pass

        self._memory_store[key] = (time.time() + ttl, serialized)
