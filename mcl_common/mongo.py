'''
MCLabs Common - Mongo Manager

Author: Chris Hinkson @cmh02
'''

import os
import logging
from typing import Optional
from pymongo import MongoClient

from mcl_common.datatypes import HelpTicket, Conversation, Message, PlayerInfo
from mcl_common.enum import TicketType, TicketStatus, TicketFeedback, MongoDatabase, MongoCollection


class MCL_MongoManager():
	'''
	MCL Mongo Manager Singleton

	Class to manage persisting tickets to MongoDB.
	'''
	_instance = None

	def __new__(cls):
		if cls._instance is None:
			cls._instance = super(MCL_MongoManager, cls).__new__(cls)
		return cls._instance

	def initialize(self, logger: Optional[logging.Logger | str] = None):
		'''
		# Class Initialization

		Initializes the mongo manager with a connection to MongoDB.
		'''

		# Load mongo connection details from environment variables
		self.mongoConnectionString = os.getenv("MCL_MONGO_CONNECTION_STRING")
		if not self.mongoConnectionString:
			raise ValueError("MCL_MONGO_CONNECTION_STRING environment variable is not set.")

		# Database Names
		help_db_name = os.getenv("MCL_MONGO_DATABASE_HELP")
		if not help_db_name:
			raise ValueError("MCL_MONGO_DATABASE_HELP environment variable is not set.")
		bot_db_name = os.getenv("MCL_MONGO_DATABASE_BOT")
		if not bot_db_name:
			raise ValueError("MCL_MONGO_DATABASE_BOT environment variable is not set.")

		# Collection Names
		tickets_col_name = os.getenv("MCL_MONGO_COLLECTION_TICKETS")
		if not tickets_col_name:
			raise ValueError("MCL_MONGO_COLLECTION_TICKETS environment variable is not set.")
		players_col_name = os.getenv("MCL_MONGO_COLLECTION_PLAYERS")
		if not players_col_name:
			raise ValueError("MCL_MONGO_COLLECTION_PLAYERS environment variable is not set.")
		system_status_col_name = os.getenv("MCL_MONGO_COLLECTION_SYSTEM_STATUS")
		if not system_status_col_name:
			raise ValueError("MCL_MONGO_COLLECTION_SYSTEM_STATUS environment variable is not set.")

		# Create connection with pymongo
		self.client = MongoClient(self.mongoConnectionString)

		# Store databases and collections in dictionaries
		self.databases = {
			MongoDatabase.HELP: self.client[help_db_name],
			MongoDatabase.BOT: self.client[bot_db_name]
		}

		self.collections = {
			MongoDatabase.HELP: {
				MongoCollection.TICKETS: self.databases[MongoDatabase.HELP][tickets_col_name]
			},
			MongoDatabase.BOT: {
				MongoCollection.PLAYERS: self.databases[MongoDatabase.BOT][players_col_name],
				MongoCollection.SYSTEM_STATUS: self.databases[MongoDatabase.BOT][system_status_col_name]
			}
		}

		# Log initialization
		if logger is None:
			self.logger = logging.getLogger("MCL_API_Logger")
		elif isinstance(logger, str):
			self.logger = logging.getLogger(logger)
		else:
			self.logger = logger

		# Ping the database to verify the connection and authentication
		try:
			self.client.admin.command('ping')
			self.logger.info("Successfully pinged MongoDB. Connection and auth are verified.")
		except Exception as e:
			self.logger.error(f"Failed to ping MongoDB: {e}")
			raise e

		self.logger.info(f"Mongo Manager initialized with PID {os.getpid()}.")

	def shutdown(self):

		# Close mongo connection
		self.client.close()
		self.logger.info(f"Mongo Manager connection closed for PID {os.getpid()}.")

	def register_session(self, system_name: str, session_id: str) -> None:
		"""
		## Register Session

		Registers the active session ID for a given system (e.g. "backend" or "discord") in the "system_status" collection.
		"""
		self.collections[MongoDatabase.BOT][MongoCollection.SYSTEM_STATUS].replace_one(
			{"_id": system_name},
			{"_id": system_name, "session_id": session_id},
			upsert=True
		)

	def get_active_session(self, system_name: str) -> Optional[str]:
		"""
		## Get Active Session

		Retrieves the active session ID for a given system from the "system_status" collection.
		"""
		status_doc = self.collections[MongoDatabase.BOT][MongoCollection.SYSTEM_STATUS].find_one({"_id": system_name})
		if status_doc:
			return status_doc.get("session_id")
		return None


	def saveTicket(self, ticket: HelpTicket):
		
		# Convert ticket to dict and save to mongo
		ticketDict = ticket.toDict()
		ticketId = ticketDict["ticketId"]

		# Define filter and update for upsert
		filter = {"ticketId": ticketId}
		result = self.collections[MongoDatabase.HELP][MongoCollection.TICKETS].replace_one(
			filter=filter,
			replacement=ticketDict,
			upsert=True
		)
		return result

	def getTicket(self, ticketId: int) -> HelpTicket:

		# Get the ticket data from mongo
		ticket_data = self.collections[MongoDatabase.HELP][MongoCollection.TICKETS].find_one({"ticketId": ticketId})
			
		# Check if ticket doesn't exist, if so init with blank ticket for id
		if not ticket_data:
			self.logger.warning(f"Ticket with ID {ticketId} not found in MongoDB. Initializing blank ticket.")
			return HelpTicket(
				ticketId=ticketId, 
				playerInfo=PlayerInfo(minecraftUUID="Unknown"), 
				type=TicketType.SUPPORT
			)
			
		# Deserialize and return ticket
		return self._deserializeTicket(ticket_data)

	def getTicketByThreadId(self, threadId: int) -> Optional[HelpTicket]:
		"""
		## Get Ticket By Thread ID

		Retrieves a help ticket by its linked Discord thread ID.
		"""
		ticket_data = self.collections[MongoDatabase.HELP][MongoCollection.TICKETS].find_one({"threadId": threadId})
		if not ticket_data:
			return None
		return self._deserializeTicket(ticket_data)

	def _deserializeTicket(self, ticket_data: dict) -> HelpTicket:
		# If ticket does exist, then repop fields
		ticket = HelpTicket(
			ticketId=ticket_data["ticketId"],
			playerInfo=PlayerInfo.fromDict(ticket_data["playerInfo"]),
			type=TicketType(ticket_data["type"]),
			conversation=Conversation.fromDict(ticket_data["conversation"]) if "conversation" in ticket_data else None,
			threadId=ticket_data.get("threadId")
		)
		ticket.status = TicketStatus(ticket_data["status"])
		ticket.feedback = TicketFeedback(ticket_data["feedback"])
		ticket.claimedBy = ticket_data.get("claimedBy")
		ticket.closedBy = ticket_data.get("closedBy")
		ticket.time_create = ticket_data.get("time_create")
		ticket.time_claim = ticket_data.get("time_claim")
		ticket.time_close = ticket_data.get("time_close")
		return ticket

	def getAllTicketIds(self, type: Optional[TicketType] = None, status: Optional[TicketStatus] = None) -> list[int]:
		"""
		## Get All Ticket IDs

		Retrieves a list of all ticket IDs. You can pass a type, status, or both to filter.
		"""

		# Build dynamic filter based on provided parameters
		query_filter = {}
		if type is not None:
			query_filter["type"] = type.value
		if status is not None:
			query_filter["status"] = status.value

		# Project to only get ticketId
		projection = {"ticketId": 1, "_id": 0}
		cursor = self.collections[MongoDatabase.HELP][MongoCollection.TICKETS].find(query_filter, projection)

		# Extract ticket IDs from cursor
		ticket_ids = [doc["ticketId"] for doc in cursor]
		return ticket_ids

	def getNextTicketId(self) -> int:
		"""
		## Get Next Ticket ID

		Retrieves the next ticket ID by finding the max existing ID and adding 1.
		"""

		# Get all id's and return max + 1
		allTicketIds: list[int] = self.getAllTicketIds()
		if not allTicketIds:
			return 1
		return max(allTicketIds) + 1
