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
import requests
from typing import Dict
from src.network.schemas import QuestionSchema
from fastapi.encoders import jsonable_encoder
from concurrent.futures import ThreadPoolExecutor

from src.network.relay import MCL_OutboundRelay
from src.internal.mongo import MCL_MongoManager
from src.utils.enum import TicketType, TicketStatus, TicketFeedback, TicketAction
from src.utils.datatypes import Message, Conversation, HelpTicket, PlayerInfo


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
		# Check if the ticket exists in memory, otherwise retrieve from MongoDB
		if ticketId not in self.tickets:
			ticket = self.mongoManager.getTicket(ticketId)
			if not ticket or ticket.playerInfo.minecraftUUID == "Unknown":
				self.logger.error(f"Attempted to update thread for non-existent ticket with ID {ticketId}.")
				return
			self.tickets[ticketId] = ticket

		# Update the thread ID
		self.tickets[ticketId].threadId = threadId

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=self.tickets[ticketId]
		)

	def closeTicket(self, ticketId: int, closedBy: str):
		'''
		# Close Ticket

		Closes an existing help ticket and moves it to the closed tickets dictionary.
		'''
		
		# Check if the ticket exists
		if ticketId not in self.tickets:
			self.logger.error(f"Attempted to close non-existent ticket with ID {ticketId}.")
			return
		
		# Close the ticket
		self.tickets[ticketId].close(
			closedBy=closedBy
		)

		# Save to mongo, remove, and relay update
		self.mongoManager.saveTicket(
			ticket=self.tickets[ticketId]
		)
		self.tickets.pop(ticketId)
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.CLOSE
		)

	def claimTicket(self, ticketId: int, claimedBy: str):
		'''
		# Claim Ticket

		Claims an existing help ticket and moves it to the claimed tickets dictionary.
		'''
		
		# Check if the ticket exists
		if ticketId not in self.tickets:
			self.logger.error(f"Attempted to claim non-existent ticket with ID {ticketId}.")
			return
		
		# Claim the ticket
		self.tickets[ticketId].claim(
			claimedBy=claimedBy
		)

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=self.tickets[ticketId]
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
		# Check if the ticket exists
		if ticketId not in self.tickets:
			self.logger.error(f"Attempted to unclaim non-existent ticket with ID {ticketId}.")
			return

		# Unclaim the ticket
		self.tickets[ticketId].unclaim()

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=self.tickets[ticketId]
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
		
		# Check if the ticket exists
		if ticketId not in self.tickets:
			self.logger.error(f"Attempted to set feedback for non-existent ticket with ID {ticketId}.")
			return
		
		# Set the feedback for the ticket
		self.tickets[ticketId].setFeedback(
			feedback=feedback
		)

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=self.tickets[ticketId]
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
		
		# Check if the ticket exists
		if ticketId not in self.tickets:
			self.logger.error(f"Attempted to add message to non-existent ticket with ID {ticketId}.")
			return
		
		# Add the message to the conversation
		self.tickets[ticketId].conversation.appendMessage(
			message=message
		)

		# Save to mongo
		self.mongoManager.saveTicket(
			ticket=self.tickets[ticketId]
		)

		# Relay update
		MCL_OutboundRelay().relay(
			ticketId=ticketId,
			action=TicketAction.NEWMESSAGE
		)

	def getTicketInfo(self, ticketId: int) -> dict:
		'''
		# Get Ticket Info

		Retrieves the information for a help ticket.

		## Parameters
			ticketId (int): The ID of the help ticket to retrieve information for.

		## Returns
			dict: The help ticket information.
		'''
		
		# Check if the ticket exists
		if ticketId not in self.tickets:
			self.logger.error(f"Attempted to get info for non-existent ticket with ID {ticketId}.")
			return None
		return self.tickets[ticketId].toDict()