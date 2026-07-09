'''
MCLabs Wiki RAG - API Endpoints

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
import uuid
from typing import Dict
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Request, HTTPException

from src.network.relay import MCL_OutboundRelay
from src.network.security import verifyRequest
from src.internal.helpmanager import MCL_HelpManager
from src.utils.datatypes import Message, PlayerInfo
from src.network.schemas import BaseHelpQuestionSchema, QuestionSchema
from src.utils.enum import TicketType, TicketStatus, TicketFeedback
from src.network.limiter import limiter
from src.network.router import MclRouter

'''
# API ROUTER

Creation of the API router for all endpoints.
'''
router: APIRouter = MclRouter.getNewRouter()



'''
# WAKEUP ENDPOINT

This endpoint is used solely for waking up the API when asleep on Railway.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests
'''
@router.post("/wakeup")
@limiter.limit("50/minute")
def wakeup(request: Request):
	
	# Log for debugging
	request.app.state.logger.debug(f"Received wakeup request! \nRequest: {request}")

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "awake"}
	)

'''
# RAG QUERY ENDPOINT

There is a singular endpoint for querying the RAG system.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "question": The question you want to ask (max 256 characters)
- "include_context": (optional) Boolean to include context chunks in the response
'''

class RagQuerySchema(BaseModel):
	'''
	# RagQuerySchema

	Model for query requests to the RAG API.
	'''

	# The question to ask
	question: str = Field(description="A search query, such as a question..")

	# Whether to include context chunks in the response
	include_context: bool = Field(default=False, description="Whether to include context chunks in the response.")

@router.post("/query")
@limiter.limit("100/minute")
def query(request: Request, body: RagQuerySchema):

	# Get the request data
	data: Dict = body.model_dump()

	# Print for debugging
	request.app.state.logger.debug(f"Received query request! \nRequest: {request}")

	# Get the question from the request
	question = data.get("question")
	includeContext = data.get("include_context", "False")

	# Log question for debugging``
	request.app.state.logger.debug(f"Received question: {question}")

	# If no question provided, return error
	if not question:
		
        # Log missing question
		request.app.state.logger.debug("No question provided in request")

		# Return error
		raise HTTPException(
			status_code=400, 
			detail="Missing 'question'"
		)

	# If question is too long, return error
	if len(question) > 256:

		# Log too long question
		request.app.state.logger.debug("Question is too long (max 256 characters)!")

		# Return error
		raise HTTPException(
			status_code=400, 
			detail="Question is too long (max 256 characters)!"
		)

	# Get the response from the RAG pipeline and return
	result, topChunks = request.app.state.InstanceRag.queryPipeline(question)
     
	# Log answer for debugging
	request.app.state.logger.debug(f"Answer to question {question}: {result}")	

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

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "type": The type of ticket to be created. Must be one of TicketType enum.
- "playerInfo": The identification details of the player creating the ticket.
'''

class PlayerInfoSchema(BaseModel):
	'''
	# PlayerInfoSchema

	Model for player identification details.
	'''
	minecraftUsername: Optional[str] = Field(default=None, description="The Minecraft username of the player.")
	minecraftUUID: Optional[str] = Field(default=None, description="The Minecraft UUID of the player.")
	discordUsername: Optional[str] = Field(default=None, description="The Discord username of the player.")
	discordId: Optional[str] = Field(default=None, description="The Discord ID of the player.")

class CreateTicketSchema(BaseModel):
	'''
	# CreateTicketSchema

	Model for creating new help tickets.
	'''

	# The type of ticket to be created
	type: TicketType = Field(description="The type of ticket to be created.")

	# The identification details of the player creating the ticket
	playerInfo: PlayerInfoSchema = Field(description="The identification details of the player creating the ticket.")

@router.post("/create_ticket")
@limiter.limit("100/minute")
def create_ticket(request: Request, body: CreateTicketSchema):

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketType: TicketType | None = data.get("type")
	playerInfoData: Dict | None = data.get("playerInfo")

	# Validate that we got a ticket type and playerInfo
	if not ticketType:
		raise HTTPException(
			status_code=400,
			detail="Missing 'type'"
		)
	if not playerInfoData:
		raise HTTPException(
			status_code=400,
			detail="Missing 'playerInfo'"
		)

	# Instantiate PlayerInfo datatype
	playerInfo = PlayerInfo(
		minecraftUsername=playerInfoData.get("minecraftUsername"),
		minecraftUUID=playerInfoData.get("minecraftUUID"),
		discordUsername=playerInfoData.get("discordUsername"),
		discordId=playerInfoData.get("discordId")
	)

	# Create ticket
	ticketId = MCL_HelpManager().createTicket(
		type=ticketType,
		playerInfo=playerInfo
	)

	# Return ticketId in response
	return JSONResponse(
		status_code=200,
		content={
			"status": "success",
			"ticketId": ticketId
		}
	)

