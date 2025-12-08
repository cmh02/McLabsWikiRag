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
import asyncio
import requests
import discord
from discord import app_commands
from discord.ext import commands, tasks

from discordbot.components import AdminHelpPanel
from discordbot.threadmanager import MCL_ThreadManager

'''
BOT DEFINITION
'''

# Configure Discord intents
intents = discord.Intents.default()
intents.messages = True

# Initialize bot
class MclBot(commands.Bot):

	async def setup_hook(self):

		# Initialize aiohttp session
		self.session = aiohttp.ClientSession()

		# Initialize thread manager
		mainChannelId = int(os.getenv("DISCORD_HELP_CHANNEL_ID"))
		MCL_ThreadManager().initialize(bot=self, channelId=mainChannelId)

	async def close(self):
		await self.session.close()
		await super().close()

bot = MclBot(
	command_prefix="/", 
	intents=intents, 
	activity=discord.Streaming(
		name="MCLabs Wiki", 
		url="https://labs-mc.com/wiki/Main_Page"
	)
)

@bot.event
async def on_ready():
	print(f"Discord bot is ready!")
	await bot.tree.sync()

	# Start admin panel
	async def post_admin_panel(self, channelId: int):

		# Get channel and pins
		channel = self.get_channel(channelId)
		if channel is None:
			print(f"Admin Panel Channel ID {channelId} not found!")
			return
		else:
			print(f"About to post admin panel in channel: {channel.name} ({channel.id})")
		pinnedMessages = await channel.pins()

		# Build embed
		embed = discord.Embed(
			title="MCL Help System — Admin Panel",
			description="This panel shows all current help questions.\nUse the buttons below to manage them."
		)

		# If the admin panel is already posted, then update it
		if pinnedMessages:
			for message in pinnedMessages:
				if message.embeds[0].title == "MCL Help System — Admin Panel":
					await message.edit(embed=embed, view=AdminHelpPanel(bot=self))
					return

		# Otherwise, post a new admin panel
		message = await channel.send(embed=embed, view=AdminHelpPanel(bot=self))
		await message.pin()
		print(f"Admin panel posted and pinned in channel: {channel.name} ({channel.id})")
	await post_admin_panel(channelId=int(os.getenv("DISCORD_HELP_CHANNEL_ID")))

