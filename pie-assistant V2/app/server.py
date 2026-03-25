import os
import time
import re
import requests
import numpy as np
import faiss
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# ---------------------------------------------------------
# CONFIG (from environment / add-on options)
# ---------------------------------------------------------
SEARX_URL        = os.getenv("SEARX_URL",        "http://searxng:8080/search")
OLLAMA_URL       = os.getenv("OLLAMA_URL",        "http://ollama:11434/api/chat")
OLLAMA_EMBED_URL = os.getenv("OLLAMA_EMBED_URL",  "http://ollama:11434/api/embed")
MODEL            = os.getenv("MODEL",             "smollm2:360m")
EMBED_MODEL      = os.getenv("EMBED_MODEL",       "nomic-embed-text")

CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE",    "600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "40"))
TOP_K_CHUNKS  = int(os.getenv("TOP_K_CHUNKS",  "2"))
SCRAPE_PAGES  = int(os.getenv("SCRAPE_PAGES",  "1"))
SNIPPET_PAGES = int(os.getenv("SNIPPET_PAGES", "4"))

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
EMBED_TIMEOUT   = int(os.getenv("EMBED_TIMEOUT",   "60"))
CHAT_TIMEOUT    = int(os.getenv("CHAT_TIMEOUT",    "120"))
TEMPERATURE     = float(os.getenv("TEMPERATURE",   "0.2"))
NUM_CTX         = int(os.getenv("NUM_CTX",         "8192"))

# Derived
TOTAL_RESULTS = SCRAPE_PAGES + SNIPPET_PAGES

# ---------------------------------------------------------
# URL FILTERS
# ---------------------------------------------------------
IMAGE_EXTENSIONS = re.compile(
    r"\.(jpg|jpeg|png|gif|webp|svg|bmp|ico|tiff|avif)(\?.*)?$",
    re.IGNORECASE,
)
YOUTUBE_DOMAINS = re.compile(
    r"(youtube\.com|youtu\.be|youtube-nocookie\.com)",
    re.IGNORECASE,
)


def should_skip_url(url: str) -> tuple[bool, str]:
    if IMAGE_EXTENSIONS.search(url):
        return True, "image URL"
    if YOUTUBE_DOMAINS.search(url):
        return True, "YouTube URL"
    return False, ""


# ---------------------------------------------------------
# SCRAPER
# ---------------------------------------------------------
def scrape_page(url: str, char_limit: int = 5000) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        content_type = r.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return ""

        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup([
            "script", "style", "nav", "footer", "header", "aside",
            "form", "iframe", "img", "figure", "picture", "svg",
            "canvas", "video", "audio", "map", "area",
        ]):
            tag.decompose()

        main = soup.find("article") or soup.find("main") or soup.find("body")
        text = (
            main.get_text(separator=" ", strip=True)
            if main else soup.get_text(separator=" ", strip=True)
        )
        return re.sub(r"\s+", " ", text).strip()[:char_limit]

    except Exception:
        return ""


# ---------------------------------------------------------
# CHUNKING
# ---------------------------------------------------------
def chunk_text(text: str) -> list[str]:
    if not text:
        return []
    chunks = []
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    for i in range(0, len(text), step):
        chunk = text[i : i + CHUNK_SIZE]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


