'''
MCLabs Wiki RAG - Flask API

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
import uuid
from contextlib import asynccontextmanager

# API
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

# Google API
from google import genai

# MCL Packages
from mcl_common.logger import MCL_Logger
from src.internal.helpmanager import MCL_HelpManager
from mcl_common.mongo import MCL_MongoManager
from mcl_common.limiter import limiter
from src.network.relay import MCL_OutboundRelay
from src.network.endpoints import router as InternalEndpointsRouter

'''
FASTAPI APP STARTUP / SHUTDOWN
'''
@asynccontextmanager
async def lifespan(app: FastAPI):

	# Load environment variables from .env file if not in Railway environment
	if os.getenv("RAILWAY_ENVIRONMENT_ID") is None:
		from dotenv import load_dotenv
		load_dotenv()

	# Setup logging
	app.state.logger = MCL_Logger.setup_logger("MCL_API_Logger")

	# Gemini client
	# if not os.getenv("GOOGLE_GEMINI_API_KEY"):
	# 	app.state.logger.error("GOOGLE_GEMINI_API_KEY environment variable is not set.")
	# 	raise ValueError("GOOGLE_GEMINI_API_KEY environment variable is not set.")
	# app.state.InstanceClient = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

	# Load the index and documents
	# app.state.InstanceWikiEmbedder = MCL_WikiEmbedder(client=app.state.InstanceClient)
	# app.state.InstanceWikiEmbedder.loadIndexAndDocuments()

	# RAG instance
	# app.state.InstanceRag = MCL_WikiRag(client=app.state.InstanceClient, wikiEmbedder=app.state.InstanceWikiEmbedder)

	# Initialize Help Manager
	MCL_HelpManager().initialize()

	# Initialize Mongo Manager
	MCL_MongoManager().initialize(logger=app.state.logger)

	# Track backend session ID to handle rolling restarts cleanly
	app.state.session_id = str(uuid.uuid4())
	try:
		MCL_MongoManager().register_session("backend", app.state.session_id)
		app.state.logger.info(f"Registered backend session: {app.state.session_id}")
	except Exception as e:
		app.state.logger.exception(f"Failed to register backend session in MongoDB: {e}")

	# Initialize Outbound Relay
	MCL_OutboundRelay().initialize()

	# Log startup
	startupMessage: str = f"MCL Backend API started with PID {os.getpid()}!"
	app.state.logger.info(startupMessage)
	await MCL_OutboundRelay().messageDiscordAdminChannel(f"🟢 {startupMessage}")

	# Yield back for app lifetime
	yield

	# Check if this instance is still the active session in MongoDB
	is_active = hasattr(app.state, "session_id")
	if is_active:
		try:
			active_id = MCL_MongoManager().get_active_session("backend")
			if active_id and active_id != app.state.session_id:
				is_active = False
				app.state.logger.info(f"This session ({app.state.session_id}) is not active (current active: {active_id}). Skipping shutdown notification.")
		except Exception as mongo_err:
			app.state.logger.exception(f"Error checking active session in MongoDB during shutdown: {mongo_err}")

	# Log shutdown
	shutdownMessage: str = f"MCL Backend API shutting down with PID {os.getpid()}!"
	app.state.logger.info(shutdownMessage)
	if is_active:
		await MCL_OutboundRelay().messageDiscordAdminChannel(f"🔴 {shutdownMessage}")

	# Shutdown Mongo Manager
	MCL_MongoManager().shutdown()

'''
FASTAPI APP DEFINITION
'''

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # type: ignore[arg-type]
app.include_router(InternalEndpointsRouter)