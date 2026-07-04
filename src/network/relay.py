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
import threading
from typing import List, Dict

from src.utils.enum import TicketAction, RelayDestination

'''
OUTBOUND RELAY
'''

class MCL_RelayQueueData():
	'''
	MCL Relay Queue Data

	Class to manage the data associated with a queued outbound relay call.
	'''
	def __init__(self, ticketId: int, action: TicketAction, destination: RelayDestination, originTime: float, lastAttemptTime: float | None):
		
		# ID of the ticket that was updated
		self.ticketId: int = ticketId

		# Specific action that was taken - see enum TicketAction for possible values
		self.action: TicketAction = action

		# Destination of the update - see enum RelayDestination for possible values
		self.destination: RelayDestination = destination

		# Time the update was created (epoch time)
		self.originTime: float = originTime

		# Time the update was last attempted to be sent (epoch time)
		self.lastAttemptTime: float | None = lastAttemptTime

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

		# Queue Poll Interval defines how often (in seconds) we check queue for updates that should be retried
		env_relayQueuePollInterval = os.getenv("MCL_RELAY_QUEUE_POLL_INTERVAL")
		if not env_relayQueuePollInterval:
			self.logger.error("MCL_RELAY_QUEUE_POLL_INTERVAL environment variable is not set.")
			raise ValueError("MCL_RELAY_QUEUE_POLL_INTERVAL environment variable is not set.")
		self.relayQueuePollInterval = float(env_relayQueuePollInterval)
		if not self.relayQueuePollInterval:
			self.logger.error("MCL_RELAY_QUEUE_POLL_INTERVAL environment variable could not be parsed correctly.")
			raise ValueError("MCL_RELAY_QUEUE_POLL_INTERVAL environment variable could not be parsed correctly.")
		if self.relayQueuePollInterval <= 0:
			self.logger.error("MCL_RELAY_QUEUE_POLL_INTERVAL environment variable must be a positive number.")
			raise ValueError("MCL_RELAY_QUEUE_POLL_INTERVAL environment variable must be a positive number.")
		
		# Queue Retry Interval defines how long (in seconds) we wait before retrying an update that has not been ACK'd
		env_relayQueueRetryInterval = os.getenv("MCL_RELAY_QUEUE_RETRY_INTERVAL")
		if not env_relayQueueRetryInterval:
			self.logger.error("MCL_RELAY_QUEUE_RETRY_INTERVAL environment variable is not set.")
			raise ValueError("MCL_RELAY_QUEUE_RETRY_INTERVAL environment variable is not set.")
		self.relayQueueRetryInterval = float(env_relayQueueRetryInterval)
		if not self.relayQueueRetryInterval:
			self.logger.error("MCL_RELAY_QUEUE_RETRY_INTERVAL environment variable could not be parsed correctly.")
			raise ValueError("MCL_RELAY_QUEUE_RETRY_INTERVAL environment variable could not be parsed correctly.")
		if self.relayQueueRetryInterval <= 0:
			self.logger.error("MCL_RELAY_QUEUE_RETRY_INTERVAL environment variable must be a positive number.")
			raise ValueError("MCL_RELAY_QUEUE_RETRY_INTERVAL environment variable must be a positive number.")

		# Relay outbound queue
		self.queue: List[uuid.UUID] = []
		self._lock: threading.Lock = threading.Lock()
		self._thread: threading.Thread | None = None
		self._stopEvent: threading.Event = threading.Event()

		# Dictionaries for update information
		self.data: Dict[uuid.UUID, MCL_RelayQueueData] = {}

	def relay(self, ticketId: int, action: TicketAction):
		'''
		# Master Relay

		Notifies all relevant external systems (Minecraft server, Discord bot) of a ticket update.

		## Parameters
		- `ticketId` (int): The ID of the ticket that was updated.
		- `action` (TicketAction): The action that was taken on the ticket.
		'''

		# Create update for minecraft
		updateId_Minecraft: uuid.UUID = uuid.uuid4()
		self.data[updateId_Minecraft] = MCL_RelayQueueData(
			ticketId = ticketId, 
			action = action, 
			destination = RelayDestination.MINECRAFT,
			originTime = time.time(),
			lastAttemptTime = None
		)
		self.queue.append(updateId_Minecraft)

		# Create update for discord
		updateId_Discord: uuid.UUID = uuid.uuid4()
		self.data[updateId_Discord] = MCL_RelayQueueData(
			ticketId = ticketId, 
			action = action, 
			destination = RelayDestination.DISCORD,
			originTime = time.time(),
			lastAttemptTime = None
		)
		self.queue.append(updateId_Discord)

	def acknowledgeUpdate(self, updateId: uuid.UUID):
		'''
		# Acknowledge Update

		Acknowledges an update from the receiving system, removing it from the queue.

		## Parameters
		- `updateId` (uuid.UUID): The unique ID of the update to acknowledge.
		'''
		if updateId not in self.data:
			self.logger.warning(f"Attempted to acknowledge unknown update {updateId}.")
			return
		self.queue.remove(updateId)
		data = self.data.pop(updateId, None)
		self.logger.info(f"Acknowledged update {updateId} and removed update from queue: {data}.")

	def startRelayUpdateLoop(self):
		'''
		# Start Relay Thread

		Start the relay thread to process the outbound relay queue.
		'''
		pass

	def stopRelayUpdateLoop(self):
		'''
		# Stop Relay Thread

		Stops the relay thread to process the outbound relay queue.
		'''
		pass