'''
MCLabs Discord Bot - Helpsystem Cog

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

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

		try:
			await interaction.response.send_message(
				"Thank you! Your question has been logged successfully.",
				ephemeral=True
			)
		except Exception as e:
			self.logger.exception(f"Error responding to modal submission: {e}")

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
