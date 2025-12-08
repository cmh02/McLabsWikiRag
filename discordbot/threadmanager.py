'''
MCLabs Discord Thread Manager

Author: Chris Hinkson @cmh02

(NOTE: The term 'thread' in this context refers to Discord threads created for help questions, not system threads.)
'''

'''
MODULE IMPORTS
'''

# System
import os
import re
import logging
from typing import List, Dict, Any
from bidict import bidict

# Discord
from discord.ext.commands import Bot
from discord import PinnedMessage

# Local
from discordbot.components import HelpQuestionEmbed

'''
THREAD MANAGER
'''

class MCL_ThreadManager():
	'''
	THREAD MANAGER SINGLETON

	Singleton to manage Discord threads corresponding to help questions in the MCLabs help system.
	'''
	_instance = None

	def __new__(cls):
		if cls._instance is None:
			cls._instance = super(MCL_ThreadManager, cls).__new__(cls)
		return cls._instance
	
	def initialize(self, bot: Bot, channelId: int):
		'''
		# Class Initialization

		Initializes the thread manager with a reference to the Discord bot.
		'''

		# Initialize logger
		self.logger = logging.getLogger("MCL_DISCORD_Logger")

		# Initialize with bot reference
		self.bot: Bot = bot
		
		# Store channel ID and reference for help threads
		self.channelId: int = channelId
		self.channel = self.bot.get_channel(channelId)

		# Build regex patttern for thread names
		self.THREAD_REGEX: re.Pattern = re.compile(r"^Help\s+Question\s+(\d+)$", re.IGNORECASE)

		# Print initialization message
		print(f"MCL ThreadManager instance created (PID {os.getpid()}) for channel ID {channelId}!")

	async def getAdminPanelMessage(self) -> PinnedMessage | Any:

		# Get pinned messages in master channel
		pinnedMessages = await self.channel.pins()

		# If no pinned messages, error
		if not pinnedMessages:
			self.logger.error("No pinned messages found in the help channel. Cannot find admin panel message.")
			return None

		for message in pinnedMessages:
			if message.embeds[0].title == "MCL Help System — Admin Panel":
				return message

	def getAllThreads(self) -> bidict[int, int]:
		'''
		## Get All Threads in Channel

		Returns all Discord threads in the initialized channel.

		### Returns
		- Dictionary of Discord thread IDs and the corresponding question ID in the channel.
		'''

		# Return threads with info
		return bidict({
			channelThread.id: self.parseQuestionIdFromThreadName(channelThread.name)
			for channelThread in self.channel.threads
		})
	
	def parseQuestionIdFromThreadName(self, threadName: str) -> int:
		'''
		## Parse Question ID from Thread Name

		Extracts the help question ID from a Discord thread name.

		### Parameters
		- threadName (str): The name of the Discord thread.

		### Returns
		- The extracted question ID as an integer, or None if not found.
		'''

		# Regex to find question ID in thread name
		match = self.THREAD_REGEX.match(threadName)
		if match:
			return int(match.group(1))
		return None

	async def createHelpThread(self, questionId: int, questionPlayer: str, questionStatus: str, questionContent: str, questionClaimedBy: str=None):
		'''
		## Create New Help Thread

		Creates a new Discord thread for a given help question.

		### Parameters
		- questionId (int): The ID of the help question.
		- questionPlayer (str): The player who asked the question.
		- questionContent (str): The content of the help question.
		- questionStatus (str): The status of the help question.
		- questionClaimedBy (str): The admin who claimed the question, if any
		'''

		# Build thread name
		threadName = f"Help Question {questionId}"
		
		# Log creation
		self.logger.debug(f"Creating new help thread '{threadName}' for question ID {questionId} from player {questionPlayer}.")

		# Grab the admin message
		adminMessage = await self.getAdminPanelMessage()
		if not adminMessage:
			self.logger.error("Failed to find admin panel message. Cannot create help thread.")
			return

		# Make the thread creation async
		thread = await adminMessage.create_thread(name=threadName, auto_archive_duration=1008)

		# Make an embed, send in channel, and pin it
		embed = HelpQuestionEmbed(
			questionId=questionId,
			questionText=questionContent,
			questionStatus=questionStatus,
			questionClaimedBy=questionClaimedBy or "Unclaimed"
		)
		embedMessage = await thread.send(content="A new help question has been created!", embed=embed)
		await embedMessage.pin()

	async def deleteHelpThread(self, threadId: int=None, questionId: int=None):
		'''
		## Delete Help Thread

		Deletes the Discord thread corresponding to a given help question.

		### Parameters
		- threadId (int): The ID of the Discord thread.
		- questionId (int): The ID of the help question.

		NOTE: Either threadId or questionId must be provided. If both are provided, we will use
		the threadId to delete the thread.
		'''

		# Make sure we have at least one identifier
		if threadId is None and questionId is None:
			raise ValueError("Either threadId or questionId must be provided to delete a help thread.")
		
		# Get all threads that currently exist
		allThreads = self.getAllThreads()

		# If we only have questionId, find the threadId
		if threadId is None:
			threadId = allThreads.inverse.get(questionId)
			if threadId is None:
				raise ValueError(f"No thread found for question ID {questionId}.")

		# If we were given a threadId, make sure it exists
		if threadId not in allThreads:
			raise ValueError(f"No thread found with thread ID {threadId}.")
		
		# Log deletion
		self.logger.debug(f"Deleting help thread ID {threadId} for question ID {allThreads[threadId]}.")
		
		# Delete the thread
		thread = self.bot.get_channel(threadId)
		await thread.delete()

	async def updateHelpThread(self, threadId: int=None, questionId: int=None, questionPlayer: str=None, questionStatus: str=None, questionContent: str=None, questionClaimedBy: str=None):
		'''
		## Update Help Thread

		Updates the Discord thread corresponding to a given help question.

		### Parameters
		- threadId (int): The ID of the Discord thread.
		- questionId (int): The ID of the help question.
		- questionPlayer (str): The player who asked the question.
		- questionContent (str): The content of the help question.
		- questionStatus (str): The status of the help question.
		- questionClaimedBy (str): The admin who claimed the question, if any

		NOTE: Either threadId or questionId must be provided. If both are provided, we will use
		the threadId to update the thread.
		'''

		# Make sure we have at least one identifier
		if threadId is None and questionId is None:
			raise ValueError("Either threadId or questionId must be provided to update a help thread.")
		
		# Get all threads that currently exist
		allThreads = self.getAllThreads()

		# If we only have questionId, find the threadId
		if threadId is None:
			threadId = allThreads.inverse.get(questionId)
			if threadId is None:
				raise ValueError(f"No thread found for question ID {questionId}.")

		# If we were given a threadId, make sure it exists
		if threadId not in allThreads:
			raise ValueError(f"No thread found with thread ID {threadId}.")
		
		# Get the thread
		thread = self.bot.get_channel(threadId)

		# Update the pinned embed message
		pinnedMessages = await thread.pins()
		if not pinnedMessages:
			raise ValueError(f"No pinned messages found in thread ID {threadId} to update.")
		
		# Log update
		self.logger.debug(f"Updating help thread ID {threadId} for question ID {allThreads[threadId]}.")

		# Update the embed
		pinnedEmbedMessage = pinnedMessages[0]
		newEmbed = HelpQuestionEmbed(
			questionId=questionId,
			questionText=questionContent,
			questionStatus=questionStatus,
			questionClaimedBy=questionClaimedBy or "Unclaimed"
		 )
		await pinnedEmbedMessage.edit(embed=newEmbed)