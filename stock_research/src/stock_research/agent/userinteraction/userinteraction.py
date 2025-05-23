from typing import Optional, Dict, List
from ...backend.message_broker import message_broker
from ..llm.llm import LLMManager
import json
import asyncio
from functools import partial
import google.generativeai as genai

class UserInteraction:
    # Common HTML template for all updates
    MESSAGE_TEMPLATE = """
    <div class="message-container" style="
        font-family: system-ui, -apple-system, sans-serif;
        padding: {padding};
        background-color: white;
        border-radius: 8px;
        margin-bottom: {margin};
        border: 1px solid {border_color};
        color: black;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
    ">
        <div style="
            border-left: 2px solid {border_color};
            padding-left: 10px;
        ">
            {content}
        </div>
    </div>
    """

    # Style configurations for different message types
    STYLES = {
        "step": {
            "padding": "8px 12px",
            "bg_color": "#ffffff",
            "margin": "8px",
            "border_color": "rgba(37, 99, 235, 0.15)",
            "text_color": "black"
        },
        "iteration": {
            "padding": "12px 16px",
            "bg_color": "#ffffff",
            "margin": "12px",
            "border_color": "rgba(5, 150, 105, 0.15)",
            "text_color": "black"
        },
        "final": {
            "padding": "16px 20px",
            "bg_color": "#ffffff",
            "margin": "16px",
            "border_color": "rgba(109, 40, 217, 0.15)",
            "text_color": "black"
        }
    }

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
        
        content = f"""
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">{icon}</span>
            <span style="flex: 1;">{message}</span>
        </div>
        """
        
        html = UserInteraction.MESSAGE_TEMPLATE.format(
            content=content,
            **UserInteraction.STYLES["step"]
        )
        
        message_broker.send_update(session_id, html)

    @staticmethod
    async def send_iteration_summary(session_id: str, iteration_data: Dict, llm_manager: LLMManager) -> None:
        """Generate a user-friendly iteration summary using LLM"""
        if not session_id or not iteration_data:
            return

        prompt = f"""
        Create a clear, concise summary of this analysis step.
        Focus on explaining what was done, what inputs were used, and what was discovered.
        Keep it user-friendly and avoid technical jargon.

        Context:
        - Stage: {iteration_data.get('stage', 'unknown')}
        - Tool Used: {iteration_data.get('tool_name', 'none')}
        - Action: {iteration_data.get('action', 'unknown')}
        - Result: {iteration_data.get('result', 'No result available')}

        Format your response with:
        1. A clear one-sentence overview of what was done
        2. 2-3 bullet points with key details
        3. Use this exact HTML format for bullet points:
        <ul style="margin: 15px 0; padding-left: 20px;">
            <li style="margin-bottom: 8px;">Point here</li>
        </ul>
        """

        try:
            summary = await UserInteraction._generate_llm_response(llm_manager, prompt)
            if not summary:
                summary = f"""
                <p>Step: {iteration_data.get('stage', 'unknown')}</p>
                <ul style="margin: 15px 0; padding-left: 20px;">
                    <li style="margin-bottom: 8px;">Action: Used {iteration_data.get('tool_name', 'tool')} to {iteration_data.get('action', 'analyze data')}</li>
                    <li style="margin-bottom: 8px;">Result: {iteration_data.get('result', 'No result available')}</li>
                </ul>
                """

            content = f"""
            <div style="display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 18px;">📊</span>
                    <h3 style="margin: 0; font-size: 18px; color: black;">Analysis Step Summary</h3>
                </div>
                <div style="line-height: 1.6; color: black;">{summary}</div>
            </div>
            """

            html = UserInteraction.MESSAGE_TEMPLATE.format(
                content=content,
                **UserInteraction.STYLES["iteration"]
            )
            
            message_broker.send_update(session_id, html)
        except Exception as e:
            message_broker.send_update(session_id, f"Error creating summary: {str(e)}")

    @staticmethod
    async def send_final_result(session_id: str, raw_data: Dict, query_type: str, llm_manager: LLMManager) -> None:
        """Generate a well-formatted, user-friendly final result using LLM"""
        if not session_id or not raw_data:
            return

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
        5. Always use bullet points for clarity
        6. Keep the entire response under 200 words
        7. Make it easy to read and understand for non-technical users
        8. Inject HTML tags to make the response more readable.
        9. Include a table of the data if relevant.
        10.Inlclude a header which says "Final Results"
        """

        try:
            summary = await UserInteraction._generate_llm_response(llm_manager, prompt)
            if not summary:
                summary = str(raw_data.get('result', 'No results available'))

            content = f"""
            <div style="display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 18px;">🎯</span>
                    <h3 style="margin: 0; font-size: 18px; color: black;">{query_type.title()} Results</h3>
                </div>
                <div style="line-height: 1.6; color: black;">{summary}</div>
            </div>
            """

            html = UserInteraction.MESSAGE_TEMPLATE.format(
                content=content,
                **UserInteraction.STYLES["final"]
            )
            
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

            # Handle step update
            UserInteraction.send_step_update(session_id, stage, message)

        except Exception as e:
            error_msg = f"Error sending update: {str(e)}"
            message_broker.send_update(session_id, error_msg, "error")


    @staticmethod
    async def send_introductory_message(tools_description: str) -> str:
        """
        Creates a friendly introduction message summarizing the agent's capabilities based on available tools.
        
        Args:
            tools_description: String containing descriptions of all available tools
            
        Returns:
            str: A friendly introduction message with capabilities summary
        """
        prompt = f"""
        Given these available tools and their descriptions:
        {tools_description}

        Create a friendly, one-sentence introduction that summarizes the key capabilities. 
        The introduction should:
        1. Start with "I am your AI assistant"
        2. Group similar tools together (e.g., math operations, email functions)
        3. Focus on high-level capabilities rather than listing specific functions
        4. Be concise but informative
        5. Use natural, friendly language

        Example format:
        "I am your AI assistant capable of [main capability 1], [main capability 2], and [main capability 3]."
        """

        llm = LLMManager()
        response = await llm.generate_content(prompt)
        
        # Combine with tools list for complete introduction
        full_intro = f"{response.text}\n\nHere are all the tools I can use:\n{tools_description}"
        
        return full_intro


user_interaction = UserInteraction()