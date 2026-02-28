import os
import time
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

SEARX_URL = os.getenv("SEARX_URL", "http://searxng:8080/search")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434/api/chat")
MODEL = os.getenv("MODEL", "SmolLM2:360M")

MAX_RESULTS = int(os.getenv("MAX_RESULTS", "5"))
CTX_CHAR_LIMIT = int(os.getenv("CTX_CHAR_LIMIT", "2500"))

TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "80"))
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))

FRESH_KEYWORDS = [
    "latest", "last", "current", "now", "recent",
    "today", "this year", "this month", "this week",
    "updated", "new", "live"
]

YEAR_RE = re.compile(r"\b(20\d{2})\b")


def needs_fresh_info(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in FRESH_KEYWORDS)


def freshness_score(snippet: str) -> int:
    score = 0
    text = (snippet or "").lower()

    years = YEAR_RE.findall(text)
    if years:
        latest_year = max(int(y) for y in years)
        score += (latest_year - 2019) * 10

    for w in ["today", "this year", "this month", "recent", "latest", "updated"]:
        if w in text:
            score += 5

    return score


def searx_snippet_search(query: str, max_results: int = 5):
    params = {"q": query, "format": "json"}

    if needs_fresh_info(query):
        params.update({"categories": "news", "time_range": "month"})

    headers = {"User-Agent": "Mozilla/5.0"}

    t0 = time.time()
    r = requests.get(SEARX_URL, params=params, headers=headers, timeout=10)
    search_time = time.time() - t0

    ct = r.headers.get("Content-Type", "")
    if "application/json" not in ct:
        return [], search_time, f"Expected JSON but got Content-Type={ct}"

    data = r.json()
    results = []
    for item in data.get("results", []):
        title = item.get("title") or ""
        snippet = item.get("content") or item.get("snippet") or ""
        url = item.get("url") or ""
        results.append({"title": title, "snippet": snippet, "url": url})
        if len(results) >= max_results:
            break

    # Wikipedia priority only if freshness not required
    if not needs_fresh_info(query):
        wiki = [x for x in results if "wikipedia.org" in x["url"]]
        others = [x for x in results if "wikipedia.org" not in x["url"]]
        results = wiki + others

    results.sort(key=lambda x: freshness_score(x.get("snippet", "")), reverse=True)
    return results[:max_results], search_time, None


def generate_answer(question: str, snippets):
    context_text = "\n\n".join(s.get("snippet", "") for s in snippets)
    context_text = context_text[:CTX_CHAR_LIMIT]

    system_prompt = (
        "You are a helpful assistant.\n"
        "Output ONLY the final answer as a single sentence.\n"
        "Do NOT include context, explanations, reasoning, or descriptions.\n"
        "Do NOT repeat the question.\n"
        "Do NOT reference the context explicitly.\n"
        "Only output the final humanized answer based on the context."
    )

    user_prompt = f"Here is the context:\n{context_text}\n\nQuestion:\n{question}\n\nGenerate the final answer and make the answer straight forward."

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "num_predict": NUM_PREDICT,
            "temperature": TEMPERATURE,
            "num_ctx": NUM_CTX,
        },
    }

    t0 = time.time()
    r = requests.post(OLLAMA_URL, json=payload, timeout=60)
    llm_time = time.time() - t0

    if r.status_code != 200:
        return None, llm_time, f"Ollama error {r.status_code}: {r.text}"

    data = r.json()
    msg = (data.get("message") or {}).get("content", "")
    return msg.strip(), llm_time, None


@app.get("/health")
def health():
    return jsonify({"ok": True, "model": MODEL})


@app.post("/ask")
def ask():
    body = request.get_json(silent=True) or {}
    q = (body.get("text") or body.get("query") or "").strip()
    if not q:
        return jsonify({"error": "Missing 'text'"}), 400

    snippets, search_time, s_err = searx_snippet_search(q, max_results=MAX_RESULTS)
    if s_err:
        return jsonify({"error": "searx_failed", "detail": s_err, "search_time": search_time}), 502

    answer, llm_time, o_err = generate_answer(q, snippets)
    if o_err:
        return jsonify({"error": "ollama_failed", "detail": o_err, "llm_time": llm_time}), 502

    return jsonify({
        "reply": answer,
        "timing": {"search_s": round(search_time, 3), "llm_s": round(llm_time, 3)},
        "sources": snippets,   # keep this for debugging; Assist integration can ignore it
    })


