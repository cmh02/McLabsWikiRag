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
from src.datatypes import Message
from src.schemas import BaseHelpQuestionSchema, QuestionSchema
from src.enum import TicketType, TicketStatus, TicketFeedback, UpdateSource

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



'''
# CREATE TICKET ENDPOINT

This endpoint can be used for making a new help ticket.

## Request Headers
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "update_source": The source of the update. Must be one of UpdateSource enum.
- "type": The type of ticket to be created. Must be one of TicketType enum.
- "player": The UUID of the player creating the ticket.
'''

class CreateTicketSchema(BaseModel):
	'''
	# CreateTicketSchema

	Model for creating new help tickets. Inherits authentication from BaseModel.
	'''

	# The type of ticket to be created
	type: TicketType = Field(description="The type of ticket to be created.")

	# The source of the update
	update_source: UpdateSource = Field(description="The source of the update.")

	# The UUID of the player creating the ticket
	player: str = Field(description="The UUID of the player creating the ticket.")

@app.post("/create_ticket")
@appLimiter.limit("100/minute")
def create_ticket(request: Request, body: CreateTicketSchema):
	
	# Verify request
	verifyRequest(
		request=request,
		verifyToken=True,
		verifyIpAddress=False
	)

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketType: TicketType = data.get("type")
	updateSource: UpdateSource = data.get("update_source")
	player: str = data.get("player")

	# Create ticket
	ticketId = MCL_HelpManager().createTicket(
		type=ticketType,
		player=player
	)

	# Return ticketId in response
	return JSONResponse(
		status_code=200,
		content={
			"status": "success",
			"ticketId": ticketId
		}
	)

class CloseTicketSchema(BaseModel):
	'''
	# CloseTicketSchema

	Model for closing help tickets. Inherits authentication from BaseModel.
	'''

	# The ID of the ticket to be closed
	ticketId: int = Field(description="The ID of the ticket to be closed.")

	# The source of the update
	update_source: UpdateSource = Field(description="The source of the update.")

	# The UUID of the player closing the ticket
	closedBy: str = Field(description="The UUID of the player closing the ticket.")

@app.post("/close_ticket")
@appLimiter.limit("100/minute")
def close_ticket(request: Request, body: CloseTicketSchema):
	
	# Verify request
	verifyRequest(
		request=request,
		verifyToken=True,
		verifyIpAddress=False
	)

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int = data.get("ticketId")
	updateSource: UpdateSource = data.get("update_source")
	closedBy: str = data.get("closedBy")

	# Close ticket
	MCL_HelpManager().closeTicket(
		ticketId=ticketId,
		closedBy=closedBy
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)

class ClaimTicketSchema(BaseModel):
	'''
	# ClaimTicketSchema

	Model for claiming help tickets. Inherits authentication from BaseModel.
	'''

	# The ID of the ticket to be claimed
	ticketId: int = Field(description="The ID of the ticket to be claimed.")

	# The source of the update
	update_source: UpdateSource = Field(description="The source of the update.")

	# The UUID of the player claiming the ticket
	claimedBy: str = Field(description="The UUID of the player claiming the ticket.")

@app.post("/claim_ticket")
@appLimiter.limit("100/minute")
def claim_ticket(request: Request, body: ClaimTicketSchema):
	
	# Verify request
	verifyRequest(
		request=request,
		verifyToken=True,
		verifyIpAddress=False
	)

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int = data.get("ticketId")
	updateSource: UpdateSource = data.get("update_source")
	claimedBy: str = data.get("claimedBy")

	# Claim ticket
	MCL_HelpManager().claimTicket(
		ticketId=ticketId,
		claimedBy=claimedBy
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)

class UnclaimTicketSchema(BaseModel):
	'''
	# UnclaimTicketSchema

	Model for unclaiming help tickets. Inherits authentication from BaseModel.
	'''

	# The ID of the ticket to be unclaimed
	ticketId: int = Field(description="The ID of the ticket to be unclaimed.")

	# The source of the update
	update_source: UpdateSource = Field(description="The source of the update.")

