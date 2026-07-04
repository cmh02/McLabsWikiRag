'''
MCLabs Backend - Outbound Relay

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import logging

from src.utils.enum import TicketAction

'''
OUTBOUND RELAY
'''

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
		# Class Initialization

		Initializes the outbound relay for queuing updates.
		We queue updates to prevent update loss.
		Updates will be retried until ACK'd by the receiving system.
		'''

		# Initialize logger for singleton
		self.logger = logging.getLogger("MCL_API_Logger")

		# Make two outbound queues for Minecraft server and Discord bot
		self.minecraft_queue = []
		self.discord_queue = []

	@staticmethod
	def notifyAll(self, ticketId: int, action: TicketAction):
		'''
		# Notify All

		Notifies all relevant external systems (Minecraft server, Discord bot) of a ticket update.

		## Parameters
		- `ticketId` (int): The ID of the ticket that was updated.
		- `action` (TicketAction): The action that was taken on the ticket.
		'''

		MCL_OutboundRelay.notifyMinecraftServer(ticketId, action)
		MCL_OutboundRelay.notifyDiscordBot(ticketId, action)

	@staticmethod
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

	@staticmethod
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