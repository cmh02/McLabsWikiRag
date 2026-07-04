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
import datetime
from uuid import UUID
from discord import app_commands
from discord.ext import commands, tasks
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, HTTPException
from typing import Dict
from pydantic import BaseModel

from discordbot.logger import MCL_Logger
from discordbot.components import AdminHelpPanel, AdminHelpEmbed
from discordbot.threadmanager import MCL_ThreadManager

'''
BOT BACKEND SETUP
'''

# Initialize app
app = FastAPI()

@app.post("/wakeup")
def wakeup(request: Request):
	'''
	# WAKEUP ENDPOINT

	This endpoint is used solely for waking up the API when asleep on Railway. It still needs authentication.
	'''

	# Log wakeup attempt
	app.state.logger.debug(f"Discord bot wakeup request received!")
	
	# Return success message
	return JSONResponse(
		status_code=200,
		content={"status": "awake"}
	)

class UpdateRequest(BaseModel):
	update_id: UUID
	ticket_action: str
	ticket_id: int

@app.post("/update")
def update(request: Request, updateRequest: UpdateRequest):
	'''
	# UPDATE ENDPOINT

	This endpoint receives relay notifications from the backend.
	'''

	# Validate and extract request data
	data = updateRequest.model_dump()
	updateId = data.get("update_id")
	ticketAction = data.get("ticket_action")
	ticketId = data.get("ticket_id")

	# Placeholder for follow-up bot logic
	app.state.logger.info(
		f"Received relay update {updateId} for ticket {ticketId} with action {ticketAction}."
	)

	# Return success message
	return JSONResponse(
		status_code=200,
		content={
			"status": "success"
		}
	)
	
'''
BOT DEFINITION
'''

# Initialize bot
class MclBot(commands.Bot):

	async def setup_hook(self):
		self.session = aiohttp.ClientSession()

	async def close(self):
		await self.session.close()
		await super().close()

# Configure Discord intents
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

# Initialize bot
bot = MclBot(
	command_prefix="/", 
	intents=intents, 
	activity=discord.Streaming(
		name="MCLabs Wiki", 
		url="https://labs-mc.com/wiki/Main_Page"
	)
)

'''
BOT RUN
'''

# Run the bot
token: str | None = os.getenv("DISCORD_BOT_TOKEN")
if token is None:
	raise ValueError("DISCORD_BOT_TOKEN environment variable is not set.")
bot.run(token)
