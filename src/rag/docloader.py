'''
MCLabs Wiki RAG - Document Loader

Author: Chris Hinkson @cmh02
'''

import os
import json
import faiss
from mcl_common.logger import MCL_Logger
from src.rag.document import RagDocument

class MCL_WikiDocLoader():

	# Class Constructor
	def __init__(self, path_embeddings: str | None = None):

		# Current file and directory paths
		self.CURRENT_FILE_PATH = os.path.abspath(__file__)
		self.CURRENT_DIR = os.path.dirname(self.CURRENT_FILE_PATH)
		self.ROOT_DIR = os.path.dirname(self.CURRENT_DIR)
		self.PROJECT_ROOT = os.path.dirname(self.ROOT_DIR)

		# Embeddings folder path
		if path_embeddings is None:
			data_dir = os.getenv("RAILWAY_DATA_DIRECTORY")
			if not data_dir:
				raise ValueError("RAILWAY_DATA_DIRECTORY environment variable is not set.")
			if not os.path.isabs(data_dir):
				data_path = os.path.join(self.PROJECT_ROOT, data_dir)
			else:
				data_path = data_dir
			self.PATH_EMBEDDINGS = os.path.join(data_path, 'embeddings/')
		else:
			self.PATH_EMBEDDINGS = path_embeddings

		# Initialize placeholders for index and documents
		self.index = None
		self.documents = []

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
	def performIndexSearch(self, queryVector, k: int):
		if self.index is None:
			raise RuntimeError("FAISS index has not been loaded. Call loadIndexAndDocuments() first.")
		return self.index.search(queryVector, k)

	# Retrieve document metadata by index
	def getDocument(self, index: int) -> RagDocument:
		return self.documents[index]
