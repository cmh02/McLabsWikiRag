'''
MCLabs Wiki GPT - Discord Bot

Author: Chris Hinkson @cmh02
'''

'''
SOCKS MONKEY PATCH
'''

import os
import socks
import socket as _socket
from urllib.parse import urlparse

# Define monkeypatch so we can use proxy for mongo
def socks_monkey_patch():
	tailscaleProxyUrl = os.getenv("RAILWAY_TAILSCALE_DOMAIN")
	if not tailscaleProxyUrl:
		raise ValueError("RAILWAY_TAILSCALE_DOMAIN environment variable is not set.")
	print(f"Applying Tailscale SOCKS5 proxy patch pointing to: {tailscaleProxyUrl}")
	proxy = urlparse(tailscaleProxyUrl)
	socks.set_default_proxy(
		socks.SOCKS5,
		proxy.hostname,
		proxy.port,
		rdns=True
	)
	_socket.socket = socks.socksocket
	if hasattr(_socket, 'SOCK_CLOEXEC'):
		delattr(_socket, 'SOCK_CLOEXEC')

# Execute the patch before any internal imports or mongo imports
socks_monkey_patch()



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

from mcl_common.logger import MCL_Logger
from mcl_common.limiter import limiter
from mcl_common.datatypes import PlayerInfo
from discordbot.network.endpoints import router as InternalEndpointsRouter
from discordbot.network.relay import MCL_OutboundRelay
from mcl_common.mongo import MCL_MongoManager
from discordbot.components.ticket_view import HelpTicketThreadView

'''
BOT DEFINITION
'''

