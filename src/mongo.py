'''
MCLabs Backend - Mongo Manager

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

'''
MONGO MANAGER
'''

import os
import logging

from src.datatypes import HelpTicket
from src.enum import TicketType, TicketStatus


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

	def initialize(self):
		'''
		# Class Initialization

		Initializes the mongo manager with a connection to MongoDB.
		'''

		# Log initialization
		self.logger = logging.getLogger("MCL_API_Logger")
		self.logger.info(f"Mongo Manager initialized with PID {os.getpid()}.")

	def saveTicket(self, ticket: HelpTicket):
		pass

	def getTicket(self, ticketId: int) -> HelpTicket:
		pass

	def getNextTicketId(self) -> int:
		pass

	def getAllTicketIds(self, type: TicketType=None, status: TicketStatus=None) -> list[int]:
		"""
		## Get All Ticket IDs

		Retrieves a list of all ticket IDs. You can pass a type, status, or both to filter.
		"""
		pass