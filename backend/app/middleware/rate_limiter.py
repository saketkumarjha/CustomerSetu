from slowapi import Limiter
from slowapi.util import get_remote_address

# Module-level limiter instance.
# Imported in main.py and in routes that need limiting.
# key_func=get_remote_address → rate limit is per client IP.
limiter = Limiter(key_func=get_remote_address)