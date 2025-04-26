from stock_research.backend.app import app
from stock_research.backend.message_broker import message_broker
import webbrowser
import threading
import time

def open_chrome_extension():
    """
    Wait briefly then open Chrome to the extensions page.
    User will need to load the extension manually first time.
    """
    time.sleep(2)
    #webbrowser.open('chrome://extensions/')
    print("Please load the extension from the Chrome extensions page if not already loaded.")

def main():
    print("Starting Stock Research Assistant...")
    
    # Start Chrome extension helper in background
    #threading.Thread(target=open_chrome_extension, daemon=True).start()
    
    # Run Flask application
    print("Starting backend server...")
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader when running in main
    )

if __name__ == "__main__":
    main()