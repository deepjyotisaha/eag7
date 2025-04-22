import asyncio
from ..agent.agent import main as agent_main, log as agent_log
from .message_broker import message_broker
import sys
import types

async def process_stock_query(session_id: str, query: str):
    """
    Process a stock query using the agent and send updates via message broker
    """
    try:
        # Store original log function
        original_log = agent_log

        # Create a new log function that sends updates to the message broker
        def new_log(stage: str, msg: str):
            # Still call original log for console output
            original_log(stage, msg)
            
            # Convert agent logs to user updates
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

        # Replace the log function in the agent module
        sys.modules[agent_log.__module__].log = new_log

        print("Running agent with query:", query)

        # Run the agent
        await agent_main(query)

    except Exception as e:
        message_broker.send_update(
            session_id, 
            f"Error during analysis: {str(e)}", 
            "final"
        )
    finally:
        # Restore original log function
        sys.modules[agent_log.__module__].log = original_log
        message_broker.close_session(session_id)

def start_stock_analysis(session_id: str, query: str):
    """Start stock analysis in a background thread"""
    async def run_analysis():
        await process_stock_query(session_id, query)

    def thread_target():
        asyncio.run(run_analysis())

    import threading
    thread = threading.Thread(target=thread_target)
    thread.start()