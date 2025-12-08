'''
MCLabs Discord Components

Author: Chris Hinkson @cmh02

(NOTE: The term 'thread' in this context refers to Discord threads created for help questions, not system threads.)
'''

'''
MODULE IMPORTS
'''
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