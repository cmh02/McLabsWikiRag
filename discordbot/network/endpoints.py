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
from discordbot.utils.transcript import generate_html_transcript
from discordbot.network.schemas import UpdateRequest, AdminMessageRequest
from discordbot.components.ticket_view import HelpTicketThreadView, generate_ticket_embed, HELPER_ROLE_IDS

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
		# Retrieve the latest ticket state from Mongo (non-blocking)
		mongo = MCL_MongoManager()
		ticket = await asyncio.to_thread(mongo.getTicket, ticketId)
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
				for attempt in range(5):
					if ticket.conversation and ticket.conversation.messages:
						break
					bot.logger.info(f"Ticket {ticketId} conversation is empty. Retrying fetch in 300ms (attempt {attempt + 1}/5)...")
					await asyncio.sleep(0.3)
					ticket = await asyncio.to_thread(mongo.getTicket, ticketId)

				# Create a new public thread on the ticket channel
				thread = await channel.create_thread(
					name=f"🎫-ticket-{ticketId}",
					type=discord.ChannelType.private_thread,
					auto_archive_duration=10080  # 7 days
				)
				
				# Generate initial embed
				embed = generate_ticket_embed(ticket)
				
				# Send status card in thread with persistent view
				view = HelpTicketThreadView()
				status_msg = await thread.send(embed=embed, view=view)
				
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
				
				# Save thread ID and status message ID to the backend
				await MCL_OutboundRelay().update_ticket_thread(ticketId, thread.id, status_msg.id)

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

			# Find status message in the thread directly by ID
			status_msg = None
			if ticket.statusMessageId:
				try:
					status_msg = bot.get_message(ticket.statusMessageId)
					if not status_msg:
						status_msg = await thread.fetch_message(ticket.statusMessageId)
				except discord.NotFound:
					bot.logger.error(f"Status message with ID {ticket.statusMessageId} not found in thread {thread.id}.")

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

				# Generate and send HTML transcript to player and staff
				try:

					# Resolve usernames for all participants to construct a clean transcript
					user_ids_to_resolve = set()
					if ticket.playerInfo.discordId and ticket.playerInfo.discordId.isdigit():
						user_ids_to_resolve.add(ticket.playerInfo.discordId)
					if ticket.claimedBy and ticket.claimedBy.isdigit():
						user_ids_to_resolve.add(ticket.claimedBy)
					if ticket.closedBy and ticket.closedBy.isdigit():
						user_ids_to_resolve.add(ticket.closedBy)
					
					for msg in ticket.conversation.messages:
						if msg.sender.discordId and msg.sender.discordId.isdigit():
							user_ids_to_resolve.add(msg.sender.discordId)
					
					resolved_names = {}
					for uid in user_ids_to_resolve:
						try:
							user = bot.get_user(int(uid))
							if not user:
								user = await bot.fetch_user(int(uid))
							if user:
								resolved_names[uid] = user.name
						except Exception as resolve_err:
							bot.logger.warning(f"Could not resolve username for Discord ID {uid}: {resolve_err}")

					html_content = generate_html_transcript(ticket, resolved_names)

					# Determine recipients: player and claimed helper
					recipients = set()
					if ticket.playerInfo.discordId and ticket.playerInfo.discordId.isdigit():
						recipients.add(ticket.playerInfo.discordId)
					if ticket.claimedBy and ticket.claimedBy.isdigit():
						recipients.add(ticket.claimedBy)

					# Upload the transcript to the administration/moderation channel first
					admin_channel_id = os.getenv("DISCORD_ADMIN_CHANNEL_ID")
					transcript_url = None
					if admin_channel_id:
						try:
							admin_channel = bot.get_channel(int(admin_channel_id))
							if not admin_channel:
								admin_channel = await bot.fetch_channel(int(admin_channel_id))
							if admin_channel:
								fp = io.BytesIO(html_content.encode('utf-8'))
								discord_file = discord.File(fp=fp, filename=f"transcript-ticket-{ticketId}.html")
								admin_msg = await admin_channel.send(
									content=f"📝 **Ticket #{ticketId} Closed** - Transcript Archive",
									file=discord_file
								)
								if admin_msg.attachments:
									transcript_url = admin_msg.attachments[0].url
									bot.logger.info(f"Uploaded ticket {ticketId} transcript to admin channel: {transcript_url}")
						except Exception as upload_err:
							bot.logger.error(f"Failed to upload ticket {ticketId} transcript to admin channel: {upload_err}")

					for r_id in recipients:
						try:
							user = bot.get_user(int(r_id))
							if not user:
								user = await bot.fetch_user(int(r_id))
							if user:
								creator_mention = f"<@{ticket.playerInfo.discordId}>" if ticket.playerInfo.discordId else "Unknown"
								claimed_mention = f"<@{ticket.claimedBy}>" if ticket.claimedBy else "Not Claimed"
								closed_mention = f"<@{ticket.closedBy}>" if ticket.closedBy else "Unknown"

								if transcript_url:
									# Send premium embed with a link button to the hosted transcript
									dm_embed = discord.Embed(
										title=f"🎫 Ticket #{ticketId} Closed",
										description="Your help ticket has been successfully closed. A complete styled transcript of the conversation is available via the button below.",
										color=discord.Color.red(),
										timestamp=datetime.now(timezone.utc)
									)
									dm_embed.add_field(name="Opened By", value=creator_mention, inline=True)
									dm_embed.add_field(name="Claimed By", value=claimed_mention, inline=True)
									dm_embed.add_field(name="Closed By", value=closed_mention, inline=True)
									dm_embed.set_footer(text="MCLabs Ticket Archiver")

									# Create view with link button
									view = discord.ui.View()
									view.add_item(discord.ui.Button(label="View Ticket Transcript", url=transcript_url, emoji="📄"))

									await user.send(embed=dm_embed, view=view)
									bot.logger.info(f"Successfully sent ticket {ticketId} transcript DM with Link Button to user {r_id}.")
								else:
									# Fallback: Send the file directly in the DM if upload failed
									fp = io.BytesIO(html_content.encode('utf-8'))
									discord_file = discord.File(fp=fp, filename=f"transcript-ticket-{ticketId}.html")

									dm_embed = discord.Embed(
										title=f"🎫 Ticket #{ticketId} Closed",
										description="Your help ticket has been successfully closed. A complete styled transcript of the conversation has been attached below for your records.",
										color=discord.Color.red(),
										timestamp=datetime.now(timezone.utc)
									)
									dm_embed.add_field(name="Opened By", value=creator_mention, inline=True)
									dm_embed.add_field(name="Claimed By", value=claimed_mention, inline=True)
									dm_embed.add_field(name="Closed By", value=closed_mention, inline=True)
									dm_embed.set_footer(text="MCLabs Ticket Archiver")

									await user.send(embed=dm_embed, file=discord_file)
									bot.logger.info(f"Successfully sent ticket {ticketId} transcript DM as file attachment to user {r_id} (fallback).")
						except discord.Forbidden:
							bot.logger.warning(f"Could not send DM to user {r_id} (DMs are likely disabled/restricted).")
						except Exception as dm_err:
							bot.logger.error(f"Failed to send DM transcript to user {r_id}: {dm_err}")
				except Exception as trans_err:
					bot.logger.exception(f"Error handling ticket {ticketId} transcript: {trans_err}")

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
