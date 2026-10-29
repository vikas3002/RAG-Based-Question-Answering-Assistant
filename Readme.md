# RAG Question-Answering API

A Flask backend that answers questions **only from a provided PDF** using Retrieval-Augmented Generation.

**Stack:** Flask, ChromaDB, `BAAI/bge-small-en-v1.5` (local embeddings), pypdf, Groq LLM (OpenAI-compatible client)

## How it works

1. The PDF in `docs/` is cleaned, split by headings into chunks, embedded, and stored in ChromaDB (indexed at startup).
2. A question is embedded and the top-k similar chunks are retrieved.
3. Only those chunks are sent to the LLM, which answers strictly from them.
4. If no chunk is relevant, the API returns: `The answer is not available in the provided document.`

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # add your GROQ_API_KEY
```

Put the PDF in the `docs/` folder, then run:

```bash
python app.py
```

## API

`POST /ask`

```json
{ "question": "What is the importance of business communication?" }
```

Response:

```json
{ "answer": "..." }
```

| Case | Status |
|---|---|
| Invalid JSON, or empty / missing / non-string `question` | 400 |
| System error (LLM, retrieval, etc.) | 500 |

```bash
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the objectives of business communication?"}'
```

## Assumptions

- Answers come only from the PDF in `docs/`; no outside knowledge is used.
- The PDF has a text layer (scanned PDFs would need OCR).
- Chunks scoring below 0.3 cosine similarity are ignored.
- Heading and page-header rules in `rag_store.py` are tuned to the provided PDF.
- The index is built at startup, so a changed PDF needs a restart.
