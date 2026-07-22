'''
MCLabs Discord Bot - Helpsystem Cog

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import time
import logging
import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from typing import cast, TYPE_CHECKING

if TYPE_CHECKING:
	from discordbot.bot import MclBot
	from discordbot.network.relay import MCL_OutboundRelay
	from discordbot.components.ticket_view import handle_discord_create

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

	def __init__(self, logger: logging.Logger, default_question: str | None = None):
		super().__init__()
		self.logger = logger
		if default_question:
			self.question_input.default = default_question[:1000]

	async def on_submit(self, interaction: discord.Interaction):
		'''
		# On Submit

		Logs the user details and their question, then acknowledges.
		'''
		user = interaction.user
		username = user.name
		question = self.question_input.value
		bot = cast("MclBot", interaction.client)

		self.logger.info(f"HelpSystem Ask: User ID: {user.id}, Username: {username}, Question: {question}")

		# Defer the interaction immediately
		await interaction.response.defer(ephemeral=True)

		# Config for API requests
		domain_backend = os.getenv("RAILWAY_API_DOMAIN")
		if not domain_backend:
			raise EnvironmentError("RAILWAY_API_DOMAIN environment variable is not set.")
		token = os.getenv("API_TOKEN")
		if not token:
			raise EnvironmentError("API_TOKEN environment variable is not set.")
		user_agent = os.getenv("USER_AGENT_DISCORDBOT")
		if not user_agent:
			raise EnvironmentError("USER_AGENT_DISCORDBOT environment variable is not set.")
		headers = {
			"Content-Type": "application/json",
			"Authorization": token,
			"User-Agent": user_agent
		}

		# Ensure backend API is awake if last successful communication was > 5 minutes ago
		relay = MCL_OutboundRelay()
		current_time = time.time()
		if current_time - relay._last_success_time > 300.0:
			self.logger.info("API last active check failed or timed out. Ensuring backend is awake before creating ticket...")
			is_awake = await bot.ensureApiAwake(numberTries=5, sleepInterval=3)
			if is_awake:
				relay._last_success_time = time.time()
			else:
				self.logger.warning("Failed to verify backend is awake, proceeding with request anyway.")

		ticket_id = None
		try:
			# 1. Create ticket on backend
			async with bot.session.post(
				f"https://{domain_backend}/create_ticket",
				headers=headers,
				json={
					"type": "SUPPORT",
					"playerInfo": {
						"discordId": str(user.id),
						"discordUsername": username
					}
				},
				timeout=aiohttp.ClientTimeout(total=30)
			) as resp:
				if resp.status != 200:
					raise RuntimeError(f"Backend API create_ticket returned status {resp.status}")
				relay._last_success_time = time.time()
				resp_json = await resp.json()
				ticket_id = resp_json.get("ticketId")

			if not ticket_id:
				raise RuntimeError("No ticketId returned by backend API.")

		except Exception as e:
			self.logger.exception(f"Error handling /ask modal submission (ticket creation failed): {e}")
			await interaction.followup.send(
				"An error occurred while creating your help ticket. Please try again later.",
				ephemeral=True
			)
			return

		# If ticket was created successfully, attempt to append the question and trigger thread creation
		try:
			# 2. Append the user's question to the ticket conversation
			async with bot.session.post(
				f"https://{domain_backend}/append_ticket_message",
				headers=headers,
				json={
					"ticketId": ticket_id,
					"content": question,
					"sender": {
						"discordId": str(user.id),
						"discordUsername": username
					}
				},
				timeout=aiohttp.ClientTimeout(total=30)
			) as resp:
				if resp.status != 200:
					self.logger.error(f"Failed to append message to ticket {ticket_id}. Status: {resp.status}")
				else:
					relay._last_success_time = time.time()

			# Trigger thread creation in the background
			asyncio.create_task(handle_discord_create(bot, ticket_id))

		except Exception as e:
			self.logger.exception(f"Error appending question/creating thread for ticket {ticket_id}: {e}")
			# Still attempt thread creation as the ticket exists
			asyncio.create_task(handle_discord_create(bot, ticket_id))

		# 3. Inform the user of successful creation
		await interaction.followup.send(
			f"Thank you! Your help ticket #{ticket_id} has been created successfully. A dedicated thread will be opened for you shortly.",
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
	@app_commands.describe(question="An optional question to pre-populate the form")
	async def ask(self, interaction: discord.Interaction, question: str | None = None):
		'''
		# Ask Command

		Opens a modal asking the user to input a question.
		'''
		self.logger.info(f"Ask slash command invoked by {interaction.user} ({interaction.user.id}) with question parameter: {question}")
		try:
			modal = HelpSystemModal(self.logger, default_question=question)
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
