'''
MCLabs Discord Bot - Network Security

Author: Chris Hinkson @cmh02
'''

import os
import logging
from fastapi import HTTPException, Request

'''
LOGGER SETUP
'''
logger = logging.getLogger("MCL_DISCORD_Logger")

'''
Security Utilities
'''

def verifyRequest(request: Request, verifyToken: bool = True, verifyIpAddress: bool = False) -> None:
	'''
	# verifyRequest

	Verifies both the API token and IP address of the incoming request.
	'''
	client_ip = request.client.host if request.client else "unknown"

	logger.debug(
		f"API request received from IP `{client_ip}` with verifications enabled: token={verifyToken}, ip={verifyIpAddress}"
	)

	try:
		if verifyToken:
			verifyApiToken(request=request)
		if verifyIpAddress:
			verifyIp(request=request)
		logger.info(f"API request has been successfully verified for new request from IP `{client_ip}`!")
	except HTTPException as exc:
		logger.warning(
			f"API request failed verification for new request from IP {client_ip}! \nstatus_code={exc.status_code} \ndetail={exc.detail}"
		)
		raise

def verifyApiToken(request: Request) -> None:
	'''
	# verifyApiToken

	Verifies that the API token provided in the request headers matches the expected token.
	'''
	token = request.headers.get("Authorization")
	if not token:
		logger.warning("Missing API token in request headers.")
		raise HTTPException(
			status_code=401,
			detail="Missing API token"
		)

	matchToken = os.getenv("API_TOKEN")
	if not matchToken:
		logger.error("API_TOKEN environment variable is not set.")
		raise HTTPException(
			status_code=500,
			detail="Server configuration error ATNS!"
		)

	if token != matchToken:
		logger.warning("Invalid API token attempt.")
		raise HTTPException(
			status_code=401,
			detail="Invalid API token"
		)

def verifyIp(request: Request) -> None:
	'''
	# verifyIp

	Verifies that the IP address of the incoming request is in the allowed list.
	'''
	if not request.client:
		raise HTTPException(
			status_code=400,
			detail="Unable to determine client IP address"
		)

	client_ip = request.client.host
	allowed_ips = os.getenv("ALLOWED_IPS", "").split(",")
	if not allowed_ips or allowed_ips == [""]:
		logger.error("ALLOWED_IPS environment variable is not set or empty.")
		raise HTTPException(
			status_code=500,
			detail="Server configuration error AIPNS!"
		)

	if client_ip not in allowed_ips:
		logger.warning(f"Unauthorized IP address attempt: {client_ip}")
		raise HTTPException(
			status_code=403,
			detail="Unauthorized IP address"
		)
