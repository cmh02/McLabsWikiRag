'''
MCLabs Wiki RAG - Document Fetch and Embedding

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
import json
import datetime

# Vector Database
import faiss
from faiss import extra_wrappers

# Data Handling
import numpy as np

# Web-Related
import requests
from bs4 import BeautifulSoup

# Google API
from google import genai
from google.genai import types

# MCL Packages
from mcl_common.config import settings
from mcl_common.logger import MCL_Logger
from src.rag.document import RagDocument, DocumentSource

'''
WIKI EMBEDDER CLASS

This class will handle fetching, parsing, chunking, and embedding all of the MCL Wiki pages.
'''

class MCL_WikiEmbedder():

	# Class Constructor
	def __init__(self, 
		client: genai.Client,
		dataDirectory: str,
		embeddingModelName: str,
		embeddingDimension: int
	):

		# Input Validation
		if (client is None):
			raise ValueError("MCLabs Wiki Embedder requires Google GenAI Client object to be provided!")
		if ((dataDirectory is None) or (dataDirectory.strip() == "")):
			raise ValueError("MCLabs Wiki Embedder requires data directory to be provided!")
		if ((embeddingModelName is None) or (embeddingModelName.strip() == "")):
			raise ValueError("MCLabs Wiki Embedder requires embedding model name to be provided!")
		if (embeddingDimension is None):
			raise ValueError("MCLabs Wiki Embedder requires embedding dimension to be provided!")
		self.client: genai.Client = client
		self.dataDirectory: str = dataDirectory
		self.embeddingModelName: str = embeddingModelName
		self.embeddingDimension: int = embeddingDimension

		# Embeddings folder path
		self.PATH_EMBEDDINGS = os.path.join(self.dataDirectory, 'embeddings/')
		os.makedirs(self.PATH_EMBEDDINGS, exist_ok=True)

		# MCL Wiki URL
		self.MCL_WIKI_API_URL = "https://labs-mc.com/w/api.php"

		# Make index and document list
		self.index = faiss.IndexFlatL2(self.embeddingDimension)
		self.documents = []

		# Log creation
		self.logger = MCL_Logger.setup_logger("MCL_API_Logger")
		self.logger.info(f"New WikiEmbedder instance created!")

	# Main function to fetch, chunk, embed, and index wiki pages
	def fetchAndEmbedWiki(self, batch_size=10, raw_weight=1.0):

		# Initialize the apcontinue parameter for pagination
		apcontinue = None
		while True:
			
			# Get the next batch of page titles
			titles, apcontinue = self._getPageTitlesBatch(apcontinue, batch_size=10)

			# Break the loop if no titles are returned
			if not titles:
				break
			
			# Get content chunks for all pages in the batch
			allChunks = {}
			allEmbeddings = {}
			for title, content in zip(titles, self._fetchPageContentBatch(titles)):

				# Get chunks and embeddings
				allChunks[title] = self._chunkWikiPage(content)

				# Embed all chunks in the batch
				allEmbeddings[title] = self.embedChunks(allChunks[title])

			# Flatten embeddings for FAISS
			flatEmbeddings = [chunkEmbedding for pageEmbeddings in allEmbeddings.values() for chunkEmbedding in pageEmbeddings]
			embeddingsMatrix = np.vstack(flatEmbeddings).astype('float32')
			faiss.normalize_L2(embeddingsMatrix)
			self.index.add(embeddingsMatrix)  # type: ignore

			# Flatten chunks into documents with titles
			for pageTitle, chunkList in allChunks.items():
				for chunkText in chunkList:
					self.documents.append(
						RagDocument(
							title=pageTitle,
							content=chunkText,
							source=DocumentSource.WIKI,
							date=None,
							scale=raw_weight
						)
					)

			self.logger.info(f"Processed batch of {len(titles)} pages")

			# Break the loop if there are no more pages to fetch
			if not apcontinue:
				break

		self.logger.info(f"FAISS index has {self.index.ntotal} vectors")

	# Function to load, chunk, embed, and index help questions
	def fetchAndEmbedHelpQuestions(self, helpQuestionsFilePath: str, raw_weight=1.0):

		# Load help questions from file
		with open(helpQuestionsFilePath, "r") as helpQuestionFile:
			helpQuestionList = [line.strip() for line in helpQuestionFile]

		# Every two rows -> Q&A  pair -> combine into single chunk
		helpQuestionPairs = []
		for line in helpQuestionList:

			# Remove the log timestamp if present
			try:
				if line.startswith("[") and "] " in line:
					line = line.split("] ", 1)[1]

				# Get the question, answer, and timestamp
				doctime, question, answer = line.split("|||")
			except Exception as e:
				self.logger.error(f"Exception `{e}` occured while parsing help question line: {line}. Skipping!")
				continue
			
			# Determine if the doc has old unix (no period) or new unix (has period)
			try:
				if "." in doctime:
					# New format with period, in common unix timestamp format
					doc_timestamp = float(doctime)
				else:
					doc_timestamp = float(doctime) / 1000.0
			except Exception as e:
				self.logger.error(f"Exception `{e}` occured while parsing timestamp in help question line: {line}. Skipping!")
				continue

			# Remove the answer prefix if present
			helpQuestionPairs.append((doc_timestamp, question, answer))

		# Turn Q&A pairs into chunks with a readable date header
		chunks = []
		for t, q, a in helpQuestionPairs:
			readable_date = datetime.datetime.fromtimestamp(t).date().isoformat()
			chunks.append(f"T: {readable_date}\nQ: {q}\nA: {a}")

		# Embed the chunks in batches of 100 (gemini limit)
		embeddings = []
		for i in range(0, len(chunks), 100):
			embeddings.extend(self.embedChunks(chunks[i:i+100]))

		# Add to FAISS index
		embeddingsMatrix = np.vstack(embeddings).astype('float32')
		faiss.normalize_L2(embeddingsMatrix)
		self.index.add(embeddingsMatrix)  # type: ignore

		# Add to documents with title "Help Question", source HelpQuestion, and date
		for (t, q, a), chunk in zip(helpQuestionPairs, chunks):
			self.documents.append(
				RagDocument(
					title="Help Question",
					content=chunk,
					source=DocumentSource.HELP_QUESTION,
					date=t,
					scale=raw_weight
				)
			)
		self.logger.info(f"Added {len(chunks)} help questions to the index and documents!")

	# Save the FAISS index and documents to disk
	def saveIndexAndDocuments(self):
		# Save the index and documents for later use
		faiss.write_index(self.index, f"{self.PATH_EMBEDDINGS}wiki.index")
		
		# Save documents to JSON
		json_path = f"{self.PATH_EMBEDDINGS}wiki_docs.json"
		with open(json_path, "w", encoding="utf-8") as f:
			json.dump([doc.model_dump() for doc in self.documents], f, indent=2)
		self.logger.info(f"Saved index and {len(self.documents)} documents to disk as JSON")

	# Embed text chunk using Gemini API
	def embedChunks(self, chunks: list[str]) -> list[np.ndarray]:
		
		# Make embedding request and return as numpy array
		response = self.client.models.embed_content(
			model=self.embeddingModelName,
			contents=chunks,
			config=types.EmbedContentConfig(
				task_type="RETRIEVAL_DOCUMENT",
				output_dimensionality=self.embeddingDimension
			)
		)
		if not response.embeddings:
			return []
		return [np.array(documentEmbedding.values) for documentEmbedding in response.embeddings]

	# Get a batch of page titles
	def _getPageTitlesBatch(self, apcontinue=None, batch_size=10):
		
		# Define parameters and make API request
		params = {
			"action": "query",
			"list": "allpages",
			"format": "json",
			"aplimit": batch_size,
		}
		if apcontinue:
			params["apcontinue"] = apcontinue
		request = requests.get(self.MCL_WIKI_API_URL, params=params).json()

		# Extract titles and continuation token then return
		titles = [page["title"] for page in request["query"]["allpages"]]
		next_continue = request.get("continue", {}).get("apcontinue")
		return titles, next_continue

	# Fetch and parse a wiki page to extract text content
	def _fetchPageContentBatch(self, titles: list[str]) -> list[str]:
		
		# Make list to hold page contents
		contents = []

		# Define parameters and make API requests
		for title in titles:
			params = {
				"action": "parse",
				"page": title,
				"prop": "text",
				"format": "json"
			}
			response = requests.get(self.MCL_WIKI_API_URL, params=params).json()

			# Parse HTML content to extract text
			contents.append(BeautifulSoup(markup=response["parse"]["text"]["*"], features="html.parser").get_text())
			
		# Return list of page contents
		return contents

	# Chunk text into smaller pieces for processing
	def _chunkWikiPage(self, text, chunk_size=500, overlap=50):
		
		# Split text into words and yield chunks with overlap
		chunks = []
		words = text.split()
		for i in range(0, len(words), chunk_size - overlap):
			chunks.append(" ".join(words[i:i+chunk_size]))
		return chunks