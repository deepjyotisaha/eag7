import asyncio
from ..agent.agent import agent
from .message_broker import message_broker
import sys
import types
from .server_manager import mcp_server
import threading
from ..agent.userinteraction.userinteraction import user_interaction
import traceback

async def process_agent_query(session_id: str, query: str):
    """Process a query using the agent instance"""
    try:
        if not mcp_server.initialized:
            await user_interaction.send_update(
                session_id=session_id,
                stage="agent",
                message="Waiting for server initialization..."
            )
            if not mcp_server.wait_for_initialization():
                raise Exception("Server initialization timeout")

        try:
            # Directly pass the server_manager to agent
            await agent.process_query(
                server_manager=mcp_server,
                user_input=query,
                session_id=session_id
            )
            
        except Exception as e:
            error_details = traceback.format_exc()
            error_msg = f"Error during analysis: {str(e)}\n\nDetails:\n{error_details}"
            print(error_msg)
            await user_interaction.send_update(
                session_id=session_id,
                stage="error",
                message=error_msg,
                is_final=True,
                raw_data={"error": str(e), "traceback": error_details},
                query_type="error"
            )
            
    finally:
        message_broker.close_session(session_id)

def start_stock_analysis(session_id: str, query: str):
    """Start stock analysis in a background thread"""
    def thread_target():
        asyncio.run(process_agent_query(session_id, query))

    thread = threading.Thread(target=thread_target)
    thread.start()