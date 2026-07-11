'''
MCLabs Common Enums

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from enum import Enum

class TicketType(Enum):
	SUPPORT = "SUPPORT"

class TicketStatus(Enum):
	OPEN = "OPEN"
	CLAIMED = "CLAIMED"
	CLOSED = "CLOSED"

class TicketFeedback(Enum):
	NONE = "NONE"
	HELPFUL = "HELPFUL"
	UNHELPFUL = "UNHELPFUL"

class TicketAction(Enum):
	CREATE = "CREATE"
	CLOSE = "CLOSE"
	CLAIM = "CLAIM"
	UNCLAIM = "UNCLAIM"
	FEEDBACK = "FEEDBACK"
	NEWMESSAGE = "NEW_MESSAGE"

class RelayDestination(Enum):
	'''
	MCL Relay Destination

	Enum to define the possible destinations for outbound relay calls.
	'''
	MINECRAFT = "MINECRAFT"
	DISCORD = "DISCORD"

class MongoDatabase(Enum):
	HELP = "help"
	BOT = "bot"

class MongoCollection(Enum):
	TICKETS = "tickets"
	PLAYER_INFO = "playerinfo"
	SYSTEM_STATUS = "system_status"