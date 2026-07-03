'''
MCLabs Wiki RAG - API Router

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

from fastapi import APIRouter, Request, HTTPException, Header, Depends

from src.network.security import verifyRequest

'''
API ROUTER

Creation of the API router for all endpoints. 
This will be included in the main FastAPI app in api.py.
The router also handles global header requirements.
'''

class MclRouter():

	@staticmethod
	def getNewRouter() -> APIRouter:
		"""
		Creates a new APIRouter instance with global header validation.

		Returns:
			APIRouter: A new APIRouter instance with global header validation.
		"""
		return APIRouter(dependencies=[Depends(MclRouter.validateGlobalRequestHeaders)])

	@staticmethod
	def validateGlobalRequestHeaders(
			request: Request,
			authorization: str = Header(
				...,
				description="API token for authentication",
				alias="Authorization"
			),
			user_agent: str = Header(
				...,
				description="User agent string to identify discord versus minecraft requests",
				alias="User-Agent"
			)
		):

		# Verify request headers are given
		if not authorization.strip():
			raise HTTPException(
				status_code=400,
				detail="Missing authorization header"
			)
		if not user_agent.strip():
			raise HTTPException(
				status_code=400,
				detail="Missing user-agent header"
			)

		# Implement API auth
		verifyRequest(
			request=request,
			verifyToken=True,
			verifyIpAddress=False
		)