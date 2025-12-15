'''
MCLabs Backend - Security Module

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
import os
import logging
from fastapi import HTTPException, Request

'''
LOGGER SETUP
'''
logger = logging.getLogger("MCL_API_Logger")

'''
Security Utilities
'''

def verifyRequest(request: Request, verifyToken: bool=True, verifyIpAddress: bool=True) -> None:
	'''
	# verifyRequest

	Verifies both the API token and IP address of the incoming request.

	## Parameters
	- request: The incoming FastAPI request object.

	## Raises
	- HTTPException: If the API token is missing/invalid or the IP address is not allowed.
	'''

	# Verify API token
	if verifyToken:
		verifyApiToken(request=request)

	# Verify IP address
	if verifyIpAddress:
		verifyIp(request=request)
		
def verifyApiToken(request: Request) -> None:
	'''
	# verifyApiToken

	Verifies that the API token provided in the request headers matches the expected token.

	## Parameters
	- request: The incoming FastAPI request object.

	## Raises
	- HTTPException: If the API token is missing or invalid.
	'''

	# Get request header token
	token = request.headers.get("X-API-Token")

	# Check if token is missing
	if not token:
		# Print for debugging
		logger.warning("Missing API token in request headers.")
		
		# Return error
		raise HTTPException(
			status_code=401, 
			detail="Missing API token"
		)

	# Check if token is invalid
	if token != os.getenv("API_TOKEN"):
			
		# Print for debugging
		logger.warning(f"Invalid API token attempt: {token}")
				  
		# Return error
		raise HTTPException(
			status_code=401, 
			detail="Invalid API token"
		)
	
def verifyIp(request: Request) -> None:
	'''
	# verifyIp

	Verifies that the IP address of the incoming request is in the allowed list.

	## Parameters
	- request: The incoming FastAPI request object.

	## Raises
	- HTTPException: If the IP address is not allowed.
	'''

	# Get client IP address
	client_ip = request.client.host

	# Get allowed IPs from environment variable
	allowed_ips = os.getenv("ALLOWED_IPS", "").split(",")

	# Check if client IP is in allowed list
	if client_ip not in allowed_ips:

		# Print for debugging
		logger.warning(f"Unauthorized IP address attempt: {client_ip}")

		# Return error
		raise HTTPException(
			status_code=403,
			detail="Unauthorized IP address"
		)