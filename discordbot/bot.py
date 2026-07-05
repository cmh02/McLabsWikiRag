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
		self.logger.info("MCL Discord Bot has been initialized!")

	async def setup_hook(self):
		self.session = aiohttp.ClientSession()

		# Dynamically load all cogs/extensions in the cogs directory
		cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
		if os.path.exists(cogs_dir):
			for filename in os.listdir(cogs_dir):
				if filename.endswith(".py") and not filename.startswith("_"):
					extension_name = f"discordbot.cogs.{filename[:-3]}"
					try:
						await self.load_extension(extension_name)
						self.logger.info(f"Loaded extension: {extension_name}")
					except Exception as e:
						self.logger.exception(f"Failed to load extension {extension_name}: {e}")
						raise e
		else:
			self.logger.warning(f"Cogs directory not found at: {cogs_dir}")

		# Sync application commands with Discord
		try:
			self.logger.info("Syncing Discord command tree...")
			synced = await self.tree.sync()
			self.logger.info(f"Successfully synced {len(synced)} command(s) globally.")
		except Exception as e:
			self.logger.exception(f"Failed to sync command tree: {e}")
			raise e

		self.logger.info("MCL Discord Bot has completed setup!")

	async def close(self):
		self.logger.info("MCL Discord Bot is shutting down!")
		await self.session.close()
		await super().close()
		self.logger.info("MCL Discord Bot has shut down!")

	async def on_ready(self):
		self.logger.info("MCL Discord Bot is ready!")

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
		name="MCLabs Help Assistant", 
		description="Ranked #2 Helper",
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
	app.state.logger.info(f"MCL Discord Bot API is starting up with PID {os.getpid()}!")

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
	app.state.logger.info(f"MCL Discord Bot API is shutting down with PID {os.getpid()}!")
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
