'''
MCLabs Help Manager

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
from enum import Enum
from typing import Dict
from datetime import datetime

'''
QUESTION STATUS ENUM
'''

class QuestionStatus(Enum):
	OPEN = "OPEN"
	CLAIMED = "CLAIMED"
	ANSWERED = "ANSWERED"

'''
HELP MANAGER
'''

class MCL_HelpManager():
	'''
	MCL_HelpManager

	Class to manage the live help system for MCLabs. Serves as the backend correspondent to the in-game
	help QA system. Primary use is for syncronizing in-game help system to the discord bot.
	'''

	def __init__(self):
		'''
		# Class Constructor

		Initializes the help manager with an empty dictionary for help questions.
		'''

		# Dict for holding help questions
		self.helpQuestions: Dict[str, str] = {}

	def addQuestion(self, questionID: int, questionPlayer: str, questionContent: str, questionTime: datetime) -> bool:
		'''
		## Add New Question

		Adds a help question to the help questions dictionary.

		### Parameters
		- questionID (int): The ID of the help question.
		- questionPlayer (str): The player who asked the help question.
		- questionContent (str): The content of the help question.
		- questionTime (datetime): The time the help question was asked.

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
		if not questionTime or not isinstance(questionTime, datetime):
			raise ValueError(f"An invalid question time was provided when adding a help question: {questionTime}")
		
		# Check if the question ID already exists
		if questionID in self.helpQuestions:
			raise ValueError(f"A question with ID {questionID} already exists.")

		# Add the question to the dictionary
		self.helpQuestions[questionID] = {
			"player": questionPlayer,
			"content": questionContent,
			"time": questionTime,
			"status": QuestionStatus.OPEN,
			"claimedBy": None,
			"claimedTime": None,
			"answeredBy": None,
			"answeredTime": None,
			"answer": None
		}
		return True

	def removeQuestion(self, questionID: int) -> bool:
		'''
		# Remove Question

		Removes a help question from the help questions dictionary.

		## Parameters
		- questionID (int): The ID of the help question to remove.

		### Returns
		- bool: True if the question was removed successfully. Exception will occur otherwise.
		'''

		# Check that question ID is provided and valid
		if not questionID or not isinstance(questionID, int):
			raise ValueError(f"An invalid question ID was provided when removing a help question: {questionID}")
		
		# Check if the question ID exists
		if questionID not in self.helpQuestions:
			raise ValueError(f"No question with ID {questionID} exists.")

		# Remove the question from the dictionary
		del self.helpQuestions[questionID]
		return True
	
	def answerQuestion(self, questionID: int, answeredBy: str, answerContent: str) -> bool:
		'''
		# Answer Question

		Answers a help question in the help questions dictionary.

		## Parameters
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
			raise ValueError(f"No question with ID {questionID} exists.")

		# Answer the question in the dictionary
		self.helpQuestions[questionID]["status"] = QuestionStatus.ANSWERED
		self.helpQuestions[questionID]["claimedBy"] = answeredBy
		self.helpQuestions[questionID]["claimedTime"] = datetime.now()
		self.helpQuestions[questionID]["answeredBy"] = answeredBy
		self.helpQuestions[questionID]["answeredTime"] = datetime.now()
		self.helpQuestions[questionID]["answer"] = answerContent
		return True
	
	def claimQuestion(self, questionID: int, claimedBy: str) -> bool:
		'''
		# Claim Question

		Claims a help question in the help questions dictionary.

		## Parameters
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
			raise ValueError(f"No question with ID {questionID} exists.")
		
		# Check if the question is already claimed
		if self.helpQuestions[questionID]["status"] == QuestionStatus.CLAIMED:
			raise ValueError(f"Question with ID {questionID} is already claimed.")

		# Claim the question in the dictionary
		self.helpQuestions[questionID]["status"] = QuestionStatus.CLAIMED
		self.helpQuestions[questionID]["claimedBy"] = claimedBy
		self.helpQuestions[questionID]["claimedTime"] = datetime.now()
		return True

	def unclaimQuestion(self, questionID: int) -> bool:
		'''
		# Unclaim Question

		Unclaims a help question in the help questions dictionary.

		## Parameters
		- questionID (int): The ID of the help question to unclaim.

		### Returns
		- bool: True if the question was unclaimed successfully. Exception will occur otherwise.
		'''

		# Check that question ID is provided and valid
		if not questionID or not isinstance(questionID, int):
			raise ValueError(f"An invalid question ID was provided when unclaiming a help question: {questionID}")
		
		# Check if the question ID exists
		if questionID not in self.helpQuestions:
			raise ValueError(f"No question with ID {questionID} exists.")

		# Unclaim the question in the dictionary
		self.helpQuestions[questionID]["status"] = QuestionStatus.OPEN
		self.helpQuestions[questionID]["claimedBy"] = None
		self.helpQuestions[questionID]["claimedTime"] = None
		return True