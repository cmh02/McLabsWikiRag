'''
MCLabs Discord Bot - Help System UI Components

Author: Chris Hinkson @cmh02
'''

import logging
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
		ticket = mongo.getTicketByThreadId(interaction.channel_id)
		if not ticket:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		# Call claim API on backend
		success = await MCL_OutboundRelay().claim_ticket(ticket.ticketId, str(interaction.user.id))
		if success:
			await interaction.response.send_message("Claiming ticket...", ephemeral=True)
		else:
			await interaction.response.send_message("Failed to claim ticket via API.", ephemeral=True)

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
		ticket = mongo.getTicketByThreadId(interaction.channel_id)
		if not ticket:
			await interaction.response.send_message("Could not find ticket for this thread in database.", ephemeral=True)
			return

		# Call unclaim API on backend
		success = await MCL_OutboundRelay().unclaim_ticket(ticket.ticketId)
		if success:
			await interaction.response.send_message("Unclaiming ticket...", ephemeral=True)
		else:
			await interaction.response.send_message("Failed to unclaim ticket via API.", ephemeral=True)

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
		ticket = mongo.getTicketByThreadId(interaction.channel_id)
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
		ticket = mongo.getTicketByThreadId(interaction.channel_id)
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

