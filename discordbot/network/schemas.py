'''
MCLabs Discord Bot - API Schemas

Author: Chris Hinkson @cmh02
'''

from uuid import UUID
from pydantic import BaseModel, Field

class UpdateRequest(BaseModel):
	'''
	# UpdateRequest

	Model for relay update requests from the backend API.
	'''
	update_id: UUID = Field(description="The unique update ID from relay.")
	ticket_action: str = Field(description="The action taken on the ticket.")
	ticket_id: int = Field(description="The ticket ID.")


class AdminMessageRequest(BaseModel):
	'''
	# AdminMessageRequest

	Model for sending a message to the administration channel.
	'''
	message: str = Field(description="The message content to send to the admin channel.")

