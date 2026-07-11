'''
MCLabs Backend - Help Manager

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
import json
import logging
from typing import Dict, Optional
from src.network.schemas import QuestionSchema
from fastapi.encoders import jsonable_encoder
from concurrent.futures import ThreadPoolExecutor

from src.network.relay import MCL_OutboundRelay
from mcl_common.mongo import MCL_MongoManager
from mcl_common.enum import TicketType, TicketStatus, TicketFeedback, TicketAction
from mcl_common.datatypes import Message, Conversation, HelpTicket, PlayerInfo


'''
HELP MANAGER
'''

class MCL_HelpManager():
	'''
	MCL Help Manager Singleton

	Class to manage help tickets for the MCLabs help system. Provides the
	central source-of-truth for all help tickets and associated conversations.
	'''
	_instance = None

	def __new__(cls):
		if cls._instance is None:
			cls._instance = super(MCL_HelpManager, cls).__new__(cls)
		return cls._instance

	def initialize(self):
		'''
		# Class Initialization

		Initializes the help manager with an empty dictionary for help questions.
		'''

		# Dict for holding help tickets
		self.tickets: Dict[int, HelpTicket] = {}

		# Create executor for threading
		# self.executor = ThreadPoolExecutor(max_workers=5)

		# Get mongo manager for persistence
		self.mongoManager = MCL_MongoManager()

		# Log initialization
		self.logger = logging.getLogger("MCL_API_Logger")
		self.logger.info(f"Help Manager initialized with PID {os.getpid()}.")

	def _getOrLoadTicket(self, ticketId: int) -> Optional[HelpTicket]:
		'''
		# Get Or Load Ticket

		Gets the ticket from the in-memory cache, or retrieves it from MongoDB and caches it if found.
		'''
		if ticketId in self.tickets:
			return self.tickets[ticketId]

		ticket = self.mongoManager.getTicket(ticketId)
		if ticket and ticket.playerInfo.minecraftUUID != "Unknown":
			self.tickets[ticketId] = ticket
			return ticket
		return None

	def createTicket(self, type: TicketType, playerInfo: PlayerInfo) -> int:
		'''
		# Create Ticket

		Creates a new help ticket and adds it to the open tickets dictionary.

		## Parameters
			type (TicketType): The type of the help ticket.
			playerInfo (PlayerInfo): The identification details of the player.

		## Returns
			int: The ID of the newly created help ticket.
		'''
		
		# Generate a new ticket id
		ticketId = self.mongoManager.getNextTicketId()

		# Create new help ticket
		newTicket = HelpTicket(
			ticketId=ticketId,
			playerInfo=playerInfo,
			type=type
		)

		# Add the new ticket to the dictionary
		self.tickets[ticketId] = newTicket
		self.mongoManager.saveTicket(
			ticket=newTicket
		)

		# Relay update and return
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.CREATE
		)
		return ticketId

	def updateTicketThread(self, ticketId: int, threadId: int):
		'''
		# Update Ticket Thread ID

		Updates the Discord thread ID for an existing help ticket.
		'''
		ticket = self._getOrLoadTicket(ticketId)
		if not ticket:
			self.logger.error(f"Attempted to update thread for non-existent ticket with ID {ticketId}.")
			return

		# Update the thread ID
		ticket.threadId = threadId

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=ticket
		)

	def closeTicket(self, ticketId: int, closedBy: str):
		'''
		# Close Ticket

		Closes an existing help ticket and moves it to the closed tickets dictionary.
		'''
		ticket = self._getOrLoadTicket(ticketId)
		if not ticket:
			self.logger.error(f"Attempted to close non-existent ticket with ID {ticketId}.")
			return
		
		# Close the ticket
		ticket.close(
			closedBy=closedBy
		)

		# Save to mongo, remove, and relay update
		self.mongoManager.saveTicket(
			ticket=ticket
		)
		self.tickets.pop(ticketId, None)
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.CLOSE
		)

	def claimTicket(self, ticketId: int, claimedBy: str):
		'''
		# Claim Ticket

		Claims an existing help ticket and moves it to the claimed tickets dictionary.
		'''
		ticket = self._getOrLoadTicket(ticketId)
		if not ticket:
			self.logger.error(f"Attempted to claim non-existent ticket with ID {ticketId}.")
			return
		
		# Claim the ticket
		ticket.claim(
			claimedBy=claimedBy
		)

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=ticket
		)

		# Relay update
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.CLAIM
		)

	def unclaimTicket(self, ticketId: int):
		'''
		# Unclaim Ticket

		Unclaims an existing help ticket and moves it back to the open tickets dictionary.
		
		## Parameters
			ticketId (int): The ID of the help ticket to unclaim.

		## Returns
			None
		'''
		ticket = self._getOrLoadTicket(ticketId)
		if not ticket:
			self.logger.error(f"Attempted to unclaim non-existent ticket with ID {ticketId}.")
			return

		# Unclaim the ticket
		ticket.unclaim()

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=ticket
		)

		# Relay update
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.UNCLAIM
		)

	def setTicketFeedback(self, ticketId: int, feedback: TicketFeedback):
		'''
		# Set Ticket Feedback

		Sets the feedback for a help ticket.

		## Parameters
			ticketId (int): The ID of the help ticket to set feedback for.
			feedback (TicketFeedback): The feedback to set for the help ticket.

		## Returns
			None
		'''
		ticket = self._getOrLoadTicket(ticketId)
		if not ticket:
			self.logger.error(f"Attempted to set feedback for non-existent ticket with ID {ticketId}.")
			return
		
		# Set the feedback for the ticket
		ticket.setFeedback(
			feedback=feedback
		)

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=ticket
		)

		# Relay update
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.FEEDBACK
		)

	def addMessageToConversation(self, ticketId: int, message: Message):
		'''
		# Add Message to Conversation

		Adds a message to the conversation associated with a help ticket.

		## Parameters
			ticketId (int): The ID of the help ticket to add the message to.
			message (Message): The message to add to the conversation.

		## Returns
			None
		'''
		ticket = self._getOrLoadTicket(ticketId)
		if not ticket:
			self.logger.error(f"Attempted to add message to non-existent ticket with ID {ticketId}.")
			return
		
		# Add the message to the conversation
		ticket.conversation.appendMessage(
			message=message
		)

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=ticket
		)

		# Relay update
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.NEWMESSAGE
		)

	def getTicketInfo(self, ticketId: int) -> Optional[dict]:
		'''
		# Get Ticket Info

		Retrieves the information for a help ticket.

		## Parameters
			ticketId (int): The ID of the help ticket to retrieve information for.

		## Returns
			dict: The help ticket information.
		'''
		ticket = self._getOrLoadTicket(ticketId)
		if not ticket:
			self.logger.error(f"Attempted to get info for non-existent ticket with ID {ticketId}.")
			return None
		return ticket.toDict()