#from google import genai
#from google.genai import types
import google.generativeai as genai
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

# Configure the API
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

genai.configure(api_key=api_key)

sentence = "How does AlphaFold work?"

response = genai.embed_content(
    model="models/gemini-embedding-exp-03-07",
    content=sentence,
    #config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    task_type="RETRIEVAL_DOCUMENT"
)

print(response)

#embedding_vector = np.array(response.embedding[0].values, dtype=np.float32)

# The response now contains the embedding directly
embedding_vector = np.array(response['embedding'], dtype=np.float32)

print(f"🔢 Vector length: {len(embedding_vector)}")
print(f"📈 First 5 values: {embedding_vector[:5]}")