@bot.tree.command(name="ask", description="Ask me anything!")
async def ask(interaction: discord.Interaction, question: str):

	# Make API request to wake up the API, trying a few times if necessary
	try:

		# Define wakeup variables
		wakeupCount = 0
		isAwake = False
		wakeup_payload = {"api_token": os.getenv("API_TOKEN")}

		# Attempt wakeup up to 5 times
		while (wakeupCount < 5) and not isAwake:
			async with bot.session.post(
				url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/wakeup", 
				json=wakeup_payload
			) as response:
				await response.json()

				# If we get an OK (200) or rate limit (429), consider the API awake
				if response.status in (200, 429):
					isAwake = True

				# Otherwise, wait a bit and try again
				else:
					wakeupCount += 1
					await asyncio.sleep(3)

		# If we couldn't wake up the API, inform the user
		if not isAwake:
			print(f"Wakeup Failed after 5 attempts!")
			await interaction.response.send_message(
				content=f"The API is currently unavailable. Please try again later.", 
				ephemeral=True
			)
			return
	except Exception as e:
		print(f"Wakeup Exception [ERROR CODE 001]: {e}")
		await interaction.response.send_message(
			content=f"An error has occured while waking up the API. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

	# Make API request to the RAG endpoint and get response
	query_response = None
	query_data = None
	try:
		query_payload = {
			"api_token": os.getenv("API_TOKEN"), 
			"question": question, 
			"include_context": "False"
		}
		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/query", 
			json=query_payload
		) as response:
			query_response = response
			query_data = await query_response.json()
	except Exception as e:
		print(f"Query Exception [ERROR CODE 003]: {e}")
		await interaction.response.send_message(
			content=f"An error has occured while querying the API. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return
	
	# Respond in Discord
	try:
		if query_response is None or query_data is None:
			await interaction.response.send_message(
				content=f"An error has occured while processing your request. Please contact a developer for further assistance!", 
				ephemeral=True
			)
			return
		elif query_response.status == 200:
			answer = query_data.get("answer", "An error has occured while processing your request. Please contact a developer for further assistance!")
			await interaction.response.send_message(
				content=answer,
				ephemeral=True
			)
		elif query_response.status == 429:
			print(f"Rate Limit Hit: {query_data}")
			await interaction.response.send_message(
				content=f"We are experiencing an increased number of requests. Please try again later.", 
				ephemeral=True
			)
		else:
			print(f"Query Error {query_response.status}: {query_data.get('error', 'Unknown error')}")
			await interaction.response.send_message(
				content=f"An error has occured while processing your request. Please contact a developer for further assistance!", 
				ephemeral=True
			)
	except Exception as e:
		print(f"Response Exception [ERROR CODE 004]: {e}")
		await interaction.response.send_message(
			content=f"An error has occured while responding to your request. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

'''
HELP SYSTEM - SYNCHRONIZATION
'''
@tasks.loop(seconds=15)
async def sync_help_questions():
	'''
	## Sync Help Questions Task

	Periodically syncs help questions from the API to Discord threads.
	'''

	# Fetch questions from the API
	questions_data = None
	try:
		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/list", 
			json={"api_token": os.getenv("API_TOKEN")}
		) as response:
			if response.status == 200:
				questions_data = await response.json()
			else:
				print(f"Help Questions Fetch Error {response.status}")
				return
	except Exception as e:
		print(f"Help Questions Fetch Exception [ERROR CODE 005]: {e}")
		return

	# Make sure some questions exist
	questions = questions_data.get("questions", [])
	if not questions:
		return
	
	# Get existing threads mapping
	threads_ThreadIdToQuestionId = MCL_ThreadManager().getAllThreads()
	threads_QuestionIdToThreadId = threads_ThreadIdToQuestionId.inverse

	# Sync each question to a Discord thread
	for question in questions:
		question_id = question.get("id")
		question_player = question.get("player")
		question_text = question.get("question")
		question_status = question.get("status", "Open")
		question_claimed_by = question.get("claimed_by", "Unclaimed")

		# Check if a thread for this question already exists
		if question_id in threads_QuestionIdToThreadId:

			# If this question already exists, then update the thread with new info
			thread_id = threads_QuestionIdToThreadId[question_id]
			await MCL_ThreadManager().updateHelpThread(
				threadId=thread_id,
				questionId=question_id,
				questionPlayer=question_player,
				questionStatus=question_status,
				questionContent=question_text,
				questionClaimedBy=question_claimed_by
			)

		else:

			# Otherwise, create a new thread for this question
			await MCL_ThreadManager().createHelpThread(
				questionId=question_id,
				questionPlayer=question_player,
				questionStatus=question_status,
				questionContent=question_text,
				questionClaimedBy=question_claimed_by
			)

	# Delete any threads for questions that no longer exist
	for thread_id, question_id in threads_ThreadIdToQuestionId.items():
		if not any(q.get("id") == question_id for q in questions):
			await MCL_ThreadManager().deleteHelpThread(threadId=thread_id)

'''
HELP SYSTEM - COMMAND INTERACTIONS
'''

@app_commands.command(name="add", description="Add a help question to the help system.")
@app_commands.describe(id="Question ID", question="The help question to add.")
async def add_help_question(interaction: discord.Interaction, id: str, question: str):
	'''
	## Add Help Question Command
	'''
	return

@app_commands.command(name="remove", description="Remove a help question from the help system.")
@app_commands.describe(id="Question ID")
async def remove_help_question(interaction: discord.Interaction, id: str):
	'''
	## Remove Help Question Command
	'''
	return

@app_commands.command(name="answer", description="Answer a help question in the help system.")
@app_commands.describe(id="Question ID", answer="The answer to the help question.")
async def answer_help_question(interaction: discord.Interaction, id: str, answer: str):
	'''
	## Answer Help Question Command
	'''
	return

@app_commands.command(name="claim", description="Claim a help question to work on.")
@app_commands.describe(id="Question ID")
async def claim_help_question(interaction: discord.Interaction, id: str):
	'''
	## Claim Help Question Command
	'''
	return

@app_commands.command(name="unclaim", description="Unclaim a help question.")
@app_commands.describe(id="Question ID")
async def unclaim_help_question(interaction: discord.Interaction, id: str):
	'''
	## Unclaim Help Question Command
	'''
	return






'''
BOT RUN
'''

# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
