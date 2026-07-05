'''
MCLabs Discord Bot - Helpsystem Cog

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import logging
import discord
from discord import app_commands
from discord.ext import commands

'''
MODAL DEFINITION
'''

class HelpSystemModal(discord.ui.Modal, title="Ask a Question"):
	'''
	# HelpSystemModal

	A popup modal that requests a question from the user.
	'''

	question_input = discord.ui.TextInput(
		label="Ask A Question:",
		style=discord.TextStyle.paragraph,
		placeholder="Type your question here...",
		required=True,
		max_length=1000
	)

	def __init__(self, logger: logging.Logger):
		super().__init__()
		self.logger = logger

	async def on_submit(self, interaction: discord.Interaction):
		'''
		# On Submit

		Logs the user details and their question, then acknowledges.
		'''
		user = interaction.user
		username = user.name
		question = self.question_input.value

		self.logger.info(f"HelpSystem Ask: User ID: {user.id}, Username: {username}, Question: {question}")

		# Defer the interaction immediately as backend calls and thread creation take time
		await interaction.response.defer(ephemeral=True)

		try:
			# Get configured ticket creation channel
			channel_id = os.getenv("TICKET_CHANNEL_ID")
			if not channel_id:
				raise ValueError("TICKET_CHANNEL_ID environment variable is not set.")
			
			channel = interaction.client.get_channel(int(channel_id))
			if not channel:
				channel = await interaction.client.fetch_channel(int(channel_id))

			if not isinstance(channel, discord.TextChannel):
				raise ValueError(f"Channel ID {channel_id} is not a text channel.")

			# Config for API requests
			api_url = os.getenv("RAILWAY_API_DOMAIN")
			token = os.getenv("API_TOKEN")
			user_agent = os.getenv("USER-AGENT-DISCORD-BOT")

			headers = {
				"Content-Type": "application/json",
				"Authorization": token or "",
				"User-Agent": user_agent or "Discord-Bot"
			}

			# 1. Create ticket on backend
			async with interaction.client.session.post(
				f"https://{api_url}/create_ticket",
				headers=headers,
				json={
					"type": "SUPPORT",
					"player": str(user.id)
				},
				timeout=10
			) as resp:
				if resp.status != 200:
					raise RuntimeError(f"Backend API create_ticket returned status {resp.status}")
				resp_json = await resp.json()
				ticket_id = resp_json.get("ticketId")

			if not ticket_id:
				raise RuntimeError("No ticketId returned by backend API.")

			# 2. Append the user's question to the ticket conversation
			async with interaction.client.session.post(
				f"https://{api_url}/append_ticket_message",
				headers=headers,
				json={
					"ticketId": ticket_id,
					"content": question,
					"sentBy": str(user.id)
				},
				timeout=10
			) as resp:
				if resp.status != 200:
					self.logger.error(f"Failed to append message to ticket {ticket_id}. Status: {resp.status}")

			# 3. Create Discord thread below the target channel
			thread = await channel.create_thread(
				name=f"ticket-{ticket_id}-{username}",
				auto_archive_duration=10080, # 7 days
				type=discord.ChannelType.public_thread
			)

			# 4. Add the creator to the thread and notify Helpers+
			await thread.add_user(user)
			helper_role_mention = "<@&1447520265113174066>"
			await thread.send(f"New ticket created by {user.mention}. Staff notification: {helper_role_mention}")

			# 5. Link the Discord thread ID to the ticket on the backend
			async with interaction.client.session.post(
				f"https://{api_url}/update_ticket_thread",
				headers=headers,
				json={
					"ticketId": ticket_id,
					"threadId": thread.id
				},
				timeout=10
			) as resp:
				if resp.status != 200:
					self.logger.error(f"Failed to link thread ID to ticket {ticket_id}. Status: {resp.status}")

			# 6. Retrieve ticket from MongoDB and send embed with persistent buttons
			from discordbot.internal.mongo import MCL_MongoManager
			mongo = MCL_MongoManager()
			ticket = mongo.getTicket(ticket_id)

			from discordbot.components.ticket_view import generate_ticket_embed, HelpTicketThreadView
			embed = generate_ticket_embed(ticket, creator=user)
			await thread.send(embed=embed, view=HelpTicketThreadView())

			# 7. Inform the user of successful creation
			await interaction.followup.send(
				f"Thank you! Your help ticket #{ticket_id} has been created: {thread.mention}.",
				ephemeral=True
			)

		except Exception as e:
			self.logger.exception(f"Error handling /ask modal submission: {e}")
			await interaction.followup.send(
				"An error occurred while creating your help ticket. Please try again later.",
				ephemeral=True
			)

	async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
		self.logger.exception(f"Error in HelpSystemModal: {error}")
		try:
			await interaction.response.send_message(
				"An error occurred while processing your question.",
				ephemeral=True
			)
		except Exception:
			pass

'''
COG DEFINITION
'''

class HelpSystem(commands.Cog):
	'''
	# HelpSystem Cog

	Contains command(s) for the user help system.
	'''

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.logger = logging.getLogger("MCL_DISCORD_Logger")
		self.logger.info("Helpsystem Cog initialized!")

	@app_commands.command(name="ask", description="Submit a question to the help system.")
	async def ask(self, interaction: discord.Interaction):
		'''
		# Ask Command

		Opens a modal asking the user to input a question.
		'''
		self.logger.info(f"Ask slash command invoked by {interaction.user} ({interaction.user.id})")
		try:
			modal = HelpSystemModal(self.logger)
			await interaction.response.send_modal(modal)
		except Exception as e:
			self.logger.exception(f"Error showing /ask modal: {e}")
			try:
				await interaction.response.send_message(
					"Could not open the question form. Please try again later.",
					ephemeral=True
				)
			except Exception:
				pass

async def setup(bot: commands.Bot):
	await bot.add_cog(HelpSystem(bot))
