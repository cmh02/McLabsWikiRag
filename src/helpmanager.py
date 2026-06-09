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
from src.schemas import QuestionSchema
from fastapi.encoders import jsonable_encoder
from concurrent.futures import ThreadPoolExecutor

from src.mongo import MCL_MongoManager
from src.enum import TicketType, TicketStatus, TicketFeedback
from src.datatypes import Message, Conversation, HelpTicket


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

	def createTicket(self, type: TicketType, player: str) -> int:
		'''
		# Create Ticket

		Creates a new help ticket and adds it to the open tickets dictionary.

		## Parameters
			type (TicketType): The type of the help ticket.
			player (str): The UUID of the player creating the ticket.

		## Returns
			int: The ID of the newly created help ticket.
		'''
		
		# Generate a new ticket id
		ticketId = self.mongoManager.getNextTicketId()

		# Create new help ticket
		newTicket = HelpTicket(
			ticketId=ticketId,
			player=player,
			type=type
		)

		# Add the new ticket to the dictionary
		self.tickets[ticketId] = newTicket
		self.mongoManager.saveTicket(
			ticket=newTicket
		)
		return ticketId

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

		# Save to mongo then remove from help manager
		self.mongoManager.saveTicket(
			ticket=self.tickets[ticketId]
		)
		self.tickets.pop(ticketId)

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