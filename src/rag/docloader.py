'''
MCLabs Wiki RAG - Document Loader

Author: Chris Hinkson @cmh02
'''

import os
import json
import faiss
import numpy as np
from typing import List, Dict
from mcl_common.logger import MCL_Logger
from mcl_common.enum import RagIndexType
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

		# Validate paths
		self.PATH_EMBEDDINGS = os.path.join(self.dataDirectory, 'embeddings/')
		if not os.path.exists(self.PATH_EMBEDDINGS):
			raise FileNotFoundError(f"Embeddings folder not found at {self.PATH_EMBEDDINGS}!")
		self.PATH_INDEX_HEAVY: str = os.path.join(self.PATH_EMBEDDINGS, 'wiki.index')
		if not os.path.exists(self.PATH_INDEX_HEAVY):
			raise FileNotFoundError(f"Heavy FAISS index not found at {self.PATH_INDEX_HEAVY}!")
		self.PATH_INDEX_CACHE: str = os.path.join(self.PATH_EMBEDDINGS, 'semantic_cache.index')
		if not os.path.exists(self.PATH_INDEX_CACHE):
			raise FileNotFoundError(f"Cache FAISS index not found at {self.PATH_INDEX_CACHE}!")
		self.PATH_DOCS_HEAVY: str = os.path.join(self.PATH_EMBEDDINGS, 'wiki_docs.json')
		if not os.path.exists(self.PATH_DOCS_HEAVY):
			raise FileNotFoundError(f"Heavy Documents JSON not found at {self.PATH_DOCS_HEAVY}!")
		self.PATH_DOCS_CACHE: str = os.path.join(self.PATH_EMBEDDINGS, 'semantic_cache_answers.json')
		if not os.path.exists(self.PATH_DOCS_CACHE):
			raise FileNotFoundError(f"Cache Documents JSON not found at {self.PATH_DOCS_CACHE}!")

		# Initialize placeholders for index and documents
		self.index: Dict[RagIndexType, faiss.IndexFlatIP] = {}
		self.documents: Dict[RagIndexType, List[RagDocument]] = {}

		# Log creation
		self.logger = MCL_Logger.setup_logger("MCL_API_Logger")
		self.logger.info("New WikiDocLoader instance created!")

	# Load the FAISS index and documents from disk
	def loadIndexAndDocuments(self):

		# Load index files into memory
		self.index[RagIndexType.HEAVY] = faiss.read_index(self.PATH_INDEX_HEAVY)
		self.index[RagIndexType.CACHE] = faiss.read_index(self.PATH_INDEX_CACHE)

		# Load documents into memory
		with open(self.PATH_DOCS_HEAVY, "r", encoding="utf-8") as f:
			self.documents[RagIndexType.HEAVY] = [RagDocument.model_validate(doc) for doc in json.load(f)]
		with open(self.PATH_DOCS_CACHE, "r", encoding="utf-8") as f:
			self.documents[RagIndexType.CACHE] = json.load(f)
		self.logger.info(f"Loaded semantic cache index and {len(self.documents[RagIndexType.CACHE])} cached answers from disk!")
		self.logger.info(f"Loaded heavy FAISS index and {len(self.documents[RagIndexType.HEAVY])} documents from disk!")

	# Perform nearest neighbors search in the FAISS index
	def performIndexSearch(self, queryVector: np.ndarray, k: int, indexType: RagIndexType) -> tuple[np.ndarray, np.ndarray]:
		if self.index[indexType] is None:
			raise RuntimeError(f"{indexType} FAISS index has not been loaded. Call loadIndexAndDocuments() first.")
		return self.index[indexType].search(queryVector, k) # type: ignore

	# Retrieve document metadata by index
	def getDocument(self, index: int, indexType: RagIndexType) -> RagDocument:
		if self.documents[indexType] is None:
			raise RuntimeError(f"{indexType} documents have not been loaded. Call loadIndexAndDocuments() first.")
		return self.documents[indexType][index]
