'''
MCLabs Discord Bot - Help System UI Components

Author: Chris Hinkson @cmh02
'''

import os
import io
import logging
import asyncio
import discord
from typing import Optional
from datetime import datetime, timezone

from mcl_common.datatypes import HelpTicket
from mcl_common.enum import TicketStatus, TicketFeedback
from mcl_common.mongo import MCL_MongoManager
from discordbot.network.relay import MCL_OutboundRelay

logger = logging.getLogger("MCL_DISCORD_Logger")

# Configured staff/helper role IDs
HELPER_ROLE_IDS = [1447520265113174066]

def is_helper_plus(member: discord.Member) -> bool:
	'''
	# Is Helper Plus

	Checks if a member is Administrator or has a Helper+ role.
	'''
	if member.guild_permissions.administrator:
		return True
	for role in member.roles:
		if role.id in HELPER_ROLE_IDS:
			return True
	return False

def generate_ticket_embed(ticket: HelpTicket, creator: Optional[discord.Member] = None, creator_name: Optional[str] = None) -> discord.Embed:
	'''
	# Generate Ticket Embed

	Generates a premium, stylized status embed for the help ticket thread.
	'''
	if ticket.status == TicketStatus.OPEN:
		color = discord.Color.blue()
		status_str = "🟢 Open"
	elif ticket.status == TicketStatus.CLAIMED:
		color = discord.Color.gold()
		status_str = f"🟡 Claimed by <@{ticket.claimedBy}>" if ticket.claimedBy else "🟡 Claimed"
	elif ticket.status == TicketStatus.CLOSED:
		color = discord.Color.red()
		status_str = f"🔴 Closed by <@{ticket.closedBy}>" if ticket.closedBy else "🔴 Closed"
	else:
		color = discord.Color.light_grey()
		status_str = f"Status: {ticket.status.value}"

	embed = discord.Embed(
		title=f"🎫 Help Ticket #{ticket.ticketId}",
		description="Welcome to your help ticket thread! Staff members have been notified and will assist you shortly.",
		color=color,
		timestamp=datetime.fromtimestamp(ticket.time_create, tz=timezone.utc) if ticket.time_create else datetime.now(timezone.utc)
	)

	creator_mention = f"<@{creator.id}>" if creator else (f"<@{ticket.playerInfo.discordId}>" if ticket.playerInfo.discordId else "Unknown")
	creator_tag = creator.name if creator else (ticket.playerInfo.discordUsername or creator_name or "Unknown")

	embed.add_field(name="Ticket Creator", value=creator_mention, inline=True)
	embed.add_field(name="Discord Username", value=f"`{creator_tag}`", inline=True)
	
	minecraft_account = f"`{ticket.playerInfo.minecraftUsername}`" if ticket.playerInfo.minecraftUsername else "`Not Linked`"
	embed.add_field(name="Minecraft Account", value=minecraft_account, inline=True)
	embed.add_field(name="Status", value=status_str, inline=True)

	# Feedback field
	if ticket.feedback == TicketFeedback.HELPFUL:
		feedback_val = "👍 Helpful"
	elif ticket.feedback == TicketFeedback.UNHELPFUL:
		feedback_val = "👎 Unhelpful"
	else:
		feedback_val = "None"
	embed.add_field(name="Feedback", value=feedback_val, inline=True)

	# Extract the original question
	question = "No question provided."
	if ticket.conversation and ticket.conversation.messages:
		# The first message sent by the player
		for msg in ticket.conversation.messages:
			if msg.sender.minecraftUUID == ticket.playerInfo.minecraftUUID or msg.sender.discordId == ticket.playerInfo.discordId:
				question = msg.content
				break
	embed.add_field(name="Question Asked", value=question, inline=False)

	embed.set_footer(text="MCLabs Ticket System")
	return embed


