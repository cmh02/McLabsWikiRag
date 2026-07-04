'''
MCLabs Wiki GPT - Discord Bot

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import asyncio
import logging
import aiohttp
import discord
from discord.ext import commands
from contextlib import asynccontextmanager
from fastapi import FastAPI
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from discordbot.utils.logger import MCL_Logger
from discordbot.network.limiter import limiter
from discordbot.network.endpoints import router as InternalEndpointsRouter
from discordbot.network.relay import MCL_OutboundRelay

'''
BOT DEFINITION
'''

class MclBot(commands.Bot):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.logger = logging.getLogger("MCL_DISCORD_Logger")

	async def setup_hook(self):
		self.session = aiohttp.ClientSession()

	async def close(self):
		await self.session.close()
		await super().close()

	async def on_ready(self):
		self.logger.info("MCL Discord Bot is online and ready!")

# Configure Discord intents
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

# Initialize bot instance
bot = MclBot(
	command_prefix="/", 
	intents=intents, 
	activity=discord.Streaming(
		name="MCLabs Wiki", 
		url="https://labs-mc.com/wiki/Main_Page"
	)
)

'''
FASTAPI APP STARTUP / SHUTDOWN
'''
@asynccontextmanager
async def lifespan(app: FastAPI):

	# Ensure that we are running on Railway
	if os.getenv("RAILWAY_ENVIRONMENT_ID") is None:
		raise RuntimeError("RAILWAY_ENVIRONMENT_ID environment variable is not set.")
	
	# Setup logging
	app.state.logger = MCL_Logger.setup_logger()

	# Store bot reference in app state
	app.state.bot = bot

	# Initialize outbound relay with bot
	MCL_OutboundRelay().initialize(bot)

	# Start the Discord bot in the background
	token = os.getenv("DISCORD_BOT_TOKEN")
	if not token:
		app.state.logger.error("DISCORD_BOT_TOKEN environment variable is not set.")
		raise ValueError("DISCORD_BOT_TOKEN environment variable is not set.")

	# Startup Discord bot
	app.state.bot_task = asyncio.create_task(bot.start(token))
	app.state.logger.info(f"MCL Discord Bot API started with PID {os.getpid()}!")

	# Yield lifespan
	yield

	# Shutdown bot gracefully
	app.state.logger.info(f"Attempting to shut down MCL Discord Bot API with PID {os.getpid()}!")
	await bot.close()
	try:
		await app.state.bot_task
	except asyncio.CancelledError:
		pass
	app.state.logger.info(f"MCL Discord Bot API shut down with PID {os.getpid()}!")

'''
FASTAPI APP DEFINITION
'''

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.include_router(InternalEndpointsRouter)

'''
BOT RUN
'''

if __name__ == "__main__":
	import uvicorn
	port = int(os.getenv("PORT", 5000))
	uvicorn.run("discordbot.bot:app", host="0.0.0.0", port=port, log_level="info")
