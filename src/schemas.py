'''
MCLabs Common Pydantic Schemas

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from fastapi import Header

from src.helpmanager import UpdateSource

'''
MODEL DEFINITIONS
'''

class BaseHelpQuestionSchema(BaseModel):
	'''
	# BaseHelpQuestionRequest

	Basic model for help question requests to the API. All this provides is the help question ID and source.
	'''

	# Help question ID converted to int if needed
	question_id: int = Field(description="The ID of the help question.", ge=0)
	@field_validator("question_id", mode="before")
	def validate_question_id(cls, id: int | str) -> int:
		if isinstance(id, str):
			return int(id)
		return id
	
	# Source of the help question (either minecraft or discord)
	question_source: UpdateSource = Field(description="The source of the help question.")
	
class QuestionSchema(BaseModel):
	'''
	# QuestionSchema

	Model for help question listing response.
	'''
	id: int = Field(description="The ID of the help question.")
	player: str = Field(description="The player who asked the help question.")
	content: str = Field(description="The content of the help question.")
	status: str = Field(description="The status of the help question.")
	claimedBy: Optional[str] = Field(default=None, description="The staff member who claimed the help question, if any.")
	answeredBy: Optional[str] = Field(default=None, description="The staff member who answered the help question, if any.")
	answer: Optional[str] = Field(default=None, description="The answer to the help question, if any.")