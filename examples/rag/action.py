from typing import Dict, Any, Union
from pydantic import BaseModel
from mcp import ClientSession
import ast

# Optional: import log from agent if shared, else define locally
try:
    from agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{stage}] {msg}")


class ToolCallResult(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Union[str, list, dict]
    raw_response: Any


def parse_function_call(response: str) -> tuple[str, Dict[str, Any]]:
    """Parses FUNCTION_CALL string into tool name and arguments."""
    try:
        if not response.startswith("FUNCTION_CALL:"):
            raise ValueError("Not a valid FUNCTION_CALL")

        _, function_info = response.split(":", 1)
        parts = [p.strip() for p in function_info.split("|")]
        func_name, param_parts = parts[0], parts[1:]

        result = {}
        for part in param_parts:
            if "=" not in part:
                raise ValueError(f"Invalid param: {part}")
            key, value = part.split("=", 1)

            try:
                parsed_value = ast.literal_eval(value)
            except Exception:
                parsed_value = value.strip()

            # Handle nested keys
            keys = key.split(".")
            current = result
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = parsed_value

        log("parser", f"Parsed: {func_name} → {result}")
        return func_name, result

    except Exception as e:
        log("parser", f"❌ Failed to parse FUNCTION_CALL: {e}")
        raise


async def execute_tool(session: ClientSession, tools: list[Any], response: str) -> ToolCallResult:
    """Executes a FUNCTION_CALL via MCP tool session."""
    tool_name = "unknown"
    arguments = {}
    
    try:
        print(f"Starting tool execution for response: {response}")
        tool_name, arguments = parse_function_call(response)
        print(f"Parsed tool call: {tool_name} with args {arguments}")

        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found in registered tools")

        log("tool", f"⚙️ Calling '{tool_name}' with: {arguments}")
        print(f"Calling tool {tool_name} with session {id(session)}")
        
        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            print(f"Tool call completed, result: {result}")
            log("tool", f"Raw result from tool: {result}")
        except Exception as e:
            print(f"Tool call failed: {str(e)}")
            log("tool", f"❌ Tool call failed: {str(e)}")
            raise

        if result is None:
            log("tool", "⚠️ Tool returned None")
            out = "No result returned from tool"
        elif hasattr(result, 'content'):
            if isinstance(result.content, list):
                out = [getattr(item, 'text', str(item)) for item in result.content]
            else:
                out = getattr(result.content, 'text', str(result.content))
            log("tool", f"Processed content result: {out}")
        else:
            out = str(result)
            log("tool", f"Converted result to string: {out}")

        print(f"Tool execution completed successfully: {out}")
        log("tool", f"✅ {tool_name} result: {out}")
        
        return ToolCallResult(
            tool_name=tool_name,
            arguments=arguments,
            result=out,
            raw_response=result
        )

    except Exception as e:
        error_msg = f"⚠️ Execution failed for '{response}': {str(e)}"
        print(error_msg)
        log("tool", error_msg)
        return ToolCallResult(
            tool_name=tool_name,
            arguments=arguments,
            result=f"Error: {str(e)}",
            raw_response=None
        )
