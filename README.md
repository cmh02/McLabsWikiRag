# MCLabs Wiki RAG & Help System

Welcome to the **MCLabs Wiki RAG & Help System**! 

This repository coordinates a multi-platform support ecosystem for the [MCLabs Minecraft Server](https://labs-mc.com/), integrating a custom FastAPI/Gunicorn backend service, a Retrieval-Augmented Generation (RAG) pipeline powered by Google Gemini, a cross-platform Discord ticket bot, and in-game Minecraft Skript integrations.

---

## 🗺️ Project Architecture Overview

The system is split into three main modules:

1. **Backend Service ([src/](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src))**: Exposes REST endpoints for querying RAG, tracking active servers, managing help tickets, and synchronizing player chat states.
2. **Discord Bot ([discordbot/](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/discordbot))**: A Discord application hosting slash commands, interactive buttons/modals, and real-time chat relays mapped to active in-game player tickets.
3. **Common Utilities ([mcl_common/](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/mcl_common))**: A shared repository namespace providing standardized logging, database models, database handlers (MongoDB), utility classes, and a central Pydantic-powered settings system.

For a detailed visual guide to the system's architecture and runtime query processes, refer to the [System Architecture Diagram](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/rag/RAG.md#1-system-architecture).

---

## 🤖 AI In the Help System

The core feature of this platform is the automated answering of help tickets using a highly targeted Retrieval-Augmented Generation (RAG) pipeline.

### 1. Ingestion and Indexing (Prework)
Data is harvested from two main sources:
* **MCLabs Official Wiki**: Scraped using the MediaWiki API. Chunks are generated using a 500-word sliding window with a 50-word overlap.
* **Help Ticket Q&A Dumps**: Parsed from database logs, where each question-answer pair is kept as a discrete semantic chunk.

These chunks are embedded using Google Gemini's `text-embedding-004` and loaded into a normalized **FAISS L2 flat vector index** (`wiki.index`) along with a JSON-serialized document lookup registry (`wiki_docs.json`).

### 2. Retrieval and Scoring Heuristics
When a player asks a question, the backend retrieves candidate chunks and modifies the raw Euclidean distance scores using custom weighting scales defined by RAG hyperparameters:
* **Source Scale Boosts**: Elevates or reduces the relevance of a chunk depending on whether it originated from the Wiki or FAQ logs.
* **Recency Decay**: Automatically decays the score of older Q&A entries exponentially based on a configured half-life (in days) to prevent outdated help information.
* **Season Boost**: Prioritizes support questions from the current active map season.

For the math formulas and code implementation of these filters, read the [Retrieval & Scoring Modifiers Documentation](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/rag/RAG.md#5-retrieval--scoring-modifiers-mcl_wikirag).

### 3. Generative Replying & "UNANSWERABLE" Guardrails
When a ticket is created, the system triggers the RAG query pipeline asynchronously via [_processRagResponseWorkflow](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/internal/helpmanager.py#L323).
* **First Message Automated Answers**: The system only intercepts and replies automatically to the **first message** in a ticket. This ensures immediate feedback for common queries without interfering with ongoing human staff conversations.
* **Strict Classification & Fallback ("UNANSWERABLE")**: The prompt instructions force the LLM to output exactly `UNANSWERABLE` if the query is a greeting, statement, thank-you, or if the retrieved RAG context has insufficient information.
* **No Spam Routing**: If the RAG engine returns `UNANSWERABLE`, the backend silently drops the automatic reply, routing the ticket directly to manual staff queues without sending spam to the player.

---

## 🎮 User-Facing Features

### 1. In-Game Ticket Support (Minecraft Server)
Players on the Minecraft server can use `/ticket` or support commands configured through the Minecraft [skript/](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/skript) system. 
* **Reflection-Based Requests**: Network communications are handled asynchronously via [mclwikirag.sk](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/skript/mclwikirag.sk) using `skript-reflect` to interface directly with Java HTTP libraries.
* **AI Responses**: If the question matches indexed documentation, the AI (`WikiGPT`) directly answers the player in-game.

### 2. Discord Ticket Support System (`/ask`)
Members can trigger support threads from Discord. The complete flow is documented in the [Discord Bot README](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/discordbot/README.md):
* **Pop-Up Modals**: Running `/ask` prompts a modal for typing questions.
* **Dedicated Support Threads**: Submitting the modal spawns a public channel thread named `🎫-ticket-[ID]`.
* **Persistent Status Cards**: Includes dynamic buttons (`Claim`, `Unclaim`, `Feedback`, `Close`) that remain functional across bot restarts using persistent views.
* **In-Game Chat Relay**: A real-time WebSocket/REST bridge relays Discord thread messages to the player if they are online in Minecraft, and relays the player's in-game messages back to the Discord thread.

---

## ⚙️ Configuration & Environment Variables

Configuration is centralized in [mcl_common/config.py](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/mcl_common/config.py) using `pydantic-settings`. 

The global config is declared in the [Settings](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/mcl_common/config.py#L4) Pydantic model, which automatically reads and validates values from the OS environment variables or local `.env` files.

### Common Config Variables

| Environment Alias | Pydantic Field | Description |
|---|---|---|
| `GOOGLE_GEMINI_API_KEY` | `google_gemini_api_key` | Developer access token for Gemini API |
| `GOOGLE_GEMINI_MODEL` | `google_gemini_model` | Generative LLM to use (e.g. `gemini-2.5-flash`) |
| `GOOGLE_EMBEDDING_MODEL` | `google_embedding_model` | Model name for vector embeddings (`text-embedding-004`) |
| `MCL_MONGO_CONNECTION_STRING` | `mcl_mongo_connection_string` | URI for the MongoDB server |
| `DISCORD_BOT_TOKEN` | `discord_bot_token` | Token for the Discord bot client |
| `DISCORD_TICKET_CHANNEL_ID` | `discord_ticket_channel_id` | Channel ID where bot threads are created |
| `DISCORD_OPEN_CHANNEL_ID` | `discord_open_channel_id` | Channel ID where the persistent ticket creation button/embed is kept |
| `RAILWAY_API_DOMAIN` | `railway_api_domain` | The deployed backend API endpoint domain |
| `RAG_HP_SOURCESCALE_WIKI` | `rag_hp_sourcescale_wiki` | Weight scaling factor for Wiki sources |
| `RAG_HP_SOURCESCALE_FAQ` | `rag_hp_sourcescale_faq` | Weight scaling factor for FAQ/Support sources |
| `RAG_HP_RECENCYHALFLIFE` | `rag_hp_recencyhalflife` | Exponential decay half-life in days |
| `RAG_HP_SEASONBOOST` | `rag_hp_seasonboost` | Boost factor for current active map season |

To load the configuration in any Python module, import the global settings instance:
```python
from mcl_common.config import settings

# Access properties directly
mongo_uri = settings.mcl_mongo_connection_string
embedding_dim = settings.google_embedding_dimensions
```

---

## 📚 Technical Documentation Links

For deeper technical implementation details, reference the individual sub-module guides:

* 🧠 **[RAG System Details & Mathematical Heuristics (RAG.md)](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/src/rag/RAG.md)**: Detailed equations for recency decay, chunking overlapping parameters, database indexing, and scaling strategies.
* 🤖 **[Discord Bot commands and API (discordbot/README.md)](file:///Users/chrishinkson/Programming/Personal%20Projects/MCLabs/McLabsWikiGpt/discordbot/README.md)**: Detailed bot API endpoints, thread workflows, persistent UI buttons, and deployment rolling restarts.
