'''
MCLabs Discord Bot - API Endpoints

Author: Chris Hinkson @cmh02
'''

import os
import discord
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from discordbot.network.limiter import limiter
from discordbot.network.router import MclRouter
from discordbot.network.schemas import UpdateRequest, AdminMessageRequest

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
async def update(request: Request, updateRequest: UpdateRequest):
	
	# Validate and extract request data
	data = updateRequest.model_dump()
	updateId = data.get("update_id")
	ticketAction = data.get("ticket_action")
	ticketId = data.get("ticket_id")

	# For now, just log
	request.app.state.logger.info(f"Received relay update {updateId} for ticket {ticketId} with action {ticketAction}.")

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "success"}
	)


'''
# ADMIN MESSAGE ENDPOINT

This endpoint allows authenticated clients to send a message to the Discord admin channel.
'''
@router.post("/send_admin_message")
@limiter.limit("30/minute")
async def send_admin_message(request: Request, payload: AdminMessageRequest):
	
	# Get bot instance from request app state
	bot = request.app.state.bot
	if not bot:
		raise HTTPException(
			status_code=500,
			detail="Discord bot client not initialized"
		)

	admin_channel_id = os.getenv("DISCORD_ADMIN_CHANNEL_ID")
	if not admin_channel_id:
		bot.logger.error("DISCORD_ADMIN_CHANNEL_ID environment variable is not set.")
		raise HTTPException(
			status_code=500,
			detail="Server configuration error: Admin channel not configured"
		)

	try:
		channel_id = int(admin_channel_id)
	except ValueError:
		bot.logger.error("DISCORD_ADMIN_CHANNEL_ID is not a valid integer.")
		raise HTTPException(
			status_code=500,
			detail="Server configuration error: Invalid admin channel ID"
		)

	# Try to get the channel from the cache first, then fetch it if not cached
	channel = bot.get_channel(channel_id)
	if not channel:
		try:
			channel = await bot.fetch_channel(channel_id)
		except Exception as e:
			bot.logger.exception(f"Failed to fetch admin channel with ID {channel_id}: {e}")
			raise HTTPException(
				status_code=404,
				detail="Admin channel not found on Discord"
			)

	if not channel:
		raise HTTPException(
			status_code=404,
			detail="Admin channel not found"
		)

	if not isinstance(channel, discord.TextChannel):
		raise HTTPException(
			status_code=400,
			detail="Admin channel is not a text channel"
		)

	try:
		await channel.send(payload.message)
		bot.logger.info(f"Successfully sent admin message: {payload.message}")
	except Exception as e:
		bot.logger.exception(f"Failed to send message to admin channel: {e}")
		raise HTTPException(
			status_code=500,
			detail="Failed to send message to Discord admin channel"
		)

	return JSONResponse(
		status_code=200,
		content={"status": "success", "message": "Message sent to admin channel"}
	)
