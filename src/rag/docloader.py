'''
MCLabs Wiki RAG - Document Loader

Author: Chris Hinkson @cmh02
'''

import os
import pickle
import faiss
from mcl_common.logger import MCL_Logger

class MCL_WikiDocLoader():

	# Class Constructor
	def __init__(self, path_embeddings: str | None = None):

		# Current file and directory paths
		self.CURRENT_FILE_PATH = os.path.abspath(__file__)
		self.CURRENT_DIR = os.path.dirname(self.CURRENT_FILE_PATH)
		self.ROOT_DIR = os.path.dirname(self.CURRENT_DIR)

		# Embeddings folder path
		if path_embeddings is None:
			self.PATH_EMBEDDINGS = os.path.join(self.ROOT_DIR, 'embeddings/')
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
		self.index = faiss.read_index(f"{self.PATH_EMBEDDINGS}wiki.index")
		with open(f"{self.PATH_EMBEDDINGS}wiki_docs.pkl", "rb") as f:
			self.documents = pickle.load(f)
		self.logger.info(f"Loaded index and {len(self.documents)} documents from disk")
