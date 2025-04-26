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
    intent: str           # Required field
    entities: List[str] = []  # Required field with default
    tool_hint: Optional[str] = None  # Optional field with default


def extract_perception(user_input: str) -> PerceptionResult:
    """Extracts intent, entities, and tool hints using LLM"""
    prompt = f"""
    You are an AI that extracts structured facts from user input.
    Input: "{user_input}"
    Return the response as a Python dictionary with keys:
    - intent: (brief phrase about what the user wants)
    - entities: a list of strings representing keywords or values
    - tool_hint: (name of the MCP tool that might be useful, if any)
    """
    logger.info("user_input: %s", user_input)
    try:
        logger.info("Generating perception...")
        response = model.generate_content(contents=prompt)
        raw = response.text.strip()
        logger.info("LLM output: %s", raw)

        # Clean the output
        clean = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        
        try:
            parsed = json.loads(clean)
            
            # Ensure entities is a list
            if isinstance(parsed.get("entities"), dict):
                parsed["entities"] = list(parsed["entities"].values())
            
            # Create PerceptionResult with all required fields
            return PerceptionResult(
                user_input=user_input,
                intent=parsed.get("intent", "unknown"),  # Provide default value
                entities=parsed.get("entities", []),     # Provide default value
                tool_hint=parsed.get("tool_hint")        # Optional field
            )
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON: %s", e)
            # Fallback with default values
            return PerceptionResult(
                user_input=user_input,
                intent="unknown",
                entities=[],
                tool_hint=None
            )
            
    except Exception as e:
        logger.error("Extraction failed: %s", e)
        # Fallback with default values
        return PerceptionResult(
            user_input=user_input,
            intent="unknown",
            entities=[],
            tool_hint=None
        )
