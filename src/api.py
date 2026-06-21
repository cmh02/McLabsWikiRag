'''
MCLabs Wiki RAG - Flask API

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager

# Typing
from typing import cast, Dict, Optional

# API
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, HTTPException, Request
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler

# Google API
from google import genai

# MCL Packages
from src.rag import MCL_WikiRag
from src.utils.logger import MCL_Logger
from src.network.security import verifyRequest
from src.rag.docfetch import MCL_WikiEmbedder
from src.internal.helpmanager import MCL_HelpManager
from src.internal.mongo import MCL_MongoManager
from src.utils.datatypes import Message
from src.network.schemas import BaseHelpQuestionSchema, QuestionSchema
from src.utils.enum import TicketType, TicketStatus, TicketFeedback, UpdateSource
from src.network.limiter import limiter
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
	app.state.logger = MCL_Logger.setup_logger()

	# Gemini client
	app.state.InstanceClient = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

	# Load the index and documents
	app.state.InstanceWikiEmbedder = MCL_WikiEmbedder(client=app.state.InstanceClient)
	app.state.InstanceWikiEmbedder.loadIndexAndDocuments()

	# RAG instance
	app.state.InstanceRag = MCL_WikiRag(client=app.state.InstanceClient, wikiEmbedder=app.state.InstanceWikiEmbedder)

	# Initialize Help Manager
	MCL_HelpManager().initialize()

	# Initialize Mongo Manager
	MCL_MongoManager().initialize()

	# Log startup
	app.state.logger.info(f"MCL RAG API started with PID {os.getpid()}!")

	# Yield back for app lifetime
	yield

	# Shutdown Mongo Manager
	MCL_MongoManager().shutdown()

	# Log shutdown
	app.state.logger.info(f"MCL RAG API shutting down with PID {os.getpid()}!")

	# Save help questions on shutdown

'''
FASTAPI APP DEFINITION
'''

# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(InternalEndpointsRouter)