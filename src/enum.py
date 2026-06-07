'''
MCLabs Common Enums

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from enum import Enum

class TicketStatus(Enum):
	OPEN = "OPEN"
	CLAIMED = "CLAIMED"
	CLOSED = "CLOSED"

class UpdateSource(Enum):
	MINECRAFT = "MINECRAFT"
	DISCORD = "DISCORD"