# ---------------------------------------------------------
# EMBEDDING
# ---------------------------------------------------------
def embed_batch(texts: list[str]) -> list[list[float]]:
    r = requests.post(
        OLLAMA_EMBED_URL,
        json={"model": EMBED_MODEL, "input": texts},
        timeout=EMBED_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if "embeddings" in data:
        return data["embeddings"]
    raise ValueError(f"Unexpected embedding response: {data}")


# ---------------------------------------------------------
# FAISS STORE
# ---------------------------------------------------------
class FaissStore:
    def __init__(self, dim: int):
        self.index = faiss.IndexFlatIP(dim)
        self.meta: list[dict] = []

    def add(self, items: list[dict], vectors: list[list[float]]) -> None:
        if not items or not vectors:
            return
        mat = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(mat)
        self.index.add(mat)
        self.meta.extend(items)

    def search(self, vector: list[float], k: int) -> list[dict]:
        if self.index.ntotal == 0:
            return []
        q = np.array([vector], dtype=np.float32)
        faiss.normalize_L2(q)
        scores, ids = self.index.search(q, min(k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            results.append({**self.meta[idx], "score": float(score)})
        return results


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------
def searx_search(query: str) -> list[dict]:
    r = requests.get(
        SEARX_URL,
        params={"q": query, "format": "json"},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()

    results = []
    for item in r.json().get("results", []):
        url = item.get("url", "") or ""
        skip, _ = should_skip_url(url)
        if skip:
            continue
        results.append({
            "title":   item.get("title", "") or "",
            "snippet": item.get("content") or item.get("snippet", "") or "",
            "url":     url,
        })
        if len(results) >= TOTAL_RESULTS:
            break

    return results


# ---------------------------------------------------------
# BUILD CONTEXT POOL
# ---------------------------------------------------------
def build_context_pool(results: list[dict]) -> list[dict]:
    contexts = []

    # Scraped pages
    for i in range(min(SCRAPE_PAGES, len(results))):
        result = results[i]
        text = scrape_page(result["url"])
        if not text:
            text = result["snippet"]   # fall back to snippet if scrape fails

        contexts.append({
            "source_title": result["title"],
            "source_url":   result["url"],
            "source_type":  "scraped",
            "text":         text,
        })

    # Snippet-only pages
    for i in range(SCRAPE_PAGES, min(SCRAPE_PAGES + SNIPPET_PAGES, len(results))):
        result = results[i]
        contexts.append({
            "source_title": result["title"],
            "source_url":   result["url"],
            "source_type":  "snippet",
            "text":         result["snippet"] or result["title"],
        })

    return contexts


# ---------------------------------------------------------
# CHUNK → EMBED → RETRIEVE
# ---------------------------------------------------------
def build_chunk_items(contexts: list[dict]) -> list[dict]:
    chunk_items = []
    for ctx in contexts:
        for chunk in chunk_text(ctx["text"]):
            chunk_items.append({
                "source_title": ctx["source_title"],
                "source_url":   ctx["source_url"],
                "source_type":  ctx["source_type"],
                "text":         chunk,
            })
    return chunk_items


def retrieve_chunks(query: str, chunk_items: list[dict]) -> list[dict]:
    if not chunk_items:
        return []

    texts   = [item["text"] for item in chunk_items]
    vectors = embed_batch(texts)

    dim   = len(vectors[0])
    store = FaissStore(dim=dim)
    store.add(chunk_items, vectors)

    query_vec = embed_batch([query])[0]
    return store.search(query_vec, TOP_K_CHUNKS)


# ---------------------------------------------------------
# GENERATE ANSWER
# ---------------------------------------------------------
def generate_answer(question: str, chunks: list[dict]) -> tuple[str, float]:
    context_parts = [
        f"[Chunk {i} — {c['source_type']} — {c['source_title']}]\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    ]
    context_text = "\n\n".join(context_parts)[:8000]

    system_prompt = (
        "You are a helpful assistant. "
        "Give a straight-forward, concise answer. "
        "Do NOT repeat the question. "
        "Do NOT reference the context explicitly. "
        "Only output the final humanized answer. "
        "If you don't find the answer in the context, say you don't know."
    )
    user_prompt = (
        f"Here is the context:\n{context_text}\n\n"
        f"Question:\n{question}\n\n"
        "Generate the final answer and make it straight forward."
    )

    t0 = time.time()
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "stream": False,
            "think":  False,
            "options": {"temperature": TEMPERATURE, "num_ctx": NUM_CTX},
        },
        timeout=CHAT_TIMEOUT,
    )
    llm_time = time.time() - t0

    if r.status_code != 200:
        return f"Ollama error {r.status_code}: {r.text}", llm_time

    return r.json()["message"]["content"].strip(), llm_time


# ---------------------------------------------------------
# FLASK ENDPOINTS
# ---------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({"ok": True, "model": MODEL, "embed_model": EMBED_MODEL})


@app.post("/ask")
def ask():
    body = request.get_json(silent=True) or {}
    q = (body.get("text") or body.get("query") or "").strip()
    if not q:
        return jsonify({"error": "Missing 'text'"}), 400

    # 1. Search
    t0 = time.time()
    try:
        results = searx_search(q)
    except Exception as e:
        return jsonify({"error": "searx_failed", "detail": str(e)}), 502
    search_time = time.time() - t0

    if not results:
        return jsonify({"error": "no_results", "detail": "SearXNG returned no results"}), 502

    # 2. Build context pool (scrape + snippets)
    t1 = time.time()
    contexts = build_context_pool(results)
    scrape_time = time.time() - t1

    # 3. Chunk → embed → retrieve
    t2 = time.time()
    try:
        chunk_items = build_chunk_items(contexts)
        retrieved   = retrieve_chunks(q, chunk_items)
    except Exception as e:
        return jsonify({"error": "retrieval_failed", "detail": str(e)}), 502
    retrieval_time = time.time() - t2

    if not retrieved:
        return jsonify({"error": "no_chunks", "detail": "No relevant chunks found"}), 502

    # 4. Generate
    answer, llm_time = generate_answer(q, retrieved)

    return jsonify({
        "reply": answer,
        "timing": {
            "search_s":    round(search_time,    3),
            "scrape_s":    round(scrape_time,    3),
            "retrieval_s": round(retrieval_time, 3),
            "llm_s":       round(llm_time,       3),
        },
        "sources": [
            {"title": c["source_title"], "url": c["source_url"], "type": c["source_type"]}
            for c in contexts
        ],
    })