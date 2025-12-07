'''
MCLabs Wiki GPT - Discord Bot

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import time
import aiohttp
import requests
import discord
from discord import app_commands
from discord.ext import commands, tasks

'''
BOT DEFINITION
'''

# Configure Discord intents
intents = discord.Intents.default()
intents.messages = True

# Initialize bot
class MclBot(commands.Bot):

	async def setup_hook(self):
		self.session = aiohttp.ClientSession()

	async def close(self):
		await self.session.close()
		await super().close()


bot = MclBot(command_prefix="/", intents=intents, activity=discord.Streaming(name="MCLabs Wiki", url="https://labs-mc.com/wiki/Main_Page"))

@bot.event
async def on_ready():
    print(f"Discord bot is ready!")
    await bot.tree.sync()

@bot.tree.command(name="ask", description="Ask me anything!")
async def ask(interaction: discord.Interaction, question: str):

	# Make API request to wake up the API, trying a few times if necessary
	try:
		wakeupCount = 0
		isAwake = False
		wakeup_payload = {"api_token": os.getenv("API_TOKEN")}
		while (wakeupCount < 5) and not isAwake:
			wakeup_response = requests.post(f"https://{os.getenv('RAILWAY_API_DOMAIN')}/wakeup", json=wakeup_payload)
			wakeup_data = wakeup_response.json()
			if wakeup_response.status_code in [200, 429]:
				isAwake = True
			else:
				wakeupCount += 1
				time.sleep(3)
		if not isAwake:
			print(f"Wakeup Failed after 5 attempts!")
			await interaction.response.send_message(content=f"The API is currently unavailable. Please try again later.", ephemeral=True)
	except Exception as e:
		print(f"Wakeup Exception [ERROR CODE 001]: {e}")
		await interaction.response.send_message(content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", ephemeral=True)

	# Make sure wakeup was successful
	try:
		if wakeup_response.status_code not in [200, 429]:
			print(f"Wakeup Error {wakeup_response.status_code}: {wakeup_data.get('error', 'Unknown error')}")
			await interaction.response.send_message(content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", ephemeral=True)
	except Exception as e:
		print(f"Wakeup Exception [ERROR CODE 002]: {e}")
		await interaction.response.send_message(content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", ephemeral=True)

	# Make API request to the RAG endpoint and get response
	try:
		query_payload = {"api_token": os.getenv("API_TOKEN"), "question": question, "include_context": "False"}
		query_response = requests.post(f"https://{os.getenv('RAILWAY_API_DOMAIN')}/query", json=query_payload)
		query_data = query_response.json()
	except Exception as e:
		print(f"Query Exception [ERROR CODE 003]: {e}")
		await interaction.response.send_message(content=f"An error has occured while querying the API. Please contact a developer for further assistance!", ephemeral=True)
	
	# Respond in Discord
	try:
		if query_response.status_code == 200:
			answer = query_data.get("answer", "An error has occured while processing your request. Please contact a developer for further assistance!")
			await interaction.response.send_message(content=answer, ephemeral=True)
		elif query_response.status_code == 429:
			print(f"Rate Limit Hit: {query_data}")
			await interaction.response.send_message(content=f"We are experiencing an increased number of requests. Please try again later.", ephemeral=True)
		else:
			print(f"Query Error {query_response.status_code}: {query_data.get('error', 'Unknown error')}")
			await interaction.response.send_message(content=f"An error has occured while processing your request. Please contact a developer for further assistance!", ephemeral=True)
	except Exception as e:
		print(f"Response Exception [ERROR CODE 004]: {e}")
		await interaction.response.send_message(content=f"An error has occured while responding to your request. Please contact a developer for further assistance!", ephemeral=True)

'''
HELP SYSTEM - SYNCHRONIZATION
'''
@tasks.loop(seconds=5)
async def sync_help_questions():
	'''
	## Sync Help Questions Task

	Periodically syncs help questions from the API to Discord threads.
	'''

	# Fetch questions from the API
	getQuestions_payload = {"api_token": os.getenv("API_TOKEN")}
	async with bot.session.post(f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/list", json=getQuestions_payload) as response:
		if response.status != 200:
			print(f"Failed to fetch help questions: {response.status}")
			return
		questions = await response.json()
		questions = questions.get("questions", [])

	# For each question, check if Discord thread exists
	for question in questions:
		questionId = question.get("question_id")



'''
HELP SYSTEM - ADMIN PANEL
'''

class AdminHelpPanel(discord.ui.view):

	# Initialize the admin panel view
	def __init__(self):
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

@bot.command()
@commands.has_permissions(administrator=True)
async def initpanel(ctx):
    embed = discord.Embed(
        title="MCL Help System — Admin Panel",
        description="This panel shows all current help questions.\nUse the buttons below to manage them."
    )

    await ctx.send(embed=embed, view=AdminHelpPanel())

'''
HELP SYSTEM - COMMAND INTERACTIONS
'''

@app_commands.command(name="add", description="Add a help question to the help system.")
@app_commands.describe(id="Question ID", question="The help question to add.")
async def add_help_question(interaction: discord.Interaction, questionId: str, question: str):
	'''
	## Add Help Question Command
	'''


	pass

@app_commands.command(name="remove", description="Remove a help question from the help system.")
@app_commands.describe(id="Question ID")
async def remove_help_question(interaction: discord.Interaction, id: str):
	'''
	## Remove Help Question Command
	'''
	pass

@app_commands.command(name="answer", description="Answer a help question in the help system.")
@app_commands.describe(id="Question ID", answer="The answer to the help question.")
async def answer_help_question(interaction: discord.Interaction, id: str, answer: str):
	'''
	## Answer Help Question Command
	'''
	pass

@app_commands.command(name="claim", description="Claim a help question to work on.")
@app_commands.describe(id="Question ID")
async def claim_help_question(interaction: discord.Interaction, id: str):
	'''
	## Claim Help Question Command
	'''
	pass

@app_commands.command(name="unclaim", description="Unclaim a help question.")
@app_commands.describe(id="Question ID")
async def unclaim_help_question(interaction: discord.Interaction, id: str):
	'''
	## Unclaim Help Question Command
	'''
	pass






'''
BOT RUN
'''

# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
