'''
MCLabs Common - Logging Middleware

Author: Chris Hinkson @cmh02
'''

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestLoggingMiddleware(BaseHTTPMiddleware):
	'''
	# RequestLoggingMiddleware

	FastAPI middleware that intercepts all incoming requests to log
	their basic properties (method, path, client IP, processing time, status code)
	at the DEBUG level.
	'''
	async def dispatch(self, request: Request, call_next):
		start_time = time.time()
		
		# Get connection metadata
		client_ip = request.client.host if request.client else "unknown"
		method = request.method
		path = request.url.path
		
		# Retrieve the application logger if configured, default to fallback
		logger = getattr(request.app.state, "logger", None)
		if not logger:
			logger = logging.getLogger("MCL_Logger")
			
		logger.debug(f"Incoming Request: {method} {path} from {client_ip}")
		
		try:
			response = await call_next(request)
			process_time = (time.time() - start_time) * 1000
			logger.debug(
				f"Completed Request: {method} {path} - Status: {response.status_code} "
				f"({process_time:.2f}ms)"
			)
			return response
		except Exception as e:
			process_time = (time.time() - start_time) * 1000
			logger.exception(
				f"Failed Request: {method} {path} ({process_time:.2f}ms) - Error: {e}"
			)
			raise e
