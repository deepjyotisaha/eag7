import asyncio
from ..agent.agent import agent
from .message_broker import message_broker
import sys
import types
from .server_manager import mcp_server
import threading

async def process_agent_query(session_id: str, query: str):
    """Process a query using the agent instance"""
    try:
        if not mcp_server.initialized:
            message_broker.send_update(session_id, "Waiting for server initialization...")
            if not mcp_server.wait_for_initialization():
                raise Exception("Server initialization timeout")

        try:
            async def process_with_session(session):
                return await agent.process_query(
                    session=session,
                    user_input=query,
                    tools=mcp_server.tools,
                    tool_descriptions=mcp_server.tool_descriptions,
                    session_id=session_id
                )
            
            await mcp_server.execute_command(process_with_session)
            
        except Exception as e:
            error_msg = f"Error during analysis: {str(e)}"
            print(error_msg)
            message_broker.send_update(session_id, error_msg, "final")
            
    finally:
        message_broker.close_session(session_id)

def start_stock_analysis(session_id: str, query: str):
    """Start stock analysis in a background thread"""
    def thread_target():
        asyncio.run(process_agent_query(session_id, query))

    thread = threading.Thread(target=thread_target)
    thread.start()