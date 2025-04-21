#from google import genai
#from google.genai import types
import google.generativeai as genai
import faiss
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

# Configure the API
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

genai.configure(api_key=api_key)

# Load API key
#client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# Helper: Get Gemini embedding for a text
def get_embedding(text: str) -> np.ndarray:
    result = genai.embed_content(
        model="models/gemini-embedding-exp-03-07",
        content=text,
        #config=types.EmbedContentConfig(task_type="CLUSTERING") #https://ai.google.dev/gemini-api/docs/embeddings
        task_type="CLUSTERING"
    )
    #return np.array(result.embeddings[0].values, dtype=np.float32)
    return np.array(result['embedding'], dtype=np.float32)

# Step 1: Sentences to index
sentences = [
    "The early bird catches the worm.",
    "A stitch in time saves nine.",
    "Better late than never.",
    "Birds of a feather flock together."
]

# Step 2: Get embeddings and create FAISS index
embeddings = [get_embedding(s) for s in sentences]
dimension = len(embeddings[0])
print(f"🔢 Vector length: {dimension}")
print(f"🔢 Embeddings: {embeddings}")
index = faiss.IndexFlatL2(dimension)
index.add(np.stack(embeddings))

# Step 3: Query embedding
query = "People with similar traits stick together."
query_embedding = get_embedding(query).reshape(1, -1)
print(f"🔢 Query embedding: {query_embedding}")

# Step 4: Search FAISS
D, I = index.search(query_embedding, k=1)
print(f"Closest match to: \"{query}\"")
print(f">>> {sentences[I[0][0]]}")

print(f"🔢 D: {D}")
print(f"🔢 I: {I}")