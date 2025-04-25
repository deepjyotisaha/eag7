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

#def log(stage: str, msg: str):
#    """Simple console logging function"""
#    now = datetime.datetime.now().strftime("%H:%M:%S")
#    print(f"[{now}] [{stage}] {msg}")

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
        try:
            if not session_id:
                session_id = f"session-{int(time.time())}"
                
            query = user_input
            step = 0
            reasoning_steps = []
            
            self.logger.info(f"Processing query: {user_input}")
            
            await user_interaction.send_update(
                session_id=session_id,
                stage="agent",
                message=f"Processing query: {user_input}"
            )
            
            while step < max_steps:
                self.logger.info(f"Step {step + 1} started")
                
                # Extract perception
                self.logger.info("Generating perception...")
                perception = extract_perception(user_input)
                self.logger.info(f"Intent: {perception.intent}, Tool hint: {perception.tool_hint}, Entities: {perception.entities}")
                await user_interaction.send_update(
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
                self.logger.info(f"Retrieved {len(retrieved)} memories")
                await user_interaction.send_update(
                    session_id=session_id,
                    stage="memory",
                    message=f"Retrieved {len(retrieved)} relevant data points"
                )

                self.logger.info("Retrieved memories Content: %s", retrieved)
                
                reasoning_steps.append({
                    "stage": "memory",
                    "action": "retrieve_context",
                    "result": f"Found {len(retrieved)} relevant items"
                })
                
                # Generate plan
                self.logger.info("Generating plan...")
                #self.logger.info("Perception: %s", perception)
                #self.logger.info("Retrieved: %s", retrieved)
                #self.logger.info("Tool descriptions: %s", tool_descriptions)
                plan = generate_plan(
                    perception,
                    retrieved,
                    tool_descriptions=tool_descriptions
                )
                self.logger.info(f"Plan generated: {plan}")
                await user_interaction.send_update(
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
                    self.logger.info(f"Final result: {final_result}")
                    
                    # Send iteration summary
                    await user_interaction.send_update(
                        session_id=session_id,
                        stage="reasoning",
                        message="Completed analysis",
                        iteration_data={
                            "stage": "final",
                            "steps": reasoning_steps,
                            "result": final_result
                        },
                        llm_manager=self.llm
                    )
                    
                    # Send final result
                    await user_interaction.send_update(
                        session_id=session_id,
                        stage="agent",
                        message=final_result,
                        is_final=True,
                        raw_data={
                            "analysis_result": final_result,
                            "reasoning_steps": reasoning_steps,
                            "confidence": "high"
                        },
                        query_type="analysis",
                        llm_manager=self.llm
                    )
                    break
                
                # Execute tool
                try:
                    self.logger.info("Executing tool...")
                    result = await execute_tool(session, tools, plan)
                    self.logger.info(f"Tool execution: {result.tool_name} -> {result.result}")
                    
                    await user_interaction.send_update(
                        session_id=session_id,
                        stage="tool",
                        message=f"Using {result.tool_name}",
                        iteration_data={
                            "stage": "tool",
                            "tool_name": result.tool_name,
                            "action": result.arguments,
                            "result": result.result
                        },
                        llm_manager=self.llm
                    )
                    
                    reasoning_steps.append({
                        "stage": "tool",
                        "tool_name": result.tool_name,
                        "action": result.arguments,
                        "result": result.result
                    })
                    self.logger.info("Adding details in memory")

                    # Store result in memory
                    self.memory.add(MemoryItem(
                        text=f"Tool call: {result.tool_name} with {result.arguments}, got: {result.result}",
                        type="tool_output",
                        tool_name=result.tool_name,
                        user_query=user_input,
                        tags=[result.tool_name],
                        session_id=session_id
                    ))
                    
                    user_input = f"Original task: {query}\nPrevious output: {result.result}\nWhat should I do next?"
                    
                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    self.logger.error(error_msg)
                    await user_interaction.send_update(
                        session_id=session_id,
                        stage="error",
                        message=error_msg,
                        is_final=True,
                        raw_data={"error": str(e), "steps": reasoning_steps},
                        query_type="error",
                        llm_manager=self.llm
                    )
                    break
                
                step += 1
                
        except Exception as e:
            error_msg = f"Query processing error: {str(e)}"
            self.logger.error(error_msg)
            await user_interaction.send_update(
                session_id=session_id,
                stage="error",
                message=error_msg,
                is_final=True,
                raw_data={"error": str(e)},
                query_type="error",
                llm_manager=self.llm
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
    logger = setup_logging(__name__)
    logger.warning("warning", "Direct agent execution is deprecated. Please use the Agent class through the server manager.")
    return

if __name__ == "__main__":
    logger = setup_logging(__name__)
    logger.warning("warning", "Direct script execution is deprecated. Please start the Flask server instead.")

# Find the ASCII values of characters in INDIA and then return sum of exponentials of those values.
# How much Anmol singh paid for his DLF apartment via Capbridge? 
# What do you know about Don Tapscott and Anthony Williams?
# What is the relationship between Gensol and Go-Auto?