class HelpTicketThreadView(discord.ui.View):
	'''
	# HelpTicketThreadView

	Persistent view containing the interactive buttons in the ticket thread.
	'''
	def __init__(self):
		super().__init__(timeout=None)

	@discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="🙋‍♂️", custom_id="btn_claim_ticket")
	async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
		logger.info(f"Button Claim clicked by {interaction.user}")
		
		# Ensure interaction user is a Member
		if not isinstance(interaction.user, discord.Member):
			await interaction.response.send_message("Command must be run in a server.", ephemeral=True)
			return

		# Check helper+ role
		if not is_helper_plus(interaction.user):
			await interaction.response.send_message("Only staff/Helper+ can claim tickets.", ephemeral=True)
			return

		# Get ticket by thread ID
		if interaction.channel_id is None:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		mongo = MCL_MongoManager()
		ticket = await asyncio.to_thread(mongo.getTicketByThreadId, interaction.channel_id)
		if not ticket:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		# Acknowledge the interaction immediately
		await interaction.response.defer()

		# Call claim API on backend
		success = await MCL_OutboundRelay().claim_ticket(ticket.ticketId, str(interaction.user.id))
		if not success:
			await interaction.followup.send("Failed to claim ticket via API.", ephemeral=True)
		else:
			await handle_discord_claim(interaction.client, ticket.ticketId)

	@discord.ui.button(label="Unclaim", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id="btn_unclaim_ticket")
	async def unclaim(self, interaction: discord.Interaction, button: discord.ui.Button):
		logger.info(f"Button Unclaim clicked by {interaction.user}")

		# Ensure interaction user is a Member
		if not isinstance(interaction.user, discord.Member):
			await interaction.response.send_message("Command must be run in a server.", ephemeral=True)
			return

		# Check helper+ role
		if not is_helper_plus(interaction.user):
			await interaction.response.send_message("Only staff/Helper+ can unclaim tickets.", ephemeral=True)
			return

		# Get ticket by thread ID
		if interaction.channel_id is None:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		mongo = MCL_MongoManager()
		ticket = await asyncio.to_thread(mongo.getTicketByThreadId, interaction.channel_id)
		if not ticket:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		# Check if the ticket is claimed
		if ticket.status != TicketStatus.CLAIMED or not ticket.claimedBy:
			await interaction.response.send_message("You cannot unclaim a ticket that isn't claimed.", ephemeral=True)
			return

		# Acknowledge the interaction immediately
		await interaction.response.defer()

		# Call unclaim API on backend
		success = await MCL_OutboundRelay().unclaim_ticket(ticket.ticketId)
		if not success:
			await interaction.followup.send("Failed to unclaim ticket via API.", ephemeral=True)
		else:
			await handle_discord_unclaim(interaction.client, ticket.ticketId)

	@discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="btn_close_ticket")
	async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
		logger.info(f"Button Close clicked by {interaction.user}")

		# Ensure interaction user is a Member
		if not isinstance(interaction.user, discord.Member):
			await interaction.response.send_message("Command must be run in a server.", ephemeral=True)
			return

		# Get ticket by thread ID
		if interaction.channel_id is None:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		mongo = MCL_MongoManager()
		ticket = await asyncio.to_thread(mongo.getTicketByThreadId, interaction.channel_id)
		if not ticket:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		# Check if clicking user is helper+ OR the ticket creator
		is_creator = str(interaction.user.id) == ticket.playerInfo.discordId
		if not (is_creator or is_helper_plus(interaction.user)):
			await interaction.response.send_message("Only the ticket creator or Helper+ can close this ticket.", ephemeral=True)
			return

		# Prompt confirmation
		view = CloseConfirmationView(ticket.ticketId, str(interaction.user.id))
		await interaction.response.send_message("Are you sure you want to close this ticket?", view=view, ephemeral=True)

	@discord.ui.button(label="Feedback", style=discord.ButtonStyle.primary, emoji="⭐", custom_id="btn_ticket_feedback")
	async def feedback(self, interaction: discord.Interaction, button: discord.ui.Button):
		logger.info(f"Button Feedback clicked by {interaction.user}")

		# Ensure interaction user is a Member
		if not isinstance(interaction.user, discord.Member):
			await interaction.response.send_message("Command must be run in a server.", ephemeral=True)
			return

		# Get ticket by thread ID
		if interaction.channel_id is None:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		mongo = MCL_MongoManager()
		ticket = await asyncio.to_thread(mongo.getTicketByThreadId, interaction.channel_id)
		if not ticket:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		# Check if clicking user is the ticket creator
		is_creator = str(interaction.user.id) == ticket.playerInfo.discordId
		if not is_creator:
			await interaction.response.send_message("Only the ticket creator can submit feedback.", ephemeral=True)
			return

		# Prompt feedback buttons
		view = FeedbackSelectionView(ticket.ticketId)
		await interaction.response.send_message("Please rate the assistance you received:", view=view, ephemeral=True)


