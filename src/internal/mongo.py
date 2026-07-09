'''
MCLabs Backend - Mongo Manager

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

'''
MONGO MANAGER
'''

import os
import logging
from typing import Optional
from starlette import status
from pymongo import MongoClient

from src.utils.datatypes import HelpTicket, Conversation, Message, PlayerInfo
from src.utils.enum import TicketType, TicketStatus, TicketFeedback


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

	def initialize(self):
		'''
		# Class Initialization

		Initializes the mongo manager with a connection to MongoDB.
		'''

		# Load mongo connection details from environment variables
		self.mongoConnectionString = os.getenv("MCL_MONGO_CONNECTION_STRING")
		if not self.mongoConnectionString:
			raise ValueError("MCL_MONGO_CONNECTION_STRING environment variable is not set.")
		self.mongoDatabaseName = os.getenv("MCL_MONGO_DATABASE_NAME")
		if not self.mongoDatabaseName:
			raise ValueError("MCL_MONGO_DATABASE_NAME environment variable is not set.")
		self.mongoCollectionName = os.getenv("MCL_MONGO_COLLECTION_NAME")
		if not self.mongoCollectionName:
			raise ValueError("MCL_MONGO_COLLECTION_NAME environment variable is not set.")

		# Create connection with pymongo
		self.client = MongoClient(self.mongoConnectionString)
		self.db = self.client[self.mongoDatabaseName]
		self.collection = self.db[self.mongoCollectionName]

		# Log initialization
		self.logger = logging.getLogger("MCL_API_Logger")
		self.logger.info(f"Mongo Manager initialized with PID {os.getpid()}.")

	def shutdown(self):

		# Close mongo connection
		self.client.close()
		self.logger.info(f"Mongo Manager connection closed for PID {os.getpid()}.")

	def saveTicket(self, ticket: HelpTicket):
		
		# Convert ticket to dict and save to mongo
		ticketDict = ticket.toDict()
		ticketId = ticketDict["ticketId"]

		# Define filter and update for upsert
		filter = {"ticketId": ticketId}
		result = self.collection.replace_one(
			filter=filter,
			replacement=ticketDict,
			upsert=True
		)
		return result

	def getTicket(self, ticketId: int) -> HelpTicket:

		# Get the ticket data from mongo
		ticket_data = self.collection.find_one({"ticketId": ticketId})
			
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
		ticket_data = self.collection.find_one({"threadId": threadId})
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

	def getAllTicketIds(self, type: TicketType=None, status: TicketStatus=None) -> list[int]:
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
		cursor = self.collection.find(query_filter, projection)

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