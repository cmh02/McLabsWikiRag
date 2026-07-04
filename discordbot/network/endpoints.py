'''
MCLabs Discord Bot - API Endpoints

Author: Chris Hinkson @cmh02
'''

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from discordbot.network.limiter import limiter
from discordbot.network.router import MclRouter
from discordbot.network.schemas import UpdateRequest

'''
# API ROUTER

Creation of the API router for all endpoints.
'''
router: APIRouter = MclRouter.getNewRouter()


'''
# WAKEUP ENDPOINT

This endpoint is used solely for waking up the API when asleep on Railway.
'''
@router.post("/wakeup")
@limiter.limit("50/minute")
def wakeup(request: Request):
	
	# Log wakeup attempt
	request.app.state.logger.debug("Discord bot wakeup request received!")
	
	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "awake"}
	)


'''
# UPDATE ENDPOINT

This endpoint receives relay notifications from the backend.
'''
@router.post("/update")
@limiter.limit("100/minute")
def update(request: Request, updateRequest: UpdateRequest):
	
	# Validate and extract request data
	data = updateRequest.model_dump()
	updateId = data.get("update_id")
	ticketAction = data.get("ticket_action")
	ticketId = data.get("ticket_id")

	# Placeholder for follow-up bot logic
	request.app.state.logger.info(
		f"Received relay update {updateId} for ticket {ticketId} with action {ticketAction}."
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "success"}
	)
