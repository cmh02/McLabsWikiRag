'''
MCLabs Common - API Limiter
'''

from slowapi import Limiter
from slowapi.util import get_remote_address

# Global API Limiter instance
limiter = Limiter(key_func=get_remote_address)
