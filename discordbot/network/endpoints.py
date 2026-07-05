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

		if ticket and ticket.threadId:
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
				from src.utils.enum import TicketAction
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
