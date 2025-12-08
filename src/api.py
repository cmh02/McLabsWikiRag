'''
MCLabs Wiki RAG - Flask API

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
from datetime import datetime
from contextlib import asynccontextmanager

# Typing
from typing import cast, Dict, Optional

# API
from pydantic import BaseModel, Field, field_validator
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
from src.helpmanager import MCL_HelpManager
from src.schemas import BaseRequestSchema, BaseHelpQuestionSchema

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

	# Initialize Help Manager
	MCL_HelpManager().initialize()

	# Yield back for app lifetime
	yield

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
WAKEUP ENDPOINT

This endpoint is used solely for waking up the API when asleep on Railway. It still needs authentication.
'''
@app.post("/wakeup")
@appLimiter.limit("50/minute")
def wakeup(request: Request, body: BaseRequestSchema):
	
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

class RagQuerySchema(BaseRequestSchema):
	'''
	# RagQuerySchema

	Model for query requests to the RAG API. Inherits authentication from BaseRequestSchema.
	'''

	# The question to ask
	question: str = Field(description="A search query, such as a question..")

	# Whether to include context chunks in the response
	include_context: bool = Field(default=False, description="Whether to include context chunks in the response.")

@app.post("/query")
@appLimiter.limit("100/minute")
def query(request: Request, body: RagQuerySchema):

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

class AddHelpQuestionSchema(BaseHelpQuestionSchema):
	'''
	# AddHelpQuestionSchema

	Model for adding help question requests to the API. Inherits from BaseHelpQuestionRequestSchema.
	'''

	# Player who asked the help question
	question_player: str = Field(description="The player who asked the help question.")

	# Content of the help question
	question_content: str = Field(description="The content of the help question.")

	# Time the help question was asked as datetime object
	question_time: datetime = Field(description="The time the help question was asked.")
	@field_validator("question_time", mode="before")
	def convertUnixStringToDatetime(cls, unixString):
		# Accept strings or ints
		if isinstance(unixString, (int, float, str)) and str(unixString).isdigit():
			return datetime.fromtimestamp(int(unixString))
		return 0
	
@app.post("/help/add")
@appLimiter.limit("100/minute")
def add_help_question(request: Request, body: AddHelpQuestionSchema):
	
	# Get request data
	data: Dict = body.model_dump()
	
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

	# Add the help question
	success = MCL_HelpManager().addQuestion(
		questionID=data.get("question_id"),
		questionPlayer=data.get("question_player"),
		questionContent=data.get("question_content"),
		questionTime=data.get("question_time")
	)

	# Return success message
	if not success:
		raise HTTPException(
			status_code=500,
			detail=f"Failed to add help question {data.get('question_id')}"
		)
	return JSONResponse(
		status_code=200,
		content={"status": f"help question {data.get('question_id')} added successfully"}
	)

'''
REMOVE HELP QUESTION ENDPOINT

This endpoint will allow for removing help questions via question ID. This endpoint is specifically
for removing help questions from the queue, not to answer them.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to remove
'''

@app.post("/help/remove")
@appLimiter.limit("100/minute")
def remove_help_question(request: Request, body: BaseHelpQuestionSchema):
	
	# Get request data
	data: Dict = body.model_dump()
	
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

	# Remove the help question
	success = MCL_HelpManager().removeQuestion(
		questionID=data.get("question_id")
	)

	# Return success message
	if not success:
		raise HTTPException(
			status_code=500,
			detail=f"Failed to remove help question {data.get('question_id')}"
		)
	return JSONResponse(
		status_code=200,
		content={"status": f"help question {data.get('question_id')} removed successfully"}
	)

'''
ANSWER HELP QUESTION ENDPOINT

This endpoint will allow for answering help questions via question ID. This should be used to provide an
answer that will be later retrieved by the in-game help system.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to answer
- "answer": The answer to the help question
- "answered_by": The name of the staff member answering the question
'''

class AnswerHelpQuestionSchema(BaseHelpQuestionSchema):
	'''
	# AnswerHelpQuestionSchema

	Model for answering help question requests to the API. Inherits from BaseHelpQuestionRequestSchema.
	'''

	# The answer to the help question
	answer: str = Field(description="The answer to the help question.")

	# The staff member answering the help question
	answered_by: str = Field(description="The name of the staff member answering the question.")

