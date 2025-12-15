'''
MCLabs Discord Components

Author: Chris Hinkson @cmh02

(NOTE: The term 'thread' in this context refers to Discord threads created for help questions, not system threads.)
'''

'''
MODULE IMPORTS
'''

import os
import discord
import logging
from discord.ext.commands import Bot
from discord.ui import View, Button

'''
UI COMPONENTS
'''

class AdminHelpPanel(View):
	'''
	# Admin Help Panel

	Discord UI View for the admin panel to manage help questions.
	'''

	# Initialize the admin panel view
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		self.bot = bot
		self.logger = logging.getLogger("MCL_DISCORD_Logger")

	# Only allow admins to interact with buttons
	def check_admin(self, interaction: discord.Interaction) -> bool:
		return interaction.user.guild_permissions.administrator
	
	# Clear all button for admins
	@discord.ui.button(label="Clear All", style=discord.ButtonStyle.danger, custom_id="admin_help_clear_all")
	async def clear_all(self, interaction: discord.Interaction, button: discord.ui.button):
		if not self.check_admin(interaction):
			return await interaction.response.send_message(content="You do not have permission to use this button.", ephemeral=True)
		
		# Log button usage
		self.logger.info(f"Admin {interaction.user} used Clear All button in Help Admin Panel.")

		# Delete all threads in the channel
		return await interaction.response.send_message(content="Not Implemented.", ephemeral=True)

class AdminHelpEmbed(discord.Embed):
	'''
	# Admin Help Embed

	Discord Embed for displaying admin help panel information.
	'''

	def __init__(self, questionList: str = "No active questions."):
		super().__init__(
			title="MCL Help System — Admin Panel",
			description="This panel shows all current help questions.\nUse the buttons below to manage them.",
		)
		self.add_field(
			name="Active Questions", 
			value=questionList, 
			inline=False
		)

class HelpQuestionPanel(View):
	'''
	# Help Question Panel

	Discord UI View for help question management buttons.
	'''

	# Initialize the help question panel view
	def __init__(self, bot: Bot, questionId: int):
		super().__init__(timeout=None)
		self.bot = bot
		self.questionId = questionId
		self.logger = logging.getLogger("MCL_DISCORD_Logger")

	# Claim button
	@discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="help_claim")
	async def claim(self, interaction: discord.Interaction, button: discord.ui.button):

		# Delay response
		await interaction.response.defer(thinking=True)

		# Log button usage
		self.logger.info(f"User {interaction.user} used Claim button for help question ID {self.questionId}.")
		
		try:
			# Try to wake up the API
			isAwake = await self.bot.ensureApiAwake(numberTries=5, sleepInterval=3)
			if not isAwake:
				await interaction.followup.send(
					content=f"The API is currently unavailable. Please try again later.", 
					ephemeral=True
				)
				return

			# Make API request to claim the help question
			async with self.bot.session.post(
				url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/claim",
				headers={
					"Content-Type": "application/json",
					"Authorization": os.getenv("API_TOKEN")
				},
				json={
					"question_id": int(self.questionId),
					"claimed_by": interaction.user.display_name
				}
			) as response:
				if response.status == 200:
					await interaction.followup.send(
						content=f"Claimed!", 
						ephemeral=True
					)
					return
				else:
					await interaction.followup.send(
						content=f"Try Again!", 
						ephemeral=True
					)
					return
		except Exception as e:
			await interaction.followup.send(
				content=f"An error occurred while trying to claim the help question: {str(e)}", 
				ephemeral=True
			)
			return

	# Unclaim button
	@discord.ui.button(label="Unclaim", style=discord.ButtonStyle.gray, custom_id="help_unclaim")
	async def unclaim(self, interaction: discord.Interaction, button: discord.ui.button):
		
		# Delay response
		await interaction.response.defer(thinking=True)

		# Log button usage
		self.logger.info(f"User {interaction.user} used Unclaim button for help question ID {self.questionId}.")
		
		try:
			# Try to wake up the API
			isAwake = await self.bot.ensureApiAwake(numberTries=5, sleepInterval=3)
			if not isAwake:
				await interaction.followup.send(
					content=f"The API is currently unavailable. Please try again later.", 
					ephemeral=True
				)
				return
			
			# Make API request to unclaim the help question
			async with self.bot.session.post(
				url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/unclaim", 
				headers={
					"Content-Type": "application/json",
					"Authorization": os.getenv("API_TOKEN")
				},
				json={
					"question_id": int(self.questionId)
				}
			) as response:
				if response.status == 200:
					await interaction.followup.send(
						content=f"Unclaimed!", 
						ephemeral=True
					)
					return
				else:
					await interaction.followup.send(
						content=f"Try Again!", 
						ephemeral=True
					)
					return
		except Exception as e:
			await interaction.followup.send(
				content=f"An error occurred while trying to unclaim the help question: {str(e)}", 
				ephemeral=True
			)
			return
			
	# Delete button
	@discord.ui.button(label="Delete", style=discord.ButtonStyle.red, custom_id="help_delete")
	async def delete(self, interaction: discord.Interaction, button: discord.ui.button):
		
		# Delay response
		await interaction.response.defer(thinking=True)

		# Log button usage
		self.logger.info(f"User {interaction.user} used Delete button for help question ID {self.questionId}.")

		try:
			# Try to wake up the API
			isAwake = await self.bot.ensureApiAwake(numberTries=5, sleepInterval=3)
			if not isAwake:
				await interaction.followup.send(
					content=f"The API is currently unavailable. Please try again later.", 
					ephemeral=True
				)
				return

			# Make API request to remove the help question
			async with self.bot.session.post(
				url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/remove", 
				headers={
					"Content-Type": "application/json",
					"Authorization": os.getenv("API_TOKEN")
				},
				json={
					"question_id": int(self.questionId)
				}
			) as response:
				if response.status == 200:
					await interaction.followup.send(
						content=f"Help question #{self.questionId} removed successfully!", 
						ephemeral=True
					)
					return
				else:
					await interaction.followup.send(
						content=f"Failed to remove help question #{self.questionId}. Please try again later.", 
						ephemeral=True
					)
					return
		except Exception as e:
			await interaction.followup.send(
				content=f"An error occurred while trying to remove help question #{self.questionId}: {str(e)}", 
				ephemeral=True
			)
			return

class HelpQuestionEmbed(discord.Embed):
	'''
	# Help Question Embed

	Discord Embed for displaying help question details.
	'''

	def __init__(self, questionId: int, questionText: str, questionStatus: str, questionClaimedBy: str):
		super().__init__(
			title=f"Help Question #{questionId}",
			description=questionText,
			color=discord.Color.blue()
		)
		self.add_field(name="Status", value=questionStatus, inline=True)
		self.add_field(name="Claimed By", value=questionClaimedBy, inline=True)