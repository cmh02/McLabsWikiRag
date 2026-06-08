'''
MCLabs Wiki RAG - Flask API

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager

# Typing
from typing import cast, Dict, Optional

# API
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, HTTPException, Request
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler

# Google API
from google import genai

# MCL Packages
from src.rag import MCL_WikiRag
from src.logger import MCL_Logger
from src.security import verifyRequest
from src.docfetch import MCL_WikiEmbedder
from src.helpmanager import MCL_HelpManager
from src.mongo import MCL_MongoManager
from src.schemas import BaseHelpQuestionSchema, QuestionSchema

'''
FASTAPI APP STARTUP / SHUTDOWN
'''
@asynccontextmanager
async def lifespan(app: FastAPI):

	# Load environment variables from .env file if not in Railway environment
	if os.getenv("RAILWAY_ENVIRONMENT_ID") is None:
		from dotenv import load_dotenv
		load_dotenv()

	# Setup logging
	app.state.logger = MCL_Logger.setup_logger()

	# Gemini client
	app.state.InstanceClient = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

	# Load the index and documents
	app.state.InstanceWikiEmbedder = MCL_WikiEmbedder(client=app.state.InstanceClient)
	app.state.InstanceWikiEmbedder.loadIndexAndDocuments()

	# RAG instance
	app.state.InstanceRag = MCL_WikiRag(client=app.state.InstanceClient, wikiEmbedder=app.state.InstanceWikiEmbedder)

	# Initialize Help Manager
	MCL_HelpManager().initialize()
	MCL_HelpManager().loadQuestionsFromJson(filePath=os.getenv("HELP_QUESTIONS_FILE_PATH", "data/help_questions.json"))

	# Initialize Mongo Manager
	MCL_MongoManager().initialize()

	# Log startup
	app.state.logger.info(f"MCL RAG API started with PID {os.getpid()}!")

	# Yield back for app lifetime
	yield

	# Log shutdown
	app.state.logger.info(f"MCL RAG API shutting down with PID {os.getpid()}!")

	# Save help questions on shutdown
	MCL_HelpManager().saveQuestionsToJson(filePath=os.getenv("HELP_QUESTIONS_FILE_PATH", "data/help_questions.json"))

'''
FASTAPI APP DEFINITION
'''

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)
appLimiter = Limiter(key_func=get_remote_address)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = appLimiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

'''
# WAKEUP ENDPOINT

This endpoint is used solely for waking up the API when asleep on Railway. It still needs authentication.

## Request Headers
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests
'''
@app.post("/wakeup")
@appLimiter.limit("50/minute")
def wakeup(request: Request):
	
	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Log for debugging
	app.state.logger.debug(f"Received wakeup request! \nRequest: {request}")

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "awake"}
	)

'''
# RAG QUERY ENDPOINT

There is a singular endpoint for querying the RAG system. Users can POST to /query with a JSON body containing:

## Request Headers
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "question": The question you want to ask (max 256 characters)
- "include_context": (optional) Boolean to include context chunks in the response
'''

class RagQuerySchema(BaseModel):
	'''
	# RagQuerySchema

	Model for query requests to the RAG API. Inherits authentication from BaseModel.
	'''

	# The question to ask
	question: str = Field(description="A search query, such as a question..")

	# Whether to include context chunks in the response
	include_context: bool = Field(default=False, description="Whether to include context chunks in the response.")

@app.post("/query")
@appLimiter.limit("100/minute")
def query(request: Request, body: RagQuerySchema):

	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Get the request data
	data: Dict = body.model_dump()

	# Print for debugging
	app.state.logger.debug(f"Received query request! \nRequest: {request}")

	# Get the question from the request
	question = data.get("question")
	includeContext = data.get("include_context", "False")

	# Log question for debugging``
	app.state.logger.debug(f"Received question: {question}")

	# If no question provided, return error
	if not question:
		
        # Log missing question
		app.state.logger.debug("No question provided in request")

		# Return error
		raise HTTPException(
			status_code=400, 
			detail="Missing 'question'"
		)

	# If question is too long, return error
	if len(question) > 256:

		# Log too long question
		app.state.logger.debug("Question is too long (max 256 characters)!")

		# Return error
		raise HTTPException(
			status_code=400, 
			detail="Question is too long (max 256 characters)!"
		)

	# Get the response from the RAG pipeline and return
	result, topChunks = app.state.InstanceRag.queryPipeline(question)
     
	# Log answer for debugging
	app.state.logger.debug(f"Answer to question {question}: {result}")	

	# Return the result
	if includeContext in [False, "False", "false", 0, "0"]:
		return JSONResponse(
			status_code=200,
			content={"answer": result}
		)
	return JSONResponse(
		status_code=200,
		content={"answer": result, "context": topChunks}
	)