from flask import Flask, request, Response, stream_with_context
import json
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def process_stock_query(query):
    # This is where you would implement your actual stock research logic
    # For now, we'll simulate processing with some dummy responses
    updates = [
        "Analyzing your query...",
        "Fetching market data...",
        "Processing financial statements...",
        f"Final analysis for query: '{query}' completed. Here's a summary of findings..."
    ]
    return updates

@app.route('/query')
def query():
    query_text = request.args.get('message', '')
    
    def generate():
        # Get processing updates
        updates = process_stock_query(query_text)
        
        # Send intermediate updates
        for i, update in enumerate(updates):
            if i < len(updates) - 1:
                data = {'type': 'update', 'content': update}
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(1)  # Simulate processing time
            else:
                # Send final message
                data = {'type': 'final', 'content': update}
                yield f"data: {json.dumps(data)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream'
    )

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)