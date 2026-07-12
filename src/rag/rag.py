'''
MCLabs Wiki RAG - RAG Prompting and Response

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
import datetime

# Vector Database
import faiss

# Data Handling
import numpy as np

# Google API
from google import genai
from google.genai import types

# MCL Packages
from mcl_common.logger import MCL_Logger
from src.rag.docloader import MCL_WikiDocLoader

'''
RAG CLASS

This class will handle actually performing RAG prompting and response generation.
'''

class MCL_WikiRag():

	# Class Constructor
	def __init__(self, client: genai.Client | None = None, docLoader: MCL_WikiDocLoader | None = None):

		# Make client if not provided
		if client is None:
			self.client = genai.Client(api_key=os.getenv('GOOGLE_GEMINI_API_KEY'))
		else:
			self.client = client

		# Make WikiDocLoader instance if not provided
		if docLoader is None:
			self.docLoader = MCL_WikiDocLoader()
			self.docLoader.loadIndexAndDocuments()
		else:
			self.docLoader = docLoader

		# Load Google Gemini model name from environment (required)
		model_name = os.getenv('GOOGLE_GEMINI_MODEL')
		if not model_name:
			raise ValueError("GOOGLE_GEMINI_MODEL environment variable is not set.")
		self.model_name: str = model_name

		# Set up logger
		self.logger = MCL_Logger.setup_logger("MCL_API_Logger")
		self.logger.info(f"New WikiRag instance created with model: {self.model_name}!")

	# Full pipeline function to handle a user query
	def queryPipeline(self, question, topK=5) -> tuple:
		
		# Embed the query
		queryVector = self._embedQuery(question)
		
		# Retriev top-K chunks
		topChunks = self._retrieveChunks(queryVector, topK=topK)

		# Generate the answer
		answer = self._generateAnswer(question, topChunks)

		# Return the answer and the top chunks used
		return answer, topChunks

	# Embed a user's query using Gemini
	def _embedQuery(self, query) -> np.ndarray:
		
		# Get embedding using API
		response = self.client.models.embed_content(
			model="text-embedding-001",
			contents=[query],
			config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
		)
		
		# Return embedding as a numpy float32 vector
		if not response.embeddings:
			raise ValueError("No embeddings returned from Gemini API.")
		return np.array(response.embeddings[0].values, dtype=np.float32)

	# Retrieve top-K relevant chunks from FAISS index
	def _retrieveChunks(self, queryVector, topK=5) -> list:
		
		# Normalize the query vector
		faiss.normalize_L2(queryVector.reshape(1, -1))

		# Create list for results
		results = []
		current_date = datetime.date.today()

		# Get top K*2 nearest neighbors for resorting
		distances, indices = self.docLoader.performIndexSearch(queryVector.reshape(1, -1), topK * 2)

		# Sort results by type and date
		for score, index in zip(distances[0], indices[0]):

			# Get the document
			doc = self.docLoader.getDocument(index)

			# Modify score based on document type
			if doc.get("source") == "helpQA":
				
				# Apply FAQ boost
				score *= int(os.getenv('RAG_HP_FAQSCOREBOOST', 1.2))

				# Apply time boosts if date is present
				if "date" in doc:
					try:
						# Document date boost, targeted at prioritizing most recent FAQs, with 50% being > 90 days
						documentDate = datetime.date.fromisoformat(doc.get("date"))
						documentAge = (current_date - documentDate).days
						lam = np.log(2) / int(os.getenv("RAG_HP_RECENCYHALFLIFE", 90.0))
						score *= np.exp(-lam * documentAge)

						# Current season boost, targeted at prioritizing FAQs from the current season (since May 1st)
						if documentDate >= datetime.date(current_date.year, 5, 1):
							score *= int(os.getenv('RAG_HP_SEASONBOOST', 1.1))

					except Exception:
						# Incase of date parsing error, just ignore
						pass  

			# Append the (possibly modified) score and document to results
			results.append((score, doc))

		# Sort results by modified score in descending order
		results.sort(key=lambda x: x[0], reverse=True)
		
		# Return the retrieved top k chunks
		return [doc for score, doc in results[:topK]]

	# Generate an answer using Gemini with the retrieved chunks as context
	def _generateAnswer(self, question, topChunks) -> str | None:
		
		# Combine chunks into context and create the prompt
		contextText = "\n".join([f"{chunk['title']}: {chunk['content']}" for chunk in topChunks])
		prompt = f"""
		You are a helpful assistant for players on a minecraft server. 
		Use the following wiki and Q&A context to answer the given question. 

		CRITICAL INSTRUCTIONS:
		1. Determine if the question contains an actual question, inquiry, or request for information. If it does not (e.g. it is a simple greeting, statement, thank you, or irrelevant message), respond with exactly "UNANSWERABLE".
		2. If the provided context does not contain enough information to answer the question, or if you don't know the answer, respond with exactly "UNANSWERABLE".
		3. Provide a medium-length answer with details while being concise.
		4. Do not hallucinate. Do not try to answer using general knowledge that is not related to the minecraft server.
		5. Prefer FAQ chunks if present. If multiple answers conflict, choose the most recent one.
		6. Ignore any context that regards factions, the /f command, or raid world.
		7. Never refer to 'chems' as 'chemicals', only use the word 'chems'.
		8. Refer to the Town world as the Overworld and the Company world as the Underworld.

		Context:
		{contextText}

		Question: {question}

		Answer:"""
		
		# Get the answer using the API
		response = self.client.models.generate_content(
			model=self.model_name,
			contents=prompt
		)
		
		# Return the generated answer text
		return response.text