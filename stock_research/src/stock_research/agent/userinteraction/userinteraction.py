from typing import Optional
from ...backend.message_broker import message_broker

class UserInteraction:
    @staticmethod
    def send_update(session_id: str, stage: str, message: str, is_final: bool = False) -> None:
        """
        Send updates to the user through the message broker
        
        Args:
            session_id: The unique session identifier
            stage: Current processing stage (perception, memory, plan, tool, agent)
            message: The message to send to the user
            is_final: Whether this is the final result
        """
        if not session_id:
            return
            
        formatted_message = message
        
        if stage == "perception":
            formatted_message = f"Understanding query: {message}"
        elif stage == "memory":
            formatted_message = f"Analyzing historical data: {message}"
        elif stage == "plan":
            formatted_message = f"Planning analysis: {message}"
        elif stage == "tool":
            formatted_message = f"Gathering market data: {message}"
            
        if is_final:
            message_broker.send_update(session_id, formatted_message, "final")
        else:
            message_broker.send_update(session_id, formatted_message)

# Global instance for easy access
user_interaction = UserInteraction()