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
from mcl_common.datatypes import HelpTicket, Conversation, Message, PlayerInfo, ServerStatus, DiscordInfo
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
		server_status_col_name = os.getenv("MCL_MONGO_COLLECTION_SERVER_STATUS")
		if not server_status_col_name:
			raise ValueError("MCL_MONGO_COLLECTION_SERVER_STATUS environment variable is not set.")

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
				MongoCollection.SYSTEM_STATUS: self.databases[MongoDatabase.BOT][system_status_col_name],
				MongoCollection.SERVER_STATUS: self.databases[MongoDatabase.BOT][server_status_col_name]
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

		New refactored lookup process:
		1. Take in a request from an endpoint.
		2. Check if we already have this player registered in MongoDB synchronously.
		3. If found, merge the existing Minecraft and Discord details immediately.
		4. Check if any of the data is missing (i.e. any of the 4 fields is None or empty/whitespace).
		5. If NOT missing, skip any external queries, and simply launch an async mongo update with this latest given information.
		6. If data is missing, we launch a background task to get data from MongoDB, lookup authoritative names externally, update Mongo, and relay the update.
		"""
		# Clean fields and handle empty strings as None
		playerInfo.minecraftUsername = playerInfo.minecraftUsername.strip() if playerInfo.minecraftUsername else None
		playerInfo.minecraftUUID = playerInfo.minecraftUUID.strip() if playerInfo.minecraftUUID else None
		playerInfo.discordUsername = playerInfo.discordUsername.strip() if playerInfo.discordUsername else None
		playerInfo.discordId = playerInfo.discordId.strip() if playerInfo.discordId else None

		# Query MongoDB synchronously first to resolve any already linked player information
		try:
			existingPlayer = self.getPlayerInfo(
				playerInfo.minecraftUsername,
				playerInfo.minecraftUUID,
				playerInfo.discordUsername,
				playerInfo.discordId
			)
			if existingPlayer:
				if not playerInfo.minecraftUsername:
					playerInfo.minecraftUsername = existingPlayer.minecraftUsername
				if not playerInfo.minecraftUUID:
					playerInfo.minecraftUUID = existingPlayer.minecraftUUID
				if not playerInfo.discordUsername:
					playerInfo.discordUsername = existingPlayer.discordUsername
				if not playerInfo.discordId:
					playerInfo.discordId = existingPlayer.discordId
		except Exception as e:
			self.logger.error(f"Error checking existing player info synchronously: {e}")

		# Check if any of the data is missing
		is_missing = not (
			playerInfo.minecraftUsername and
			playerInfo.minecraftUUID and
			playerInfo.discordUsername and
			playerInfo.discordId
		)

		if not is_missing:
			# Skip any kind of queries, simply launch an async mongo update
			if backgroundTasks is not None:
				backgroundTasks.add_task(self.savePlayerInfo, playerInfo)
			else:
				try:
					loop = asyncio.get_running_loop()
				except RuntimeError:
					loop = None

				if loop and loop.is_running():
					loop.run_in_executor(None, self.savePlayerInfo, playerInfo)
				else:
					self.savePlayerInfo(playerInfo)
		else:
			# Launch background task to go get data from the mongo database using what was given,
			# then lookup Minecraft and Discord names async, merge them, update MongoDB, and relay.
			if backgroundTasks is not None:
				backgroundTasks.add_task(self._runBackgroundResolve, playerInfo)
			else:
				try:
					loop = asyncio.get_running_loop()
				except RuntimeError:
					loop = None

				if loop and loop.is_running():
					loop.create_task(self._runBackgroundResolve(playerInfo))
				else:
					asyncio.run(self._runBackgroundResolve(playerInfo))

		return playerInfo

	async def _runBackgroundResolve(self, playerInfo: PlayerInfo) -> None:
		"""
		## Run Background Resolve

		Runs the background pipeline when some player data is missing:
		1. Get data from MongoDB using the given fields.
		2. Merge the retrieved database data into playerInfo.
		3. Lookup Minecraft UUID and Discord ID to get authoritative names async.
		4. Merge the updated names.
		5. Save to MongoDB.
		6. Send out update for new player info refresh.
		"""
		from mcl_common.user_lookup import UserInfoLookup

		loop = asyncio.get_running_loop()

		# Store initial values to compare at the end
		initial_username = playerInfo.minecraftUsername
		initial_uuid = playerInfo.minecraftUUID
		initial_discord_username = playerInfo.discordUsername
		initial_discord_id = playerInfo.discordId

		# 1. Get data from MongoDB using whatever was given.
		existingPlayer = await loop.run_in_executor(
			None,
			self.getPlayerInfo,
			playerInfo.minecraftUsername,
			playerInfo.minecraftUUID,
			playerInfo.discordUsername,
			playerInfo.discordId
		)

		# 2. Merge retrieved MongoDB data into the playerInfo object (if found)
		if existingPlayer:
			if not playerInfo.minecraftUsername:
				playerInfo.minecraftUsername = existingPlayer.minecraftUsername
			if not playerInfo.minecraftUUID:
				playerInfo.minecraftUUID = existingPlayer.minecraftUUID
			if not playerInfo.discordUsername:
				playerInfo.discordUsername = existingPlayer.discordUsername
			if not playerInfo.discordId:
				playerInfo.discordId = existingPlayer.discordId

		# If we have minecraftUsername but no minecraftUUID, Mojang API lookup by name is needed first.
		if playerInfo.minecraftUsername and not playerInfo.minecraftUUID:
			try:
				resolved_uuid = await UserInfoLookup.getMinecraftUuidByName(playerInfo.minecraftUsername)
				if resolved_uuid:
					playerInfo.minecraftUUID = resolved_uuid
			except Exception as e:
				self.logger.error(f"Error in background lookup of Minecraft UUID by name: {e}")

		# 3. Use the minecraft UUID and discord ID to lookup the minecraft name and discord name async.
		new_minecraft_username = None
		new_discord_username = None

		async def lookup_minecraft():
			nonlocal new_minecraft_username
			if playerInfo.minecraftUUID:
				try:
					new_minecraft_username = await UserInfoLookup.getMinecraftNameByUuid(playerInfo.minecraftUUID)
				except Exception as e:
					self.logger.error(f"Error in background lookup of Minecraft name by UUID: {e}")

		async def lookup_discord():
			nonlocal new_discord_username
			if playerInfo.discordId:
				try:
					discord_data = await UserInfoLookup.getDiscordUserById(playerInfo.discordId)
					if discord_data and "username" in discord_data:
						new_discord_username = discord_data["username"]
				except Exception as e:
					self.logger.error(f"Error in background lookup of Discord user by ID: {e}")

		# Run lookups concurrently
		await asyncio.gather(lookup_minecraft(), lookup_discord())

		# 4. Combine the updated names into the playerInfo object
		if new_minecraft_username:
			playerInfo.minecraftUsername = new_minecraft_username
		if new_discord_username:
			playerInfo.discordUsername = new_discord_username

		# 5. Save/update MongoDB
		await loop.run_in_executor(None, self.savePlayerInfo, playerInfo)

		# 6. Check if player info changed and send update relay
		info_resolved = (
			(playerInfo.minecraftUsername != initial_username) or
			(playerInfo.minecraftUUID != initial_uuid) or
			(playerInfo.discordUsername != initial_discord_username) or
			(playerInfo.discordId != initial_discord_id)
		)

		if info_resolved:
			try:
				open_ticket_ids = await loop.run_in_executor(None, self.getOpenTicketIdsForPlayer, playerInfo)
				for ticket_id in open_ticket_ids:
					await loop.run_in_executor(None, MCL_OutboundRelay().relay, ticket_id, TicketAction.PLAYERINFOUPDATE)
			except (ImportError, ModuleNotFoundError):
				# Not running in backend context
				pass
			except Exception as e:
				self.logger.error(f"Error sending player info update notification: {e}")

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
		ticket_data = self.collections[MongoDatabase.HELP][MongoCollection.TICKETS].find_one({"discordInfo.threadId": threadId})
		if not ticket_data:
			return None
		return self._deserializeTicket(ticket_data)

	def _deserializeTicket(self, ticket_data: dict) -> HelpTicket:
		player_info = PlayerInfo.fromDict(ticket_data["playerInfo"])

		# Dynamically resolve authoritative player info from players database
		try:
			authoritative = self.getPlayerInfo(
				player_info.minecraftUsername,
				player_info.minecraftUUID,
				player_info.discordUsername,
				player_info.discordId
			)
			if authoritative:
				if authoritative.minecraftUsername:
					player_info.minecraftUsername = authoritative.minecraftUsername
				if authoritative.minecraftUUID:
					player_info.minecraftUUID = authoritative.minecraftUUID
				if authoritative.discordUsername:
					player_info.discordUsername = authoritative.discordUsername
				if authoritative.discordId:
					player_info.discordId = authoritative.discordId
		except Exception as e:
			self.logger.error(f"Error fetching authoritative player info on deserialize: {e}")

		# If ticket does exist, then repop fields
		ticket = HelpTicket(
			ticketId=ticket_data["ticketId"],
			playerInfo=player_info,
			type=TicketType(ticket_data["type"]),
			conversation=Conversation.fromDict(ticket_data["conversation"]) if "conversation" in ticket_data else None,
			discordInfo=DiscordInfo.fromDict(ticket_data["discordInfo"]) if "discordInfo" in ticket_data else None
		)
		ticket.status = TicketStatus(ticket_data["status"])
		ticket.feedback = TicketFeedback(ticket_data["feedback"])
		ticket.claimedBy = PlayerInfo.fromDict(ticket_data["claimedBy"]) if ticket_data.get("claimedBy") else None
		ticket.closedBy = PlayerInfo.fromDict(ticket_data["closedBy"]) if ticket_data.get("closedBy") else None
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

	def getServerStatus(self) -> Optional[ServerStatus]:
		"""
		## Get Server Status

		Retrieves the latest Minecraft server status from the database.
		"""
		doc = self.collections[MongoDatabase.BOT][MongoCollection.SERVER_STATUS].find_one({"_id": "current_status"})
		if not doc:
			# Fallback if no specific doc is found, get the most recently updated one
			doc = self.collections[MongoDatabase.BOT][MongoCollection.SERVER_STATUS].find_one(sort=[("last_updated", -1)])
		if doc:
			return ServerStatus.fromDict(doc)
		return None

	def saveServerStatus(self, status: ServerStatus) -> Any:
		"""
		## Save Server Status

		Saves or updates the Minecraft server status in the database.
		"""
		status_dict = status.toDict()
		status_dict["_id"] = "current_status"
		result = self.collections[MongoDatabase.BOT][MongoCollection.SERVER_STATUS].replace_one(
			{"_id": "current_status"},
			status_dict,
			upsert=True
		)
		return result

	def getHelperLeaderboard(self) -> list[dict]:
		"""
		## Get Helper Leaderboard

		Aggregates the tickets collection to figure out each staff member's
		positive / no / negative feedback counts, ranked by total claimed tickets.
		"""
		pipeline = [
			{
				"$match": {
					"claimedBy": {"$exists": True, "$ne": None}
				}
			},
			{
				"$group": {
					"_id": "$claimedBy.discordId",
					"total_claimed": {"$sum": 1},
					"positive": {
						"$sum": {
							"$cond": [{"$eq": ["$feedback", "HELPFUL"]}, 1, 0]
						}
					},
					"negative": {
						"$sum": {
							"$cond": [{"$eq": ["$feedback", "UNHELPFUL"]}, 1, 0]
						}
					},
					"no_feedback": {
						"$sum": {
							"$cond": [
								{"$in": ["$feedback", ["NONE", None]]}, 
								1, 
								0
							]
						}
					}
				}
			},
			{
				"$sort": {
					"total_claimed": -1
				}
			}
		]
		cursor = self.collections[MongoDatabase.HELP][MongoCollection.TICKETS].aggregate(pipeline)
		return list(cursor)
