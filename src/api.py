'''
MCLabs Wiki RAG - Flask API

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
from contextlib import asynccontextmanager

# Typing
from typing import Dict

# Fast API and Pydantic
from pydantic import BaseModel, Field
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler

# Google API
from google import genai

# MCL Packages
from src.rag import MCL_WikiRag
from src.docfetch import MCL_WikiEmbedder

'''
FASTAPI APP STARTUP / SHUTDOWN
'''
@asynccontextmanager
async def lifespan(app: FastAPI):

	# Load environment variables from .env file if not in Railway environment
	if os.getenv("RAILWAY_ENVIRONMENT_ID") is None:
		from dotenv import load_dotenv
		load_dotenv()

	# Gemini client
	app.state.InstanceClient = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

	# Load the index and documents
	app.state.InstanceWikiEmbedder = MCL_WikiEmbedder(client=app.state.InstanceClient)
	app.state.InstanceWikiEmbedder.loadIndexAndDocuments()

	# RAG instance
	app.state.InstanceRag = MCL_WikiRag(client=app.state.InstanceClient, wikiEmbedder=app.state.InstanceWikiEmbedder)
	yield

'''
FASTAPI APP STARTUP / SHUTDOWN
'''
# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)
appLimiter = Limiter(key_func=get_remote_address)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = appLimiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

'''
PYDANTIC MODELS
'''
class BaseRequest(BaseModel):
	'''
	# BaseRequest

	Basic model for all requests to the API. All this provides is authentication via API token.
	'''

	# API token for authentication
	api_token: str = Field(description="API token for authentication.")

class BaseQueryRequest(BaseRequest):
	'''
	# BaseQueryRequest

	Model for query requests to the API. Inherits authentication from BaseRequest.
	'''

	# The question to ask
	question: str = Field(description="A search query, such as a question..")

	# Whether to include context chunks in the response
	include_context: bool = Field(default=False, description="Whether to include context chunks in the response.")

'''
WAKEUP ENDPOINT

This endpoint is used solely for waking up the API when asleep on Railway. It still needs authentication.
'''
@app.post("/wakeup")
@appLimiter.limit("50/minute")
def wakeup(request: Request, body: BaseRequest):
	
	# Get the request data
	data: Dict = body.model_dump()

	# Print for debugging
	if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
		print(f"Received wakeup request: {request}")
		print(f"Received wakeup request data: {data}")

	# Check API token
	if data.get("api_token") != os.getenv("API_TOKEN"):
			
		# Print for debugging
		if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
			print(f"Invalid API token attempt: {data.get('api_token')}")
				  
		# Return error
		raise HTTPException(
			status_code=401, 
			detail="Invalid API token"
		)

	# Return success message
	return {"status": "awake"}

'''
QUESTION ENDPOINT

There is a singular endpoint for querying the RAG system. Users can POST to /query with a JSON body containing:
- "api_token": Your API token for authentication
- "question": The question you want to ask (max 256 characters)
- "include_context": (optional) Boolean to include context chunks in the response
'''
@app.post("/query")
@appLimiter.limit("100/minute")
def query(request: Request, body: BaseQueryRequest):

	# Get the request data
	data: Dict = body.model_dump()

	# Print for debugging
	if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
		print(f"Received request: {request}")
		print(f"Received request data: {data}")

	# Check API token
	if data.get("api_token") != os.getenv("API_TOKEN"):
            
		# Print for debugging
		if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
			print(f"Invalid API token attempt: {data.get('api_token')}")
                  
		# Return error
		raise HTTPException(
			status_code=401, 
			detail="Invalid API token"
		)

	# Get the question from the request
	question = data.get("question")
	includeContext = data.get("include_context", "False")

	# Print for debugging
	if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
		print(f"Received question: {question}")

	# If no question provided, return error
	if not question:
        # Print for debugging
		if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
			print("No question provided in request")

		# Return error
		raise HTTPException(
			status_code=400, 
			detail="Missing 'question'"
		)

	# If question is too long, return error
	if len(question) > 256:
		# Print for debugging
		if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
			print("Question is too long (max 256 characters)!")

		# Return error
		raise HTTPException(
			status_code=400, 
			detail="Question is too long (max 256 characters)!"
		)

	# Get the response from the RAG pipeline and return
	result, topChunks = app.state.InstanceRag.queryPipeline(question)
     
	# Print for debugging
	if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
		print(f"Answer to question {question}: {result}")	

	# Return the result
	if includeContext in [False, "False", "false", 0, "0"]:
		return {"answer": result}
	return {"answer": result, "context": topChunks}