class CloseConfirmationView(discord.ui.View):
	'''
	# CloseConfirmationView

	Ephemeral view to confirm ticket closure.
	'''
	def __init__(self, ticket_id: int, closed_by: str):
		super().__init__(timeout=60)
		self.ticket_id = ticket_id
		self.closed_by = closed_by

	@discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="🔒")
	async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
		# Disable buttons
		for item in self.children:
			if isinstance(item, (discord.ui.Button, discord.ui.Select)):
				item.disabled = True
		await interaction.response.edit_message(content="Closing ticket...", view=self)

		success = await MCL_OutboundRelay().close_ticket(self.ticket_id, self.closed_by)
		if not success:
			await interaction.followup.send("Failed to close ticket via API.", ephemeral=True)
		else:
			await handle_discord_close(interaction.client, self.ticket_id)

	@discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
	async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
		for item in self.children:
			if isinstance(item, (discord.ui.Button, discord.ui.Select)):
				item.disabled = True
		await interaction.response.edit_message(content="Cancelled ticket closure.", view=self)


class FeedbackSelectionView(discord.ui.View):
	'''
	# FeedbackSelectionView

	Ephemeral view to choose Helpful/Unhelpful feedback.
	'''
	def __init__(self, ticket_id: int):
		super().__init__(timeout=60)
		self.ticket_id = ticket_id

	@discord.ui.button(label="Helpful 👍", style=discord.ButtonStyle.success)
	async def helpful(self, interaction: discord.Interaction, button: discord.ui.Button):
		for item in self.children:
			if isinstance(item, (discord.ui.Button, discord.ui.Select)):
				item.disabled = True
		await interaction.response.edit_message(content="Submitting feedback...", view=self)

		success = await MCL_OutboundRelay().set_ticket_feedback(self.ticket_id, "HELPFUL")
		if success:
			await interaction.followup.send("Thank you for your feedback!", ephemeral=True)
			await handle_discord_feedback(interaction.client, self.ticket_id)
		else:
			await interaction.followup.send("Failed to submit feedback via API.", ephemeral=True)

	@discord.ui.button(label="Unhelpful 👎", style=discord.ButtonStyle.danger)
	async def unhelpful(self, interaction: discord.Interaction, button: discord.ui.Button):
		for item in self.children:
			if isinstance(item, (discord.ui.Button, discord.ui.Select)):
				item.disabled = True
		await interaction.response.edit_message(content="Submitting feedback...", view=self)

		success = await MCL_OutboundRelay().set_ticket_feedback(self.ticket_id, "UNHELPFUL")
		if success:
			await interaction.followup.send("Thank you for your feedback!", ephemeral=True)
			await handle_discord_feedback(interaction.client, self.ticket_id)
		else:
			await interaction.followup.send("Failed to submit feedback via API.", ephemeral=True)


class HelpTicketCreateView(discord.ui.View):
	'''
	# HelpTicketCreateView

	Persistent view containing the button to open a support ticket.
	'''
	def __init__(self):
		super().__init__(timeout=None)

	@discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="btn_create_ticket")
	async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
		logger.info(f"Button Create Ticket clicked by {interaction.user}")
		from discordbot.cogs.helpsystem import HelpSystemModal
		modal = HelpSystemModal(logger)
		await interaction.response.send_modal(modal)


