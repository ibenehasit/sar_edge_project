import json
import chromadb
import requests

OLLAMA = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"

def embed(texts):
    r = requests.post(f"{OLLAMA}/api/embed",
                      json={"model": EMBED_MODEL, "input": texts}, timeout=120)
    r.raise_for_status()
    return r.json()["embeddings"]

entries = json.load(open("/ros2_ws/knowledge/fallacies.json"))
docs = [
    f"{e['name']}: {e['definition']} Example: {e['example']} "
    f"Not to be confused with: {e['not_to_be_confused_with']}"
    for e in entries
]

client = chromadb.PersistentClient(path="/ros2_ws/rag_db")   # on the mounted volume
col = client.get_or_create_collection("fallacies", metadata={"hnsw:space": "cosine"})
col.upsert(ids=[e["name"] for e in entries], documents=docs,
           embeddings=embed(docs), metadatas=[{"name": e["name"]} for e in entries])
print(f"Stored {col.count()} entries")