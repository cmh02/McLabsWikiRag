'''
MCLabs Wiki RAG - Flask API

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
from datetime import datetime, timedelta

# Typing
from typing import Dict, List, Any

# Fast API and Pydantic
from pydantic import BaseModel, Field
from fastapi import FastAPI, Response, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Google API
from google import genai

# MCL Packages
from src.rag import MCL_WikiRag
from src.docfetch import MCL_WikiEmbedder

'''
FASTAPI APP SETUP
'''

# Build rate limiter
appLimiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI()
app.state.limiter = appLimiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Load environment variables from .env file if not in Railway environment
if os.getenv("RAILWAY_ENVIRONMENT_ID") is None:
    from dotenv import load_dotenv
    load_dotenv()

# Gemini client
client = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

# Load the index and documents
InstanceWikiEmbedder = MCL_WikiEmbedder(client=client)
InstanceWikiEmbedder.loadIndexAndDocuments()

# RAG instance
InstanceRag = MCL_WikiRag(client=client, wikiEmbedder=InstanceWikiEmbedder)

'''
PYDANTIC MODELS
'''
class BaseQueryRequest(BaseModel):

	# API token for authentication
	api_token: str = Field(description="API token for authentication.")

	# The question to ask
	question: str = Field(description="A search query, such as a question..")

	# Whether to include context chunks in the response
	include_context: bool = Field(default=False, description="Whether to include context chunks in the response.")

'''
API ENDPOINT

There is a singular endpoint for querying the RAG system. Users can POST to /query with a JSON body containing:
- "api_token": Your API token for authentication
- "question": The question you want to ask (max 256 characters)
- "include_context": (optional) Boolean to include context chunks in the response
'''
# Querying RAG via API
@app.post("/query")
@appLimiter.limit("100/minute")
def query(request: BaseQueryRequest):

	# Get the request data
	data: Dict = request.model_dump()

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
	result, topChunks = InstanceRag.queryPipeline(question)
     
	# Print for debugging
	if os.environ.get("MCL_DEBUG", "FALSE") == "TRUE":
		print(f"Answer to question {question}: {result}")	

	# Return the result
	if includeContext in [False, "False", "false", 0, "0"]:
		return {"answer": result}
	return {"answer": result, "context": topChunks}