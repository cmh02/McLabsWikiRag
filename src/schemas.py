'''
MCLabs Common Pydantic Schemas

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from pydantic import BaseModel, Field

'''
MODEL DEFINITIONS
'''

class BaseRequestSchema(BaseModel):
	'''
	# BaseRequest

	Basic model for all requests to the API. All this provides is authentication via API token.
	'''

	# API token for authentication
	api_token: str = Field(description="API token for authentication.")

class BaseHelpQuestionSchema(BaseRequestSchema):
	'''
	# BaseHelpQuestionRequest

	Basic model for help question requests to the API. All this provides is the help question ID.
	'''

	# Help question ID
	question_id: int = Field(description="The ID of the help question.")