async def _get_ticket_thread_and_message(bot, ticket_id: int, ticket: Optional[HelpTicket] = None):
	'''
	Helper to retrieve the ticket from MongoDB, locate its Discord thread, and fetch its status message.
	'''
	mongo = MCL_MongoManager()
	if not ticket:
		ticket = await asyncio.to_thread(mongo.getTicket, ticket_id)
	if not ticket:
		logger.error(f"Ticket with ID {ticket_id} not found in database.")
		return None, None, None

	thread_id = ticket.threadId
	if not thread_id:
		logger.warning(f"No threadId associated with ticket {ticket_id}. Cannot process.")
		return ticket, None, None

	thread = bot.get_channel(thread_id)
	if not thread:
		try:
			thread = await bot.fetch_channel(thread_id)
		except Exception as e:
			logger.error(f"Failed to fetch thread with ID {thread_id}: {e}")
			return ticket, None, None

	if not thread or not isinstance(thread, discord.Thread):
		logger.error(f"Thread with ID {thread_id} not found or is not a thread.")
		return ticket, None, None

	# Find status message in the thread directly by ID
	status_msg = None
	if ticket.statusMessageId:
		try:
			status_msg = discord.utils.get(bot.cached_messages, id=ticket.statusMessageId)
			if not status_msg:
				status_msg = await thread.fetch_message(ticket.statusMessageId)
		except discord.NotFound:
			logger.error(f"Status message with ID {ticket.statusMessageId} not found in thread {thread.id}.")
		except Exception as e:
			logger.error(f"Error fetching status message {ticket.statusMessageId}: {e}")

	return ticket, thread, status_msg


async def handle_discord_create(bot, ticket_id: int, ticket: Optional[HelpTicket] = None) -> bool:
	'''
	Creates a new public thread on the ticket channel, sends the status card,
	and sends/deletes transient mentions for notifications.
	'''
	mongo = MCL_MongoManager()
	if not ticket:
		ticket = await asyncio.to_thread(mongo.getTicket, ticket_id)
	if not ticket:
		logger.error(f"Ticket with ID {ticket_id} not found in database for create.")
		return False

	# Check the ticket channel
	ticket_channel_id = os.getenv("DISCORD_TICKET_CHANNEL_ID")
	if not ticket_channel_id:
		logger.error("DISCORD_TICKET_CHANNEL_ID environment variable is not set.")
		return False
	
	try:
		channel_id = int(ticket_channel_id)
	except ValueError:
		logger.error("DISCORD_TICKET_CHANNEL_ID is not a valid integer.")
		return False

	channel = bot.get_channel(channel_id)
	if not channel:
		try:
			channel = await bot.fetch_channel(channel_id)
		except Exception as e:
			logger.error(f"Failed to fetch ticket channel {channel_id}: {e}")
			return False

	if not channel or not isinstance(channel, discord.TextChannel):
		logger.error(f"Ticket channel with ID {channel_id} not found or is not a text channel.")
		return False

	if ticket.threadId:
		logger.info(f"Ticket {ticket_id} already has thread {ticket.threadId}. Skipping thread creation.")
		return True

	# Wait up to 1.5s for the initial question message to be committed to MongoDB
	for attempt in range(5):
		if ticket.conversation and ticket.conversation.messages:
			break
		logger.info(f"Ticket {ticket_id} conversation is empty. Retrying fetch in 300ms (attempt {attempt + 1}/5)...")
		await asyncio.sleep(0.3)
		ticket = await asyncio.to_thread(mongo.getTicket, ticket_id)

	# Create a new public thread on the ticket channel
	try:
		thread = await channel.create_thread(
			name=f"🎫-ticket-{ticket_id}",
			type=discord.ChannelType.private_thread,
			auto_archive_duration=10080  # 7 days
		)
	except Exception as e:
		logger.error(f"Failed to create Discord thread for ticket {ticket_id}: {e}")
		return False
	
	# Generate initial embed
	embed = generate_ticket_embed(ticket)
	
	# Send status card in thread with persistent view
	view = HelpTicketThreadView()
	try:
		status_msg = await thread.send(embed=embed, view=view)
	except Exception as e:
		logger.error(f"Failed to send status card message for ticket {ticket_id}: {e}")
		return False
	
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
			logger.error(f"Failed to send/delete transient thread pings: {e}")
	
	logger.info(f"Created Discord thread {thread.id} for ticket {ticket_id}.")
	
	# Save thread ID and status message ID to the backend
	await MCL_OutboundRelay().update_ticket_thread(ticket_id, thread.id, status_msg.id)
	return True


async def handle_discord_claim(bot, ticket_id: int, ticket: Optional[HelpTicket] = None) -> bool:
	'''
	Updates status card embed in the thread.
	'''
	ticket, thread, status_msg = await _get_ticket_thread_and_message(bot, ticket_id, ticket)
	if not ticket or not thread:
		return False

	# Edit status card embed
	if status_msg:
		try:
			embed = generate_ticket_embed(ticket)
			await status_msg.edit(embed=embed)
			logger.info(f"Updated status card embed for ticket {ticket_id} thread.")
		except Exception as e:
			logger.error(f"Failed to edit status card for ticket {ticket_id}: {e}")

	return True


