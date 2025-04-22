import asyncio
from ..agent.agent import agent, log as agent_log
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
        
        original_log = agent_log

        def new_log(stage: str, msg: str):
            original_log(stage, msg)
            print(f"[{stage}] {msg}")  # Add direct console logging
            
            if stage == "perception":
                message_broker.send_update(session_id, f"Understanding query: {msg}")
            elif stage == "memory":
                message_broker.send_update(session_id, f"Analyzing historical data: {msg}")
            elif stage == "plan":
                message_broker.send_update(session_id, f"Planning analysis: {msg}")
            elif stage == "tool":
                message_broker.send_update(session_id, f"Gathering market data: {msg}")
            elif stage == "agent":
                if msg.startswith("✅ FINAL RESULT:"):
                    final_result = msg.replace("✅ FINAL RESULT:", "").strip()
                    message_broker.send_update(session_id, final_result, "final")
                else:
                    message_broker.send_update(session_id, msg)

        sys.modules[agent_log.__module__].log = new_log

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
            
        finally:
            sys.modules[agent_log.__module__].log = original_log

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