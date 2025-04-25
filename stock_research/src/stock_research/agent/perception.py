from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv
#from google import genai
import google.generativeai as genai
import re
import json
from .config.log_config import setup_logging

# Optional: import log from agent if shared, else define locally
#try:
#    from agent import log
#except ImportError:
#    import datetime
#    def log(stage: str, msg: str):
#        now = datetime.datetime.now().strftime("%H:%M:%S")
#        print(f"[{now}] [{stage}] {msg}")

logger = setup_logging(__name__)

load_dotenv()

# Get API key
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")            
logger.info("Gemini API configured successfully")


class PerceptionResult(BaseModel):
    user_input: str
    intent: Optional[str]
    entities: List[str] = []
    tool_hint: Optional[str] = None


def extract_perception(user_input: str) -> PerceptionResult:
    """Extracts intent, entities, and tool hints using LLM"""

    prompt = f"""
You are an AI that extracts structured facts from user input.

Input: "{user_input}"

Return the response as a Python dictionary with keys:
- intent: (brief phrase about what the user wants)
- entities: a list of strings representing keywords or values (e.g., ["INDIA", "ASCII"])
- tool_hint: (name of the MCP tool that might be useful, if any)

Output only the dictionary on a single line. Do NOT wrap it in ```json or other formatting. Ensure `entities` is a list of strings, not a dictionary.
    """

    try:
        logger.info("Generating perception...")
        logger.info("Prompt: %s", prompt)
        response = model.generate_content(
            contents=prompt
        )
        logger.info("LLM output: %s", response.text)
        raw = response.text.strip()
        #logger.info("perception", f"LLM output: {raw}")

        # Strip Markdown backticks if present
        clean = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(clean)
        except Exception as e:
            logger.error("Failed to parse cleaned output: %s", e)
            raise

        # Fix common issues
        if isinstance(parsed.get("entities"), dict):
            parsed["entities"] = list(parsed["entities"].values())


        return PerceptionResult(user_input=user_input, **parsed)

    except Exception as e:
        logger.error("Extraction failed: %s", e)
        return PerceptionResult(user_input=user_input)