async def handle_discord_unclaim(bot, ticket_id: int, ticket: Optional[HelpTicket] = None) -> bool:
	'''
	Updates status card embed in the thread.
	'''
	ticket, thread, status_msg = await _get_ticket_thread_and_message(bot, ticket_id, ticket)
	if not ticket or not thread:
		return False

	# Edit status card embed
	if status_msg:
		try:
			embed = generate_ticket_embed(ticket)
			await status_msg.edit(embed=embed)
			logger.info(f"Updated status card embed for ticket {ticket_id} thread.")
		except Exception as e:
			logger.error(f"Failed to edit status card for ticket {ticket_id}: {e}")

	return True


async def handle_discord_playerinfo_update(bot, ticket_id: int, ticket: Optional[HelpTicket] = None) -> bool:
	'''
	Updates status card embed in the thread when player info is resolved or updated.
	'''
	ticket, thread, status_msg = await _get_ticket_thread_and_message(bot, ticket_id, ticket)
	if not ticket or not thread:
		return False

	# Edit status card embed with the latest info
	if status_msg:
		try:
			embed = generate_ticket_embed(ticket)
			await status_msg.edit(embed=embed)
			logger.info(f"Updated status card embed for ticket {ticket_id} due to player info update.")
		except Exception as e:
			logger.error(f"Failed to edit status card for ticket {ticket_id} player info update: {e}")
			return False
	return True


async def handle_discord_close(bot, ticket_id: int, ticket: Optional[HelpTicket] = None) -> bool:
	'''
	Updates status card embed, posts closed notification message,
	generates and sends transcript DMs, and archives/locks the thread.
	'''
	ticket, thread, status_msg = await _get_ticket_thread_and_message(bot, ticket_id, ticket)
	if not ticket or not thread:
		return False

	if thread.archived:
		logger.info(f"Thread for ticket {ticket_id} is already archived. Skipping close flow.")
		return True

	# Edit status card embed
	if status_msg:
		try:
			embed = generate_ticket_embed(ticket)
			await status_msg.edit(embed=embed)
			logger.info(f"Updated status card embed for ticket {ticket_id} thread.")
		except Exception as e:
			logger.error(f"Failed to edit status card for ticket {ticket_id}: {e}")

	# Check for duplicate close notification
	already_notified = False
	try:
		async for msg in thread.history(limit=10):
			if msg.author.id == bot.user.id and "Ticket has been closed by" in msg.content:
				already_notified = True
				break
	except Exception as e:
		logger.warning(f"Error checking thread history for duplicates for ticket {ticket_id}: {e}")

	if not already_notified:
		# Notify the thread
		closed_by = ticket.closedBy or "Unknown"
		try:
			await thread.send(f"🔒 Ticket has been closed by <@{closed_by}>.")
		except Exception as e:
			logger.error(f"Failed to send close notification message to thread {thread.id}: {e}")

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
		
		if ticket.conversation and ticket.conversation.messages:
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
				logger.warning(f"Could not resolve username for Discord ID {uid}: {resolve_err}")

		from discordbot.utils.transcript import generate_html_transcript
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
					discord_file = discord.File(fp=fp, filename=f"transcript-ticket-{ticket_id}.html")
					admin_msg = await admin_channel.send(
						content=f"📝 **Ticket #{ticket_id} Closed** - Transcript Archive",
						file=discord_file
					)
					if admin_msg.attachments:
						transcript_url = admin_msg.attachments[0].url
						logger.info(f"Uploaded ticket {ticket_id} transcript to admin channel: {transcript_url}")
			except Exception as upload_err:
				logger.error(f"Failed to upload ticket {ticket_id} transcript to admin channel: {upload_err}")

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
							title=f"🎫 Ticket #{ticket_id} Closed",
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
						logger.info(f"Successfully sent ticket {ticket_id} transcript DM with Link Button to user {r_id}.")
					else:
						# Fallback: Send the file directly in the DM if upload failed
						fp = io.BytesIO(html_content.encode('utf-8'))
						discord_file = discord.File(fp=fp, filename=f"transcript-ticket-{ticket_id}.html")

						dm_embed = discord.Embed(
							title=f"🎫 Ticket #{ticket_id} Closed",
							description="Your help ticket has been successfully closed. A complete styled transcript of the conversation has been attached below for your records.",
							color=discord.Color.red(),
							timestamp=datetime.now(timezone.utc)
						)
						dm_embed.add_field(name="Opened By", value=creator_mention, inline=True)
						dm_embed.add_field(name="Claimed By", value=claimed_mention, inline=True)
						dm_embed.add_field(name="Closed By", value=closed_mention, inline=True)
						dm_embed.set_footer(text="MCLabs Ticket Archiver")

						await user.send(embed=dm_embed, file=discord_file)
						logger.info(f"Successfully sent ticket {ticket_id} transcript DM as file attachment to user {r_id} (fallback).")
			except discord.Forbidden:
				logger.warning(f"Could not send DM to user {r_id} (DMs are likely disabled/restricted).")
			except Exception as dm_err:
				logger.error(f"Failed to send DM transcript to user {r_id}: {dm_err}")
	except Exception as trans_err:
		logger.exception(f"Error handling ticket {ticket_id} transcript: {trans_err}")

	# Archive and lock the thread
	try:
		await thread.edit(archived=True, locked=True)
		logger.info(f"Archived and locked Discord thread {thread.id} for ticket {ticket_id}.")
	except Exception as e:
		logger.error(f"Failed to archive/lock thread {thread.id} for ticket {ticket_id}: {e}")
	return True


