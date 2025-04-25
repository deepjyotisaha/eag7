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
            # Create a wrapper function that will be executed with the session
            async def process_with_session(session):
                # Extract just the tool objects from the registry
                tools = [info['tool'] for info in mcp_server.tool_registry.values()]
                return await agent.process_query(
                    session=session,
                    user_input=query,
                    tools=tools,  # Pass the actual tool objects
                    tool_descriptions=mcp_server.get_tools_description(),
                    session_id=session_id
                )
            
            # Execute using the RAG server since it's the main processing server
            await mcp_server.execute_command('rag', process_with_session)
            
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