class UpdateTicketThreadSchema(BaseModel):
	'''
	# UpdateTicketThreadSchema

	Model for updating a ticket with its Discord thread ID.
	'''
	ticketId: int = Field(description="The ID of the ticket to update.")
	threadId: int = Field(description="The Discord thread ID to link to the ticket.")

@router.post("/update_ticket_thread")
@limiter.limit("100/minute")
def update_ticket_thread(request: Request, body: UpdateTicketThreadSchema):

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int | None = data.get("ticketId")
	threadId: int | None = data.get("threadId")

	# Validate that we got a ticketId and threadId
	if not ticketId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'ticketId'"
		)
	if not threadId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'threadId'"
		)

	# Update ticket thread
	MCL_HelpManager().updateTicketThread(
		ticketId=ticketId,
		threadId=threadId
	)

	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)



'''
# CLOSE TICKET ENDPOINT

This endpoint can be used for closing an existing help ticket.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "ticketId": The ID of the ticket to be closed.
- "closedBy": The UUID of the player closing the ticket.
'''

class CloseTicketSchema(BaseModel):
	'''
	# CloseTicketSchema

	Model for closing help tickets.
	'''

	# The ID of the ticket to be closed
	ticketId: int = Field(description="The ID of the ticket to be closed.")

	# The UUID of the player closing the ticket
	closedBy: str = Field(description="The UUID of the player closing the ticket.")

@router.post("/close_ticket")
@limiter.limit("100/minute")
def close_ticket(request: Request, body: CloseTicketSchema):
	
	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int | None = data.get("ticketId")
	closedBy: str | None = data.get("closedBy")

	# Validate that we got a ticketId and closedBy
	if not ticketId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'ticketId'"
		)
	if not closedBy:
		raise HTTPException(
			status_code=400,
			detail="Missing 'closedBy'"
		)

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



'''
# CLAIM TICKET ENDPOINT

This endpoint can be used for claiming an existing help ticket.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "ticketId": The ID of the ticket to be claimed.
- "claimedBy": The UUID of the player claiming the ticket.
'''

class ClaimTicketSchema(BaseModel):
	'''
	# ClaimTicketSchema

	Model for claiming help tickets.
	'''

	# The ID of the ticket to be claimed
	ticketId: int = Field(description="The ID of the ticket to be claimed.")

	# The UUID of the player claiming the ticket
	claimedBy: str = Field(description="The UUID of the player claiming the ticket.")

@router.post("/claim_ticket")
@limiter.limit("100/minute")
def claim_ticket(request: Request, body: ClaimTicketSchema):
	
	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int | None = data.get("ticketId")
	claimedBy: str | None = data.get("claimedBy")

	# Validate that we got a ticketId and claimedBy
	if not ticketId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'ticketId'"
		)
	if not claimedBy:
		raise HTTPException(
			status_code=400,
			detail="Missing 'claimedBy'"
		)

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



'''
# UNCLAIM TICKET ENDPOINT

This endpoint can be used for unclaiming an existing help ticket.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "ticketId": The ID of the ticket to be unclaimed.
'''

class UnclaimTicketSchema(BaseModel):
	'''
	# UnclaimTicketSchema

	Model for unclaiming help tickets.
	'''

	# The ID of the ticket to be unclaimed
	ticketId: int = Field(description="The ID of the ticket to be unclaimed.")

@router.post("/unclaim_ticket")
@limiter.limit("100/minute")
def unclaim_ticket(request: Request, body: UnclaimTicketSchema):

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int | None = data.get("ticketId")

	# Validate that we got a ticketId
	if not ticketId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'ticketId'"
		)

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



'''
# SET TICKET FEEDBACK ENDPOINT

This endpoint can be used for setting feedback for an existing help ticket.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "ticketId": The ID of the ticket to set feedback for.
- "feedback": The feedback to be set. Must be one of TicketFeedback enum.
'''

class SetTicketFeedbackSchema(BaseModel):
	'''
	# SetTicketFeedbackSchema

	Model for setting help ticket feedback.
	'''

	# The ID of the ticket to set feedback for
	ticketId: int = Field(description="The ID of the ticket to set feedback for.")

	# The feedback to be set
	feedback: TicketFeedback = Field(description="The feedback to be set.")

