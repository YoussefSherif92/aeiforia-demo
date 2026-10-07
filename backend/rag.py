import os
from pathlib import Path

import requests
from google import genai
from google.genai import types


QDRANT_URL = os.environ["QDRANT_URL"]
COLLECTION = "payment_procedures_v1"
DIMENSIONS = 768


def client():
    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=60000),
    )


def embed(text):
    result = client().models.embed_content(
        model=os.environ["EMBEDDING_MODEL"],
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=DIMENSIONS
        ),
    )
    return result.embeddings[0].values


def index_knowledge():
    text = Path(
        "/app/knowledge/payment_procedure.txt"
    ).read_text(encoding="utf-8")

    chunks = [
        chunk.strip()
        for chunk in text.split("\n\n")
        if chunk.strip()
    ]

    response = requests.get(
        f"{QDRANT_URL}/collections/{COLLECTION}", timeout=10
    )

    if response.status_code == 404:
        response = requests.put(
            f"{QDRANT_URL}/collections/{COLLECTION}",
            json={
                "vectors": {
                    "size": DIMENSIONS,
                    "distance": "Cosine",
                }
            },
            timeout=10,
        )

    response.raise_for_status()

    points = []
    for index, chunk in enumerate(chunks):
        points.append({
            "id": index + 1,
            "vector": embed(chunk),
            "payload": {
                "source": "payment_procedure.txt",
                "passage": chunk,
            },
        })

    response = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        params={"wait": "true"},
        json={"points": points},
        timeout=30,
    )
    response.raise_for_status()

    return {"indexed_passages": len(points)}


def explain_invoice(invoice):
    outstanding = invoice["total"] - invoice["paid"]

    if outstanding > 0:
        topic = "Partial payment: payment below invoice total."
    elif outstanding < 0:
        topic = "Overpayment: payments exceed invoice total."
    else:
        topic = "Exact payment: received amount equals invoice total."

    response = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
        json={
            "vector": embed(topic),
            "limit": 2,
            "with_payload": True,
        },
        timeout=15,
    )
    response.raise_for_status()

    sources = [
        hit["payload"]
        for hit in response.json()["result"]
    ]

    if not sources:
        raise ValueError("No procedure passages were retrieved.")

    context = "\n\n".join(
        f"[{index + 1}] {source['passage']}"
        for index, source in enumerate(sources)
    )

    prompt = f"""
Explain this fictional invoice case in simple English.

Invoice: {invoice['number']}
Invoice total: EUR {invoice['total']}
Received payments: EUR {invoice['paid']}
Outstanding balance: EUR {outstanding}
Status: {invoice['status']}

Retrieved demonstration procedure:
{context}

Give:
1. The observed payment result.
2. The next action supported by the procedure.
3. What a human reviewer should check.

Cite retrieved passages using [1] or [2].
Do not invent a cause for the difference.
Describe possible causes only as possibilities.
Do not claim this procedure is law or an actual Aeiforia policy.
Do not change any data or claim that an action was performed.
"""

    result = client().models.generate_content(
        model=os.environ["GEMINI_MODEL"],
        contents=prompt,
    )

    if not result.text:
        raise ValueError("Gemini returned no explanation.")

    return {
        "explanation": result.text,
        "sources": sources,
    }