'''
MCLabs Discord Bot - API Endpoints

Author: Chris Hinkson @cmh02
'''

import os
import io
import asyncio
import discord
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, HTTPException

from mcl_common.limiter import limiter
from mcl_common.router import MclRouter
from mcl_common.enum import TicketAction
from mcl_common.mongo import MCL_MongoManager
from discordbot.network.relay import MCL_OutboundRelay
from discordbot.network.schemas import UpdateRequest, AdminMessageRequest
from discordbot.components.ticket_view import (
	HelpTicketThreadView,
	generate_ticket_embed,
	HELPER_ROLE_IDS,
	handle_discord_create,
	handle_discord_claim,
	handle_discord_unclaim,
	handle_discord_close,
	handle_discord_feedback,
	handle_discord_newmessage,
	handle_discord_playerinfo_update
)

'''
# API ROUTER

Creation of the API router for all endpoints.
'''
router: APIRouter = MclRouter.getNewRouter()

# Simple health check at root level required by network
@router.get("/")
@limiter.limit("50/minute")
async def health_check(request: Request):
    return {"status": "ok"}



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
	updateId = updateRequest.update_id
	ticketAction = updateRequest.ticket_action
	ticketId = updateRequest.ticket_id

	# Get bot instance from request app state
	bot = request.app.state.bot
	if not bot:
		raise HTTPException(
			status_code=500,
			detail="Discord bot client not initialized"
		)

	bot.logger.info(f"Received relay update {updateId} for ticket {ticketId} with action {ticketAction}.")

	try:
		# Process action-specific handlers
		if ticketAction == TicketAction.CREATE.value:
			await handle_discord_create(bot, ticketId)
		elif ticketAction == TicketAction.CLAIM.value:
			await handle_discord_claim(bot, ticketId)
		elif ticketAction == TicketAction.UNCLAIM.value:
			await handle_discord_unclaim(bot, ticketId)
		elif ticketAction == TicketAction.CLOSE.value:
			await handle_discord_close(bot, ticketId)
		elif ticketAction == TicketAction.FEEDBACK.value:
			await handle_discord_feedback(bot, ticketId)
		elif ticketAction == TicketAction.NEWMESSAGE.value:
			await handle_discord_newmessage(bot, ticketId)
		elif ticketAction == TicketAction.PLAYERINFOUPDATE.value:
			await handle_discord_playerinfo_update(bot, ticketId)
		else:
			bot.logger.warning(f"Unhandled relay action {ticketAction} for ticket {ticketId}.")

		# Acknowledge the update back to the backend RAG API
		# This clears it from the relay queue
		relay_success = await MCL_OutboundRelay().acknowledge_update(str(updateId))
		if not relay_success:
			bot.logger.error(f"Failed to acknowledge update {updateId} to the backend.")

	except Exception as e:
		bot.logger.exception(f"Error processing bot update payload for ticket {ticketId}: {e}")
		raise HTTPException(status_code=500, detail=str(e))

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
