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