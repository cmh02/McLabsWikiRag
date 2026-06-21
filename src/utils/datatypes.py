'''
MCLabs Common Datatypes

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from typing import Optional
from datetime import datetime

from src.utils.enum import TicketType, TicketStatus, TicketFeedback


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
	
	@staticmethod
	def fromDict(data: dict) -> 'Message':
		return Message(
			timestamp=data["timestamp"],
			sender=data["sender"],
			content=data["content"]
		)
	
class Conversation:
	'''
	# Conversation

	Represents a conversation between a player and staff members.
	'''

	def __init__(self):
		self.messages: list[Message] = []

	def appendMessage(self, message: Message):
		self.messages.append(object=message)

	def getLastMessage(self) -> Optional[Message]:
		if len(self.messages) == 0:
			return None
		return self.messages[-1]

	def toDict(self) -> dict:
		return {
			"messages": [message.toDict() for message in self.messages]
		}
	
	@staticmethod
	def fromDict(data: dict) -> 'Conversation':
		conv = Conversation()
		for message_data in data.get("messages", []):
			message = Message.fromDict(message_data)
			conv.appendMessage(message)
		return conv
	
class HelpTicket:
	'''
	# HelpTicket

	Represents a help ticket, which contains a conversation and several metadata fields.
	'''

	def __init__(self, 
			  	 ticketId: int, 
				 player: str,
				 type: TicketType,
				 conversation: Optional[Conversation] = None
				):
		self.ticketId: int = ticketId
		self.player: str = player
		self.type: TicketType = type
		self.conversation: Conversation = conversation if conversation else Conversation(conversationId=ticketId)
		self.status: TicketStatus = TicketStatus.OPEN
		self.feedback: TicketFeedback = TicketFeedback.NONE
		self.claimedBy: Optional[str] = None
		self.closedBy: Optional[str] = None
		self.time_create: Optional[float] = datetime.now().timestamp()
		self.time_claim: Optional[float] = None
		self.time_close: Optional[float] = None

	def toDict(self) -> dict:
		"""
		## Serialize As Dictionary
		Serializes the help ticket as a dictionary for easy JSON conversion.

		### Parameters
			None

		### Returns
			dict: A dictionary representation of the help ticket.
		"""
		return {
			"ticketId": self.ticketId,
			"player": self.player,
			"type": self.type.value,
			"conversation": self.conversation.toDict(),
			"status": self.status.value,
			"feedback": self.feedback.value,
			"claimedBy": self.claimedBy,
			"closedBy": self.closedBy,
			"time_create": self.time_create,
			"time_claim": self.time_claim,
			"time_close": self.time_close
		}
	
	def appendMessage(self, message: Message):
		"""
		## Append Message to Conversation
		Appends a message to the help ticket's conversation.

		### Parameters
			message (Message): The message to append to the conversation.

		### Returns
			None
		"""
		self.conversation.appendMessage(message=message)

	def getLastMessage(self) -> Optional[Message]:
		"""
		## Get Last Message from Conversation
		Retrieves the last message in the help ticket's conversation.

		### Parameters
			None

		### Returns
			Optional[Message]: The last message in the conversation, or None if there are no messages.
		"""
		return self.conversation.getLastMessage()
	
	def open(self):
		"""
		## Open Ticket
		Open the help ticket.

		### Parameters
			None

		### Returns
			None
		"""
		self.status = TicketStatus.OPEN
		self.closedBy = None
		self.time_close = None

	def claim(self, claimedBy: str):
		"""
		## Claim Ticket
		Claim the help ticket for a staff member.

		### Parameters
			claimedBy (str): The UUID of the staff member claiming the ticket.

		### Returns
			None
		"""
		self.status = TicketStatus.CLAIMED
		self.claimedBy = claimedBy
		self.time_claim = datetime.now().timestamp()

	def unclaim(self):
		"""
		## Unclaim Ticket
		Unclaim the help ticket, returning it to the open status.

		### Parameters
			None

		### Returns
			None
		"""
		self.status = TicketStatus.OPEN
		self.claimedBy = None
		self.time_claim = None

	def close(self, closedBy: str):
		"""
		## Close Ticket
		Close the help ticket for a staff member.

		### Parameters
			closedBy (str): The UUID of the staff member closing the ticket.

		### Returns
			None
		"""
		self.status = TicketStatus.CLOSED
		self.closedBy = closedBy
		self.time_close = datetime.now().timestamp()

	def setFeedback(self, feedback: TicketFeedback):
		"""
		## Set Feedback
		Set the feedback for the help ticket.

		### Parameters
			feedback (TicketFeedback): The feedback to set.

		### Returns
			None
		"""
		self.feedback = feedback