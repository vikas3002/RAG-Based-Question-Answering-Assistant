#  RAG-Based Question Answering Assistant

A Flask backend that answers questions **strictly from a provided PDF** using Retrieval-Augmented Generation (RAG). The document is cleaned, split into heading-aware chunks, embedded locally, and stored in ChromaDB. Only the retrieved chunks are sent to the LLM (Groq, OpenAI-compatible API).

If the answer is not in the document, the API returns exactly:

> The answer is not available in the provided document.

## Features

- `POST /ask` API with input validation and graceful error handling
- PDF cleaning: page headers removed, hyphenated line breaks fixed, bullets normalised
- Heading-aware chunking, so a heading, its explanation and its list stay together
- Persistent ChromaDB index with incremental re-indexing when the file changes
- Similarity threshold: out-of-scope questions are refused without calling the LLM

## How it works

```
docs/PDF -> clean -> split by headings -> chunk -> embed (bge-small-en-v1.5) -> ChromaDB

POST /ask -> validate -> embed question -> top-k chunks -> threshold filter
          -> prompt + retrieved chunks only -> Groq LLM -> answer
          (no relevant chunk -> "The answer is not available in the provided document.")
```

## Project structure

```
├── app.py              # Flask app: /ask (main API), /chat and /clear (web UI)
├── rag_store.py        # Cleaning, chunking, embeddings, ChromaDB retrieval
├── requirements.txt
├── .env.example        # Template for .env
├── docs/               # Put the PDF here
├── templates/ and static/   # Optional web UI
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
```

Add your key to `.env`:

```
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Place the PDF in `docs/`, then run:

```bash
python app.py
```

The server starts at `http://127.0.0.1:5000`. The PDF is indexed at startup.

## API

`POST /ask`

Request:

```json
{ "question": "What is the importance of business communication?" }
```

Response:

```json
{ "answer": "..." }
```

| Case | Status | Body |
|---|---|---|
| Invalid JSON, or empty / missing / non-string `question` | 400 | `{"error": "..."}` |
| System error (LLM, retrieval, etc.) | 500 | `{"error": "Internal server error"}` |

```bash
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the objectives of business communication?"}'
```

## Assumptions

- Answers come only from the PDF in `docs/`; no outside knowledge is used.
- The PDF has a text layer (scanned PDFs would need OCR).
- Embeddings are generated locally; only the LLM needs an API key.
- Chunks with cosine similarity below 0.3 are ignored (`min_score` in `app.py`).
- Chunk size is 1500 characters, so short sections stay in one chunk.
- Heading and page-header patterns in `rag_store.py` are tuned to the provided PDF.
- The index is built at startup, so a changed PDF needs a restart. To rebuild from scratch, delete `chroma_db/`.

## Configuration

| Setting | Where | Purpose |
|---|---|---|
| `GROQ_API_KEY`, `GROQ_MODEL` | `.env` | LLM access |
| `min_score`, `k` | `retrieve()` in `app.py` | Similarity cutoff and number of chunks used |
| `size`, `overlap` | `chunk_text()` in `rag_store.py` | Chunk size and overlap |
| `CHUNK_VERSION` | `rag_store.py` | Change after editing cleaning or chunking so the PDF re-indexes |

## Limitations

- Scanned or image-only PDFs are not supported without OCR.
- Heading detection is rule-based and tuned to the provided PDF.
- `/chat` (web UI) keeps one global history shared by all visitors; `/ask` is stateless.
