# src/stock_research/backend/server_manager.py
import asyncio
import threading
from typing import Optional
import subprocess
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os
from queue import Queue
from concurrent.futures import Future

class MCPServerManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPServerManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = False
            self.session: Optional[ClientSession] = None
            self.tools = None
            self.tool_descriptions = None
            self._init_lock = threading.Lock()
            self._init_event = threading.Event()
            self._session_lock = threading.Lock()
            self._command_queue = Queue()
            self._response_futures = {}
            self._loop = None
    
    def _run_mcp_server(self):
        """Run MCP server in a separate thread"""
        async def server_loop():
            # Get the absolute path to example3.py
            current_dir = os.path.dirname(os.path.abspath(__file__))
            example3_path = os.path.join(
                current_dir, 
                "..", 
                "agent",
                "example3.py"
            )
            
            server_params = StdioServerParameters(
                command="uv",
                args=["run", example3_path]
            )
            
            while True:
                try:
                    print("Starting MCP server connection...")
                    async with stdio_client(server_params) as (read, write):
                        print("MCP client connected, creating session...")
                        async with ClientSession(read, write) as session:
                            print("Initializing MCP session...")
                            await session.initialize()
                            print("MCP session initialized")
                            
                            # Get and store tools
                            tools_result = await session.list_tools()
                            self.tools = tools_result.tools
                            self.tool_descriptions = "\n".join(
                                f"- {tool.name}: {getattr(tool, 'description', 'No description')}" 
                                for tool in self.tools
                            )
                            
                            with self._session_lock:
                                self.session = session
                                self.initialized = True
                                self._init_event.set()
                                print(f"MCP server ready with {len(self.tools)} tools")
                            
                            # Keep the session alive and handle requests
                            while True:
                                try:
                                    # Process any pending commands
                                    while not self._command_queue.empty():
                                        cmd, future = self._command_queue.get_nowait()
                                        try:
                                            result = await cmd(session)
                                            future.set_result(result)
                                        except Exception as e:
                                            future.set_exception(e)
                                    
                                    # Periodic health check
                                    await session.list_tools()
                                    await asyncio.sleep(1)
                                except Exception as e:
                                    print(f"Session health check failed: {e}")
                                    break
                                    
                except Exception as e:
                    print(f"MCP server error: {str(e)}")
                    self.initialized = False
                    self._init_event.clear()
                    await asyncio.sleep(5)  # Wait before retrying
                    
        def run_async_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(server_loop())
            
        thread = threading.Thread(target=run_async_loop, daemon=True)
        thread.start()
    
    async def execute_command(self, cmd):
        """Execute a command in the server thread"""
        future = Future()
        self._command_queue.put((cmd, future))
        
        while not future.done():
            await asyncio.sleep(0.1)
            
        return future.result()
    
    def start(self):
        """Start the MCP server if not already running"""
        with self._init_lock:
            if not self.initialized:
                self._run_mcp_server()
    
    def get_session(self) -> Optional[ClientSession]:
        """Get the current session with lock"""
        with self._session_lock:
            return self.session
    
    def wait_for_initialization(self, timeout=30):
        """Wait for server to initialize"""
        return self._init_event.wait(timeout)
    
    def get_tools_description(self) -> str:
        """Get formatted description of available tools"""
        if not self.initialized:
            return "Server not initialized"
        return "Available Tools:\n" + self.tool_descriptions

# Global instance
mcp_server = MCPServerManager()

async def process_agent_query(session: ClientSession, query: str):
    """Process a query using the global agent instance"""
    await agent.process_query(
        session=session,
        user_input=query,
        tools=mcp_server.tools,
        tool_descriptions=mcp_server.tool_descriptions,
        session_id=f"stock-{int(time.time())}"
    )