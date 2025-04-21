# Stock Research Assistant

A Chrome extension-based tool that provides AI-powered stock research and analysis capabilities.

## Features

- Chrome extension with side panel interface
- Real-time stock data analysis
- Interactive query system
- Live updates during analysis
- AI-powered insights

## Installation

### Prerequisites

- Python 3.12 or higher
- Google Chrome browser
- pip (Python package installer)

### Backend Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd stock-research
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

### Chrome Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked" and select the `extension` directory from this project

## Usage

1. Start the backend server:
```bash
python main.py
```

2. The Chrome extensions page will open automatically
3. Click the extension icon to open the side panel
4. Enter your stock research query in the input field
5. View real-time updates and final analysis

## Project Structure
