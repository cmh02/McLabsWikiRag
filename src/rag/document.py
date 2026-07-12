'''
MCLabs Wiki RAG - RagDocument Data Type

Author: Chris Hinkson @cmh02
'''

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class DocumentSource(str, Enum):
    """
    # Document Source Enum

    Represents the source of a document in the RAG system.
    Scaling can be applied to the raw weight of a document based on its source.
    """
    WIKI = "Wiki"
    HELP_QUESTION = "HelpQuestion"

class RagDocument(BaseModel):
    """
    # RagDocument Data Type

    Represents a document in the RAG system.
    
    title: str
        The title of the document.

    content: str
        The content of the document.

    source: DocumentSource
        The source of the document.

    date: float
        The date of the document as a Unix timestamp.

    scale: float
        The scale factor to apply to the document's similarity score.
    """
    title: Optional[str] = None
    content: str
    source: DocumentSource
    date: Optional[float] = None  # Unix timestamp
    scale: float = Field(default=1.0, ge=0.0)
