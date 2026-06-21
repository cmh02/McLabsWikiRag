'''
MCLabs Wiki RAG - API Limiter

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from slowapi import Limiter
from slowapi.util import get_remote_address

'''
GLOBAL API LIMITER
'''
limiter = Limiter(key_func=get_remote_address)