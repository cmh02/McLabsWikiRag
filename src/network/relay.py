'''
MCLabs Backend - Outbound Relay

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import time
import uuid
import logging
from typing import List, Dict

from src.utils.enum import TicketAction

'''
OUTBOUND RELAY
'''

class MCL_RelayQueueData():
	'''
	MCL Relay Queue Data

	Class to manage the data associated with a queued outbound relay call.
	'''
	def __init__(self, ticketId: int, action: TicketAction, time: float):
		self.ticketId = ticketId
		self.action = action
		self.timestamp = time

class MCL_OutboundRelay():
	'''
	MCL Outbound Relay

	Class to manage outbound API calls for the MCLabs backend. Provides a
	single point of management for all outbound API calls, including logging
	and error handling.
	'''
	_instance = None

	def __new__(cls):
		if cls._instance is None:
			cls._instance = super(MCL_OutboundRelay, cls).__new__(cls)
		return cls._instance

	def initialize(self):
		'''
		# Relay Initialization

		Initializes the outbound relay for queuing updates.
		We queue updates to prevent update loss.
		Updates will be retried until ACK'd by the receiving system.
		'''

		# Initialize logger for singleton
		self.logger = logging.getLogger("MCL_API_Logger")
		self.logger.info(f"Initialized MCL Outbound Relay on PID {os.getpid()}.")

		# Make two outbound queues for Minecraft server and Discord bot
		self.queue_Minecraft: List[uuid.UUID] = []
		self.queue_Discord: List[uuid.UUID] = []

		# Dictionaries for update information
		self.data: Dict[uuid.UUID, MCL_RelayQueueData] = {}

	def notifyAll(self, ticketId: int, action: TicketAction):
		'''
		# Notify All

		Notifies all relevant external systems (Minecraft server, Discord bot) of a ticket update.

		## Parameters
		- `ticketId` (int): The ID of the ticket that was updated.
		- `action` (TicketAction): The action that was taken on the ticket.
		'''

		self.notifyMinecraftServer(ticketId, action)
		self.notifyDiscordBot(ticketId, action)

	def notifyMinecraftServer(self, ticketId: int, action: TicketAction):
		'''
		# Notify Minecraft Server

		Notifies the Minecraft server of a ticket update via an outbound API call.

		## Parameters
		- `ticketId` (int): The ID of the ticket that was updated.
		- `action` (TicketAction): The action that was taken on the ticket.
		'''

		# Log the outbound API call
		logger = logging.getLogger("MCL_API_Logger")
		logger.info(f"Notifying Minecraft server of ticket {ticketId} update with action {action.value}.")

		# Generate a unique update ID for queueing / tracking
		updateId: uuid.UUID = uuid.uuid4()
		self.data[updateId] = MCL_RelayQueueData(
			ticketId = ticketId, 
			action = action, 
			time = time.time()
		)

	def notifyDiscordBot(self, ticketId: int, action: TicketAction):
		'''
		# Notify Discord Bot

		Notifies the Discord bot of a ticket update via an outbound API call.

		## Parameters
		- `ticketId` (int): The ID of the ticket that was updated.
		- `action` (TicketAction): The action that was taken on the ticket.
		'''

		# Log the outbound API call
		logger = logging.getLogger("MCL_API_Logger")
		logger.info(f"Notifying Discord bot of ticket {ticketId} update with action {action.value}.")

		# Generate a unique update ID for queueing / tracking
		updateId: uuid.UUID = uuid.uuid4()
		self.data[updateId] = MCL_RelayQueueData(
			ticketId = ticketId, 
			action = action, 
			time = time.time()
		)