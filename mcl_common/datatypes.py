'''
MCLabs Common Datatypes

Author: Chris Hinkson @cmh02
'''

from __future__ import annotations

'''
MODULE IMPORTS
'''
from typing import Optional
from datetime import datetime

from mcl_common.enum import TicketType, TicketStatus, TicketFeedback


'''
DATA TYPE DEFINITIONS
'''

class PlayerInfo:
	'''
	# PlayerInfo

	Represents identification details of a player (Minecraft & Discord).
	'''

	def __init__(self,
				 minecraftUsername: Optional[str] = None,
				 minecraftUUID: Optional[str] = None,
				 discordUsername: Optional[str] = None,
				 discordId: Optional[str] = None):
		self.minecraftUsername: Optional[str] = minecraftUsername
		self.minecraftUUID: Optional[str] = minecraftUUID
		self.discordUsername: Optional[str] = discordUsername
		self.discordId: Optional[str] = discordId

	def toDict(self) -> dict:
		return {
			"minecraftUsername": self.minecraftUsername,
			"minecraftUUID": self.minecraftUUID,
			"discordUsername": self.discordUsername,
			"discordId": self.discordId
		}

	@staticmethod
	def fromDict(data: dict) -> 'PlayerInfo':
		return PlayerInfo(
			minecraftUsername=data.get("minecraftUsername"),
			minecraftUUID=data.get("minecraftUUID"),
			discordUsername=data.get("discordUsername"),
			discordId=data.get("discordId")
		)

class Message:
	'''
	# Message

	Represents a message within a conversation.
	'''

	def __init__(self, timestamp: float, sender: PlayerInfo, content: str):
		self.timestamp: float = timestamp
		self.sender: PlayerInfo = sender
		self.content: str = content

	def toDict(self) -> dict:
		return {
			"timestamp": self.timestamp,
			"sender": self.sender.toDict(),
			"content": self.content
		}
	
	@staticmethod
	def fromDict(data: dict) -> 'Message':
		return Message(
			timestamp=data["timestamp"],
			sender=PlayerInfo.fromDict(data["sender"]),
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
		self.messages.append(message)

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
				 playerInfo: PlayerInfo,
				 type: TicketType,
				 conversation: Optional[Conversation] = None,
				 threadId: Optional[int] = None
				):
		self.ticketId: int = ticketId
		self.playerInfo: PlayerInfo = playerInfo
		self.type: TicketType = type
		self.conversation: Conversation = conversation if conversation else Conversation()
		self.status: TicketStatus = TicketStatus.OPEN
		self.feedback: TicketFeedback = TicketFeedback.NONE
		self.claimedBy: Optional[str] = None
		self.closedBy: Optional[str] = None
		self.time_create: Optional[float] = datetime.now().timestamp()
		self.time_claim: Optional[float] = None
		self.time_close: Optional[float] = None
		self.threadId: Optional[int] = threadId

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
			"playerInfo": self.playerInfo.toDict(),
			"type": self.type.value,
			"conversation": self.conversation.toDict(),
			"status": self.status.value,
			"feedback": self.feedback.value,
			"claimedBy": self.claimedBy,
			"closedBy": self.closedBy,
			"time_create": self.time_create,
			"time_claim": self.time_claim,
			"time_close": self.time_close,
			"threadId": self.threadId
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
