import os
import time
import redis

REDIS_URL = os.environ["REDIS_URL"]
r = redis.from_url(REDIS_URL, decode_responses=True)

def is_rate_limited(user_id: int, limit: int = 5, window_seconds: int = 60) -> bool:
    key = f"rate_limit:{user_id}"
    now = time.time()

    r.zremrangebyscore(key, 0, now - window_seconds)

    count = r.zcard(key)

    if count >= limit:
        return True

    r.zadd(key, {str(now): now})
    r.expire(key, window_seconds)

    return False