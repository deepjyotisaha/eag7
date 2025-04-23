from typing import Optional, Dict, List
from ...backend.message_broker import message_broker
from ..llm.llm import LLMManager
import json
import asyncio
from functools import partial

class UserInteraction:
    # HTML templates
    STEP_TEMPLATE = """
    <div class="step-message" style="
        display: flex;
        align-items: center;
        padding: 8px;
        background-color: #f3f4f6;
        border-radius: 4px;
        margin-bottom: 8px;
        border-left: 4px solid #2563eb;
        font-family: system-ui, -apple-system, sans-serif;
    ">
        <span style="font-size: 16px; margin-right: 8px;">{icon}</span>
        <span style="flex: 1;">{content}</span>
    </div>
    """

    ITERATION_TEMPLATE = """
    <div class="iteration-summary" style="
        padding: 12px;
        background-color: #ecfdf5;
        border-radius: 4px;
        margin-bottom: 12px;
        border: 1px solid #059669;
        font-family: system-ui, -apple-system, sans-serif;
    ">
        {content}
    </div>
    """

    FINAL_TEMPLATE = """
    <div class="final-result" style="
        padding: 16px;
        background-color: #f5f3ff;
        border-radius: 4px;
        margin-bottom: 16px;
        border: 2px solid #6d28d9;
        font-family: system-ui, -apple-system, sans-serif;
    ">
        {content}
    </div>
    """

    @staticmethod
    def format_html_message(content: str, message_type: str = "info") -> str:
        """Format a message with HTML styling"""
        styles = {
            "info": """
                color: #374151;
                background-color: #f3f4f6;
                padding: 8px;
                border-radius: 4px;
                margin-bottom: 8px;
            """,
            "step": """
                color: #2563eb;
                background-color: #eff6ff;
                padding: 8px;
                border-radius: 4px;
                margin-bottom: 8px;
                border-left: 4px solid #2563eb;
            """,
            "tool": """
                color: #059669;
                background-color: #ecfdf5;
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 12px;
                border: 1px solid #059669;
            """,
            "final": """
                color: #6d28d9;
                background-color: #f5f3ff;
                padding: 16px;
                border-radius: 4px;
                margin-bottom: 16px;
                border: 2px solid #6d28d9;
                font-weight: bold;
            """,
            "error": """
                color: #dc2626;
                background-color: #fef2f2;
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 12px;
                border: 1px solid #dc2626;
            """
        }.get(message_type, "")
        
        return f'<div style="{styles}">{content}</div>'

    @staticmethod
    async def _generate_llm_response(llm_manager: LLMManager, prompt: str) -> str:
        """Helper method to generate LLM response with error handling"""
        try:
            if llm_manager and llm_manager.model:
                return await llm_manager.generate_with_timeout(prompt)
        except Exception as e:
            return f"Error generating response: {str(e)}"
        return None

    @staticmethod
    def send_step_update(session_id: str, stage: str, message: str) -> None:
        """Simple step update with consistent formatting"""
        if not session_id:
            return

        icons = {
            "perception": "📋",
            "memory": "🔍",
            "plan": "📝",
            "tool": "⚙️",
            "agent": "🤖"
        }
        
        icon = icons.get(stage, "ℹ️")
        html = UserInteraction.STEP_TEMPLATE.format(
            icon=icon,
            content=message
        )
        
        message_broker.send_update(session_id, html)

    @staticmethod
    async def send_iteration_summary(session_id: str, iteration_data: Dict, llm_manager: LLMManager) -> None:
        """Generate a user-friendly iteration summary using LLM"""
        if not session_id or not iteration_data:
            return

        # Prepare prompt for LLM
        prompt = f"""
        Create a clear, concise summary of this analysis step.
        Focus on explaining what was done, what inputs were used, and what was discovered.
        Keep it user-friendly and avoid technical jargon.

        Context:
        - Stage: {iteration_data.get('stage', 'unknown')}
        - Tool Used: {iteration_data.get('tool_name', 'none')}
        - Action: {iteration_data.get('action', 'unknown')}
        - Result: {iteration_data.get('result', 'No result available')}

        Format the response in clear, readable bullet points.
        Keep it concise (3-4 bullet points maximum).
        """

        try:
            summary = await UserInteraction._generate_llm_response(llm_manager, prompt)
            if not summary:
                summary = f"""
                • Step: {iteration_data.get('stage', 'unknown')}
                • Action: Used {iteration_data.get('tool_name', 'tool')} to {iteration_data.get('action', 'analyze data')}
                • Result: {iteration_data.get('result', 'No result available')}
                """

            html = UserInteraction.ITERATION_TEMPLATE.format(content=summary)
            message_broker.send_update(session_id, html)
        except Exception as e:
            message_broker.send_update(session_id, f"Error creating summary: {str(e)}")

    @staticmethod
    async def send_final_result(session_id: str, raw_data: Dict, query_type: str, llm_manager: LLMManager) -> None:
        """Generate a well-formatted, user-friendly final result using LLM"""
        if not session_id or not raw_data:
            return

        # Prepare prompt for LLM
        prompt = f"""
        Create a clear, user-friendly summary of the {query_type} results.
        Focus on the key findings and insights that would be most valuable to the user.
        
        Raw Data:
        {json.dumps(raw_data, indent=2)}

        Requirements:
        1. Start with a clear, one-sentence summary of the main finding
        2. Present 2-3 key points or insights
        3. If relevant, include any important numbers or metrics
        4. If applicable, end with a brief recommendation or next steps
        5. Use bullet points for clarity
        6. Keep the entire response under 200 words
        7. Make it easy to read and understand for non-technical users
        """

        try:
            summary = await UserInteraction._generate_llm_response(llm_manager, prompt)
            if not summary:
                summary = str(raw_data.get('result', 'No results available'))

            html = UserInteraction.FINAL_TEMPLATE.format(content=summary)
            message_broker.send_update(session_id, html, "final")
        except Exception as e:
            message_broker.send_update(session_id, f"Error creating final summary: {str(e)}", "error")

    @staticmethod
    async def send_update(session_id: str, stage: str, message: str, is_final: bool = False, 
                   llm_manager: LLMManager = None, iteration_data: Dict = None, 
                   raw_data: Dict = None, query_type: str = None) -> None:
        """Main router method for all updates"""
        if not session_id:
            return

        try:
            # Handle final update
            if is_final and raw_data:
                await UserInteraction.send_final_result(session_id, raw_data, query_type or "analysis", llm_manager)
                return

            # Handle iteration update
            if iteration_data:
                await UserInteraction.send_iteration_summary(session_id, iteration_data, llm_manager)
                return

            # Handle step update (this one is synchronous)
            UserInteraction.send_step_update(session_id, stage, message)

        except Exception as e:
            error_msg = f"Error sending update: {str(e)}"
            message_broker.send_update(session_id, error_msg, "error")

# Global instance
user_interaction = UserInteraction()