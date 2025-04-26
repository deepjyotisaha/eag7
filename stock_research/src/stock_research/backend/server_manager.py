# src/stock_research/backend/server_manager.py
import asyncio
import threading
from typing import Optional, Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os
from queue import Queue
from concurrent.futures import Future
from pathlib import Path
from ..agent.userinteraction import userinteraction
from .message_broker import message_broker
from ..agent import agent
import traceback

class MCPServerManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPServerManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            current_dir = Path(__file__).parent.parent
            # Initialize server states with absolute paths
            self.servers = {
                'math': {
                    'initialized': False,
                    'session': None,
                    'tools': None,
                    'script_path': str(current_dir / "agent" / "mcp_server" / "math" / "mcp_math_server.py"),
                    'log_file': 'mcp_math_server.log',
                    'args': []
                },
                'rag': {
                    'initialized': False,
                    'session': None,
                    'tools': None,
                    'script_path': str(current_dir / "agent" / "mcp_server" / "rag" / "mcp_rag_server.py"),
                    'log_file': 'mcp_rag_server.log',
                    'args': []
                },
                'gmail': {
                    'initialized': False,
                    'session': None,
                    'tools': None,
                    'script_path': str(current_dir / "agent" / "mcp_server" / "gmail" / "src" / "gmail" / "gmail_mcp_server.py"),
                    'log_file': 'mcp_gmail_server.log',
                    'args': [],
                    'creds_file_path': str(current_dir / "agent" /  ".google" / "client_creds.json"),
                    'token_path': str(current_dir / "agent"  / ".google" / "app_tokens.json")
                }
            }
            # Tool registry maps tool names to their server and tool object
            self.tool_registry = {}  # {tool_name: {'server': server_name, 'tool': tool_obj}}
            
            self._init_lock = threading.Lock()
            self._init_event = threading.Event()
            self._session_locks = {name: threading.Lock() for name in self.servers}
            self._command_queues = {name: Queue() for name in self.servers}
            self._loops = {}
            
    def _register_tools(self, server_name: str, tools: list):
        """Register tools from a server in the tool registry"""
        for tool in tools:
            self.tool_registry[tool.name] = {
                'server': server_name,
                'tool': tool,
                'description': getattr(tool, 'description', 'No description')
            }
            
    def _run_mcp_server(self):
        """Run MCP servers in separate threads"""
        async def server_loop(server_name: str):
            server_config = self.servers[server_name]
            script_path = server_config['script_path']
            
            # Build server parameters based on server type
            base_args = ["run", script_path]
            
            # Add Gmail-specific arguments if it's the Gmail server
            if server_name == 'gmail':
                base_args.extend([
                    f"--creds-file-path={server_config['creds_file_path']}",
                    f"--token-path={server_config['token_path']}"
                ])
            
            server_params = StdioServerParameters(
                command="uv",
                args=base_args
            )
            
            while True:
                try:
                    print(f"Starting {server_name.upper()} MCP server connection...")
                    print(f"Using command: uv {' '.join(base_args)}")  # Debug print
                    async with stdio_client(server_params) as (read, write):
                        print(f"{server_name.upper()} MCP client connected, creating session...")
                        async with ClientSession(read, write) as session:
                            try:
                                print(f"Initializing {server_name.upper()} MCP session...")
                                await asyncio.wait_for(session.initialize(), timeout=30.0)
                                print(f"{server_name.upper()} MCP session initialized")
                                
                                # Get and store tools
                                tools_result = await asyncio.wait_for(session.list_tools(), timeout=30.0)
                                with self._session_locks[server_name]:
                                    self.servers[server_name]['session'] = session
                                    self.servers[server_name]['tools'] = tools_result.tools
                                    self.servers[server_name]['initialized'] = True
                                    # Register tools in the tool registry
                                    self._register_tools(server_name, tools_result.tools)
                                    print(f"{server_name.upper()} MCP server ready with {len(tools_result.tools)} tools")
                                    
                                    # Check if all servers are initialized
                                    if all(server['initialized'] for server in self.servers.values()):
                                        self._init_event.set()
                                
                                # Keep the session alive and handle requests
                                while True:
                                    try:
                                        # Process any pending commands
                                        while not self._command_queues[server_name].empty():
                                            cmd, future = self._command_queues[server_name].get_nowait()
                                            try:
                                                # Increase timeout to 120 seconds for long-running operations
                                                result = await asyncio.wait_for(cmd(session), timeout=120.0)
                                                future.set_result(result)
                                            except Exception as e:
                                                future.set_exception(e)
                                                print(f"Error executing command on {server_name}: {e}")
                                        
                                        # Periodic health check
                                        await asyncio.wait_for(session.list_tools(), timeout=5.0)
                                        await asyncio.sleep(1)
                                    except asyncio.TimeoutError:
                                        print(f"{server_name.upper()} health check timeout")
                                        break
                                    except Exception as e:
                                        print(f"{server_name.upper()} session health check failed: {e}")
                                        break
                                        
                            except asyncio.TimeoutError:
                                print(f"{server_name.upper()} initialization timeout")
                                raise
                            except Exception as e:
                                print(f"{server_name.upper()} session initialization error: {e}")
                                raise
                                    
                except Exception as e:
                    print(f"{server_name.upper()} MCP server error: {str(e)}")
                    with self._session_locks[server_name]:
                        self.servers[server_name]['initialized'] = False
                        self.servers[server_name]['session'] = None
                        self._init_event.clear()
                    await asyncio.sleep(5)  # Wait before retrying
                    
        def run_async_loop(server_name: str):
            loop = asyncio.new_event_loop()
            self._loops[server_name] = loop
            asyncio.set_event_loop(loop)
            loop.run_until_complete(server_loop(server_name))
            
        # Start each server in its own thread
        for server_name in self.servers:
            thread = threading.Thread(
                target=run_async_loop,
                args=(server_name,),
                daemon=True,
                name=f"{server_name}_server_thread"
            )
            thread.start()
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a tool by name without needing to know which server it belongs to"""
        if tool_name not in self.tool_registry:
            raise ValueError(f"Unknown tool: {tool_name}")
            
        tool_info = self.tool_registry[tool_name]
        server_name = tool_info['server']
        
        if not self.servers[server_name]['initialized']:
            raise RuntimeError(f"Server for tool {tool_name} is not initialized")
            
        async def execute(session):
            return await session.execute_tool(tool_name, kwargs)
            
        return await self.execute_command(server_name, execute)
    
    async def execute_command(self, server_name: str, cmd):
        """Execute a command in the specified server thread"""
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
            
        if not self.servers[server_name]['initialized']:
            raise RuntimeError(f"{server_name.upper()} server not initialized")
            
        future = Future()
        self._command_queues[server_name].put((cmd, future))
        
        while not future.done():
            await asyncio.sleep(0.1)
            
        return future.result()
    
    def start(self):
        """Start all MCP servers if not already running"""
        with self._init_lock:
            if not all(server['initialized'] for server in self.servers.values()):
                self._run_mcp_server()
    
    def get_session(self, server_name: str) -> Optional[ClientSession]:
        """Get the session for a specific server with lock"""
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
            
        with self._session_locks[server_name]:
            return self.servers[server_name]['session']
    
    def wait_for_initialization(self, timeout=120):  # Increased timeout to 120 seconds
        """Wait for all servers to initialize"""
        return self._init_event.wait(timeout)
    
    def get_tools_description(self) -> str:
        """Get formatted description of all available tools"""
        if not self.tool_registry:
            return "No tools available"
            
        tool_list = []
        for name, info in sorted(self.tool_registry.items()):
            tool = info['tool']
            desc = [f"- {name}: {info['description']}"]
            
            # Add input schema if available
            if hasattr(tool, 'inputSchema'):
                desc.append("  Parameters:")
                for param_name, param_info in tool.inputSchema['properties'].items():
                    desc.append(f"    - {param_name}: {param_info.get('description', 'No description')}")
                    if param_name in tool.inputSchema.get('required', []):
                        desc[-1] += " (required)"
                    
            tool_list.extend(desc)
            
        return "\n".join(tool_list)

    @property
    def initialized(self) -> bool:
        """Check if all servers are initialized"""
        return all(server['initialized'] for server in self.servers.values())

# Global instance
mcp_server = MCPServerManager()

