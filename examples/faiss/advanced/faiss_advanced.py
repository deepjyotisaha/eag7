import os
from pathlib import Path
import faiss
import numpy as np
#from google import genai
#from google.genai import types
import google.generativeai as genai
from dotenv import load_dotenv
import time

load_dotenv()
# 🔐 Gemini Setup
# Configure the API
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

genai.configure(api_key=api_key)

print("hello0")

# -- CONFIG --
CHUNK_SIZE = 40
CHUNK_OVERLAP = 10
DOC_PATH = Path("./documents")

# -- HELPERS --

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i+size])
        if chunk:
            chunks.append(chunk)
    return chunks

def get_embedding(text: str) -> np.ndarray:
    res = genai.embed_content(
        model="models/gemini-embedding-exp-03-07",
        content=text,
        #config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        task_type="RETRIEVAL_DOCUMENT"
    )
    #return np.array(res.embeddings[0].values, dtype=np.float32)
    return np.array(res['embedding'], dtype=np.float32)

# -- LOAD DOCS & CHUNK --
all_chunks = []
metadata = []

# Print current working directory and documents path for debugging
print(f"Current working directory: {os.getcwd()}")
print(f"Documents path: {DOC_PATH.absolute()}")
print(f"Documents exist: {DOC_PATH.exists()}")

print(f"🔢 Loading documents from {DOC_PATH}")

# List all txt files before processing
txt_files = list(DOC_PATH.glob("*.txt"))
print(f"Found {len(txt_files)} txt files: {[f.name for f in txt_files]}")

try:
    for file in DOC_PATH.glob("*.txt"):
        print(f"🔢 Processing file: {file.name}")
        with open(file, "r", encoding="utf-8") as f:
            print(f"🔢 Reading file: {file.name}")
            content = f.read()
            chunks = chunk_text(content)
            print(f"file: {file.name} 🔢 Chunks: {chunks}")
            for idx, chunk in enumerate(chunks):
                all_chunks.append(get_embedding(chunk))
                metadata.append({
                    "doc_name": file.name,
                    "chunk": chunk,
                    "chunk_id": f"{file.stem}_{idx}"
                })
            print(f"🔢 🔢 Metadata for {file.name}: {metadata}")
        print("Sleeping for 5 seconds")
        time.sleep(5)
except Exception as e:
    print(f"Error: {e}")

# -- CREATE FAISS INDEX --
dimension = len(all_chunks[0])
index = faiss.IndexFlatL2(dimension)
index.add(np.stack(all_chunks))

print(f"✅ Indexed {len(all_chunks)} chunks from {len(list(DOC_PATH.glob('*.txt')))} documents")

# -- SEARCH --
query = "When will Dhoni retire?"
query_vec = get_embedding(query).reshape(1, -1)
D, I = index.search(query_vec, k=3)

print(f"\n🔍 Query: {query}\n\n📚 Top Matches:")
for rank, idx in enumerate(I[0]):
    data = metadata[idx]
    print(f"\n#{rank + 1}: From {data['doc_name']} [{data['chunk_id']}]")
    print(f"→ {data['chunk']}")
