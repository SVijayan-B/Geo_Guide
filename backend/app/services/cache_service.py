import redis
import os
import json
from dotenv import load_dotenv

load_dotenv()


class CacheService:

    def __init__(self):
        self.client = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT")),
            decode_responses=True
        )

    def get(self, key):
        data = self.client.get(key)
        return json.loads(data) if data else None

    def set(self, key, value, ttl=300):
        self.client.setex(key, ttl, json.dumps(value))