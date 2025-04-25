from flask import Flask, request, Response, stream_with_context, jsonify
from flask_cors import CORS
import json
import re
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED
from .message_broker import message_broker
from .server_manager import mcp_server
from .stock_agent_handler import start_stock_analysis

app = Flask(__name__)
CORS(app)

def extract_stock_symbol(query: str) -> str:
    """Extract stock symbol from query text"""
    # Simple regex to find stock symbols (can be enhanced)
    matches = re.findall(r'\b[A-Z]{1,5}\b', query.upper())
    return matches[0] if matches else None

# Initialize services at startup instead of before_first_request
def initialize_services():
    """Initialize services"""
    try:
        # Start MCP server
        mcp_server.start()
        
        # Wait for initialization with increased timeout
        if not mcp_server.wait_for_initialization(timeout=120):
            app.logger.error("Failed to initialize MCP server: Timeout after 120 seconds")
            return
        
        # Log available tools
        tools_desc = mcp_server.get_tools_description()
        app.logger.info("MCP Server initialized successfully")
        app.logger.info(f"Available tools:\n{tools_desc}")
        
    except Exception as e:
        app.logger.error(f"Failed to initialize services: {str(e)}")

# Initialize services when the module is imported
initialize_services()

def create_html_panel(title, content, border_style="step"):
    """Create an HTML panel with the same style as send_step_update"""
    # Style configurations matching UserInteraction.STYLES
    STYLES = {
        "step": {
            "padding": "8px 12px",
            "bg_color": "#ffffff",
            "margin": "8px",
            "border_color": "rgba(37, 99, 235, 0.15)",  # Light blue
            "text_color": "black"
        },
        "iteration": {
            "padding": "12px 16px",
            "bg_color": "#ffffff",
            "margin": "12px",
            "border_color": "rgba(5, 150, 105, 0.15)",  # Light green
            "text_color": "black"
        },
        "final": {
            "padding": "16px 20px",
            "bg_color": "#ffffff",
            "margin": "16px",
            "border_color": "rgba(109, 40, 217, 0.15)",  # Light purple
            "text_color": "black"
        }
    }
    
    style = STYLES.get(border_style, STYLES["step"])
    
    return f"""
    <div class="message-container" style="
        font-family: system-ui, -apple-system, sans-serif;
        padding: {style['padding']};
        background-color: {style['bg_color']};
        border-radius: 8px;
        margin-bottom: {style['margin']};
        border: 1px solid {style['border_color']};
        color: {style['text_color']};
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
    ">
        <div style="
            border-left: 2px solid {style['border_color']};
            padding-left: 10px;
        ">
            <div style="font-weight: bold; margin-bottom: 8px;">{title}</div>
            <div>{content}</div>
        </div>
    </div>
    """

def create_html_table(title, headers, rows, style="magenta"):
    """Create an HTML table with the same style as userinteraction.py"""
    # Map Rich colors to CSS colors
    color_map = {
        "cyan": "#00ffff",
        "blue": "#0000ff",
        "magenta": "#ff00ff",
        "green": "#00ff00",
        "yellow": "#ffff00",
        "red": "#ff0000"
    }
    
    border_color = color_map.get(style, style)
    
    table_html = f"""
    <div class="table-container" style="margin: 10px 0;">
        <div class="table-title" style="color: {border_color}; font-weight: bold; margin-bottom: 10px;">
            {title}
        </div>
        <table style="width: 100%; border-collapse: separate; border-spacing: 0; border: 2px solid {border_color}; border-radius: 8px;">
            <thead>
                <tr>
                    {''.join(f'<th style="padding: 10px; border-bottom: 1px solid {border_color}; color: {border_color};">{header}</th>' for header in headers)}
                </tr>
            </thead>
            <tbody>
                {''.join(f'<tr>{"".join(f"<td style=\'padding: 10px; color: #333333;\'>{cell}</td>" for cell in row)}</tr>' for row in rows)}
            </tbody>
        </table>
    </div>
    """
    return table_html

@app.route('/status')
def status():
    """Get server status and available tools with formatted HTML response"""
    # Create single panel with welcome message and capabilities
    content = f"""
    <div style="display: flex; flex-direction: column; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">🤖</span>
            <div style="flex: 1;">
                <p style="margin: 0;">Welcome! I'm your AI-powered Stock Research Assistant, designed to help you analyze financial data, process market information, and make informed investment decisions. I combine advanced mathematical capabilities with document processing and email management to provide comprehensive financial research support.</p>
            </div>
        </div>
        
        <div style="display: flex; align-items: start; gap: 8px; margin-top: 8px;">
            <span style="font-size: 16px; margin-top: 4px;">⚙️</span>
            <div style="flex: 1;">
                <p style="margin: 0 0 8px 0;">My capabilities include:</p>
                <ul style="list-style-type: none; padding-left: 0; margin: 0;">
                    <li style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                        <span style="font-size: 16px;">📊</span>
                        <span>Analyzing financial reports and market data</span>
                    </li>
                    <li style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                        <span style="font-size: 16px;">🧮</span>
                        <span>Performing complex mathematical calculations</span>
                    </li>
                    <li style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                        <span style="font-size: 16px;">📧</span>
                        <span>Managing and processing email communications</span>
                    </li>
                    <li style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                        <span style="font-size: 16px;">🔍</span>
                        <span>Searching and analyzing research documents</span>
                    </li>
                </ul>
            </div>
        </div>
    </div>
    """
    
    # Create the message container using the UserInteraction style
    full_html = f"""
    <div class="message-container" style="
        font-family: system-ui, -apple-system, sans-serif;
        padding: 16px 20px;
        background-color: #ffffff;
        border-radius: 8px;
        margin-bottom: 16px;
        border: 1px solid rgba(37, 99, 235, 0.15);
        color: black;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
    ">
        <div style="
            border-left: 2px solid rgba(37, 99, 235, 0.15);
            padding-left: 10px;
        ">
            {content}
        </div>
    </div>
    """
    
    return jsonify({
        "status": "ready" if mcp_server.initialized else "initializing",
        "html": full_html
    })

@app.route('/query')
def query():
    query_text = request.args.get('message', '')
    
    # Create a new processing session
    session = message_broker.create_session()
    
    # Send initial status
    message_broker.send_update(
        session.session_id,
        f"Processing query: {query_text}"
    )
    
    # Enhance the query with stock-specific context if needed
    symbol = extract_stock_symbol(query_text)
    if symbol:
        enhanced_query = f"{query_text}"
        # Start the agent-based analysis
        start_stock_analysis(session.session_id, enhanced_query)
    else:
        message_broker.send_update(
            session.session_id,
            "I couldn't find a stock symbol in your query. Please provide a valid stock symbol (e.g., AAPL, MSFT).",
            "final"
        )
        message_broker.close_session(session.session_id)

    def generate():
        """Generate SSE events from the message queue"""
        while True:
            message = session.message_queue.get()  # Blocks until message is available
            
            if message is None:  # Session is complete
                break
                
            yield f"data: {json.dumps(message)}\n\n"
            
            if message['type'] == 'final':
                break

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream'
    )

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)