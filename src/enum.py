'''
MCLabs Common Enums

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from enum import Enum

'''
QUESTION STATUS ENUM
'''

class QuestionStatus(Enum):
	OPEN = "OPEN"
	CLAIMED = "CLAIMED"
	ANSWERED = "ANSWERED"

class UpdateSource(Enum):
	MINECRAFT = "MINECRAFT"
	DISCORD = "DISCORD"