
from rate_limiter import is_rate_limited
import time

for i in range(7):
    blocked = is_rate_limited(user_id=1, limit= 5 ,window_seconds=10)
    print(f"Request {i+1}: {'BLOCKED'if blocked else'ALLOWED'}") 
    time.sleep(1)

