import redis
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True    # returns strings instead of bytes
)

def get_redis():
    return redis_client