class MclBot(commands.Bot):
	session: aiohttp.ClientSession

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.logger = logging.getLogger("MCL_DISCORD_Logger")
		self.logger.info("MCL Discord Bot has been initialized!")
		self.has_sent_online = False

	async def ensureApiAwake(self, numberTries: int = 5, sleepInterval: int = 3) -> bool:
		'''
		# Ensure API Awake

		Pings the backend /wakeup endpoint with standard headers and token authentication
		to ensure the backend service is awake (since Railway can scale down / sleep).
		Uses exponential backoff for retries.
		'''
		domain_backend = os.getenv("RAILWAY_API_DOMAIN")
		token = os.getenv("API_TOKEN")
		user_agent = os.getenv("USER_AGENT_DISCORD_BOT")
		
		if not domain_backend or not token or not user_agent:
			self.logger.error("ensureApiAwake is missing required environment variables.")
			return False

		url = f"https://{domain_backend}/wakeup"
		headers = {
			"Authorization": token,
			"User-Agent": user_agent
		}

		delay = sleepInterval
		for attempt in range(numberTries):
			try:
				async with self.session.post(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
					if resp.status == 200:
						self.logger.info("Backend API is awake!")
						return True
					else:
						self.logger.warning(f"Wakeup attempt {attempt + 1} returned status {resp.status}.")
			except Exception as e:
				self.logger.warning(f"Wakeup attempt {attempt + 1} failed with exception: {e}")
			
			if attempt < numberTries - 1:
				self.logger.info(f"Sleeping for {delay} seconds before retrying wakeup...")
				await asyncio.sleep(delay)
				delay *= 1.5
				
		self.logger.error(f"Backend API failed to wake up after {numberTries} attempts.")
		return False

	async def setup_hook(self):
		self.session = aiohttp.ClientSession()

		# Validate DISCORD_TICKET_CHANNEL_ID environment variable
		ticket_channel_id = os.getenv("DISCORD_TICKET_CHANNEL_ID")
		if not ticket_channel_id:
			self.logger.error("DISCORD_TICKET_CHANNEL_ID environment variable is not set. Bot shutting down.")
			raise RuntimeError("DISCORD_TICKET_CHANNEL_ID environment variable is not set.")
		try:
			int(ticket_channel_id)
		except ValueError:
			self.logger.error("DISCORD_TICKET_CHANNEL_ID environment variable is not a valid integer. Bot shutting down.")
			raise RuntimeError("DISCORD_TICKET_CHANNEL_ID environment variable is not a valid integer.")

		# Validate DISCORD_ADMIN_CHANNEL_ID environment variable
		admin_channel_id = os.getenv("DISCORD_ADMIN_CHANNEL_ID")
		if not admin_channel_id:
			self.logger.error("DISCORD_ADMIN_CHANNEL_ID environment variable is not set. Bot shutting down.")
			raise RuntimeError("DISCORD_ADMIN_CHANNEL_ID environment variable is not set.")
		try:
			int(admin_channel_id)
		except ValueError:
			self.logger.error("DISCORD_ADMIN_CHANNEL_ID environment variable is not a valid integer. Bot shutting down.")
			raise RuntimeError("DISCORD_ADMIN_CHANNEL_ID environment variable is not a valid integer.")

		# Initialize Mongo Manager
		mongo_manager = MCL_MongoManager()
		mongo_manager.initialize(logger=self.logger)

		# Track bot session ID to handle rolling restarts cleanly
		import uuid
		self.session_id = str(uuid.uuid4())
		try:
			mongo_manager.register_session("discord", self.session_id)
			self.logger.info(f"Registered bot session: {self.session_id}")
		except Exception as e:
			self.logger.exception(f"Failed to register bot session in MongoDB: {e}")

		# Register persistent views
		self.add_view(HelpTicketThreadView())

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
			self.logger.info("Syncing Discord command tree!")
			synced = await self.tree.sync()
			self.logger.info(f"Successfully synced {len(synced)} command(s) globally.")
		except Exception as e:
			self.logger.exception(f"Failed to sync command tree: {e}")
			raise e

		self.logger.info("MCL Discord Bot has completed setup!")

	async def close(self):
		self.logger.info("MCL Discord Bot is shutting down!")
		admin_channel_id = os.getenv("DISCORD_ADMIN_CHANNEL_ID")
		if admin_channel_id:
			try:
				# Check if this instance is still the active session in MongoDB
				mongo_manager = MCL_MongoManager()
				is_active = hasattr(self, "session_id")
				if is_active:
					try:
						active_id = mongo_manager.get_active_session("discord")
						if active_id and active_id != self.session_id:
							is_active = False
							self.logger.info(f"This session ({self.session_id}) is not active (current active: {active_id}). Skipping shutdown notification.")
					except Exception as mongo_err:
						self.logger.exception(f"Error checking active session in MongoDB during shutdown: {mongo_err}")

				if is_active:
					channel = self.get_channel(int(admin_channel_id))
					if not channel:
						channel = await self.fetch_channel(int(admin_channel_id))
					if not channel:
						self.logger.error("MCL Discord Bot could not find admin channel!")
					elif not isinstance(channel, discord.TextChannel):
						self.logger.error("MCL Discord Bot admin channel is not a text channel!")
					else:
						await channel.send("🔴 MCL Discord Bot is shutting down!")
			except Exception as e:
				self.logger.exception(f"Failed to send shutdown message to admin channel: {e}")
		await self.session.close()
		try:
			MCL_MongoManager().shutdown()
		except Exception as e:
			self.logger.exception(f"Error shutting down Mongo Manager: {e}")
		await super().close()
		self.logger.info("MCL Discord Bot has shut down!")

	async def on_ready(self):
		self.logger.info("MCL Discord Bot is ready!")
		if self.has_sent_online:
			self.logger.info("MCL Discord Bot online message already sent for this session. Skipping duplicate.")
			return

		admin_channel_id = os.getenv("DISCORD_ADMIN_CHANNEL_ID")
		if admin_channel_id:
			try:
				channel = self.get_channel(int(admin_channel_id))
				if not channel:
					channel = await self.fetch_channel(int(admin_channel_id))
				if not channel:
					self.logger.error("MCL Discord Bot could not find admin channel!")
					return
				if not isinstance(channel, discord.TextChannel):
					self.logger.error("MCL Discord Bot admin channel is not a text channel!")
					return
				await channel.send("🟢 MCL Discord Bot is online!")
				self.has_sent_online = True
			except Exception as e:
				self.logger.exception(f"Failed to send online message to admin channel: {e}")

	async def on_message(self, message: discord.Message):
		# Skip bot messages
		if message.author.bot:
			return

		# Check if it's in a thread
		if isinstance(message.channel, discord.Thread):
			try:
				mongo = MCL_MongoManager()
				ticket = mongo.getTicketByThreadId(message.channel.id)
				if ticket:
					self.logger.info(f"Relaying message from Discord user {message.author.name} in thread {message.channel.id} for ticket {ticket.ticketId}.")
					
					sender = PlayerInfo(
						discordUsername=message.author.name,
						discordId=str(message.author.id)
					)
					
					success = await MCL_OutboundRelay().append_ticket_message(
						ticket_id=ticket.ticketId,
						content=message.content,
						sender=sender
					)
					if not success:
						self.logger.error(f"Failed to relay message to backend for ticket {ticket.ticketId}.")
			except Exception as e:
				self.logger.exception(f"Error handling message relay in thread: {e}")

		# Process commands if any
		await self.process_commands(message)

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
	app.state.logger = MCL_Logger.setup_logger("MCL_DISCORD_Logger")
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
app = FastAPI(
	lifespan=lifespan,
	docs_url=None,
	redoc_url=None,
	openapi_url=None
)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.include_router(InternalEndpointsRouter)