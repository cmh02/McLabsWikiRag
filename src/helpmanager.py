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

from src.enum import QuestionStatus, UpdateSource

'''
HELP MANAGER
'''

class MCL_HelpManager():
	'''
	MCL Help Manager Singleton

	Class to manage the live help system for MCLabs. Serves as the backend correspondent to the in-game
	help QA system. Primary use is for syncronizing in-game help system to the discord bot.
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

		# Dict for holding help questions
		self.helpQuestions: Dict[int, Dict] = {}

		# Create executor for threading
		self.executor = ThreadPoolExecutor(max_workers=5)

		# Log initialization
		self.logger = logging.getLogger("MCL_API_Logger")
		self.logger.info(f"Help Manager initialized with PID {os.getpid()}.")

	def loadQuestionsFromJson(self, filePath: str) -> bool:
		'''
		## Load Questions From JSON File

		Loads help questions from a JSON file into the help questions dictionary.

		### Parameters
		- filePath (str): The path to the JSON file containing help questions.

		### Returns
		- bool: True if the questions were loaded successfully, Exception will occur otherwise.
		'''

		# Check if file exists
		if not os.path.exists(filePath):
			self.logger.info(f"No help questions file found at path: {filePath}. Starting with empty help questions.")
			os.makedirs(os.path.dirname(filePath), exist_ok=True)
			return True

		# Check that file is a valid JSON file
		if not filePath.endswith(".json"):
			raise ValueError(f"The specified help questions file is not a valid JSON file: {filePath}")
		
		# Load questions from JSON file
		try:
			with open(filePath, "r") as f:
				self.helpQuestions = json.load(f)
			self.logger.info(f"Loaded help questions from JSON file: {filePath}")
		except Exception as e:
			self.logger.error(f"Failed to load help questions from JSON file: {filePath}. Error: {e}")

		# Datatype corrections
		correctedData: Dict[int, Dict] = {}
		for questionId, details in self.helpQuestions.items():
			correctedData[int(questionId)] = {
				"player": details.get("player", None),
				"content": details.get("content", None),
				"status": QuestionStatus(details.get("status", QuestionStatus.OPEN.value)),
				"claimedBy": details.get("claimedBy", None),
				"answeredBy": details.get("answeredBy", None),
				"answer": details.get("answer", None)
			}
		self.helpQuestions = correctedData

	def saveQuestionsToJson(self, filePath: str) -> bool:
		'''
		## Save Questions To JSON File

		Saves help questions from the help questions dictionary to a JSON file.

		### Parameters
		- filePath (str): The path to the JSON file to save help questions.

		### Returns
		- bool: True if the questions were saved successfully, Exception will occur otherwise.
		'''

		# Check that file directory exists, create if not
		os.makedirs(os.path.dirname(filePath), exist_ok=True)

		# Check that file is a valid JSON file
		if not filePath.endswith(".json"):
			raise ValueError(f"The specified help questions file is not a valid JSON file: {filePath}")
		
		# Save questions to JSON file
		try:
			with open(filePath, "w") as f:
				json.dump(jsonable_encoder(self.helpQuestions), f)
			self.logger.info(f"Saved help questions to JSON file: {filePath}")
			return True
		except Exception as e:
			self.logger.error(f"Failed to save help questions to JSON file: {filePath}. Error: {e}")

	def addQuestion(self, source: UpdateSource, questionID: int, questionPlayer: str, questionContent: str) -> bool:
		'''
		## Add New Question

		Adds a help question to the help questions dictionary.

		### Parameters
		- source (UpdateSource): The source of the question (MINECRAFT or DISCORD).
		- questionID (int): The ID of the help question.
		- questionPlayer (str): The player who asked the help question.
		- questionContent (str): The content of the help question.

		### Returns
		- bool: True if the question was added successfully, Exception will occur otherwise.

		'''

		# Check that question ID, player, content, and time are all provided and valid
		if not questionID or not isinstance(questionID, int):
			raise ValueError(f"An invalid question ID was provided when adding a help question: {questionID}")
		if not questionPlayer or not isinstance(questionPlayer, str):
			raise ValueError(f"An invalid question player was provided when adding a help question: {questionPlayer}")
		if not questionContent or not isinstance(questionContent, str):
			raise ValueError(f"An invalid question content was provided when adding a help question: {questionContent}")
		
		# Check if the question ID already exists
		if questionID in self.helpQuestions:
			raise ValueError(f"A question with ID {questionID} already exists.")

		# Add the question to the dictionary
		self.helpQuestions[questionID] = {
			"player": questionPlayer,
			"content": questionContent,
			"status": QuestionStatus.OPEN,
			"claimedBy": None,
			"answeredBy": None,
			"answer": None
		}

		# Log the addition
		self.logger.debug(f"Added help question ID {questionID} from player {questionPlayer}.")

		# Make call to update Discord in new thread
		self.executor.submit(self.updateDiscord)

		# If update is via discord, notify minecraft server to add question
		if source == UpdateSource.DISCORD:
			self.executor.submit(self.updateMinecraft)

		# Return success
		return True

	def removeQuestion(self, source: UpdateSource, questionID: int) -> bool:
		'''
		# Remove Question

		Removes a help question from the help questions dictionary.

		## Parameters
		- source (UpdateSource): The source of the removal (MINECRAFT or DISCORD).
		- questionID (int): The ID of the help question to remove.

		### Returns
		- bool: True if the question was removed successfully. Exception will occur otherwise.
		'''

		# Check that question ID is provided and valid
		if not questionID or not isinstance(questionID, int):
			raise ValueError(f"An invalid question ID was provided when removing a help question: {questionID}")
		
		# Check if the question ID exists
		if questionID not in self.helpQuestions:
			raise ValueError(f"No question with ID {questionID} exists! All question ID's: {list(self.helpQuestions.keys())}")

		# Remove the question from the dictionary
		del self.helpQuestions[questionID]

		# Log the removal
		self.logger.debug(f"Removed help question ID {questionID}.")

		# Make call to update Discord in new thread
		self.executor.submit(self.updateDiscord)

		# If update is via discord, notify minecraft server to remove question
		if source == UpdateSource.DISCORD:
			self.executor.submit(self.updateMinecraft)

		# Return success
		return True
	
	def answerQuestion(self, source: UpdateSource, questionID: int, answeredBy: str, answerContent: str) -> bool:
		'''
		# Answer Question

		Answers a help question in the help questions dictionary.

		## Parameters
		- source (UpdateSource): The source of the answer (MINECRAFT or DISCORD).
		- questionID (int): The ID of the help question to answer.
		- answeredBy (str): The staff answering the help question.
		- answerContent (str): The content of the answer.

		### Returns
		- bool: True if the question was answered successfully. Exception will occur otherwise.
		'''

		# Check that question ID, answeredBy, and answerContent are all provided and valid
		if not questionID or not isinstance(questionID, int):
			raise ValueError(f"An invalid question ID was provided when answering a help question: {questionID}")
		if not answeredBy or not isinstance(answeredBy, str):
			raise ValueError(f"An invalid answeredBy was provided when answering a help question: {answeredBy}")
		if not answerContent or not isinstance(answerContent, str):
			raise ValueError(f"An invalid answerContent was provided when answering a help question: {answerContent}")
		
		# Check if the question ID exists
		if questionID not in self.helpQuestions:
			raise ValueError(f"No question with ID {questionID} exists! All question ID's: {list(self.helpQuestions.keys())}")

		# Answer the question in the dictionary
		self.helpQuestions[questionID]["status"] = QuestionStatus.ANSWERED
		self.helpQuestions[questionID]["claimedBy"] = answeredBy
		self.helpQuestions[questionID]["answeredBy"] = answeredBy
		self.helpQuestions[questionID]["answer"] = answerContent

		# Log the answer
		self.logger.debug(f"Answered help question ID {questionID} by staff {answeredBy}.")

		# Make call to update Discord in new thread
		self.executor.submit(self.updateDiscord)

		# If update is via discord, notify minecraft server to answer question
		if source == UpdateSource.DISCORD:
			self.executor.submit(self.updateMinecraft)

		# Return success
		return True
	
	def claimQuestion(self, source: UpdateSource, questionID: int, claimedBy: str) -> bool:
		'''
		# Claim Question

		Claims a help question in the help questions dictionary.

		## Parameters
		- source (UpdateSource): The source of the claim (MINECRAFT or DISCORD).
		- questionID (int): The ID of the help question to claim.
		- claimedBy (str): The staff claiming the help question.

		### Returns
		- bool: True if the question was claimed successfully. Exception will occur otherwise.
		'''

		# Check that question ID and claimedBy are both provided and valid
		if not questionID or not isinstance(questionID, int):
			raise ValueError(f"An invalid question ID was provided when claiming a help question: {questionID}")
		if not claimedBy or not isinstance(claimedBy, str):
			raise ValueError(f"An invalid claimedBy was provided when claiming a help question: {claimedBy}")
		
		# Check if the question ID exists
		if questionID not in self.helpQuestions:
			raise ValueError(f"No question with ID {questionID} exists! All question ID's: {list(self.helpQuestions.keys())}")
		
		# Check if the question is already claimed
		if self.helpQuestions[questionID]["status"] == QuestionStatus.CLAIMED:
			raise ValueError(f"Question with ID {questionID} is already claimed.")

		# Claim the question in the dictionary
		self.helpQuestions[questionID]["status"] = QuestionStatus.CLAIMED
		self.helpQuestions[questionID]["claimedBy"] = claimedBy

		# Log the claim
		self.logger.debug(f"Claimed help question ID {questionID} by staff {claimedBy}.")

		# Make call to update Discord in new thread
		self.executor.submit(self.updateDiscord)

		# If update is via discord, notify minecraft server to claim question
		if source == UpdateSource.DISCORD:
			self.executor.submit(self.updateMinecraft)

		# Return success
		return True

	def unclaimQuestion(self, source: UpdateSource, questionID: int) -> bool:
		'''
		# Unclaim Question

		Unclaims a help question in the help questions dictionary.

		## Parameters
		- source (UpdateSource): The source of the unclaim (MINECRAFT or DISCORD).
		- questionID (int): The ID of the help question to unclaim.

		### Returns
		- bool: True if the question was unclaimed successfully. Exception will occur otherwise.
		'''

		# Check that question ID is provided and valid
		if not questionID or not isinstance(questionID, int):
			raise ValueError(f"An invalid question ID was provided when unclaiming a help question: {questionID}")
		
		# Check if the question ID exists
		if questionID not in self.helpQuestions:
			raise ValueError(f"No question with ID {questionID} exists! All question ID's: {list(self.helpQuestions.keys())}")

		# Unclaim the question in the dictionary
		self.helpQuestions[questionID]["status"] = QuestionStatus.OPEN
		self.helpQuestions[questionID]["claimedBy"] = None

		# Log the unclaim
		self.logger.debug(f"Unclaimed help question ID {questionID}.")

		# Make call to update Discord in new thread
		self.executor.submit(self.updateDiscord)

		# If update is via discord, notify minecraft server to unclaim question
		if source == UpdateSource.DISCORD:
			self.executor.submit(self.updateMinecraft)

		# Return success
		return True
	
	def getAllQuestions(self) -> Dict[int, str]:
		'''
		# Get All Questions

		Returns all help questions in the help questions dictionary.

		### Returns
		- Dict[int, str]: Dictionary of all help questions.
		'''
		return self.helpQuestions
	
	def updateDiscord(self):
		'''
		# Update Discord

		Updates the Discord bot with the current help questions.

		### Returns
		- bool: True if the Discord bot was updated successfully. Exception will occur otherwise.
		'''

		# Get all help questions
		questions = self.getAllQuestions()

		# Log the update to Discord
		self.logger.debug("Sending API call to Discord Bot to update help questions!")
		self.logger.debug(f"Questions: {questions}")

		# Send message to discord bot's api endpoint
		requests.post(
			url=f"https://{os.getenv('RAILWAY_DISCORD_DOMAIN')}/update",
			headers={
				"Content-Type": "application/json",
				"Authorization": os.getenv("API_TOKEN"),
				"User-Agent": os.getenv("USER-AGENT-API")
			},
			json=jsonable_encoder({ 
				"questions": [QuestionSchema(id=questionId, **details).model_dump() for questionId, details in questions.items()] 
			})
		)
		return True

	def updateMinecraft(self):
		'''
		# Update Minecraft Server

		Updates the Minecraft server with the current help questions for long-polling.

		### Returns
		- bool: True if the Minecraft server was updated successfully. Exception will occur otherwise.
		'''

		return True

	def updateMinecraftOutboundQueue(self, update: Dict):
		'''
		# Update Minecraft Outbound Queue

		Updates the outbound queue for minecraft server long-polling with a given help question update.
		'''

		pass