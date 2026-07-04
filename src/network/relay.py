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

		# Grab lock so we don't add to queue while loop is processing
		with self._lock:

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

			# Check if we need to start a new thread for the relay update loop
			if self._thread is None or not self._thread.is_alive() or self._stopEvent.is_set():
				self._stopEvent.clear()
				self._thread = threading.Thread(
					target=self.beginRelayUpdateLoop,
					daemon=True,
					name="RelayUpdateLoopThread"
				)
				self._thread.start()
				self.logger.info("Started new thread for relay update loop.")

	def acknowledgeUpdate(self, updateId: uuid.UUID):
		'''
		# Acknowledge Update

		Acknowledges an update from the receiving system, removing it from the queue.

		## Parameters
		- `updateId` (uuid.UUID): The unique ID of the update to acknowledge.
		'''

		# Grab lock so we don't remove from queue while loop is processing
		with self._lock:

			# Update queue
			if updateId not in self.data:
				self.logger.warning(f"Attempted to acknowledge unknown update {updateId}.")
				return
			self.queue.remove(updateId)
			data = self.data.pop(updateId, None)
			self.logger.info(f"Acknowledged update {updateId} and removed update from queue: {data}.")

			# Check if we need to stop the relay update loop
			if not self.queue:
				self._stopEvent.set()
				self.logger.info("No more updates in queue. Stopping relay update loop.")

	def beginRelayUpdateLoop(self):
		'''
		# Begin Relay Update Loop

		Handles entire lifecycle for sending queued updates.
		Continues sending updates until acknowledged.
		Works with threading to prevent blocking main thread.
		'''
		
		# Loop until stop event is set
		while not self._stopEvent.is_set():
			with self._lock:

				# Process each update in the queue
				for updateId in list(self.queue):

					# Validate that data is still valid
					data = self.data.get(updateId)
					if not data:
						self.logger.warning(f"Update {updateId} not found in data dictionary. Removing from queue.")
						self.queue.remove(updateId)
						continue

					# Check if we should retry the update
					if data.lastAttemptTime is None or (time.time() - data.lastAttemptTime) >= self.relayQueueRetryInterval:
					
						# Update last attempt time
						data.lastAttemptTime = time.time()

						# Notify the appropriate external system
						self.logger.info(f"Attempting to notify {data.destination} of update {updateId}: {data}.")
						self.notify(data)

			# Sleep for the poll interval before checking the queue again
			time.sleep(self.relayQueuePollInterval)

	def notify(self, data: MCL_RelayQueueData):
		'''
		# Notify

		Notifies the appropriate external system of an update.

		## Parameters
		- `data` (MCL_RelayQueueData): The data associated with the update.
		'''
		if data.destination == RelayDestination.MINECRAFT:
			self.notifyMinecraft(data)
		elif data.destination == RelayDestination.DISCORD:
			self.notifyDiscord(data)
		else:
			self.logger.error(f"Unknown destination {data.destination} for update {data}.")

	def notifyMinecraft(self, data: MCL_RelayQueueData):
		'''
		# Notify Minecraft

		Notifies the Minecraft server of an update.

		## Parameters
		- `data` (MCL_RelayQueueData): The data associated with the update.
		'''
		pass

	def notifyDiscord(self, data: MCL_RelayQueueData):
		'''
		# Notify Discord

		Notifies the Discord bot of an update.

		## Parameters
		- `data` (MCL_RelayQueueData): The data associated with the update.
		'''
		pass