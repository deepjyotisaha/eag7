class StockResearchAssistant {
    constructor() {
        this.chatContainer = document.getElementById('chatContainer');
        this.userInput = document.getElementById('userInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.querySelector('.typing-indicator');
        this.backendUrl = 'http://localhost:5000';
        
        this.setupEventListeners();
        this.setupSuggestions();
        this.setupAutoResize();
    }

    setupEventListeners() {
        this.sendButton.addEventListener('click', () => this.handleUserInput());
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleUserInput();
            }
        });
    }

    setupSuggestions() {
        document.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.userInput.value = btn.textContent.replace(/['"]/g, '');
                this.handleUserInput();
            });
        });
    }

    setupAutoResize() {
        this.userInput.addEventListener('input', () => {
            this.userInput.style.height = 'auto';
            this.userInput.style.height = (this.userInput.scrollHeight) + 'px';
        });
    }

    async handleUserInput() {
        const message = this.userInput.value.trim();
        if (!message) return;

        // Add user message
        this.addMessage(message, 'user');
        this.userInput.value = '';
        this.userInput.style.height = 'auto';

        // Show typing indicator
        this.showTypingIndicator();

        try {
            const eventSource = new EventSource(`${this.backendUrl}/query?message=${encodeURIComponent(message)}`);
            
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'update') {
                    this.hideTypingIndicator();
                    this.addMessage(data.content, 'assistant');
                } else if (data.type === 'final') {
                    this.hideTypingIndicator();
                    this.addMessage(data.content, 'assistant');
                    this.addMessage("What else would you like to know?", 'assistant');
                    eventSource.close();
                }
            };

            eventSource.onerror = (error) => {
                console.error('EventSource failed:', error);
                this.hideTypingIndicator();
                this.addMessage('Sorry, there was an error processing your request.', 'assistant');
                eventSource.close();
            };

        } catch (error) {
            console.error('Error:', error);
            this.hideTypingIndicator();
            this.addMessage('Sorry, there was an error processing your request.', 'assistant');
        }
    }

    addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = `<p>${this.escapeHtml(content)}</p>`;
        
        const timestamp = document.createElement('div');
        timestamp.className = 'timestamp';
        timestamp.textContent = this.getTimestamp();
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(timestamp);
        
        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        this.typingIndicator.style.display = 'flex';
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
    }

    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }

    getTimestamp() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Initialize the assistant when the document is loaded
document.addEventListener('DOMContentLoaded', () => {
    new StockResearchAssistant();
});