@app.post("/unclaim_ticket")
@appLimiter.limit("100/minute")
def unclaim_ticket(request: Request, body: UnclaimTicketSchema):
	
	# Verify request
	verifyRequest(
		request=request,
		verifyToken=True,
		verifyIpAddress=False
	)

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int = data.get("ticketId")
	updateSource: UpdateSource = data.get("update_source")

	# Unclaim ticket
	MCL_HelpManager().unclaimTicket(
		ticketId=ticketId
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)

class SetTicketFeedbackSchema(BaseModel):
	'''
	# SetTicketFeedbackSchema

	Model for setting help ticket feedback. Inherits authentication from BaseModel.
	'''

	# The ID of the ticket to set feedback for
	ticketId: int = Field(description="The ID of the ticket to set feedback for.")

	# The feedback to be set
	feedback: TicketFeedback = Field(description="The feedback to be set.")

	# The source of the update
	update_source: UpdateSource = Field(description="The source of the update.")

@app.post("/set_ticket_feedback")
@appLimiter.limit("100/minute")
def set_ticket_feedback(request: Request, body: SetTicketFeedbackSchema):
	
	# Verify request
	verifyRequest(
		request=request,
		verifyToken=True,
		verifyIpAddress=False
	)

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int = data.get("ticketId")
	feedback: TicketFeedback = data.get("feedback")
	updateSource: UpdateSource = data.get("update_source")

	# Set ticket feedback
	MCL_HelpManager().setTicketFeedback(
		ticketId=ticketId,
		feedback=feedback
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)

class AppendTicketMessageSchema(BaseModel):
	'''
	# AppendTicketMessageSchema

	Model for appending messages to help tickets. Inherits authentication from BaseModel.
	'''

	# The ID of the ticket to append a message to
	ticketId: int = Field(description="The ID of the ticket to append a message to.")

	# The content of the message to append
	content: str = Field(description="The content of the message to append.")

	# The source of the update
	update_source: UpdateSource = Field(description="The source of the update.")

	# The UUID of the player sending the message
	sentBy: str = Field(description="The UUID of the player sending the message.")

@app.post("/append_ticket_message")
@appLimiter.limit("500/minute")
def append_ticket_message(request: Request, body: AppendTicketMessageSchema):
	
	# Verify request
	verifyRequest(
		request=request,
		verifyToken=True,
		verifyIpAddress=False
	)

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int = data.get("ticketId")
	content: str = data.get("content")
	updateSource: UpdateSource = data.get("update_source")
	sentBy: str = data.get("sentBy")

	# Create message object
	message = Message(
		timestamp=datetime.utcnow().isoformat(),
		sender=sentBy,
		content=content
	)

	# Add message to ticket conversation
	MCL_HelpManager().addMessageToConversation(
		ticketId=ticketId,
		message=message
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)

class GetTicketSchema(BaseModel):
	'''
	# GetTicketSchema

	Model for getting help ticket information. Inherits authentication from BaseModel.
	'''

	# The ID of the ticket to get
	ticketId: int = Field(description="The ID of the ticket to get.")

@app.post("/get_ticket")
@appLimiter.limit("100/minute")
def get_ticket(request: Request, body: GetTicketSchema):
	
	# Verify request
	verifyRequest(
		request=request,
		verifyToken=True,
		verifyIpAddress=False
	)

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int = data.get("ticketId")

	# Get ticket information
	ticketInfo: Dict = MCL_HelpManager().getTicketInfo(
		ticketId=ticketId
	)

	# If ticket not found, return error
	if ticketInfo is None:
		
		# Log ticket not found
		app.state.logger.debug(f"Ticket with ID {ticketId} not found!")

		# Return error
		raise HTTPException(
			status_code=404,
			detail=f"Ticket with ID {ticketId} not found!"
		)

	# Return ticket information
	return JSONResponse(
		status_code=200,
		content=jsonable_encoder(
			obj=ticketInfo
		)
	)