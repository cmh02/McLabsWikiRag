'''
MCLabs Common Datatypes

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from typing import Optional
from datetime import datetime



'''
DATA TYPE DEFINITIONS
'''

class Message:
	'''
	# Message

	Represents a message within a conversation.
	'''

	def __init__(self, timestamp: float, sender: str, content: str):
		self.timestamp: float = timestamp
		self.sender: str = sender
		self.content: str = content

	def toDict(self) -> dict:
		return {
			"timestamp": self.timestamp,
			"sender": self.sender,
			"content": self.content
		}
	
class Conversation:
	'''
	# Conversation

	Represents a conversation between a player and staff members.
	'''

	def __init__(self, conversationId: int, player: str):
		self.conversationId: int = conversationId
		self.player: str = player
		self.messages: list[Message] = []

	def appendMessage(self, message: Message):
		self.messages.append(object=message)

	def toDict(self) -> dict:
		return {
			"conversationId": self.conversationId,
			"player": self.player,
			"messages": [message.toDict() for message in self.messages]
		}