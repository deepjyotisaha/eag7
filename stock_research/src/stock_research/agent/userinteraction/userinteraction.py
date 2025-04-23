from typing import Optional, Dict, List
from ...backend.message_broker import message_broker
from ..llm.llm import LLMManager
import json
import asyncio
from functools import partial

class UserInteraction:
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
        """Simple synchronous step update"""
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
        
        html = f"""
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
            <span style="flex: 1;">{message}</span>
        </div>
        """
        
        message_broker.send_update(session_id, html)

    @staticmethod
    def send_iteration_summary(session_id: str, iteration_data: Dict) -> None:
        """Synchronous iteration summary without LLM"""
        if not session_id or not iteration_data:
            return

        summary_styles = """
            .iteration-summary {
                font-family: system-ui, -apple-system, sans-serif;
            }
            .iteration-summary h4 {
                margin: 0 0 8px 0;
                font-size: 16px;
                font-weight: 600;
            }
            .iteration-summary p {
                margin: 4px 0;
                padding: 4px 0;
                border-bottom: 1px solid rgba(0,0,0,0.1);
            }
            .iteration-summary .label {
                font-weight: 500;
                color: #4b5563;
                display: inline-block;
                width: 80px;
            }
        """

        summary = f"""
        <style>{summary_styles}</style>
        <div class="iteration-summary">
            <h4>{iteration_data.get('stage', 'unknown').title()} Step</h4>
            <p><span class="label">Tool:</span> {iteration_data.get('tool_name', 'none')}</p>
            <p><span class="label">Action:</span> {iteration_data.get('action', 'unknown')}</p>
            <p><span class="label">Result:</span> {iteration_data.get('result', 'No result available')}</p>
        </div>
        """
        
        formatted_message = UserInteraction.format_html_message(summary, "tool")
        message_broker.send_update(session_id, formatted_message)

    @staticmethod
    def send_final_result(session_id: str, raw_data: Dict, query_type: str) -> None:
        """Synchronous final result without LLM"""
        if not session_id or not raw_data:
            return

        final_styles = """
            .final-result {
                font-family: system-ui, -apple-system, sans-serif;
            }
            .final-result h3 {
                margin: 0 0 16px 0;
                font-size: 18px;
                font-weight: 600;
                color: #4c1d95;
            }
            .results-content {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .result-item {
                padding: 8px;
                background-color: white;
                border-radius: 4px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
            .result-item strong {
                color: #4b5563;
                margin-right: 8px;
            }
        """

        final_message = f"""
        <style>{final_styles}</style>
        <div class="final-result">
            <h3>{query_type.title()} Results</h3>
            <div class="results-content">
                {UserInteraction._format_dict_to_html(raw_data)}
            </div>
        </div>
        """
        
        formatted_message = UserInteraction.format_html_message(final_message, "final")
        message_broker.send_update(session_id, formatted_message, "final")

    @staticmethod
    def _format_dict_to_html(data: Dict) -> str:
        """Helper method to format dictionary data to HTML"""
        html = ""
        for key, value in data.items():
            if isinstance(value, dict):
                html += f'<div class="result-item"><strong>{key}:</strong><div style="margin-left: 16px">{UserInteraction._format_dict_to_html(value)}</div></div>'
            elif isinstance(value, list):
                formatted_list = "<ul style='margin: 0; padding-left: 20px'>"
                for item in value:
                    formatted_list += f"<li>{item}</li>"
                formatted_list += "</ul>"
                html += f'<div class="result-item"><strong>{key}:</strong>{formatted_list}</div>'
            else:
                html += f'<div class="result-item"><strong>{key}:</strong> {value}</div>'
        return html

    @staticmethod
    def send_update(session_id: str, stage: str, message: str, is_final: bool = False, 
                   llm_manager: LLMManager = None, iteration_data: Dict = None, 
                   raw_data: Dict = None, query_type: str = None) -> None:
        """Main router method - all synchronous with optional async LLM enhancement"""
        if not session_id:
            return

        try:
            # Handle final update
            if is_final and raw_data:
                UserInteraction.send_final_result(session_id, raw_data, query_type or "analysis")
                return

            # Handle iteration update
            if iteration_data:
                UserInteraction.send_iteration_summary(session_id, iteration_data)
                return

            # Handle step update
            UserInteraction.send_step_update(session_id, stage, message)

        except Exception as e:
            error_msg = UserInteraction.format_html_message(
                f"Error sending update: {str(e)}", "error"
            )
            message_broker.send_update(session_id, error_msg, "error")

# Global instance
user_interaction = UserInteraction()