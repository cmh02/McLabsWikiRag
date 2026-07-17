'''
MCLabs Wiki RAG - Flask API

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
	
	# Resolve proxy address
	family = _socket.AF_INET
	try:
		addr_info = _socket.getaddrinfo(proxy.hostname, proxy.port, _socket.AF_UNSPEC, _socket.SOCK_STREAM)
		resolved_proxy_ip = addr_info[0][4][0]
		resolved_proxy_family = addr_info[0][0]
		print(f"Resolved proxy hostname to: {resolved_proxy_ip}")
	except Exception as e:
		print(f"Failed resolving proxy address: {e}")
		resolved_proxy_ip = proxy.hostname
	socks.set_default_proxy(
		socks.SOCKS5,
		str(resolved_proxy_ip),
		proxy.port,
		rdns=True
	)

	# Preserve a clean reference to the true original socket connect method
	original_socket_connect = _socket.socket.connect

	# Build a wrapper to allow certain domains to bypass proxy
	BYPASS_DOMAINS = {
		os.getenv("RAILWAY_DISCORD_DOMAIN"),
		os.getenv("RAILWAY_API_DOMAIN")
	}
	class CustomSocksSocket(socks.socksocket):
		def __init__(self, family=_socket.AF_INET, type=_socket.SOCK_STREAM, proto=0, *args, **kwargs):
			if family == _socket.AF_INET and resolved_proxy_family == _socket.AF_INET6:
				family = _socket.AF_INET6
			super().__init__(family, type, proto, *args, **kwargs)

		def connect(self, dest_pair):
			host = dest_pair[0] if dest_pair else ""
			
			# Check if the destination host matches any of our bypass targets
			if any(domain in str(host) for domain in BYPASS_DOMAINS):

				# Strip proxy for this request to route logic to real internet
				self.proxy = None 
				return original_socket_connect(self, dest_pair)
			
			# Otherwise, use normal SOCKS routing (e.g. for MongoDB)
			return super().connect(dest_pair)

	_socket.socket = CustomSocksSocket
	if hasattr(_socket, 'SOCK_CLOEXEC'):
		delattr(_socket, 'SOCK_CLOEXEC')

# Execute the patch before any internal imports or mongo imports
socks_monkey_patch()



'''
MODULE IMPORTS
'''

# System
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
from mcl_common.config import settings
from src.internal.helpmanager import MCL_HelpManager
from mcl_common.mongo import MCL_MongoManager
from mcl_common.limiter import limiter
from src.network.relay import MCL_OutboundRelay
from src.network.endpoints import router as InternalEndpointsRouter
from src.rag.docloader import MCL_WikiDocLoader
from src.rag.document import DocumentSource
from src.rag.rag import MCL_WikiRag

'''
FASTAPI APP STARTUP / SHUTDOWN
'''
@asynccontextmanager
async def lifespan(app: FastAPI):

	# Setup logging
	app.state.logger = MCL_Logger.setup_logger("MCL_API_Logger")

	# Gemini client
	app.state.InstanceClient = genai.Client(api_key=settings.google_gemini_api_key)

	# Load the index and documents
	app.state.InstanceWikiDocLoader = MCL_WikiDocLoader(
		dataDirectory = settings.railway_data_directory,
		embeddingDimension = settings.google_embedding_dimensions
	)
	app.state.InstanceWikiDocLoader.loadIndexAndDocuments()

	# RAG instance
	dynamic_source_scale = {
		DocumentSource.WIKI: settings.rag_hp_sourcescale_wiki,
		DocumentSource.HELP_QUESTION: settings.rag_hp_sourcescale_faq
	}
	dynamic_time_scale = {
		"recency": settings.rag_hp_recencyhalflife,
		"season": settings.rag_hp_seasonboost
	}

	app.state.InstanceRag = MCL_WikiRag(
		client=app.state.InstanceClient,
		docLoader=app.state.InstanceWikiDocLoader,
		generationModelName=settings.google_gemini_model,
		embeddingModelName=settings.google_embedding_model,
		embeddingDimension=settings.google_embedding_dimensions,
		dynamicSourceScale=dynamic_source_scale,
		dynamicTimeScale=dynamic_time_scale,
		cacheThreshold=settings.rag_hp_semantic_cache_threshold
	)

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
app = FastAPI(
	lifespan=lifespan,
	docs_url=None,
	redoc_url=None,
	openapi_url=None
)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # type: ignore[arg-type]
app.include_router(InternalEndpointsRouter)