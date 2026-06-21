'''
MCLabs Backend - Outbound Relay

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

import os
import logging

from src.enum import TicketAction

'''
OUTBOUND RELAY
'''

class MCL_OutboundRelay():
	'''
	MCL Outbound Relay Singleton

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

		Initializes the outbound relay with a logger for logging outbound API calls.
		'''

		# Log initialization
		self.logger = logging.getLogger("MCL_API_Logger")
		self.logger.info(f"Outbound Relay initialized with PID {os.getpid()}.")

	def notifyAll(self, ticketId: int, action: TicketAction):
		'''
		# Notify All

		Notifies all relevant external systems (Minecraft server, Discord bot) of a ticket update.
		'''

		self.notifyMinecraftServer(ticketId, action)
		self.notifyDiscordBot(ticketId, action)

	def notifyMinecraftServer(self, ticketId: int, action: TicketAction):
		'''
		# Notify Minecraft Server

		Notifies the Minecraft server of a ticket update via an outbound API call.
		'''

		# Log the outbound API call
		self.logger.info(f"Notifying Minecraft server of ticket {ticketId} update with action {action.value}.")

	def notifyDiscordBot(self, ticketId: int, action: TicketAction):
		'''
		# Notify Discord Bot

		Notifies the Discord bot of a ticket update via an outbound API call.
		'''

		# Log the outbound API call
		self.logger.info(f"Notifying Discord bot of ticket {ticketId} update with action {action.value}.")