import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
from sentence_transformers import SentenceTransformer
from rag_store import RagStore

app = Flask(__name__)
CORS(app)

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")

store = RagStore(
    persist_dir=os.path.join(BASE_DIR, "chroma_db"),
    embed_docs=lambda t: embedder.encode(t, normalize_embeddings=True).tolist(),
    embed_query=lambda t: embedder.encode(
        ["Represent this sentence for searching relevant passages: " + t[0]],
        normalize_embeddings=True).tolist(),
)
store.sync_folder(os.path.join(BASE_DIR, "docs"))
print("Chunks in DB:", store.count())

def retrieve(query, k=5, min_score=0.3):
    return store.retrieve(query, k=k, min_score=min_score)

NOT_FOUND_MESSAGE = "The answer is not available in the provided document."

# Prompt for the AI to answer questions using only the provided context
SYSTEM_PROMPT = (f"""You are a question-answering assistant for a single document.

STRICT RULES:
1. Answer ONLY using the information in the provided context. Never use outside knowledge, assumptions, or guesses.
2. If the context does not contain the answer, reply with exactly this sentence and nothing else: "{NOT_FOUND_MESSAGE}"
3. Do not mention "the context" or "the retrieved text" in your answer. Answer directly.
4. If the document lists items (objectives, characteristics, importance, and so on), include ALL listed items and present them as a bullet list.
5. For definitions or explanations, answer in one short paragraph that stays close to the document's wording.
6. Do not add introductions, conclusions, or repeated information.
7. Do not use Markdown heading symbols (#, ##, ###).
8. If the question is only partly covered by the context, answer the covered part and do not guess the rest."""
)

conversation_history = []  # stores only plain questions and answers

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_message = (request.json or {}).get("message")
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        hits = retrieve(user_message)
        if not hits:
            conversation_history.append({"role": "user", "content": user_message})
            conversation_history.append({"role": "assistant", "content": NOT_FOUND_MESSAGE})
            return jsonify({"reply": NOT_FOUND_MESSAGE})

        context = "\n\n".join(f"[{h['source']}]\n{h['text']}" for h in hits)
        augmented = f"Context:\n{context}\n\nQuestion: {user_message}"

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += conversation_history[-6:]          # short memory only
        messages.append({"role": "user", "content": augmented})

        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            messages=messages,
            temperature=0.1,
        )
        ai_message = response.choices[0].message.content

        # save the clean question, not the big context block
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": ai_message})
        return jsonify({"reply": ai_message})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["POST"])
def clear_history():
    conversation_history.clear()
    return jsonify({"message": "History cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)