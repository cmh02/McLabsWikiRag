'''
MCLabs Wiki RAG - Flask API

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
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
from src.schemas import BaseRequestSchema, BaseHelpQuestionSchema, QuestionSchema

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
WAKEUP ENDPOINT

This endpoint is used solely for waking up the API when asleep on Railway. It still needs authentication.
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
	
@app.post("/help/add")
@appLimiter.limit("100/minute")
def add_help_question(request: Request, body: AddHelpQuestionSchema):
	
	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Get request data
	data: Dict = body.model_dump()
	
	# Add the help question
	success = MCL_HelpManager().addQuestion(
		questionID=data.get("question_id"),
		questionPlayer=data.get("question_player"),
		questionContent=data.get("question_content"),
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
	
	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Get request data
	data: Dict = body.model_dump()

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
	
	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Get request data
	data: Dict = body.model_dump()

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
	
	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Get request data
	data: Dict = body.model_dump()

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
	
	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Get request data
	data: Dict = body.model_dump()

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
@app.post("/help/list")
@appLimiter.limit("100/minute")
def list_help_questions(request: Request, body: BaseRequestSchema):
	
	# Verify request
	verifyRequest(request=request, verifyToken=True, verifyIpAddress=False)

	# Get request data
	data: Dict = body.model_dump()

	# Get all help questions
	questions = MCL_HelpManager().getAllQuestions()

	# Return success message
	return JSONResponse(
		status_code=200,
		content=jsonable_encoder({"questions": [QuestionSchema(id=questionId, **details).model_dump() for questionId, details in questions.items()]})
	)