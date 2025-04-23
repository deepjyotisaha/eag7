import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import logging
import asyncio
from concurrent.futures import TimeoutError
from typing import Tuple, Optional, Dict
from ..config.log_config import setup_logging

class LLMManager:
    def __init__(self):
        """Initialize the LLM manager with configuration and API setup"""
        self.logger = logging.getLogger(__name__)
        self.model = None
        
    def initialize(self):
        """Initialize the LLM with API key and model configuration"""
        self.logger.info("Initializing LLM...")
        try:
            # Load environment variables
            load_dotenv()
            
            # Get API key
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not found in environment variables")
            
            # Configure Gemini
            self.logger.info("Configuring Gemini API...")
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            self.logger.info("Gemini API configured successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing LLM: {str(e)}")
            raise

    async def generate_with_timeout(self, prompt: str, timeout: int = 10):
        """
        Generate content with a timeout
        
        Args:
            prompt: The prompt to send to the LLM
            timeout: Maximum time to wait for response in seconds
            
        Returns:
            The LLM response
            
        Raises:
            TimeoutError: If generation takes too long
            Exception: For other errors during generation
        """
        self.logger.info("Starting LLM generation...")
        try:
            # Convert the synchronous generate_content call to run in a thread
            loop = asyncio.get_event_loop()
            #self.logger.info(f"Prompt: {prompt}")
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None, 
                    lambda: self.model.generate_content(
                        contents=prompt
                    )
                ),
                timeout=timeout
            )
            raw = response.text.strip()
            self.logger.info(f"LLM output: {raw}")

            for line in raw.splitlines():
                if line.strip().startswith("FUNCTION_CALL:") or line.strip().startswith("FINAL_ANSWER:"):
                    return line.strip()

            self.logger.info("LLM generation completed")
            return raw.strip()
            
        except TimeoutError:
            self.logger.error("LLM generation timed out!")
            raise
        except Exception as e:
            self.logger.error(f"Error in LLM generation: {e}")
            raise
