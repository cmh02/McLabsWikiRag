'''
MCLabs Wiki GPT - Discord Bot

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import time
import logging
import uvicorn
import aiohttp
import asyncio
import discord
import requests
import datetime
from discord import app_commands
from discord.ext import commands, tasks
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, HTTPException
from typing import Dict

from src.schemas import BaseRequestSchema
from discordbot.logger import MCL_Logger
from discordbot.components import AdminHelpPanel
from discordbot.threadmanager import MCL_ThreadManager

'''
BOT BACKEND SETUP
'''

# Initialize app
app = FastAPI()

@app.post("/wakeup")
def wakeup(request: Request, body: BaseRequestSchema):
	'''
	# WAKEUP ENDPOINT

	This endpoint is used solely for waking up the API when asleep on Railway. It still needs authentication.
	'''
	
	# Get the request data
	data: Dict = body.model_dump()

	# Log wakeup attempt
	app.state.logger.debug(f"Discord bot wakeup request received!")
	
	# Check API token
	if data.get("api_token") != os.getenv("API_TOKEN"):
			
		# Log invalid attempt
		app.state.logger.debug(f"Invalid API token attempt: {data.get('api_token')}")
				  
		# Return error
		raise HTTPException(
			status_code=401, 
			detail="Invalid API token"
		)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "awake"}
	)

class UpdateHelpSystemRequest(BaseRequestSchema):

	# List for questions
	questions: list

@app.post("/update")
async def update_help_system(request: Request, body: UpdateHelpSystemRequest):
	'''
	# Sync Help Questions Task

	Periodically syncs help questions from the API to Discord threads.
	'''

	# Get the request data
	data: Dict = body.model_dump()

	# Log update request
	app.state.logger.debug(f"Discord bot help questions update request received!")
	app.state.logger.debug(f"Request Data: {data}")

	# Make sure some questions exist
	questions = data.get("questions", [])
	if not questions:
		return JSONResponse(
			status_code=400,
			content={"error": "No questions provided"}
		)
	
	# Dispatch to bot handler
	bot.loop.create_task(
		coro=bot.handleHelpSystemUpdate(questions=questions)
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "Update Received!"}
	)
	
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

	async def handleHelpSystemUpdate(self, questions: list):
		'''
		## Handle Help System Update

		Handles updating the help system threads in Discord based on the provided questions.

		### Parameters
		- questions (list): List of help question dictionaries.
		'''

		# Get existing threads mapping
		threads_ThreadIdToQuestionId = MCL_ThreadManager().getAllThreads()
		threads_QuestionIdToThreadId = threads_ThreadIdToQuestionId.inverse

		# Debug threada and questions
		app.state.logger.debug(f"Current Threads: {threads_QuestionIdToThreadId}")
		app.state.logger.debug(f"Questions to Sync: {questions}")

		# Sync each question to a Discord thread
		for question in questions:
			question_id = question.get("id")
			question_player = question.get("player")
			question_text = question.get("question")
			question_status = question.get("status", "OPEN")
			question_claimed_by = question.get("claimedBy", "Not Claimed Yet!")

			# Check if a thread for this question already exists
			if question_id in threads_QuestionIdToThreadId:

				# Debug log
				app.state.logger.debug(f"Help System Update Handler making request to update thread for question ID {question_id}.")

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

				# Debug log
				app.state.logger.debug(f"Help System Update Handler making request to create thread for question ID {question_id}.")

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

	# Initialize logger
	app.state.logger = MCL_Logger.setup_logger()
	
	# Initialize thread manager
	mainChannelId = int(os.getenv("DISCORD_HELP_CHANNEL_ID"))
	MCL_ThreadManager().initialize(bot=bot, channelId=mainChannelId)

	# Start admin panel
	async def post_admin_panel(channelId: int):

		# Get channel and pins
		channel = bot.get_channel(channelId)
		if channel is None:
			app.state.logger.error(f"Admin Panel Channel ID {channelId} not found!")
			return
		else:
			app.state.logger.info(f"About to post admin panel in channel: {channel.name} ({channel.id})")
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
					await message.edit(embed=embed, view=AdminHelpPanel(bot=bot))
					return

		# Otherwise, post a new admin panel
		message = await channel.send(embed=embed, view=AdminHelpPanel(bot=bot))
		await message.pin()
		app.state.logger.info(f"Admin panel posted and pinned in channel: {channel.name} ({channel.id})")
	await post_admin_panel(channelId=int(os.getenv("DISCORD_HELP_CHANNEL_ID")))

	# Start API server for webhooks
	async def start_api_server():
		config = uvicorn.Config(
			app,
			host="0.0.0.0",
			port=8000,
			log_level="info"
		)
		server = uvicorn.Server(config)
		app.state.logger.info("Starting webhook API server!")
		await server.serve()
	asyncio.create_task(start_api_server())

	# Sync application commands
	await bot.tree.sync()
	app.state.logger.info("Discord bot is ready!")

'''
BOT UTILITIES
'''

STAFF_ROLES = set(["Helper", "Mod", "Admin", "Owner"])
def doStaffCheck():
	async def predicate(interaction: discord.Interaction) -> bool:
		
		# Extract user role names
		userRoles = [role.name for role in interaction.user.roles]
		app.state.logger.debug(f"User {interaction.user.name} roles: {userRoles}")

		# Check if user has any staff roles
		if STAFF_ROLES.intersection(set(userRoles)):
			return True
		return False

	return app_commands.check(predicate)


'''
BOT COMMANDS
'''

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
		app.state.logger.error(f"Query Exception [ERROR CODE 003]: {e}")
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
			app.state.logger.warning(f"Rate Limit Hit: {query_data}")
			await interaction.response.send_message(
				content=f"We are experiencing an increased number of requests. Please try again later.", 
				ephemeral=True
			)
		else:
			app.state.logger.error(f"Query Error {query_response.status}: {query_data.get('error', 'Unknown error')}")
			await interaction.response.send_message(
				content=f"An error has occured while processing your request. Please contact a developer for further assistance!", 
				ephemeral=True
			)
	except Exception as e:
		app.state.logger.error(f"Response Exception [ERROR CODE 004]: {e}")
		await interaction.response.send_message(
			content=f"An error has occured while responding to your request. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

'''
HELP SYSTEM - COMMAND INTERACTIONS
'''

@bot.tree.command(name="add", description="Add a help question to the help system.")
@doStaffCheck()
async def add_help_question(interaction: discord.Interaction, id: str, question: str):
	'''
	## Add Help Question Command
	'''
	try:
		# Acknowledge the command
		await interaction.response.defer(ephemeral=True)

		# Make API request to add the help question
		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/add", 
			json={
				"api_token": os.getenv("API_TOKEN"),
				"question_id": id,
				"question_content": question,
				"question_player": interaction.user.name,
			}
		) as response:
			if response.status == 200:
				await interaction.followup.send(
					content=f"Help question #{id} added successfully!", 
					ephemeral=True
				)
				return
			else:
				await interaction.followup.send(
					content=f"Failed to add help question #{id}. Please try again later.", 
					ephemeral=True
				)
				return
	except Exception as e:
		app.state.logger.error(f"Add Help Question Exception [ERROR CODE 006]: {e}")
		await interaction.followup.send(
			content=f"An error has occured while adding the help question. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

@bot.tree.command(name="remove", description="Remove a help question from the help system.")
@doStaffCheck()
async def remove_help_question(interaction: discord.Interaction, id: str):
	'''
	## Remove Help Question Command
	'''
	try:
		# Acknowledge the command
		await interaction.response.defer(ephemeral=True)

		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/remove", 
			json={
				"api_token": os.getenv("API_TOKEN"),
				"question_id": id
			}
		) as response:
			if response.status == 200:
				await interaction.followup.send(
					content=f"Help question #{id} removed successfully!", 
					ephemeral=True
				)
				return
			else:
				await interaction.followup.send(
					content=f"Failed to remove help question #{id}. Please try again later.", 
					ephemeral=True
				)
				return
	except Exception as e:
		app.state.logger.error(f"Remove Help Question Exception [ERROR CODE 007]: {e}")
		await interaction.followup.send(
			content=f"An error has occured while removing the help question. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

@bot.tree.command(name="answer", description="Answer a help question in the help system.")
@doStaffCheck()
async def answer_help_question(interaction: discord.Interaction, id: str, answer: str):
	'''
	## Answer Help Question Command
	'''
	try:
		# Acknowledge the command
		await interaction.response.defer(ephemeral=True)

		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/answer", 
			json={
				"api_token": os.getenv("API_TOKEN"),
				"question_id": id,
				"answered_by": interaction.user.name,
				"answer": answer
			}
		) as response:
			if response.status == 200:
				await interaction.followup.send(
					content=f"Help question #{id} answered successfully!", 
					ephemeral=True
				)
				return
			else:
				await interaction.followup.send(
					content=f"Failed to answer help question #{id}. Please try again later.", 
					ephemeral=True
				)
				return
	except Exception as e:
		app.state.logger.error(f"Answer Help Question Exception [ERROR CODE 008]: {e}")
		await interaction.followup.send(
			content=f"An error has occured while answering the help question. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

@bot.tree.command(name="claim", description="Claim a help question to work on.")
@doStaffCheck()
async def claim_help_question(interaction: discord.Interaction, id: str):
	'''
	## Claim Help Question Command
	'''
	try:
		# Acknowledge the command
		await interaction.response.defer(ephemeral=True)

		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/claim", 
			json={
				"api_token": os.getenv("API_TOKEN"),
				"question_id": id,
				"claimed_by": interaction.user.name
			}
		) as response:
			if response.status == 200:
				await interaction.followup.send(
					content=f"Help question #{id} claimed successfully!", 
					ephemeral=True
				)
				return
			else:
				await interaction.followup.send(
					content=f"Failed to claim help question #{id}. Please try again later.", 
					ephemeral=True
				)
				return
	except Exception as e:
		app.state.logger.error(f"Claim Help Question Exception [ERROR CODE 009]: {e}")
		await interaction.followup.send(
			content=f"An error has occured while claiming the help question. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

@bot.tree.command(name="unclaim", description="Unclaim a help question.")
@doStaffCheck()
async def unclaim_help_question(interaction: discord.Interaction, id: str):
	'''
	## Unclaim Help Question Command
	'''
	try:
		# Acknowledge the command
		await interaction.response.defer(ephemeral=True)

		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/unclaim", 
			json={
				"api_token": os.getenv("API_TOKEN"),
				"question_id": id
			}
		) as response:
			if response.status == 200:
				await interaction.followup.send(
					content=f"Help question #{id} unclaimed successfully!", 
					ephemeral=True
				)
				return
			else:
				await interaction.followup.send(
					content=f"Failed to unclaim help question #{id}. Please try again later.", 
					ephemeral=True
				)
				return
	except Exception as e:
		app.state.logger.error(f"Unclaim Help Question Exception [ERROR CODE 010]: {e}")
		await interaction.followup.send(
			content=f"An error has occured while unclaiming the help question. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

@bot.tree.command(name="list", description="List all help questions.")
@doStaffCheck()
async def list_help_questions(interaction: discord.Interaction):
	'''
	## List Help Questions Command
	'''
	try:
		# Acknowledge the command
		await interaction.response.defer(ephemeral=True)

		async with bot.session.post(
			url=f"https://{os.getenv('RAILWAY_API_DOMAIN')}/help/list", 
			json={
				"api_token": os.getenv("API_TOKEN")
			}
		) as response:
			if response.status == 200:
				data = await response.json()
				questions = data.get("questions", {})
				if not questions:
					await interaction.followup.send(
						content=f"There are currently no help questions.", 
						ephemeral=True
					)
					return
				else:
					message_content = "Current Help Questions:\n"
					for questionData in questions:
						message_content += f"#{questionData.get('id', 'Unknown')} (Asked By {questionData.get('player', 'Unknown')}) - {questionData.get('status', 'Open')}\n"
					await interaction.followup.send(
						content=message_content, 
						ephemeral=True
					)
					return
			else:
				await interaction.followup.send(
					content=f"Failed to retrieve help questions. Please try again later.", 
					ephemeral=True
				)
				return
	except Exception as e:
		app.state.logger.error(f"List Help Questions Exception [ERROR CODE 011]: {e}")
		await interaction.followup.send(
			content=f"An error has occured while listing the help questions. Please contact a developer for further assistance!", 
			ephemeral=True
		)
		return

'''
BOT RUN
'''

# Run the bot
bot.run(os.getenv("DISCORD_BOT_TOKEN"))