@router.post("/set_ticket_feedback")
@limiter.limit("100/minute")
def set_ticket_feedback(request: Request, body: SetTicketFeedbackSchema):

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int | None = data.get("ticketId")
	feedback: TicketFeedback | None = data.get("feedback")

	# Validate that we got a ticketId and feedback
	if not ticketId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'ticketId'"
		)
	if not feedback:
		raise HTTPException(
			status_code=400,
			detail="Missing 'feedback'"
		)

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



'''
# APPEND TICKET MESSAGE ENDPOINT

This endpoint can be used for appending messages to existing help tickets.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "ticketId": The ID of the ticket to append a message to.
- "content": The content of the message to append.
- "sentBy": The UUID of the player sending the message.
'''

class AppendTicketMessageSchema(BaseModel):
	'''
	# AppendTicketMessageSchema

	Model for appending messages to help tickets.
	'''

	# The ID of the ticket to append a message to
	ticketId: int = Field(description="The ID of the ticket to append a message to.")

	# The content of the message to append
	content: str = Field(description="The content of the message to append.")

	# The player information of the sender
	sender: PlayerInfoSchema = Field(description="The identification details of the sender.")

@router.post("/append_ticket_message")
@limiter.limit("500/minute")
def append_ticket_message(request: Request, body: AppendTicketMessageSchema):
	
	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int | None = data.get("ticketId")
	content: str | None = data.get("content")
	senderData: Dict | None = data.get("sender")

	# Validate that we got a ticketId, content, and sender
	if not ticketId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'ticketId'"
		)
	if not content:
		raise HTTPException(
			status_code=400,
			detail="Missing 'content'"
		)
	if not senderData:
		raise HTTPException(
			status_code=400,
			detail="Missing 'sender'"
		)

	# Instantiate PlayerInfo datatype
	playerInfo = PlayerInfo(
		minecraftUsername=senderData.get("minecraftUsername"),
		minecraftUUID=senderData.get("minecraftUUID"),
		discordUsername=senderData.get("discordUsername"),
		discordId=senderData.get("discordId")
	)

	# Create message object
	message = Message(
		timestamp=datetime.now(timezone.utc).timestamp(),
		sender=playerInfo,
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



'''
# GET TICKET ENDPOINT

This endpoint can be used for retrieving information about existing help tickets.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "ticketId": The ID of the ticket to retrieve information for.
'''

class GetTicketSchema(BaseModel):
	'''
	# GetTicketSchema

	Model for getting help ticket information.
	'''

	# The ID of the ticket to get
	ticketId: int = Field(description="The ID of the ticket to get.")

@router.post("/get_ticket")
@limiter.limit("100/minute")
def get_ticket(request: Request, body: GetTicketSchema):

	# Extract data from request body
	data: Dict = body.model_dump()
	ticketId: int | None = data.get("ticketId")

	# Validate that we got a ticketId
	if not ticketId:
		raise HTTPException(
			status_code=400,
			detail="Missing 'ticketId'"
		)

	# Get ticket information
	ticketInfo: Dict = MCL_HelpManager().getTicketInfo(
		ticketId=ticketId
	)

	# If ticket not found, return error
	if ticketInfo is None:
		
		# Log ticket not found
		request.app.state.logger.debug(f"Ticket with ID {ticketId} not found!")

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



'''
# ACKNOWLEDGE UPDATE ENDPOINT

This endpoint can be used for acknowledging updates from external systems.

## Request Headers (via router)
- 'Authorization': API token for authentication
- 'User-Agent': User agent string to identify discord versus minecraft requests

## JSON Body Parameters
- "guid": The unique ID of the update to acknowledge.
'''

class AcknowledgeUpdateSchema(BaseModel):
	'''
	# AcknowledgeUpdateSchema

	Model for acknowledging updates from external systems.
	'''

	# The unique ID of the update to acknowledge
	guid: str = Field(description="The unique ID of the update to acknowledge.")

@router.post("/acknowledge_update")
@limiter.limit("100/minute")
def acknowledge_update(request: Request, body: AcknowledgeUpdateSchema):

	# Extract data from request body
	data: Dict = body.model_dump()
	guid: str | None = data.get("guid")

	# Validate that we got a guid
	if not guid:
		raise HTTPException(
			status_code=400,
			detail="Missing 'guid'"
		)

	# Try parsing the guid into a uuid
	try:
		parsedGuid: uuid.UUID = uuid.UUID(guid)
	except ValueError:
		raise HTTPException(
			status_code=400,
			detail="Invalid 'guid' format"
		)

	# Acknowledge update
	MCL_OutboundRelay().acknowledge(
		updateId=parsedGuid
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)