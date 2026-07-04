'''
MCLabs Discord Bot - API Limiter

Author: Chris Hinkson @cmh02
'''

from slowapi import Limiter
from slowapi.util import get_remote_address

'''
GLOBAL API LIMITER
'''
limiter = Limiter(key_func=get_remote_address)
