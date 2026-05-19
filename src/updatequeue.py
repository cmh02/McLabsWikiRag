'''
MCLabs Backend - Update Queue

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
import datetime
from typing import Dict, Tuple
from src.schemas import QuestionSchema
from fastapi.encoders import jsonable_encoder
from concurrent.futures import ThreadPoolExecutor

from src.enum import QuestionStatus, UpdateSource

'''
UPDATE QUEUE
'''

class MCL_UpdateQueue():
	'''
	MCL Update Queue Singleton

	Class to manage the update queue for MCLabs. Primary use is to store updates for the
	server apart from actual question data.
	'''
	_instance = None

	def __new__(cls):
		if cls._instance is None:
			cls._instance = super(MCL_UpdateQueue, cls).__new__(cls)
		return cls._instance

	def initialize(self):
		'''
		# Class Initialization

		Initializes the update queue with an empty dictionary for updates.
		'''

		# Dict for holding updates
		self.updates: Dict[float, Dict] = {}

		# Create executor for threading
		self.executor = ThreadPoolExecutor(max_workers=5)

		# Log initialization
		self.logger = logging.getLogger("MCL_API_Logger")
		self.logger.info(f"Update Queue initialized with PID {os.getpid()}.")

	def loadFromFile(self, filePath: str):
		'''
		# Load Updates from File

		Loads updates from a specified JSON file into the update queue.

		Args:
			filePath (str): The path to the JSON file containing updates.
		'''

		try:
			with open(filePath, 'r') as f:
				self.updates = json.load(f)
			self.logger.info(f"Loaded updates from {filePath}.")
		except Exception as e:
			self.logger.error(f"Error loading updates from file: {e}")

	def saveToFile(self, filePath: str):
		'''
		# Save Updates to File

		Saves the current updates in the update queue to a specified JSON file.

		Args:
			filePath (str): The path to the JSON file where updates will be saved.
		'''

		try:
			with open(filePath, 'w') as f:
				json.dump(self.updates, f, indent=4)
			self.logger.info(f"Saved updates to {filePath}.")
		except Exception as e:
			self.logger.error(f"Error saving updates to file: {e}")

	def addUpdate(self, updateData: Dict):
		'''
		# Add Update to Queue

		Adds an update to the update queue. The queue is indexed by unix timestamp of addition.
		Updates should be added via the QuestionSchema model to ensure proper formatting.

		Args:
			updateData (Dict): A dictionary containing the update data. Must include a unique 'id' key.
		'''

		# Get current UNIX timestamp for key
		timestamp = datetime.datetime.now().timestamp()

		# Add update to queue
		self.updates[timestamp] = updateData
		self.logger.info(f"Added update with ID {updateData.get('id', 'N/A')} to queue at timestamp {timestamp}.")

	def getNextUpdate(self) -> Tuple[float, Dict]:
		'''
		# Get Next Update

		Retrieves the next update from the update queue. This is the update with the earliest timestamp.

		Returns:
			Dict: The next update data, or None if the queue is empty.
		'''

		if not self.updates:
			return None

		# Get the earliest timestamp key
		nextTimestamp = min(self.updates.keys())
		
		# Get the corresponding update data
		nextUpdate = self.updates[nextTimestamp]
		return nextTimestamp, nextUpdate
	
	def removeUpdate(self, updateTimestamp: float):
		'''
		# Remove Update from Queue

		Removes an update from the update queue based on its timestamp.

		Args:
			updateTimestamp (float): The UNIX timestamp key of the update to be removed.
		'''

		if updateTimestamp in self.updates:
			self.updates.pop(updateTimestamp)
			self.logger.info(f"Removed update with timestamp {updateTimestamp} from queue.")
		else:
			self.logger.warning(f"Attempted to remove update with timestamp {updateTimestamp}, but it was not found in the queue.")