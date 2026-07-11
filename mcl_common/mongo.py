'''
MCLabs Common - Mongo Manager

Author: Chris Hinkson @cmh02
'''

import os
import asyncio
import logging
from typing import Any, Optional
from pymongo import MongoClient

from src.network.relay import MCL_OutboundRelay
from mcl_common.datatypes import HelpTicket, Conversation, Message, PlayerInfo
from mcl_common.enum import TicketType, TicketStatus, TicketFeedback, MongoDatabase, MongoCollection, TicketAction


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

	def savePlayerInfo(self, playerInfo: PlayerInfo) -> Any:
		"""
		## Save Player Info

		Saves or updates a PlayerInfo object in the "players" collection.
		Finds an existing record if any non-None field matches, and updates/merges.
		"""
		playerDict = playerInfo.toDict()
		# Build a query of all non-None fields to find an existing record
		query_clauses = []
		for key, val in playerDict.items():
			if val is not None:
				query_clauses.append({key: val})

		# If all fields are None, insert as a new blank document
		if not query_clauses:
			result = self.collections[MongoDatabase.BOT][MongoCollection.PLAYERS].insert_one(playerDict)
			return result

		# Query to find if any of the fields already exist in the collection
		filter_query = {"$or": query_clauses}

		# Attempt to find an existing document
		existing = self.collections[MongoDatabase.BOT][MongoCollection.PLAYERS].find_one(filter_query)

		if existing:
			# Merge existing document data with the new non-None values
			updated_dict = {**existing, **{k: v for k, v in playerDict.items() if v is not None}}
			# Perform replace using the _id from the existing document
			result = self.collections[MongoDatabase.BOT][MongoCollection.PLAYERS].replace_one(
				{"_id": existing["_id"]},
				updated_dict
			)
			return result
		else:
			# Insert as a new document
			result = self.collections[MongoDatabase.BOT][MongoCollection.PLAYERS].insert_one(playerDict)
			return result

	def getPlayerInfo(self, 
					  minecraftUsername: Optional[str] = None,
					  minecraftUUID: Optional[str] = None,
					  discordUsername: Optional[str] = None,
					  discordId: Optional[str] = None) -> Optional[PlayerInfo]:
		"""
		## Get Player Info

		Retrieves a PlayerInfo object by querying any of the four fields.
		Returns the first matching PlayerInfo object, or None if not found.
		"""
		query_clauses = []
		if minecraftUsername is not None:
			query_clauses.append({"minecraftUsername": minecraftUsername})
		if minecraftUUID is not None:
			query_clauses.append({"minecraftUUID": minecraftUUID})
		if discordUsername is not None:
			query_clauses.append({"discordUsername": discordUsername})
		if discordId is not None:
			query_clauses.append({"discordId": discordId})

		if not query_clauses:
			return None

		filter_query = {"$or": query_clauses}
		doc = self.collections[MongoDatabase.BOT][MongoCollection.PLAYERS].find_one(filter_query)
		if doc:
			return PlayerInfo.fromDict(doc)
		return None

	def resolveAndSyncPlayerInfo(self, playerInfo: PlayerInfo, backgroundTasks: Optional[Any] = None) -> PlayerInfo:
		"""
		## Resolve and Sync Player Info

		Resolves any missing fields in the incoming PlayerInfo object by querying MongoDB.
		If MongoDB is missing any fields that the incoming object has, or if the player
		doesn't exist at all, it saves/updates the record. Database writes and external api
		lookups are performed asynchronously if backgroundTasks is provided.
		"""
		playerDict = playerInfo.toDict()
		# Build dict of non-None fields in the incoming data
		incomingFields = {k: v for k, v in playerDict.items() if v is not None}

		if not incomingFields:
			return playerInfo

		# Query database for an existing document using whatever is available
		existingPlayer = self.getPlayerInfo(
			minecraftUsername=playerInfo.minecraftUsername,
			minecraftUUID=playerInfo.minecraftUUID,
			discordUsername=playerInfo.discordUsername,
			discordId=playerInfo.discordId
		)

		needsDbUpdate = False

		if existingPlayer:
			existingDict = existingPlayer.toDict()
			# Merge any fields that are in MongoDB but missing from the incoming request
			for field, val in existingDict.items():
				if getattr(playerInfo, field) is None and val is not None:
					setattr(playerInfo, field, val)

			# Check if we were given fields that MongoDB is missing
			for field, val in incomingFields.items():
				if existingDict.get(field) is None:
					needsDbUpdate = True
					break
		else:
			# Player doesn't exist in DB at all, so we will need to save them
			needsDbUpdate = True

		# Check if there are still any missing fields that can be resolved externally
		missingResolvable = (
			(playerInfo.minecraftUUID and not playerInfo.minecraftUsername) or
			(playerInfo.minecraftUsername and not playerInfo.minecraftUUID) or
			(playerInfo.discordId and not playerInfo.discordUsername)
		)

		if missingResolvable:
			# Query external resources and save in the background (or synchronously if no backgroundTasks)
			if backgroundTasks is not None:
				backgroundTasks.add_task(self._backgroundResolveExternalAndSave, playerInfo)
			else:
				try:
					loop = asyncio.get_running_loop()
				except RuntimeError:
					loop = None

				if loop and loop.is_running():
					loop.create_task(self._backgroundResolveExternalAndSave(playerInfo))
				else:
					asyncio.run(self._backgroundResolveExternalAndSave(playerInfo))
		elif needsDbUpdate:
			# No external resolution needed, but we need to save/update the DB record
			if backgroundTasks is not None:
				backgroundTasks.add_task(self.savePlayerInfo, playerInfo)
			else:
				self.savePlayerInfo(playerInfo)

		return playerInfo

	async def _backgroundResolveExternalAndSave(self, playerInfo: PlayerInfo) -> None:
		"""
		## Background Resolve External and Save

		Queries Mojang and Discord APIs for any missing player fields,
		and saves the fully merged PlayerInfo object to MongoDB.
		"""
		from mcl_common.user_lookup import UserInfoLookup

		# Record initial values to check if they got updated/resolved
		initial_username = playerInfo.minecraftUsername
		initial_uuid = playerInfo.minecraftUUID
		initial_discord = playerInfo.discordUsername

		# Resolve Minecraft Username if we have UUID but no name
		if playerInfo.minecraftUUID and not playerInfo.minecraftUsername:
			try:
				name = await UserInfoLookup.getMinecraftNameByUuid(playerInfo.minecraftUUID)
				if name:
					playerInfo.minecraftUsername = name
			except Exception as e:
				self.logger.error(f"Error in background lookup of Minecraft name by UUID: {e}")

		# Resolve Minecraft UUID if we have username but no UUID
		if playerInfo.minecraftUsername and not playerInfo.minecraftUUID:
			try:
				uuid_str = await UserInfoLookup.getMinecraftUuidByName(playerInfo.minecraftUsername)
				if uuid_str:
					playerInfo.minecraftUUID = uuid_str
			except Exception as e:
				self.logger.error(f"Error in background lookup of Minecraft UUID by name: {e}")

		# Resolve Discord Username if we have Discord ID but no Discord Username
		if playerInfo.discordId and not playerInfo.discordUsername:
			try:
				discord_data = await UserInfoLookup.getDiscordUserById(playerInfo.discordId)
				if discord_data and "username" in discord_data:
					playerInfo.discordUsername = discord_data["username"]
			except Exception as e:
				self.logger.error(f"Error in background lookup of Discord user by ID: {e}")

		# Check if any missing info was resolved
		info_resolved = (
			(playerInfo.minecraftUsername != initial_username) or
			(playerInfo.minecraftUUID != initial_uuid) or
			(playerInfo.discordUsername != initial_discord)
		)

		# Save player info back to MongoDB (updates or creates)
		self.savePlayerInfo(playerInfo)

		# If info was resolved, notify external systems of the update
		if info_resolved:
			try:
				open_ticket_ids = self.getOpenTicketIdsForPlayer(playerInfo)
				for ticket_id in open_ticket_ids:
					MCL_OutboundRelay().relay(ticket_id, TicketAction.PLAYERINFOUPDATE)
			except ImportError:
				# Not running in backend context
				pass

	def getOpenTicketIdsForPlayer(self, playerInfo: PlayerInfo) -> list[int]:
		"""
		## Get Open Ticket IDs For Player

		Retrieves a list of open or claimed ticket IDs associated with a player.
		"""
		query_clauses = []
		if playerInfo.minecraftUUID:
			query_clauses.append({"playerInfo.minecraftUUID": playerInfo.minecraftUUID})
		if playerInfo.discordId:
			query_clauses.append({"playerInfo.discordId": playerInfo.discordId})

		if not query_clauses:
			return []

		# Only fetch open or claimed tickets
		filter_query = {
			"$and": [
				{"$or": query_clauses},
				{"status": {"$in": [TicketStatus.OPEN.value, TicketStatus.CLAIMED.value]}}
			]
		}
		projection = {"ticketId": 1, "_id": 0}
		cursor = self.collections[MongoDatabase.HELP][MongoCollection.TICKETS].find(filter_query, projection)
		return [doc["ticketId"] for doc in cursor]

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
