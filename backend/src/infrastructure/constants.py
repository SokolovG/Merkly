SESSION_TTL: int = 900  # 15 minutes — active lesson session lifetime in Redis

# Atomically increment a counter and set its TTL in a single round-trip.
# KEYS[1] = key, ARGV[1] = ttl (seconds)
LUA_INCR_AND_EXPIRE_SCRIPT: str = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""
