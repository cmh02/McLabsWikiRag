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
from fastapi import FastAPI, HTTPException

# Google API
from google import genai

# MCL Packages
from src.rag import MCL_WikiRag
from src.docfetch import MCL_WikiEmbedder

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
FASTAPI APP SETUP
'''

# Initialize FastAPI app
app = FastAPI()

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

# API Limits
MAX_REQUESTS_PER_MINUTE = 2000
MAX_REQUESTS_PER_DAY = 10000

'''
API LIMITING
'''

# Track request counts (minutes reset at top of minute, day resets at midnight pacific time)
requestCounts = {
    "minute": 0,
    "day": 0,
    "minuteReset": datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=1),
    "dayReset": datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
}

# Check and update request counts
def api_checkLimits():
    
	# Get needed info
    global requestCounts
    now = datetime.now()

    # Reset per-minute counter at the top of the minute
    if now >= requestCounts["minuteReset"]:
        requestCounts["minute"] = 0
        requestCounts["minuteReset"] = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Reset per-day counter at midnight PT (07:00 UTC)
    if now >= requestCounts["dayReset"]:
        requestCounts["day"] = 0
        requestCounts["dayReset"] = now.replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Check if we’re over limits
    if requestCounts["minute"] >= MAX_REQUESTS_PER_MINUTE:
        return False, f"Rate limit exceeded: {MAX_REQUESTS_PER_MINUTE} requests per minute", 1
    if requestCounts["day"] >= MAX_REQUESTS_PER_DAY:
        return False, f"Rate limit exceeded: {MAX_REQUESTS_PER_DAY} requests per day", 2

    # Count this request and allow
    requestCounts["minute"] += 1
    requestCounts["day"] += 1
    return True, None, 0

@app.before_request
def api_limitRequests():
    ok, errorMessage, errorCode = api_checkLimits()
    if not ok:
        return jsonify({"errormessage": errorMessage, "errorcode": errorCode}), 429

'''
API ENDPOINT

There is a singular endpoint for querying the RAG system. Users can POST to /query with a JSON body containing:
- "api_token": Your API token for authentication
- "question": The question you want to ask (max 256 characters)
- "include_context": (optional) Boolean to include context chunks in the response
'''
# Querying RAG via API
@app.post("/query")
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