async def handle_discord_feedback(bot, ticket_id: int, ticket: Optional[HelpTicket] = None) -> bool:
	'''
	Updates status card embed with the new feedback values.
	'''
	ticket, thread, status_msg = await _get_ticket_thread_and_message(bot, ticket_id, ticket)
	if not ticket or not thread:
		return False

	# Edit status card embed
	if status_msg:
		try:
			embed = generate_ticket_embed(ticket)
			await status_msg.edit(embed=embed)
			logger.info(f"Updated status card embed for ticket {ticket_id} thread (FEEDBACK).")
		except Exception as e:
			logger.error(f"Failed to edit status card for ticket {ticket_id}: {e}")
	return True


async def handle_discord_newmessage(bot, ticket_id: int, ticket: Optional[HelpTicket] = None) -> bool:
	'''
	Relays new in-game Minecraft messages to the Discord thread.
	'''
	ticket, thread, status_msg = await _get_ticket_thread_and_message(bot, ticket_id, ticket)
	if not ticket or not thread:
		return False

	# Edit status card embed
	if status_msg:
		try:
			embed = generate_ticket_embed(ticket)
			await status_msg.edit(embed=embed)
			logger.info(f"Updated status card embed for ticket {ticket_id} thread (NEWMESSAGE).")
		except Exception as e:
			logger.error(f"Failed to edit status card for ticket {ticket_id}: {e}")

	# Send incoming message to the thread if not a duplicate
	if ticket.conversation and ticket.conversation.messages:
		last_msg = ticket.conversation.messages[-1]
		
		# Get last message in Discord thread to check for duplicate
		last_discord_msg = None
		try:
			async for msg in thread.history(limit=1):
				last_discord_msg = msg
		except Exception as e:
			logger.warning(f"Failed to fetch thread history for newmessage duplicate check for ticket {ticket_id}: {e}")

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
				logger.info(f"Skipping duplicate message relay for ticket {ticket_id}: {last_msg.content}")
			else:
				logger.info(f"Skipping relay of the original question for ticket {ticket_id}: {last_msg.content}")
		else:
			# Format the message header depending on source
			sender_name = last_msg.sender.minecraftUsername or last_msg.sender.discordUsername or "Unknown"
			if last_msg.sender.minecraftUsername:
				prefix = f"**[In-Game] {sender_name}**"
			else:
				prefix = f"**{sender_name}**"
			
			try:
				await thread.send(f"{prefix}: {last_msg.content}")
				logger.info(f"Relayed new message to Discord thread: {last_msg.content}")
			except Exception as e:
				logger.error(f"Failed to send relayed message to thread {thread.id}: {e}")
	return True

