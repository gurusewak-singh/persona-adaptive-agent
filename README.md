# Persona Adaptive Customer Support Agent

An intelligent customer support system that classifies users by persona, tailors responses accordingly, and escalates critical issues to human agents — all powered by Google Gemini and a RAG pipeline built on ChromaDB.

---

## What This Project Does

This is a full-stack AI chatbot for Persona Adaptive Customer Support. When a customer sends a message:

1. The system first figures out **who** the customer is (frustrated user? technical expert? business executive?) using sentiment analysis.
2. Based on that persona, it picks a **tone-appropriate prompt** — empathetic for frustrated users, precise for technical folks, concise for executives.
3. It pulls **relevant context from a knowledge base** (stored in ChromaDB as vector embeddings) so the response is grounded in actual company documentation.
4. The agent's response itself determines whether **human escalation** is needed (data loss, security issues, legal risk, etc.) and flags it accordingly.
5. Everything — messages, sentiment scores, severity levels, escalation flags — gets **logged to PostgreSQL** for auditing and history.

The frontend is a Streamlit chat interface that talks to a FastAPI backend.

---

## Architecture

```
┌─────────────────────┐
│   Streamlit (app.py) │  ← Chat UI, session management
│   Port 8501          │
└────────┬────────────┘
         │ HTTP POST /chat (JSON body)
         ▼
┌─────────────────────┐
│   FastAPI (main.py)  │  ← API layer, JSON parsing, orchestration
│   Port 8000          │
└────────┬────────────┘
         │
    ┌────┴─────────────────────┐
    │                          │
    ▼                          ▼
┌──────────────┐     ┌─────────────────┐
│  Gemini LLM  │     │   ChromaDB      │
│  (model_     │     │   (vector store) │
│   client.py) │     │                 │
│              │     │  - KB embeddings │
│ - Sentiment  │     │  - Gemini embeds │
│   analysis   │     └─────────────────┘
│ - Response   │
│   generation │
└──────────────┘
         │
         ▼
┌──────────────────┐
│   PostgreSQL     │
│                  │
│  - queries table │
│    (chat history,│
│     sentiment,   │
│     escalation)  │
└──────────────────┘
```

### Request Flow (step by step)

```
Customer types message
        │
        ▼
Streamlit sends POST to FastAPI (/chat with session_id + query)
        │
        ▼
In parallel (asyncio.gather):
  ├─ Gemini classifies persona + sentiment  ──→  Parse JSON response
  ├─ ChromaDB fetches top-3 relevant KB chunks
  └─ PostgreSQL fetches recent conversation history
        │
        ▼
Save customer message to PostgreSQL (with sentiment score)
        │
        ▼
Pick persona-specific prompt template
        │
        ▼
Build final prompt with context + history + customer message
        │
        ▼
Gemini generates response (async)  ──→  Parse JSON response
        │
        ▼
Extract severity_level, requires_escalation, summary from response
        │
        ▼
Save agent response to PostgreSQL (with severity score + escalation flag)
        │
        ▼
If requires_escalation is true ──→ Return escalation response with summary
        │
        ▼ (if not escalated)
Return full JSON to Streamlit  ──→  Render in chat UI
```

---

## Project Structure

```
├── app.py                  # Streamlit frontend
├── main.py                 # FastAPI backend (API routes, orchestration)
├── db.py                   # Database layer (ChromaDB + PostgreSQL)
├── model_client.py         # Gemini model wrapper (async + streaming)
├── prompts.py              # All prompt templates
├── kb_preprocessing.py     # Knowledge base chunking script
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore rules
├── knowledge base/         # Raw .txt files for the KB
│   ├── account and authentication.txt
│   ├── API and developer documentation.txt
│   ├── billing and subscription.txt
│   ├── campaign and analytics.txt
│   ├── escalation policy.txt
│   └── platform performance and outages.txt
└── .env                    # Environment variables (not committed)
```

### File Breakdown

**`app.py`** — Streamlit chat UI. Generates UUID-based session IDs, renders chat bubbles with expandable metadata details, and calls the FastAPI backend via POST requests. Shows a warning banner and stops further rendering when escalation is triggered.

**`main.py`** — The brain. Receives customer queries via POST, runs sentiment analysis, context retrieval, and history fetch **concurrently** using `asyncio.gather` with `asyncio.to_thread`. Selects the right persona prompt, calls the LLM (async), parses the JSON response for severity and escalation signals, and logs everything to PostgreSQL.

**`db.py`** — Handles all database operations:

- ChromaDB: creating collections, adding documents with metadata, querying for relevant context
- PostgreSQL: saving and retrieving conversation history (with sentiment scores and escalation flags)
- Embedding: uses Gemini's `gemini-embedding-001` model to generate 1536-dim normalized vectors

**`model_client.py`** — Wrapper around the Gemini generative model (`gemini-3-flash-preview`). Three functions:

- `generate_chat_response` — async chat response generation using `generate_content_async`
- `get_customer_sentiment` — async sentiment classification using `generate_content_async`
- `generate_chat_response_stream` — synchronous streaming response via `generate_content(stream=True)`

**`prompts.py`** — All prompt templates live here. Includes:

