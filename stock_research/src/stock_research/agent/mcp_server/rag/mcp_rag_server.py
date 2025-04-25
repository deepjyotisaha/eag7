from mcp.server.fastmcp import FastMCP, Image
from mcp.server.fastmcp.prompts import base
from mcp.types import TextContent
from mcp import types
from PIL import Image as PILImage
import math
import sys
import os
import json
import faiss
import numpy as np
from pathlib import Path
import requests
from markitdown import MarkItDown
import time
#from ..models import AddInput, AddOutput, SqrtInput, SqrtOutput, StringsToIntsInput, StringsToIntsOutput, ExpSumInput, ExpSumOutput
from PIL import Image as PILImage
from tqdm import tqdm
import hashlib
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)20s() %(message)s',
        handlers=[
        logging.FileHandler('mcp_rag_server.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)

mcp = FastMCP("Document Search")

EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 256
CHUNK_OVERLAP = 40
ROOT = Path(__file__).parent.resolve()

def get_embedding(text: str) -> np.ndarray:
    try:
        mcp_log("INFO", "Requesting embedding from Ollama service")
        response = requests.post(EMBED_URL, json={"model": EMBED_MODEL, "prompt": text}, timeout=30)
        response.raise_for_status()
        embedding = response.json()["embedding"]
        mcp_log("INFO", f"Got embedding of dimension {len(embedding)}")
        return np.array(embedding, dtype=np.float32)
    except requests.exceptions.ConnectionError:
        mcp_log("ERROR", f"Could not connect to embedding service at {EMBED_URL}. Is Ollama running?")
        raise
    except requests.exceptions.Timeout:
        mcp_log("ERROR", "Embedding request timed out")
        raise
    except Exception as e:
        mcp_log("ERROR", f"Error getting embedding: {str(e)}")
        raise

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words = text.split()
    for i in range(0, len(words), size - overlap):
        yield " ".join(words[i:i+size])

def mcp_log(level: str, message: str) -> None:
    """Log a message to stderr to avoid interfering with JSON communication"""
    sys.stderr.write(f"{level}: {message}\n")
    sys.stderr.flush()

@mcp.tool()
def search_documents(query: str) -> list[str]:
    """Search for relevant content from uploaded documents."""
    ensure_faiss_ready()
    mcp_log("SEARCH", f"Query: {query}")
    try:
        # Add timing information
        start_time = time.time()
        
        index_path = str(ROOT / "faiss_index" / "index.bin")
        metadata_path = ROOT / "faiss_index" / "metadata.json"
        
        mcp_log("INFO", f"Loading FAISS index from: {index_path}")
        index = faiss.read_index(index_path)
        mcp_log("INFO", f"FAISS index loaded with {index.ntotal} vectors")
        
        mcp_log("INFO", f"Loading metadata from: {metadata_path}")
        metadata = json.loads(metadata_path.read_text())
        mcp_log("INFO", f"Metadata loaded with {len(metadata)} entries")
        
        mcp_log("INFO", "Generating embedding for query")
        query_vec = get_embedding(query).reshape(1, -1)
        
        mcp_log("INFO", "Performing FAISS search")
        D, I = index.search(query_vec, k=5)
        
        results = []
        for i, idx in enumerate(I[0]):
            data = metadata[idx]
            result = f"{data['chunk']}\n[Source: {data['doc']}, ID: {data['chunk_id']}]"
            mcp_log("INFO", f"Result {i+1} from document: {data['doc']}, distance: {D[0][i]:.4f}")
            results.append(result)
        
        elapsed = time.time() - start_time
        mcp_log("INFO", f"Search completed in {elapsed:.2f} seconds with {len(results)} results")
        return results
        
    except Exception as e:
        mcp_log("ERROR", f"Search failed: {str(e)}")
        import traceback
        mcp_log("ERROR", f"Traceback:\n{traceback.format_exc()}")
        return [f"ERROR: Failed to search: {str(e)}"]


# DEFINE RESOURCES

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    print("CALLED: get_greeting(name: str) -> str:")
    return f"Hello, {name}!"


# DEFINE AVAILABLE PROMPTS
@mcp.prompt()
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"
    print("CALLED: review_code(code: str) -> str:")


@mcp.prompt()
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]

def process_documents():
    """Process documents and create FAISS index"""
    mcp_log("INFO", "Indexing documents with MarkItDown...")
    ROOT = Path(__file__).parent.resolve()
    DOC_PATH = ROOT  / "documents"
    INDEX_CACHE = ROOT  / "faiss_index"
    INDEX_CACHE.mkdir(exist_ok=True)
    INDEX_FILE = INDEX_CACHE / "index.bin"
    METADATA_FILE = INDEX_CACHE / "metadata.json"
    CACHE_FILE = INDEX_CACHE / "doc_index_cache.json"

    def file_hash(path):
        return hashlib.md5(Path(path).read_bytes()).hexdigest()

    CACHE_META = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    metadata = json.loads(METADATA_FILE.read_text()) if METADATA_FILE.exists() else []
    index = faiss.read_index(str(INDEX_FILE)) if INDEX_FILE.exists() else None
    all_embeddings = []
    converter = MarkItDown()

    for file in DOC_PATH.glob("*.*"):
        fhash = file_hash(file)
        if file.name in CACHE_META and CACHE_META[file.name] == fhash:
            mcp_log("SKIP", f"Skipping unchanged file: {file.name}")
            continue

        mcp_log("PROC", f"Processing: {file.name}")
        try:
            result = converter.convert(str(file))
            markdown = result.text_content
            chunks = list(chunk_text(markdown))
            embeddings_for_file = []
            new_metadata = []
            for i, chunk in enumerate(tqdm(chunks, desc=f"Embedding {file.name}")):
                embedding = get_embedding(chunk)
                embeddings_for_file.append(embedding)
                new_metadata.append({"doc": file.name, "chunk": chunk, "chunk_id": f"{file.stem}_{i}"})
            if embeddings_for_file:
                if index is None:
                    dim = len(embeddings_for_file[0])
                    index = faiss.IndexFlatL2(dim)
                index.add(np.stack(embeddings_for_file))
                metadata.extend(new_metadata)
            CACHE_META[file.name] = fhash
        except Exception as e:
            mcp_log("ERROR", f"Failed to process {file.name}: {e}")

    CACHE_FILE.write_text(json.dumps(CACHE_META, indent=2))
    METADATA_FILE.write_text(json.dumps(metadata, indent=2))
    if index and index.ntotal > 0:
        faiss.write_index(index, str(INDEX_FILE))
        mcp_log("SUCCESS", "Saved FAISS index and metadata")
    else:
        mcp_log("WARN", "No new documents or updates to process.")

def ensure_faiss_ready():
    from pathlib import Path
    index_path = ROOT / "faiss_index" / "index.bin"
    meta_path = ROOT / "faiss_index" / "metadata.json"
    if not (index_path.exists() and meta_path.exists()):
        mcp_log("INFO", "Index not found — running process_documents()...")
        process_documents()
    else:
        mcp_log("INFO", "Index already exists. Skipping regeneration.")


if __name__ == "__main__":
    print("Starting the RAG server...")  
    
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        mcp.run() # Run without transport for dev server
    else:
        # Start the server in a separate thread
        import threading
        server_thread = threading.Thread(target=lambda: mcp.run(transport="stdio"))
        server_thread.daemon = True
        server_thread.start()
        
        # Wait a moment for the server to start
        time.sleep(2)
        
        # Process documents after server is running
        process_documents()
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
