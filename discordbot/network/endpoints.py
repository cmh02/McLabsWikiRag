'''
MCLabs Discord Bot - API Endpoints

Author: Chris Hinkson @cmh02
'''

import os
import discord
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
async def update(request: Request, updateRequest: UpdateRequest):
	
	# Validate and extract request data
	data = updateRequest.model_dump()
	updateId = data.get("update_id")
	ticketAction = data.get("ticket_action")
	ticketId = data.get("ticket_id")

	request.app.state.logger.info(
		f"Received relay update {updateId} for ticket {ticketId} with action {ticketAction}."
	)

	bot = request.app.state.bot

	try:
		# Query ticket directly from MongoDB
		from discordbot.internal.mongo import MCL_MongoManager
		mongo = MCL_MongoManager()
		ticket = mongo.getTicket(ticketId)

		if ticket:
			from src.utils.enum import TicketAction
			if ticketAction == TicketAction.CREATE.value:
				# 1. Resolve configured ticket creation channel
				channel_id = os.getenv("DISCORD_TICKET_CHANNEL_ID")
				if not channel_id:
					raise ValueError("DISCORD_TICKET_CHANNEL_ID environment variable is not set.")
				
				channel = bot.get_channel(int(channel_id))
				if not channel:
					channel = await bot.fetch_channel(int(channel_id))

				if not isinstance(channel, discord.TextChannel):
					raise ValueError(f"Channel ID {channel_id} is not a text channel.")

				# 2. Resolve creator user
				creator = None
				creator_username = "unknown"
				if ticket.player.isdigit():
					creator = bot.get_user(int(ticket.player))
					if not creator:
						try:
							creator = await bot.fetch_user(int(ticket.player))
						except Exception:
							pass
					if creator:
						creator_username = creator.name

				# 3. Create Discord thread below the target channel
				thread = await channel.create_thread(
					name=f"ticket-{ticket.ticketId}-{creator_username}",
					auto_archive_duration=10080, # 7 days
					type=discord.ChannelType.public_thread
				)

				# 4. Link the Discord thread ID to the ticket on the backend
				from discordbot.network.relay import MCL_OutboundRelay
				await MCL_OutboundRelay().update_ticket_thread(ticket.ticketId, thread.id)

				# 5. Add the creator to the thread and notify Helpers+
				if creator:
					try:
						await thread.add_user(creator)
					except Exception:
						pass
				helper_role_mention = "<@&1447520265113174066>"
				creator_mention = creator.mention if creator else f"<@{ticket.player}>"
				await thread.send(f"New ticket created by {creator_mention}. Staff notification: {helper_role_mention}")

				# 6. Retrieve ticket from MongoDB again to ensure updated thread ID is loaded
				ticket = mongo.getTicket(ticketId)

				# 7. Generate and send embed with persistent buttons inside the thread
				from discordbot.components.ticket_view import generate_ticket_embed, HelpTicketThreadView
				embed = generate_ticket_embed(ticket, creator=creator)
				await thread.send(embed=embed, view=HelpTicketThreadView())

			elif ticket.threadId:
				# Find the thread
				thread = bot.get_channel(ticket.threadId)
				if not thread:
					try:
						thread = await bot.fetch_channel(ticket.threadId)
					except Exception:
						thread = None

				if thread:
					# Resolve ticket creator
					creator = None
					if ticket.player.isdigit():
						creator = thread.guild.get_member(int(ticket.player))
						if not creator:
							try:
								creator = await thread.guild.fetch_member(int(ticket.player))
							except Exception:
								pass

					# Find starter message to edit
					starter_msg = None
					try:
						async for message in thread.history(limit=5, oldest_first=True):
							if message.author.id == bot.user.id and message.embeds:
								starter_msg = message
								break
					except Exception as e:
						request.app.state.logger.exception(f"Error fetching thread history: {e}")

					# Edit starter message embed
					from discordbot.components.ticket_view import generate_ticket_embed, HelpTicketThreadView
					if starter_msg:
						new_embed = generate_ticket_embed(ticket, creator=creator)
						await starter_msg.edit(embed=new_embed, view=HelpTicketThreadView())

					# Action-specific logic
					if ticketAction == TicketAction.CLAIM.value:
						await thread.send(f"🙋‍♂️ Ticket #{ticket.ticketId} has been claimed by <@{ticket.claimedBy}>.")
					elif ticketAction == TicketAction.UNCLAIM.value:
						await thread.send(f"🚫 Ticket #{ticket.ticketId} has been unclaimed.")
					elif ticketAction == TicketAction.CLOSE.value:
						await thread.send(f"🔒 Ticket #{ticket.ticketId} has been closed by <@{ticket.closedBy}>.")
						# Archive and lock the thread
						await thread.edit(archived=True, locked=True)
					elif ticketAction == TicketAction.FEEDBACK.value:
						feedback_label = "Helpful 👍" if ticket.feedback.value == "HELPFUL" else "Unhelpful 👎"
						await thread.send(f"⭐ Ticket creator submitted feedback: {feedback_label}")

	except Exception as e:
		request.app.state.logger.exception(f"Error processing bot update {updateId}: {e}")
	finally:
		# Always acknowledge the update to prevent queue clogging
		try:
			from discordbot.network.relay import MCL_OutboundRelay
			await MCL_OutboundRelay().acknowledge_update(str(updateId))
		except Exception as ae:
			request.app.state.logger.exception(f"Error acknowledging update {updateId}: {ae}")

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "success"}
	)
