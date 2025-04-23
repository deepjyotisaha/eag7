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

def log(stage: str, msg: str):
    """Simple console logging function"""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{stage}] {msg}")

max_steps = 3

class Agent:
    def __init__(self):
        self.memory = MemoryManager()
        
    async def process_query(
        self,
        session: ClientSession,
        user_input: str,
        tools: list,
        tool_descriptions: str,
        session_id: Optional[str] = None
    ):
        """
        Process a query using an existing MCP session
        
        Args:
            session: Active MCP ClientSession
            user_input: User's query
            tools: List of available tools
            tool_descriptions: Formatted tool descriptions
            session_id: Optional session identifier for memory management
        """
        try:
            if not session_id:
                session_id = f"session-{int(time.time())}"
                
            query = user_input  # Store original intent
            step = 0
            
            log("agent", f"Processing query: {user_input}")
            user_interaction.send_update(session_id, "agent", f"Processing your query: {user_input}")
            
            while step < max_steps:
                log("loop", f"Step {step + 1} started")
                
                # Extract perception
                perception = extract_perception(user_input)
                log("perception", f"Intent: {perception.intent}, Tool hint: {perception.tool_hint}")
                user_interaction.send_update(session_id, "perception", f"Intent: {perception.intent}")
                
                # Retrieve relevant memories
                retrieved = self.memory.retrieve(
                    query=user_input,
                    top_k=3,
                    session_filter=session_id
                )
                log("memory", f"Retrieved {len(retrieved)} relevant memories")
                user_interaction.send_update(session_id, "memory", f"Retrieved {len(retrieved)} relevant memories")
                
                # Generate plan
                plan = generate_plan(
                    perception,
                    retrieved,
                    tool_descriptions=tool_descriptions
                )
                log("plan", f"Plan generated: {plan}")
                user_interaction.send_update(session_id, "plan", "Generated analysis plan")
                
                # Check if we have a final answer
                if plan.startswith("FINAL_ANSWER:"):
                    final_result = plan.replace("FINAL_ANSWER:", "").strip()
                    log("agent", f"✅ FINAL RESULT: {final_result}")
                    user_interaction.send_update(session_id, "agent", final_result, is_final=True)
                    break
                
                # Execute tool
                try:
                    result = await execute_tool(session, tools, plan)
                    log("tool", f"{result.tool_name} returned: {result.result}")
                    user_interaction.send_update(session_id, "tool", f"Using {result.tool_name} to analyze data")
                    
                    # Store the result in memory
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
                    error_msg = f"Tool execution failed: {e}"
                    log("error", error_msg)
                    user_interaction.send_update(session_id, "agent", error_msg, is_final=True)
                    break
                
                step += 1
                
        except Exception as e:
            error_msg = f"Query processing error: {e}"
            log("error", error_msg)
            user_interaction.send_update(session_id, "agent", error_msg, is_final=True)
            raise
            
        finally:
            log("agent", "Query processing complete")

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