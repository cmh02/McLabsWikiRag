'''
MCLabs Wiki RAG - Document Fetch and Embedding

Author: Chris Hinkson @cmh02
'''

'''
MODULE IMPORTS
'''

# System
import os
import pickle
import datetime

# Vector Database
import faiss

# Data Handling
import numpy as np

# Web-Related
import requests
from bs4 import BeautifulSoup

# Google API
from google import genai
from google.genai import types

'''
WIKI EMBEDDER CLASS

This class will handle fetching, parsing, chunking, and embedding all of the MCL Wiki pages.
'''

class MCL_WikiEmbedder():

	# Class Constructor
	def __init__(self, client: genai.Client=None):

		# Current file and directory paths
		self.CURRENT_FILE_PATH = os.path.abspath(__file__)
		self.CURRENT_DIR = os.path.dirname(self.CURRENT_FILE_PATH)
		self.ROOT_DIR = os.path.dirname(self.CURRENT_DIR)

		# Embeddings folder path
		self.PATH_EMBEDDINGS = os.path.join(self.ROOT_DIR, 'embeddings/')
		os.makedirs(self.PATH_EMBEDDINGS, exist_ok=True)

		# MCL Wiki URL
		self.MCL_WIKI_API_URL = "https://labs-mc.com/w/api.php"

		# Make client if not provided
		if client is None:
			self.client = genai.Client(api_key=os.getenv('GOOGLE_GEMINI_API_KEY'))
		else:
			self.client = client

		# Make index and document list
		self.index = faiss.IndexFlatL2(768)
		self.documents = []

		# Print
		print(f"New WikiEmbedder instance created!")

	# Main function to fetch, chunk, embed, and index wiki pages
	def fetchAndEmbedWiki(self, batch_size=10):

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
			self.index.add(embeddingsMatrix)

			# Flatten chunks into documents with titles
			self.documents.extend([
				{"title": pageTitle, "content": chunkText, "source": "playerwiki", "date": "N/A"}
				for pageTitle, chunkList in allChunks.items()
				for chunkText in chunkList
			])

			print(f"Processed batch of {len(titles)} pages")

			# Break the loop if there are no more pages to fetch
			if not apcontinue:
				break

		print(f"FAISS index has {self.index.ntotal} vectors")

	# Function to load, chunk, embed, and index help questions
	def fetchAndEmbedHelpQuestions(self, helpQuestionsFilePath: str):

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
				print(f"Exception `{e}` occured while parsing help question line: {line}. Skipping!")
				continue
			
			# Determine if the doc has old unix (no period) or new unix (has period)
			try:
				if "." in doctime:
					# New format with period, in common unix timestamp format
					doctime = float(doctime)
				else:
					doctime = float(doctime) / 1000.0
			except Exception as e:
				print(f"Exception `{e}` occured while parsing timestamp in help question line: {line}. Skipping!")
				continue

			# Convert to ISO date
			doctime = datetime.datetime.fromtimestamp(doctime).date().isoformat()

			# Remove the answer prefix if present
			helpQuestionPairs.append((doctime, question, answer))

		# Turn Q&A pairs into chunks
		chunks = [f"T: {t}\nQ: {q}\nA: {a}" for t, q, a in helpQuestionPairs]

		# Embed the chunks in batches of 100 (gemini limit)
		embeddings = []
		for i in range(0, len(chunks), 100):
			embeddings.extend(self.embedChunks(chunks[i:i+100]))

		# Add to FAISS index
		embeddingsMatrix = np.vstack(embeddings).astype('float32')
		faiss.normalize_L2(embeddingsMatrix)
		self.index.add(embeddingsMatrix)

		# Add to documents with title "Help Question", source "helpQA", and date
		self.documents.extend([{"title": "Help Question", "content": chunk, "source": "helpQA", "date": t} for t, chunk in zip([t for t, q, a in helpQuestionPairs], chunks)])
		print(f"Added {len(chunks)} help questions to the index and documents!")

	# Save the FAISS index and documents to disk
	def saveIndexAndDocuments(self):
		# Save the index and documents for later use
		faiss.write_index(self.index, f"{self.PATH_EMBEDDINGS}wiki.index")
		with open(f"{self.PATH_EMBEDDINGS}wiki_docs.pkl", "wb") as f:
			pickle.dump(self.documents, f)
		print(f"Saved index and {len(self.documents)} documents to disk")

	# Load the FAISS index and documents from disk
	def loadIndexAndDocuments(self):
		# Load the index and documents for later use
		self.index = faiss.read_index(f"{self.PATH_EMBEDDINGS}wiki.index")
		with open(f"{self.PATH_EMBEDDINGS}wiki_docs.pkl", "rb") as f:
			self.documents = pickle.load(f)
		print(f"Loaded index and {len(self.documents)} documents from disk")

	# Embed text chunk using Gemini API
	def embedChunks(self, chunks: list[str]) -> list[np.ndarray]:
		
		# Make embedding request and return as numpy array
		response = self.client.models.embed_content(
			model="text-embedding-004",
			contents=chunks,
			config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
		)
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