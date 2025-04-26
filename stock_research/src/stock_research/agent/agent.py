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
from .action import parse_function_call

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
        server_manager,  # Now receives server_manager instead of session
        user_input: str,
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
                
                # Generate plan using all available tools
                self.logger.info("Generating plan...")
                plan = generate_plan(
                    perception,
                    retrieved,
                    tool_descriptions=server_manager.get_tools_description()
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
                    
                    # Store final result in memory using 'fact' type
                    self.memory.add(MemoryItem(
                        text=f"Final answer: {final_result}",
                        type="final_result",
                        user_query=query,  # original query
                        tags=["final_answer"],
                        session_id=session_id
                    ))
                    
                    # Send iteration summary and final result
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
                
                try:
                    self.logger.info("Executing tool...")
                    # Extract tool name and arguments from plan
                    if plan.startswith("FUNCTION_CALL:"):
                        tool_name, args = parse_function_call(plan)

                        # Get the correct server for this tool
                        if tool_name not in server_manager.tool_registry:
                            raise ValueError(f"Unknown tool: {tool_name}")
                            
                        tool_info = server_manager.tool_registry[tool_name]
                        server_name = tool_info['server']
                        
                        # Wrap arguments in input field for math tools
                        if server_name == 'math':  # All math tools need input wrapper
                            tool_args = {"input": args}
                        else:
                            tool_args = args
                        
                        # Execute the tool in its correct server context
                        async def execute_tool_in_context(session):
                            return await session.call_tool(tool_name, arguments=tool_args)
                        
                        result = await server_manager.execute_command(server_name, execute_tool_in_context)
                        
                        self.logger.info(f"Tool execution result: {result}")
                        
                        # Add the result to reasoning steps
                        reasoning_steps.append({
                            "stage": "tool",
                            "tool_name": tool_name,
                            "action": tool_args,
                            "result": str(result)
                        })
                        
                        # Store result in memory
                        self.memory.add(MemoryItem(
                            text=f"Tool call: {tool_name} with {tool_args}, got: {result}",
                            type="tool_output",
                            tool_name=tool_name,
                            user_query=user_input,
                            tags=[tool_name],
                            session_id=session_id
                        ))
                        
                        # Send iteration summary
                        await user_interaction.send_iteration_summary(
                            session_id=session_id,
                            iteration_data={
                                "stage": "tool_execution",
                                "tool_name": tool_name,
                                "action": tool_args,
                                "result": str(result)
                            },
                            llm_manager=self.llm
                        )
                        
                        # Send step update
                        #await user_interaction.send_update(
                        #    session_id=session_id,
                        #    stage="tool",
                        #    message=f"Executed {tool_name}",
                        #    iteration_data={
                        #        "stage": "tool",
                        #        "tool_name": tool_name,
                        #        "action": tool_args,
                        #        "result": str(result)
                        #    }
                        #)
                        
                        user_input = f"Original task: {query}\nPrevious output: {result}\nWhat should I do next?"
                        
                    else:
                        raise ValueError("Plan must start with FUNCTION_CALL:")
                    
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

def extract_tool_name_from_plan(plan: str) -> str:
    """Extract the tool name from the plan string.
    
    Args:
        plan: A plan string in the format "FUNCTION_CALL: tool_name|a=7|b=10"
        
    Returns:
        The tool name
    """
    if not plan.startswith("FUNCTION_CALL:"):
        raise ValueError("Plan must start with FUNCTION_CALL:")
        
    parts = plan.split(":", 1)[1].strip().split("|")
    return parts[0].strip()

def extract_tool_args_from_plan(plan: str) -> dict:
    """Extract the tool arguments from the plan string.
    
    Args:
        plan: A plan string in the format "FUNCTION_CALL: tool_name|a=7|b=10"
        
    Returns:
        Dictionary of parameters, e.g. {"a": 7, "b": 10}
    """
    if not plan.startswith("FUNCTION_CALL:"):
        raise ValueError("Plan must start with FUNCTION_CALL:")
        
    parts = plan.split(":", 1)[1].strip().split("|")
    
    # Skip the tool name and process parameters
    params = {}
    for part in parts[1:]:  # Skip the first part (tool name)
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            
            # Try to convert numeric values
            try:
                if "." in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                # Keep as string if not numeric
                pass
                
            params[key] = value
            
    return params

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