@app.post("/help/answer")
@appLimiter.limit("100/minute")
def answer_help_question(request: Request, body: AnswerHelpQuestionSchema):
	
	# Get request data
	data: Dict = body.model_dump()
	
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

	# Answer the help question
	success = MCL_HelpManager().answerQuestion(
		questionID=data.get("question_id"),
		answeredBy=data.get("answered_by"),
		answerContent=data.get("answer")
	)

	# Return success message
	if not success:
		raise HTTPException(
			status_code=500,
			detail=f"Failed to answer help question {data.get('question_id')}"
		)
	return JSONResponse(
		status_code=200,
		content={"status": f"help question {data.get('question_id')} answered successfully"}
	)

'''
CLAIM HELP QUESTION ENDPOINT

This endpoint will allow for claiming help questions via question ID. This should be used to mark a help
question as being worked on by a staff member.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to claim
- "claimed_by": The name of the staff member claiming the question
'''

class ClaimHelpQuestionSchema(BaseHelpQuestionSchema):
	'''
	# ClaimHelpQuestionSchema

	Model for claiming help question requests to the API. Inherits from BaseHelpQuestionRequestSchema.
	'''

	# The staff member claiming the help question
	claimed_by: str = Field(description="The name of the staff member claiming the question.")

@app.post("/help/claim")
@appLimiter.limit("100/minute")
def claim_help_question(request: Request, body: ClaimHelpQuestionSchema):
	
	# Get request data
	data: Dict = body.model_dump()
	
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

	# Claim the help question
	success = MCL_HelpManager().claimQuestion(
		questionID=data.get("question_id"),
		claimedBy=data.get("claimed_by")
	)

	# Return success message
	if not success:
		raise HTTPException(
			status_code=500,
			detail=f"Failed to claim help question {data.get('question_id')}"
		)
	return JSONResponse(
		status_code=200,
		content={"status": f"help question {data.get('question_id')} claimed successfully"}
	)

'''
UNCLAIM HELP QUESTION ENDPOINT

This endpoint will allow for unclaiming help questions via question ID. This should be used to mark a help
question as no longer being worked on by a staff member in the case they are unable to complete it.
- "api_token": Your API token for authentication
- "question_id": The ID of the help question to unclaim
'''
@app.post("/help/unclaim")
@appLimiter.limit("100/minute")
def unclaim_help_question(request: Request, body: BaseHelpQuestionSchema):
	
	# Get request data
	data: Dict = body.model_dump()
	
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

	# Unclaim the help question
	success = MCL_HelpManager().unclaimQuestion(
		questionID=data.get("question_id")
	)

	# Return success message
	if not success:
		raise HTTPException(
			status_code=500,
			detail=f"Failed to unclaim help question {data.get('question_id')}"
		)
	return JSONResponse(
		status_code=200,
		content={"status": f"help question {data.get('question_id')} unclaimed successfully"}
	)

'''
LIST HELP QUESTIONS ENDPOINT

This endpoint will allow for listing all current help questions in the system.
- "api_token": Your API token for authentication
'''

class QuestionSchema(BaseModel):
	'''
	# QuestionSchema

	Model for help question listing response.
	'''
	id: int = Field(description="The ID of the help question.")
	player: str = Field(description="The player who asked the help question.")
	content: str = Field(description="The content of the help question.")
	time: datetime = Field(description="The time the help question was asked.")
	status: str = Field(description="The status of the help question.")
	claimedBy: Optional[str] = Field(default=None, description="The staff member who claimed the help question, if any.")
	claimedTime: Optional[int] = Field(default=None, description="The time the help question was claimed, if any.")
	answeredBy: Optional[str] = Field(default=None, description="The staff member who answered the help question, if any.")
	answeredTime: Optional[int] = Field(default=None, description="The time the help question was answered, if any.")
	answer: Optional[str] = Field(default=None, description="The answer to the help question, if any.")

@app.post("/help/list")
@appLimiter.limit("100/minute")
def list_help_questions(request: Request, body: BaseRequestSchema):
	
	# Get request data
	data: Dict = body.model_dump()
	
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

	# Get all help questions
	questions = MCL_HelpManager().getAllQuestions()

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"questions": [QuestionSchema(id=questionId, **details) for questionId, details in questions.items()]}
	)