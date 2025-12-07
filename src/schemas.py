'''
MCLabs Common Pydantic Schemas

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from pydantic import BaseModel, Field, field_validator

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

	# Help question ID converted to int if needed
	question_id: int = Field(description="The ID of the help question.", ge=0)
	@field_validator("question_id", mode="before")
	def validate_question_id(cls, id: int | str) -> int:
		if isinstance(id, str):
			return int(id)
		return id