from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS
import json
import re
from .message_broker import message_broker
from .stock_agent_handler import start_stock_analysis

app = Flask(__name__)
CORS(app)

def extract_stock_symbol(query: str) -> str:
    """Extract stock symbol from query text"""
    # Simple regex to find stock symbols (can be enhanced)
    matches = re.findall(r'\b[A-Z]{1,5}\b', query.upper())
    return matches[0] if matches else None

@app.route('/query')
def query():
    query_text = request.args.get('message', '')
    
    # Create a new processing session
    session = message_broker.create_session()
    
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