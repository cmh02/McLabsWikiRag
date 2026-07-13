# MCLabs Wiki RAG System Documentation

Welcome to the technical documentation for the MCLabs Retrieval-Augmented Generation (RAG) system. This document explains the architecture, components, persistent storage model, scaling configuration, scoring modifiers, and prompt guidelines that power automated wiki queries and support ticket answering.

---

## Table of Contents
1. [System Architecture](#1-system-architecture)
2. [Data Representation (`RagDocument`)](#2-data-representation-ragdocument)
3. [Prework Stage: Data Ingestion & Indexing (`MCL_WikiEmbedder`)](#3-prework-stage-data-ingestion--indexing-mcl_wikiembedder)
   - [Wiki Article Ingestion](#wiki-article-ingestion)
   - [Support FAQ Ingestion](#support-faq-ingestion)
   - [Chunking Strategy](#chunking-strategy)
   - [Generating Vector Embeddings](#generating-vector-embeddings)
   - [Adding a New Data Type](#adding-a-new-data-type)
4. [Storage, Persistence & Runtime Loading (`MCL_WikiDocLoader`)](#4-storage-persistence--runtime-loading-mcl_wikidocloader)
   - [Persistence Files](#persistence-files)
   - [Persistent Volume Configuration](#persistent-volume-configuration)
   - [Runtime Load Flow](#runtime-load-flow)
5. [Retrieval & Scoring Modifiers (`MCL_WikiRag`)](#5-retrieval--scoring-modifiers-mcl_wikirag)
   - [Query Processing](#query-processing)
   - [Math-Based Scoring & Heuristics](#math-based-scoring--heuristics)
     - [Raw Score Modifier](#raw-score-modifier)
     - [Source Scale Boost](#source-scale-boost)
     - [Recency Decay (Half-Life)](#recency-decay-half-life)
     - [Season Boost](#season-boost)
   - [Resorting & Selection](#resorting--selection)
6. [Generation & Guardrails](#6-generation--guardrails)
   - [Prompt Configuration](#prompt-configuration)
   - [Conflict Resolution & Translations](#conflict-resolution--translations)
7. [Configuration & Environment Variables](#7-configuration--environment-variables)
8. [Scaling & Deployment Setup](#8-scaling--deployment-setup)
   - [Stateless Serving Dynos](#stateless-serving-dynos)
   - [Rolling Deployments & Session Tracking](#rolling-deployments--session-tracking)

---

## 1. System Architecture

The RAG system implements a decoupled pipeline consisting of a **prework ingestion stage** and a **runtime serving stage**. The prework stage extracts wiki articles and support QA logs, creates vector representations using Google Gemini, and builds a FAISS index. The serving stage loads these structures into memory to retrieve context for user queries, applying scoring heuristics to emphasize recency, source credibility, and seasonal relevance.

```mermaid
graph TD
    subgraph Ingestion Phase (Prework Stage)
        W[MCL Wiki API] -->|Parse & Chunk| WC[Wiki Chunks]
        F[Help QA File/DB Dumps] -->|Parse & Map Date| FC[FAQ Chunks]
        WC -->|text-embedding-004| WE[Document Vectors]
        FC -->|text-embedding-004| FE[Document Vectors]
        WE & FE -->|normalize L2| FAISS[FAISS IndexFlatIP]
        FAISS -->|Save to disk| FAISSD[wiki.index]
        WC & FC -->|Serialize docs| JSON[wiki_docs.json]
    end

    subgraph Query / Runtime Phase (Serving Stage)
        U[User Query / Ticket Message] -->|text-embedding-001| QV[Query Vector]
        QV -->|normalize L2| FAISSSearch[FAISS Search top 2*K]
        FAISSD --> FAISSSearch
        JSON -->|Pydantic model load| DocLoader[DocLoader Memory]
        DocLoader --> FAISSSearch
        FAISSSearch -->|Raw Matches| SM[Score Modifier Engine]
        
        SM -->|Apply Source Scale| SM
        SM -->|Apply Recency Decay| SM
        SM -->|Apply Season Boost| SM
        
        SM -->|Sort & Slice Top K| Context[Context Text]
        Context & U --> LLM[Gemini 2.5/3.5]
        LLM -->|Generate Answer| Answer[Final Response / Ticket Message]
    end
```

---

## 2. Data Representation (`RagDocument`)

To ensure type-safety and structured data transfer across all stages of RAG, the system utilizes a unified Pydantic model defined in [document.py](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/rag/document.py).

### DocumentSource Enum
An enum that classifies the document origin:
* `WIKI` (`"Wiki"`): Articles harvested from the MediaWiki Action API.
* `HELP_QUESTION` (`"HelpQuestion"`): Support Q&A logs/database entries.

### RagDocument Model
```python
class RagDocument(BaseModel):
    title: Optional[str] = None      # Document title (e.g., wiki page title)
    content: str                     # Main text block/content of the chunk
    source: DocumentSource           # Document origin (Wiki vs HelpQuestion)
    date: Optional[float] = None     # Unix timestamp representing creation date
    scale: float = 1.0               # Ingestion-level raw weight scale
```

---

## 3. Prework Stage: Data Ingestion & Indexing (`MCL_WikiEmbedder`)

The [MCL_WikiEmbedder](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/rag/docfetch.py#L41) class is responsible for harvesting source text, transforming it into vector embeddings, and building the FAISS vector database.

### Wiki Article Ingestion
* **Source**: MediaWiki Action API at `https://labs-mc.com/w/api.php`.
* **API Flow**:
  1. Retrieves all page titles using `action=query` and `list=allpages` in batches.
  2. Uses continuation queries via the `apcontinue` parameter to iterate through the entire wiki.
  3. Fetches the page markup for each title using `action=parse` and extracts the HTML block `response["parse"]["text"]["*"]`.
* **Parsing**: Cleans raw HTML using `BeautifulSoup` to strip tags and extract clear text.

### Support FAQ Ingestion
* **Source**: Raw text logs containing Q&A entries in the format: `[Timestamp] time|||question|||answer` or `time|||question|||answer`.
* **Timestamp Normalization**: Detects whether the timestamp is in milliseconds (old format) or standard Unix epoch seconds (new format) and standardizes it to seconds.
* **Chunk Formatting**: Formats question-answer pairs using a template prefix:
  ```
  T: <ISO-Date>
  Q: <Question>
  A: <Answer>
  ```

### Chunking Strategy
* **Sliding Window**: The `_chunkWikiPage` method splits raw text into words by space and compiles sliding slices:
  * **Chunk Size**: 500 words
  * **Overlap**: 50 words (retains semantic context at page boundaries)

### Generating Vector Embeddings
* **Embedding Model**: `text-embedding-004` (via the Google GenAI SDK).
* **Batching**: Inputs are processed in batches (max 100 chunks per request) to comply with API rate limits.
* **Normalization**: The embedding vectors are stacked and normalized using `faiss.normalize_L2` before being added to a `faiss.IndexFlatIP(768)` index. Since the vectors are L2-normalized, the inner product calculations act as exact cosine similarity.

### Adding a New Data Type
To add a new data type (e.g., game manuals, announcements) to the prework stage:
1. **Define the Parser**: Retrieve raw strings from the source (API, DB, or file).
2. **Format and Structure**: Create your text chunk and extract metadata (date, title, source).
3. **Chunk**: Apply the sliding window helper `_chunkWikiPage` to break down large texts.
4. **Generate Embeddings**: Batch the list of chunks and call `embedChunks(chunks)`.
5. **Normalize and Add to FAISS Index**:
   ```python
   embeddingsMatrix = np.vstack(embeddings).astype('float32')
   faiss.normalize_L2(embeddingsMatrix)
   self.index.add(embeddingsMatrix)
   ```
6. **Extend Documents Metadata**: Append matching Pydantic `RagDocument` objects to `self.documents`:
   ```python
   self.documents.append(
       RagDocument(
           title="New Source Document", 
           content=chunk_text, 
           source=DocumentSource.NEW_SOURCE, 
           date=unix_timestamp,
           scale=weight
       )
   )
   ```
7. **Write to Disk**: Run `saveIndexAndDocuments()` to overwrite the cached files in the embeddings folder.

---

## 4. Storage, Persistence & Runtime Loading (`MCL_WikiDocLoader`)

To optimize production performance and decouple the serving layer from ingestion APIs, the serving layer loads pre-computed index files from disk using [MCL_WikiDocLoader](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/rag/docloader.py#L13).

### Persistence Files
When the preprocessing stage finishes, it writes the vector store and document registry into the `embeddings/` directory:
1. **`embeddings/wiki.index`**: A FAISS binary file storing normalized document vectors.
2. **`embeddings/wiki_docs.json`**: A serialized JSON file storing the list of document metadata dictionaries (previously saved as a Python pickle file `wiki_docs.pkl`).

### Persistent Volume Configuration
In cloud environments like Railway, the `embeddings/` directory is mapped to a persistent volume. Its base path is specified via the `RAILWAY_DATA_DIRECTORY` environment variable, ensuring the files persist across builds, redeploys, and container restarts.

### Runtime Load Flow
* During application startup in [api.py](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/api.py), `app.state.InstanceWikiDocLoader` is initialized.
* `MCL_WikiDocLoader.loadIndexAndDocuments()` is called, which:
  1. Reads the FAISS index from disk via `faiss.read_index()`.
  2. Parses and validates the JSON metadata registry into a list of Pydantic `RagDocument` models using `RagDocument.model_validate(doc)`.
* The loader instance is then injected into the [MCL_WikiRag](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/rag/rag.py#L37) constructor.

---

## 5. Retrieval & Scoring Modifiers (`MCL_WikiRag`)

The `MCL_WikiRag` class manages user queries, similarity searches, and custom score/distance modifications.

### Query Processing
1. The incoming user query is embedded using Google Gemini's `text-embedding-001` (Task type: `RETRIEVAL_QUERY`).
2. The vector is normalized with `faiss.normalize_L2`.
3. A similarity search is performed on the FAISS index to retrieve the top `K * 2` nearest neighbors (giving buffer room for score modifiers).

### Math-Based Scoring & Heuristics
The raw similarity score (inner product) returned by `faiss.IndexFlatIP` is modified dynamically using environment-driven hyperparameters:

$$Score_{final} = Score_{raw} \times Scale_{doc} \times Scale_{source} \times Scale_{recency} \times Scale_{season}$$

#### Raw Score Modifier
* **`Scale_doc`**: Derived from `doc.scale` (set during ingestion, defaults to `1.0`).

#### Source Scale Boost
To adjust relevance based on document origin:
* **`Scale_source`**:
  * If `doc.source == DocumentSource.WIKI`: Uses `RAG_HP_SOURCESCALE_WIKI`.
  * If `doc.source == DocumentSource.HELP_QUESTION`: Uses `RAG_HP_SOURCESCALE_FAQ`.

#### Recency Decay (Half-Life)
Older help questions might contain outdated information. To counter this, documents with a valid timestamp decay exponentially with document age:

$$Scale_{recency} = e^{-\lambda \cdot AgeDays}$$

Where $\lambda$ represents the decay constant defined by the half-life parameter:

$$\lambda = \frac{\ln(2)}{RAG\_HP\_RECENCYHALFLIFE}$$

#### Season Boost
To prioritize support questions originating from the current map season, a season boost is applied to documents created on or after May 1st of the current calendar year:

$$Scale_{season} = RAG\_HP\_SEASONBOOST$$

### Resorting & Selection
Once modifiers are applied, the results are sorted in **descending** order of their final modified score, and the top `K` chunks are selected as context for the LLM. 
> [!NOTE]
> Since the FAISS query returns inner product values (representing cosine similarity on our L2-normalized vectors), sorting in descending order of the final modified scores correctly ranks the most similar and highly-boosted documents at the top of the returned context.

---

## 6. Generation & Guardrails

The LLM generation pipeline leverages Google Gemini with detailed system rules and semantic translations specific to the server ecosystem.

### Prompt Configuration
The prompt embeds the context chunks and the user's question, applying the following strict guidelines:
* **Strict Classification & Fallback ("UNANSWERABLE")**:
  - If the user query does not contain an actual question, inquiry, or request for information (e.g., greetings, statements, thank-yous), the model must output exactly `UNANSWERABLE`.
  - If the context does not contain enough information or if the answer is unknown, the model must output exactly `UNANSWERABLE`.
  - If the model returns `UNANSWERABLE` for support tickets, the system skips appending an automated response, letting staff handle the ticket manually.
* **Medium Length**: The model is instructed to provide a medium-length answer with details while being concise.
* **Recency Preference**: Prefer FAQ chunks if present. If multiple context chunks conflict, the most recent chunk is preferred.

### Conflict Resolution & Translations
* **Chemicals**: Never use the word "chemicals"; always refer to them as "chems".
* **Worlds**: Translate "Town world" to "Overworld" and "Company world" to "Underworld".
* **Factions**: Ignore any context regarding "factions", `/f` commands, or the "raid world".

---

## 7. Configuration & Environment Variables

All parameters are loaded from environment variables. If any are missing or invalid, the initialization of RAG components will raise a `ValueError`.

| Variable | Type | Description |
|---|---|---|
| `GOOGLE_GEMINI_API_KEY` | String | Developer access token for Google Gemini APIs (Required). |
| `GOOGLE_GEMINI_MODEL` | String | Generative text model to use (e.g., `gemini-2.5-flash`) (Required). |
| `RAILWAY_DATA_DIRECTORY` | String | Path to the persistent storage directory where `embeddings/` are stored (Required). |
| `RAG_HP_SOURCESCALE_WIKI` | Float | Scaling multiplier applied to Wiki articles (Required). |
| `RAG_HP_SOURCESCALE_FAQ` | Float | Scaling multiplier applied to Help Question/FAQ chunks (Required). |
| `RAG_HP_RECENCYHALFLIFE` | Float | Decay half-life in days for FAQs (Required). |
| `RAG_HP_SEASONBOOST` | Float | Boost multiplier for current-season FAQs (since May 1st) (Required). |

---

## 8. Scaling & Deployment Setup

The RAG system is engineered for scale, reliability, and smooth rolling updates in production environments.

### Stateless Serving Dynos
Because building vector indices is resource-intensive and requires API access to generate embeddings, the **Serving Layer** and the **Ingestion Layer** are separated:
* **Ingestion (Prework)**: Run as a one-off administration command or scheduled job. It generates the index and saves the JSON registry to `RAILWAY_DATA_DIRECTORY`.
* **Serving (FastAPI)**: Serving dynos are stateless. At startup, they load the pre-computed FAISS index and JSON documents directly into memory from the persistent volume mount. This allows the API to serve retrieval requests with sub-millisecond local calculations, with zero dependency on the MediaWiki API or raw document chunking.

### Rolling Deployments & Session Tracking
To prevent alert spam and track active deployments during horizontal scaling and rolling restarts:
1. On startup, each FastAPI server generates a unique UUID `session_id` and registers it in MongoDB.
2. The active session is registered under the `"backend"` service name. The newest starting instance automatically takes over the active session slot.
3. During container shutdown (e.g., when a scale-down or rolling deployment terminates older dynos), the shutting-down instance queries MongoDB:
   - If its `session_id` is still the active session, it notifies the administrative Discord channel of the shutdown.
   - If its `session_id` is not active (because a newer instance took over), it shuts down silently, avoiding redundant notifications.
