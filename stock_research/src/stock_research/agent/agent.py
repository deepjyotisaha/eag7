import asyncio
import time
import os
import datetime
from .perception import extract_perception
from .memory import MemoryManager, MemoryItem
from .decision import generate_plan
from .action import execute_tool
from mcp import ClientSession
from typing import Optional
from .userinteraction.userinteraction import user_interaction
from ..backend.message_broker import message_broker
from .llm.llm import LLMManager
from .config.log_config import setup_logging

def log(stage: str, msg: str):
    """Simple console logging function"""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{stage}] {msg}")

max_steps = 10

class Agent:
    def __init__(self):
        self.memory = MemoryManager()
        self.logger = setup_logging(__name__)
        self.llm = LLMManager()
        self.llm.initialize()
        
    async def process_query(
        self,
        session: ClientSession,
        user_input: str,
        tools: list,
        tool_descriptions: str,
        session_id: Optional[str] = None
    ):
        """Process a query using an existing MCP session"""
        try:
            if not session_id:
                session_id = f"session-{int(time.time())}"
                
            query = user_input  # Store original intent
            step = 0
            
            # Track reasoning steps
            reasoning_steps = []
            
            user_interaction.send_update(
                session_id=session_id,
                stage="agent",
                message=f"Processing query: {user_input}"
            )
            
            while step < max_steps:
                # Extract perception
                perception = extract_perception(user_input)
                user_interaction.send_update(
                    session_id=session_id,
                    stage="perception",
                    message=f"Intent: {perception.intent}"
                )
                
                reasoning_steps.append({
                    "stage": "perception",
                    "action": "extract_intent",
                    "result": perception.intent
                })
                
                # Retrieve memories
                retrieved = self.memory.retrieve(
                    query=user_input,
                    top_k=3,
                    session_filter=session_id
                )
                user_interaction.send_update(
                    session_id=session_id,
                    stage="memory",
                    message=f"Retrieved {len(retrieved)} relevant data points"
                )
                
                reasoning_steps.append({
                    "stage": "memory",
                    "action": "retrieve_context",
                    "result": f"Found {len(retrieved)} relevant items"
                })
                
                # Generate plan
                plan = generate_plan(
                    perception,
                    retrieved,
                    tool_descriptions=tool_descriptions
                )
                user_interaction.send_update(
                    session_id=session_id,
                    stage="plan",
                    message="Generated analysis plan"
                )
                
                reasoning_steps.append({
                    "stage": "plan",
                    "action": "create_plan",
                    "result": plan
                })
                
                # Check for final answer
                if plan.startswith("FINAL_ANSWER:"):
                    final_result = plan.replace("FINAL_ANSWER:", "").strip()
                    
                    # Send iteration summary
                    user_interaction.send_update(
                        session_id=session_id,
                        stage="reasoning",
                        message="Completed analysis",
                        iteration_data={
                            "stage": "final",
                            "steps": reasoning_steps,
                            "result": final_result
                        }
                    )
                    
                    # Send final result
                    user_interaction.send_update(
                        session_id=session_id,
                        stage="agent",
                        message=final_result,
                        is_final=True,
                        raw_data={
                            "analysis_result": final_result,
                            "reasoning_steps": reasoning_steps,
                            "confidence": "high"
                        },
                        query_type="analysis"
                    )
                    break
                
                # Execute tool
                try:
                    result = await execute_tool(session, tools, plan)
                    
                    # Send tool execution update
                    user_interaction.send_update(
                        session_id=session_id,
                        stage="tool",
                        message=f"Using {result.tool_name}",
                        iteration_data={
                            "stage": "tool",
                            "tool_name": result.tool_name,
                            "action": result.arguments,
                            "result": result.result
                        }
                    )
                    
                    reasoning_steps.append({
                        "stage": "tool",
                        "tool_name": result.tool_name,
                        "action": result.arguments,
                        "result": result.result
                    })
                    
                    # Store result in memory
                    self.memory.add(MemoryItem(
                        text=f"Tool call: {result.tool_name} with {result.arguments}, got: {result.result}",
                        type="tool_output",
                        tool_name=result.tool_name,
                        user_query=user_input,
                        tags=[result.tool_name],
                        session_id=session_id
                    ))
                    
                    # Update input for next iteration
                    user_input = f"Original task: {query}\nPrevious output: {result.result}\nWhat should I do next?"
                    
                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    user_interaction.send_update(
                        session_id=session_id,
                        stage="error",
                        message=error_msg,
                        is_final=True,
                        raw_data={"error": error_msg, "steps": reasoning_steps},
                        query_type="error"
                    )
                    break
                
                step += 1
                
        except Exception as e:
            error_msg = f"Query processing error: {str(e)}"
            user_interaction.send_update(
                session_id=session_id,
                stage="error",
                message=error_msg,
                is_final=True,
                raw_data={"error": error_msg},
                query_type="error"
            )
            raise
            
        finally:
            message_broker.close_session(session_id)

# Global agent instance
agent = Agent()

# For backwards compatibility and direct script usage
async def main(user_input: str):
    """
    Legacy entry point - prints warning and exits
    """
    log("warning", "Direct agent execution is deprecated. Please use the Agent class through the server manager.")
    return

if __name__ == "__main__":
    log("warning", "Direct script execution is deprecated. Please start the Flask server instead.")

# Find the ASCII values of characters in INDIA and then return sum of exponentials of those values.
# How much Anmol singh paid for his DLF apartment via Capbridge? 
# What do you know about Don Tapscott and Anthony Williams?
# What is the relationship between Gensol and Go-Auto?