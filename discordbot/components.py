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
from discord.ext.commands import Bot
from discord.ui import View, Button

class AdminHelpPanel(View):
	'''
	# Admin Help Panel

	Discord UI View for the admin panel to manage help questions.
	'''

	# Initialize the admin panel view
	def __init__(self, bot: Bot):
		super().__init__(timeout=None)
		self.bot = bot

	# Only allow admins to interact with buttons
	def check_admin(self, interaction: discord.Interaction) -> bool:
		return interaction.user.guild_permissions.administrator
	
	# Clear all button for admins
	@discord.ui.button(label="Clear All", style=discord.ButtonStyle.danger, custom_id="admin_help_clear_all")
	async def clear_all(self, interaction: discord.Interaction, button: discord.ui.button):
		if not self.check_admin(interaction):
			return await interaction.response.send_message(content="You do not have permission to use this button.", ephemeral=True)
		
		# Delete all threads in the channel
		deleted_threads = 0
		for thread in interaction.channel.threads:
			await thread.delete()
			deleted_threads += 1
		await interaction.response.send_message(content=f"Deleted {deleted_threads} threads.", ephemeral=True)

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

	# Claim button
	@discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="help_claim")
	async def claim(self, interaction: discord.Interaction, button: discord.ui.button):

		# Delay response
		await interaction.response.defer(thinking=True)
		
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
			json={
				"api_token": os.getenv("API_TOKEN"),
				"question_id": self.questionId,
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

	# Unclaim button
	@discord.ui.button(label="Unclaim", style=discord.ButtonStyle.gray, custom_id="help_unclaim")
	async def unclaim(self, interaction: discord.Interaction, button: discord.ui.button):
		
		# Delay response
		await interaction.response.defer(thinking=True)
		
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
			json={
				"api_token": os.getenv("API_TOKEN"),
				"question_id": self.questionId
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