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
from src.rag.docloader import MCL_WikiDocLoader
from src.rag.rag import MCL_WikiRag

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

	# Validate Gemini environment variables
	gemini_api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
	gemini_model = os.getenv("GOOGLE_GEMINI_MODEL")

	if not gemini_api_key:
		app.state.logger.error("GOOGLE_GEMINI_API_KEY environment variable is not set.")
		raise RuntimeError("GOOGLE_GEMINI_API_KEY environment variable is not set.")
	if not gemini_model:
		app.state.logger.error("GOOGLE_GEMINI_MODEL environment variable is not set.")
		raise RuntimeError("GOOGLE_GEMINI_MODEL environment variable is not set.")

	# Gemini client
	app.state.InstanceClient = genai.Client(api_key=gemini_api_key)

	# Load the index and documents
	app.state.InstanceWikiDocLoader = MCL_WikiDocLoader()
	app.state.InstanceWikiDocLoader.loadIndexAndDocuments()

	# RAG instance
	app.state.InstanceRag = MCL_WikiRag(client=app.state.InstanceClient, docLoader=app.state.InstanceWikiDocLoader)

	# Initialize Help Manager
	MCL_HelpManager().initialize()
	MCL_HelpManager().set_rag_instance(app.state.InstanceRag)

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