'''
MCLabs Discord Bot - API Endpoints

Author: Chris Hinkson @cmh02
'''

import os
import discord
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from mcl_common.limiter import limiter
from mcl_common.router import MclRouter
from discordbot.network.schemas import UpdateRequest, AdminMessageRequest
from mcl_common.mongo import MCL_MongoManager
from discordbot.network.relay import MCL_OutboundRelay
from discordbot.components.ticket_view import HelpTicketThreadView, generate_ticket_embed, HELPER_ROLE_IDS
from mcl_common.enum import TicketAction

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
		# Retrieve the latest ticket state from Mongo
		mongo = MCL_MongoManager()
		ticket = mongo.getTicket(ticketId)
		if not ticket:
			bot.logger.error(f"Ticket with ID {ticketId} not found in database for update {updateId}.")
			raise HTTPException(status_code=404, detail=f"Ticket {ticketId} not found")

		# Check the ticket channel
		ticket_channel_id = os.getenv("DISCORD_TICKET_CHANNEL_ID")
		if not ticket_channel_id:
			bot.logger.error("DISCORD_TICKET_CHANNEL_ID environment variable is not set.")
			raise HTTPException(status_code=500, detail="Ticket channel not configured")
		
		try:
			channel_id = int(ticket_channel_id)
		except ValueError:
			bot.logger.error("DISCORD_TICKET_CHANNEL_ID is not a valid integer.")
			raise HTTPException(status_code=500, detail="Invalid ticket channel ID")

		channel = bot.get_channel(channel_id)
		if not channel:
			channel = await bot.fetch_channel(channel_id)

		if not channel or not isinstance(channel, discord.TextChannel):
			bot.logger.error(f"Ticket channel with ID {channel_id} not found or is not a text channel.")
			raise HTTPException(status_code=500, detail="Invalid ticket channel configured")

		# 1. Handle CREATE action
		if ticketAction == TicketAction.CREATE.value:
			if ticket.threadId:
				bot.logger.info(f"Ticket {ticketId} already has thread {ticket.threadId}. Skipping thread creation.")
			else:
				# Wait up to 1.5s for the initial question message to be committed to MongoDB
				import asyncio
				for attempt in range(5):
					if ticket.conversation and ticket.conversation.messages:
						break
					bot.logger.info(f"Ticket {ticketId} conversation is empty. Retrying fetch in 300ms (attempt {attempt + 1}/5)...")
					await asyncio.sleep(0.3)
					ticket = mongo.getTicket(ticketId)

				# Create a new public thread on the ticket channel
				thread = await channel.create_thread(
					name=f"🎫-ticket-{ticketId}",
					type=discord.ChannelType.public_thread,
					auto_archive_duration=10080  # 7 days
				)
				
				# Generate initial embed
				embed = generate_ticket_embed(ticket)
				
				# Send status card in thread with persistent view
				view = HelpTicketThreadView()
				await thread.send(embed=embed, view=view)
				
				# Send and delete a temporary ping to add the creator and staff to the thread
				# so that it is instantly visible in their channel sidebar.
				mentions = []
				if ticket.playerInfo.discordId:
					mentions.append(f"<@{ticket.playerInfo.discordId}>")
				for role_id in HELPER_ROLE_IDS:
					mentions.append(f"<@&{role_id}>")
				
				if mentions:
					try:
						ping_msg = await thread.send(" ".join(mentions))
						await ping_msg.delete()
					except Exception as e:
						bot.logger.error(f"Failed to send/delete transient thread pings: {e}")
				
				bot.logger.info(f"Created Discord thread {thread.id} for ticket {ticketId}.")
				
				# Save thread ID to the backend
				await MCL_OutboundRelay().update_ticket_thread(ticketId, thread.id)

		# 2. Handle status updates (CLAIM, UNCLAIM, CLOSE, FEEDBACK, NEWMESSAGE)
		else:
			thread_id = ticket.threadId
			if not thread_id:
				bot.logger.warning(f"No threadId associated with ticket {ticketId} for action {ticketAction}. Cannot process.")
				return JSONResponse(status_code=400, content={"status": "error", "message": "Ticket has no thread ID"})

			thread = bot.get_channel(thread_id)
			if not thread:
				thread = await bot.fetch_channel(thread_id)

			if not thread or not isinstance(thread, discord.Thread):
				bot.logger.error(f"Thread with ID {thread_id} not found or is not a thread.")
				raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

			# Find status message in the thread
			status_msg = None
			async for message in thread.history(limit=20, oldest_first=True):
				if message.author == bot.user and message.embeds:
					status_msg = message
					break

			# Edit status card embed
			if status_msg:
				embed = generate_ticket_embed(ticket)
				await status_msg.edit(embed=embed)
				bot.logger.info(f"Updated status card embed for ticket {ticketId} thread.")

			# Perform action-specific operations
			if ticketAction == TicketAction.CLAIM.value:
				# Notify the thread
				claimed_by = ticket.claimedBy or "Unknown Staff"
				await thread.send(f"🙋‍♂️ Ticket has been claimed by <@{claimed_by}>.")

			elif ticketAction == TicketAction.UNCLAIM.value:
				# Notify the thread
				await thread.send("🚫 Ticket has been unclaimed.")

			elif ticketAction == TicketAction.CLOSE.value:
				# Notify the thread
				closed_by = ticket.closedBy or "Unknown"
				await thread.send(f"🔒 Ticket has been closed by <@{closed_by}>.")
				# Archive and lock the thread
				await thread.edit(archived=True, locked=True)
				bot.logger.info(f"Archived and locked Discord thread {thread.id} for ticket {ticketId}.")

			elif ticketAction == TicketAction.NEWMESSAGE.value:
				# Send incoming message to the thread if not a duplicate
				if ticket.conversation and ticket.conversation.messages:
					last_msg = ticket.conversation.messages[-1]
					
					# Get last message in Discord thread to check for duplicate
					last_discord_msg = None
					async for msg in thread.history(limit=1):
						last_discord_msg = msg

					is_duplicate = False
					if last_discord_msg and last_msg.sender.discordId:
						# If author ID matches and content matches, it originated from Discord
						if str(last_discord_msg.author.id) == last_msg.sender.discordId and last_discord_msg.content == last_msg.content:
							is_duplicate = True

					# Find the original question message (first message by the player)
					original_msg = None
					for msg in ticket.conversation.messages:
						is_sender_match = False
						if msg.sender.minecraftUUID and ticket.playerInfo.minecraftUUID and msg.sender.minecraftUUID == ticket.playerInfo.minecraftUUID:
							is_sender_match = True
						elif msg.sender.discordId and ticket.playerInfo.discordId and msg.sender.discordId == ticket.playerInfo.discordId:
							is_sender_match = True

						if is_sender_match:
							original_msg = msg
							break

					is_original_question = False
					if original_msg and last_msg.timestamp == original_msg.timestamp and last_msg.content == original_msg.content:
						is_original_question = True

					if is_duplicate or is_original_question:
						if is_duplicate:
							bot.logger.info(f"Skipping duplicate message relay for ticket {ticketId}: {last_msg.content}")
						else:
							bot.logger.info(f"Skipping relay of the original question for ticket {ticketId}: {last_msg.content}")
					else:
						# Format the message header depending on source
						sender_name = last_msg.sender.minecraftUsername or last_msg.sender.discordUsername or "Unknown"
						if last_msg.sender.minecraftUsername:
							prefix = f"**[In-Game] {sender_name}**"
						else:
							prefix = f"**{sender_name}**"
						
						await thread.send(f"{prefix}: {last_msg.content}")
						bot.logger.info(f"Relayed new message to Discord thread: {last_msg.content}")

		# 3. Acknowledge the update back to the backend RAG API
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
