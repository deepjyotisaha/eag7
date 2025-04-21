import yfinance as yf
from .message_broker import message_broker
import threading
import time

class StockAnalyzer:
    def __init__(self, session_id: str):
        self.session_id = session_id
    
    def send_update(self, message: str):
        """Helper method to send updates"""
        message_broker.send_update(self.session_id, message)
    
    def analyze_stock(self, symbol: str):
        """Analyze a stock and send real updates"""
        try:
            self.send_update(f"Fetching data for {symbol}...")
            stock = yf.Ticker(symbol)
            
            # Get basic info
            self.send_update("Retrieving company information...")
            info = stock.info
            self.send_update(f"Company Name: {info.get('longName', symbol)}")
            
            # Get financial data
            self.send_update("Analyzing financial metrics...")
            time.sleep(1)  # Simulate some processing
            self.send_update(f"Market Cap: ${info.get('marketCap', 'N/A')}")
            
            # Get recent price data
            self.send_update("Calculating price trends...")
            hist = stock.history(period="1mo")
            price_change = ((hist['Close'][-1] - hist['Close'][0]) / hist['Close'][0]) * 100
            self.send_update(f"30-day price change: {price_change:.2f}%")
            
            # Final analysis
            message_broker.send_update(
                self.session_id,
                f"Analysis complete for {symbol}. The stock has shown {price_change:.2f}% "
                f"change over the last 30 days.",
                "final"
            )
            
        except Exception as e:
            self.send_update(f"Error analyzing stock: {str(e)}")
            message_broker.send_update(
                self.session_id,
                "Analysis failed. Please try again.",
                "final"
            )
        finally:
            message_broker.close_session(self.session_id)

def analyze_stock_async(symbol: str, session_id: str):
    """Start stock analysis in a separate thread"""
    analyzer = StockAnalyzer(session_id)
    thread = threading.Thread(target=analyzer.analyze_stock, args=(symbol,))
    thread.start()