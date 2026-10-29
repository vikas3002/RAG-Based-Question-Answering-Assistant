# RAG-Based Question Answering Assistant

A Flask backend that answers questions **strictly from a provided document** using Retrieval-Augmented Generation (RAG). The document is cleaned, split into heading-aware chunks, embedded with a local sentence-transformer model, and stored in a persistent ChromaDB index. At question time the most relevant chunks are retrieved and only those are passed to an LLM (served through Groq's OpenAI-compatible API).

If the answer is not in the document, the API returns exactly:

> The answer is not available in the provided document.

## Features

- Retrieval-Augmented Generation over local PDF, DOCX, TXT and Markdown files
- `POST /ask` API with input validation and graceful error handling
- PDF cleaning: page headers/footers removed, hyphenated line breaks re-joined, bullet glyphs normalised, whitespace collapsed
- Heading-aware PDF chunking: the text is split at headings, repeated headings are merged, and every chunk is prefixed with its heading so lists and explanations stay together
- Persistent vector index (ChromaDB): documents are embedded once and survive restarts
- Incremental indexing: only new or changed files are re-embedded; deleted files are removed from the index
- Similarity threshold: out-of-scope questions are refused without calling the LLM
- Optional web UI served by Flask (HTML, CSS, JS)

## How it works

```
docs/ (PDF, DOCX, TXT, MD)
        |
        v
  extract text -> clean -> split by headings -> chunk -> embed (bge-small-en-v1.5) -> ChromaDB (chroma_db/)

POST /ask {"question": ...}
        |
        v
  validate -> embed question -> top-k similar chunks -> threshold filter
        |                                                   |
        | (no chunk passes the threshold)                   v
        +--> "The answer is not available..."     prompt + retrieved chunks only -> Groq LLM -> answer
```

## Project structure

```
project/
├── app.py              # Flask app, /ask (main API), /chat and /clear (web UI), LLM call
├── rag_store.py        # Cleaning, chunking, embedding, ChromaDB storage and retrieval
├── requirements.txt
├── .env                # Your secrets (not committed)
├── .env.example        # Template for .env
├── docs/               # Put the PDF here
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── script.js
```

## Setup

1. Clone the repository and create a virtual environment:

```bash
git clone <your-repo-url>
cd <your-repo-folder>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

`sentence-transformers` installs PyTorch, so the first install is a large download. Make sure `requirements.txt` lists `python-dotenv` (not `dotenv`).

3. Create your `.env` file from the template and add your Groq API key:

```bash
cp .env.example .env            # Windows: copy .env.example .env
```

```
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Get a key from the [Groq console](https://console.groq.com). Model names change over time; if you get a `model_not_found` error, list the models available to your key and update `GROQ_MODEL`.

4. Place the PDF in the `docs/` folder.

## Run

```bash
python app.py
```

On startup the terminal shows how many chunks were indexed per file. The server runs on `http://127.0.0.1:5000`.

## API

### `POST /ask`

Request:

```json
{
  "question": "What is the importance of business communication?"
}
```

Success response (`200`):

```json
{
  "answer": "Importance of Business Communication ..."
}
```

If the document does not contain the answer (`200`):

```json
{
  "answer": "The answer is not available in the provided document."
}
```

Error responses:

| Case | Status | Body |
|---|---|---|
| Body is not valid JSON, or not a JSON object | 400 | `{"error": "Request body must be valid JSON"}` |
| `question` missing, not a string, empty, or only whitespace | 400 | `{"error": "'question' must be a non-empty string"}` |
| LLM call, retrieval or any other system error | 500 | `{"error": "Internal server error"}` (details are logged on the server, not returned) |

Example:

```bash
curl -X POST http://127.0.0.1:5000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the objectives of business communication?"}'
```

### Other routes (web UI only)

- `GET /` serves the chat page.
- `POST /chat` is the UI's chat endpoint (`{"message": ...}` returns `{"reply": ...}`) and keeps short conversation history.
- `POST /clear` clears that history.

The assignment API is `/ask`. It is stateless and does not use conversation history, so each answer is based only on the chunks retrieved for that question.

## Assumptions

- The application answers only from the PDF placed in `docs/`. No outside knowledge is used.
- The source PDF is a digitally authored document with a text layer. Scanned or image-only PDFs would need OCR first.
- Headings in the PDF are written in ALL CAPS (for example `OBJECTIVES & PURPOSE OF COMMUNICATION`) or match a known title (`Importance of Business Communication`). The heading rules in `rag_store.py` (`HEADING_RE`) and the page-header rule (`HEADER_RE`) are tuned to this document and may need adjusting for a different PDF.
- Bullets in the PDF are exported as special glyphs; they are normalised to `- ` before chunking.
- Sections that repeat the same heading are merged into one section, and the chunk size is 1500 characters so a short section stays in a single chunk.
- Embeddings are generated locally with `BAAI/bge-small-en-v1.5` (no embedding API key needed). The LLM is accessed through Groq.
- A retrieved chunk is used only if its cosine similarity is at least 0.3. If no chunk passes, the fixed "not available" sentence is returned without calling the LLM.
- The index is built at startup; a new or changed document requires a restart.
- Page numbers are not stored for PDFs (page metadata is `0`) because pages are joined before chunking, so lists that cross a page break stay intact.

## Updating documents

- **Add a document:** drop it into `docs/` and restart. Only the new file is embedded.
- **Edit a document:** replace the file and restart. Its old chunks are removed and re-created.
- **Delete a document:** remove it from `docs/` and restart. Its chunks are removed from the index.
- **Rebuild everything:** delete the `chroma_db/` folder and restart.

## Configuration

| Setting | Where | Purpose |
|---|---|---|
| `GROQ_API_KEY` | `.env` | Groq API key |
| `GROQ_MODEL` | `.env` | Chat model name |
| `NOT_FOUND` | `app.py` | Exact sentence returned when the answer is not in the document (also inserted into the system prompt) |
| `SYSTEM_PROMPT` | `app.py` | Rules that restrict the LLM to the retrieved context |
| `min_score` | `retrieve()` in `app.py` | Minimum similarity for a chunk to be used. Lower it if the bot refuses too often, raise it if it answers off-topic questions |
| `k` | `retrieve()` in `app.py` | Number of chunks sent to the LLM |
| `size`, `overlap` | `chunk_text()` in `rag_store.py` | Chunk size (default 1500) and overlap (150) in characters |
| `HEADER_RE`, `HEADING_RE` | `rag_store.py` | Patterns for the repeated page header and for section headings |
| `CHUNK_VERSION` | `rag_store.py` | Change it after editing cleaning or chunking logic so existing files are re-indexed |

Calibrate `min_score` by checking the printed `scores:` line for questions inside and outside the document, then pick a value between the two groups.

## Testing

Run these against a running server:

```bash
# 1. In-document question -> answer from the PDF
curl -X POST http://127.0.0.1:5000/ask -H "Content-Type: application/json" \
  -d '{"question": "What is business communication?"}'

# 2. List question -> heading, explanation and all list items
curl -X POST http://127.0.0.1:5000/ask -H "Content-Type: application/json" \
  -d '{"question": "What are the objectives of business communication?"}'

# 3. Out-of-scope question -> exact "not available" sentence
curl -X POST http://127.0.0.1:5000/ask -H "Content-Type: application/json" \
  -d '{"question": "Who is the Prime Minister of India?"}'

# 4. Empty question -> 400
curl -X POST http://127.0.0.1:5000/ask -H "Content-Type: application/json" \
  -d '{"question": "   "}'

# 5. Invalid body -> 400
curl -X POST http://127.0.0.1:5000/ask -H "Content-Type: application/json" -d 'not json'
```

## Limitations

- Scanned or image-only PDFs have no text layer and need OCR before indexing.
- The heading detection is rule-based and tuned to the provided PDF.
- `/chat` keeps one global conversation history for the whole server process, so it is shared by all visitors. Use per-session histories for multi-user deployment. `/ask` is not affected.
- The index is built at startup; new documents need a restart.

## Tech stack

Python, Flask, flask-cors, ChromaDB, sentence-transformers (`BAAI/bge-small-en-v1.5`), pypdf, python-docx, Groq API via the OpenAI Python client.

## Security

Never commit your `.env` file or API keys. If a key is ever exposed, revoke it in the Groq console and create a new one. Run with `debug=False` outside local development.