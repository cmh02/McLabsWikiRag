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
from typing import Dict

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
from src.rag.document import RagDocument, DocumentSource

'''
RAG CLASS

This class will handle actually performing RAG prompting and response generation.
'''

class MCL_WikiRag():

	# Class Constructor
	def __init__(self, 
		client: genai.Client,
		docLoader: MCL_WikiDocLoader,
		generationModelName: str,
		embeddingModelName: str,
		embeddingDimension: int,
		dynamicSourceScale: Dict[DocumentSource, float],
		dynamicTimeScale: Dict[str, float],
		cacheThreshold: float
	):

		# Make sure required objects are passed in
		if (client is None):
			raise ValueError("MCLabs RAG Object requires Google GenAI Client object to be provided!")
		if (docLoader is None):
			raise ValueError("MCLabs RAG Object requires MCL_WikiDocLoader object to be provided!")
		if ((generationModelName is None) or (generationModelName.strip() == "")):
			raise ValueError("MCLabs RAG Object requires Google Gemini model name to be provided!")
		if ((embeddingModelName is None) or (embeddingModelName.strip() == "")):
			raise ValueError("MCLabs RAG Object requires Google Gemini embedding model name to be provided!")
		if (embeddingDimension is None):
			raise ValueError("MCLabs RAG Object requires embedding dimension to be provided!")
		if (dynamicSourceScale is None):
			raise ValueError("MCLabs RAG Object requires dynamic source scale dictionary to be provided!")
		if (dynamicTimeScale is None):
			raise ValueError("MCLabs RAG Object requires dynamic time scale dictionary to be provided!")
		if (cacheThreshold is None):
			raise ValueError("MCLabs RAG Object requires semantic cache threshold to be provided!")
		self.client: genai.Client = client
		self.docLoader: MCL_WikiDocLoader = docLoader
		self.generationModelName: str = generationModelName
		self.embeddingModelName: str = embeddingModelName
		self.embeddingDimension: int = embeddingDimension
		self.dynamicSourceScale: Dict[DocumentSource, float] = dynamicSourceScale
		self.dynamicTimeScale: Dict[str, float] = dynamicTimeScale
		self.cacheThreshold: float = cacheThreshold

		# Set up logger
		self.logger = MCL_Logger.setup_logger("MCL_API_Logger")
		self.logger.info(f"New WikiRag instance created with model: {self.generationModelName}!")

	# Full pipeline function to handle a user query
	def queryPipeline(self, question, topK=5) -> tuple:
		
		# Embed the query
		queryVector = self._embedQuery(question)

		# Check semantic cache first if loaded
		if self.docLoader.cache_index is not None and self.docLoader.cache_answers:
			# Normalize the query vector for cosine similarity search
			queryVectorNorm = queryVector.copy()
			faiss.normalize_L2(queryVectorNorm.reshape(1, -1))

			# Search cache index for the single nearest neighbor
			distances, indices = self.docLoader.cache_index.search(queryVectorNorm.reshape(1, -1), 1)

			if len(distances) > 0 and len(distances[0]) > 0:
				score = distances[0][0]
				idx = indices[0][0]
				if idx != -1 and score >= self.cacheThreshold:
					matched_item = self.docLoader.cache_answers[idx]
					self.logger.info(f"Semantic cache hit! Score: {score:.4f} >= threshold: {self.cacheThreshold:.4f}")

					# Return cached answer with a dummy RagDocument representing the cache hit
					cache_doc = RagDocument(
						title=f"Semantic Cache Hit (Score: {score:.4f})",
						content=f"Question: {matched_item['question']}\nAnswer: {matched_item['answer']}",
						source=DocumentSource.SEMANTIC_CACHE,
						date=None,
						scale=1.0
					)
					return matched_item["answer"], [cache_doc]
		
		# Retrieve top-K chunks
		topChunks = self._retrieveChunks(queryVector, topK=topK)

		# Generate the answer
		answer = self._generateAnswer(question, topChunks)

		# Return the answer and the top chunks used
		return answer, topChunks

	# Embed a user's query using Gemini
	def _embedQuery(self, query) -> np.ndarray:
		
		# Get embedding using API
		response = self.client.models.embed_content(
			model=self.embeddingModelName,
			contents=[query],
			config=types.EmbedContentConfig(
				task_type="RETRIEVAL_QUERY",
				output_dimensionality=self.embeddingDimension
			)
		)
		
		# Return embedding as a numpy float32 vector
		if not response.embeddings:
			raise ValueError("No embeddings returned from Gemini API.")
		return np.array(response.embeddings[0].values, dtype=np.float32)

	# Retrieve top-K relevant chunks from FAISS index
	def _retrieveChunks(self, queryVector, topK=5) -> list[RagDocument]:
		
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
			doc: RagDocument | None = self.docLoader.getDocument(index)
			if doc is None:
				raise ValueError(f"An error occured while trying to retrieve document at index {index} from FAISS!")

			# Apply raw weight from the document itself
			score *= doc.scale

			# Modify score based on document type
			score *= self.dynamicSourceScale[doc.source]

			# Apply time boosts if date is present
			if doc.date is not None:
				try:

					# Apply recency boost, targeted at prioritizing most recent FAQs, with 50% being > 90 days
					documentDate = datetime.date.fromtimestamp(doc.date)
					documentAge = (current_date - documentDate).days
					lam = np.log(2) / self.dynamicTimeScale["recency"]
					score *= np.exp(-lam * documentAge)

					# Current season boost, targeted at prioritizing FAQs from the current season (since May 1st)
					if documentDate >= datetime.date(current_date.year, 5, 1):
						score *= self.dynamicTimeScale["season"]

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
		contextText = "\n".join([
			f"{chunk.title}: {chunk.content}" if chunk.title else chunk.content
			for chunk in topChunks
		])
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
		response = self.client.interactions.create(
			model=self.generationModelName,
			input=prompt
		)
		
		# Return the generated answer text
		if hasattr(response, 'output_text') and response.output_text:
			return response.output_text
		if hasattr(response, 'outputs') and response.outputs:
			return response.outputs[-1].text
		return None