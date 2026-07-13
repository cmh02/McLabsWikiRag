'''
MCLabs Wiki RAG - Document Loader

Author: Chris Hinkson @cmh02
'''

import os
import json
import faiss
import numpy as np
from typing import List
from mcl_common.logger import MCL_Logger
from src.rag.document import RagDocument

class MCL_WikiDocLoader():

	# Class Constructor
	def __init__(self, 
		dataDirectory: str
	):

		# Input Validation
		if ((dataDirectory is None) or (dataDirectory.strip() == "")):
			raise ValueError("MCLabs Wiki DocLoader requires data directory to be provided!")
		self.dataDirectory: str = dataDirectory

		# Embeddings folder path
		self.PATH_EMBEDDINGS = os.path.join(self.dataDirectory, 'embeddings/')
		os.makedirs(self.PATH_EMBEDDINGS, exist_ok=True)

		# Initialize placeholders for index and documents
		self.index: faiss.IndexFlatIP | None = None
		self.documents: List[RagDocument] = []

		# Log creation
		self.logger = MCL_Logger.setup_logger("MCL_API_Logger")
		self.logger.info("New WikiDocLoader instance created!")

	# Load the FAISS index and documents from disk
	def loadIndexAndDocuments(self):

		# Load the index and documents for later use
		index_path = f"{self.PATH_EMBEDDINGS}wiki.index"
		if os.path.exists(index_path):
			self.index = faiss.read_index(index_path)
		else:
			self.logger.warning(f"wiki.index not found at {index_path}. FAISS index not loaded.")
			self.index = None
		
		# Load documents from JSON
		json_path = f"{self.PATH_EMBEDDINGS}wiki_docs.json"
		if os.path.exists(json_path):
			with open(json_path, "r", encoding="utf-8") as f:
				docs_data = json.load(f)
				self.documents = [RagDocument.model_validate(doc) for doc in docs_data]
		else:
			self.logger.warning(f"wiki_docs.json not found at {json_path}")
			self.documents = []
		self.logger.info(f"Loaded index and {len(self.documents)} documents from disk!")

	# Perform nearest neighbors search in the FAISS index
	def performIndexSearch(self, queryVector: np.ndarray, k: int):
		if self.index is None:
			raise RuntimeError("FAISS index has not been loaded. Call loadIndexAndDocuments() first.")
		return self.index.search(queryVector, k) # type: ignore

	# Retrieve document metadata by index
	def getDocument(self, index: int) -> RagDocument:
		return self.documents[index]
