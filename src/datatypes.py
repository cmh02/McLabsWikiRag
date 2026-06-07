'''
MCLabs Common Datatypes

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from typing import Optional
from datetime import datetime

from src.enum import TicketStatus, TicketFeedback


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
	
class HelpTicket:
	'''
	# HelpTicket

	Represents a help ticket, which contains a conversation and several metadata fields.
	'''

	def __init__(self, 
			  	 ticketId: int, 
				 player: str, 
				 conversation: Optional[Conversation] = None,
				 ticketStatus: Optional[TicketStatus] = TicketStatus.OPEN,
				 ticketFeedback: Optional[TicketFeedback] = TicketFeedback.NONE
				):
		self.ticketId: int = ticketId
		self.player: str = player
		self.conversation: Conversation = conversation if conversation else Conversation(conversationId=ticketId, player=player)
		self.status: TicketStatus = ticketStatus
		self.feedback: TicketFeedback = ticketFeedback