- Sentiment classification prompt (outputs persona, sentiment score, anger level, confidence)
- Three persona-specific response prompts (frustrated customer, technical expert, business executive)
- A default fallback prompt
- A prompt map that routes persona names to their templates

Each response prompt enforces a strict 3-step escalation policy and outputs severity level, escalation flag, and conversation summary.

**`kb_preprocessing.py`** — Reads `.txt` files from the `knowledge base/` folder, tokenizes them (whitespace split), chunks them into 250-token pieces with 50-token overlap, and attaches metadata (title, chunk ID). Used for one-time ingestion into ChromaDB.

---

## Persona-Based Response System

The chatbot doesn't give everyone the same generic reply. It first classifies the customer:

| Persona               | Tone                                      | Example Trigger                                                        |
| --------------------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| `frustrated_customer` | Empathetic, reassuring, non-technical     | "I've been locked out for 3 days and nobody is helping!"               |
| `technical_expert`    | Precise, structured, root-cause focused   | "Getting a 502 on the /api/campaigns endpoint after the latest deploy" |
| `business_executive`  | Concise, outcome-focused, business impact | "What's the SLA guarantee if our campaign dashboard goes down?"        |

If the model can't confidently classify, a default prompt is used.

---

## Escalation Logic

Escalation is determined by the **agent's response**, not the initial sentiment classifier. The agent follows a strict 3-step policy defined in each persona prompt:

**Step 1:** Always attempt to resolve the issue using knowledge base context.

**Step 2:** If the customer is still unsatisfied, offer alternative solutions or ask clarifying questions.

**Step 3:** Only escalate if **both** conditions are met:
- The agent has already attempted to resolve the issue at least once in the conversation.
- **AND** one of these triggers is present:
  - Customer explicitly requests a human/supervisor/manager
  - Confirmed data loss, active security breach, legal risk, or system-wide outage
  - A refund that the agent cannot process

When escalation is triggered:

- The agent's response and a summary are saved with an escalation flag in PostgreSQL
- The API returns the response along with `escalated: true`, a summary, and the severity level
- The Streamlit UI shows a warning banner and stops further bot rendering for that turn

**Important:** Frustration, anger, or strong language alone is **never** a reason to escalate. The agent is designed to de-escalate.

---

## Knowledge Base & RAG Pipeline

The system uses Retrieval Augmented Generation so responses are grounded in actual company docs, not hallucinated.

**Ingestion (one-time):**

1. `kb_preprocessing.py` reads all `.txt` files from `knowledge base/`
2. Each file is split into 250-token chunks with 50-token overlap
3. Each chunk gets metadata: `title` (filename) and `chunk_id`
4. `db.py:add_doc()` stores chunks + metadata in ChromaDB (embeddings generated via Gemini's `gemini-embedding-001`)

**At query time:**

1. Customer message is sent to ChromaDB's `query()`
2. Top 3 most relevant chunks are returned
3. These chunks are injected into the prompt as `{context}` so the LLM's answer is based on real documentation

---

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL database with a `queries` table
- ChromaDB Cloud account
- Google AI API keys (one for Gemini generative model, one for embeddings)

### Environment Variables

Create a `.env` file:

```
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_EMBEDDINGS_API_KEY=your-embeddings-api-key

CHROMADB_API_KEY=your-chromadb-key
CHROMADB_TENANT=your-tenant
CHROMADB_NAME=your-database-name
CHROMADB_COLLECTION_NAME=your-collection-name

CHAT_DB_NAME=your-postgres-db
CHAT_DB_USER=your-postgres-user
CHAT_DB_PASSWORD=your-postgres-password
CHAT_DB_HOST=localhost
CHAT_DB_PORT=5432
```

### Database Setup

Run this in your PostgreSQL database:

```sql
CREATE TABLE queries (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    message TEXT,
    sentiment_score REAL,
    escalation BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Ingest Knowledge Base

Run once to chunk and store your KB docs in ChromaDB:

```bash
python db.py
```

### Run the App

Terminal 1 — start the API server:

```bash
uvicorn main:app --reload
```

Terminal 2 — start the Streamlit UI:

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser and start chatting.

---

## Tech Stack

| Component     | Technology                                              |
| ------------- | ------------------------------------------------------- |
| Frontend      | Streamlit                                               |
| Backend API   | FastAPI                                                 |
| LLM           | Google Gemini (`gemini-3-flash-preview`)                |
| Vector Store  | ChromaDB Cloud                                          |
| Relational DB | PostgreSQL (via psycopg2)                               |
| Embeddings    | Gemini Embedding Model (`gemini-embedding-001`, 1536-dim, normalized) |

---

## Limitations / Known Trade-offs

- Tokenization is whitespace-based (not tiktoken or sentencepiece) — good enough for chunking, not exact token counts.
- Sentiment classification and response generation rely on the LLM returning valid JSON every time. There's a regex fallback parser, but edge cases can still slip through.
- No authentication on the API — anyone who can reach port 8000 can call `/chat`.
- Session IDs are UUIDs — no real user auth or session persistence across browser refreshes (Streamlit state is ephemeral).
- The escalation is a one-way flag — there's no actual human agent handoff system, just a logged record and a UI banner.
- Streaming support (`generate_chat_response_stream`) is implemented in the model client but not yet wired into the API endpoint.
