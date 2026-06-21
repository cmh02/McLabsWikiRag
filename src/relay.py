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
	MCL Outbound Relay

	Class to manage outbound API calls for the MCLabs backend. Provides a
	single point of management for all outbound API calls, including logging
	and error handling.
	'''

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