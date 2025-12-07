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

# API
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Request
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
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

class BaseHelpQuestionRequest(BaseRequest):
	'''
	# BaseHelpQuestionRequest

	Model for help question requests to the API. Inherits authentication from BaseRequest.
	'''

	# The ID of the question
	question_id: str = Field(description="The ID of the help question.")

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
	return JSONResponse(
		status_code=200,
		content={"status": "awake"}
	)

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
		return JSONResponse(
			status_code=200,
			content={"answer": result}
		)
	return JSONResponse(
		status_code=200,
		content={"answer": result, "context": topChunks}
	)

'''
ADD HELP QUESTION ENDPOINT

This endpoint will allow for adding help questions via question ID.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to add
- "question_player": The player who asked the help question
- "question_content": The content of the help question to add
- "question_time": The time the help question was asked
'''
@app.post("/help/add")
@appLimiter.limit("100/minute")
def add_help_question(request: Request, body: BaseHelpQuestionRequest):
	pass

'''
REMOVE HELP QUESTION ENDPOINT

This endpoint will allow for removing help questions via question ID. This endpoint is specifically
for removing help questions from the queue, not to answer them.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to remove
'''
@app.post("/help/remove")
@appLimiter.limit("100/minute")
def remove_help_question(request: Request, body: BaseHelpQuestionRequest):
	pass

'''
ANSWER HELP QUESTION ENDPOINT

This endpoint will allow for answering help questions via question ID. This should be used to provide an
answer that will be later retrieved by the in-game help system.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to answer
- "answer": The answer to the help question
- "answered_by": The name of the staff member answering the question
'''
@app.post("/help/answer")
@appLimiter.limit("100/minute")
def answer_help_question(request: Request, body: BaseHelpQuestionRequest):
	pass

'''
CLAIM HELP QUESTION ENDPOINT

This endpoint will allow for claiming help questions via question ID. This should be used to mark a help
question as being worked on by a staff member.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to claim
- "claimed_by": The name of the staff member claiming the question
'''
@app.post("/help/claim")
@appLimiter.limit("100/minute")
def claim_help_question(request: Request, body: BaseHelpQuestionRequest):
	pass

'''
UNCLAIM HELP QUESTION ENDPOINT

This endpoint will allow for unclaiming help questions via question ID. This should be used to mark a help
question as no longer being worked on by a staff member in the case they are unable to complete it.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to unclaim
'''
@app.post("/help/unclaim")
@appLimiter.limit("100/minute")
def unclaim_help_question(request: Request, body: BaseHelpQuestionRequest):
	pass