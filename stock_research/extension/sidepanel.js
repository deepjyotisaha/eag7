class StockResearchAssistant {
    constructor() {
        this.chatContainer = document.getElementById('chatContainer');
        this.userInput = document.getElementById('userInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.querySelector('.typing-indicator');
        this.statusIndicator = document.querySelector('.status');
        this.backendUrl = 'http://localhost:5000';
        
        this.setupEventListeners();
        this.setupSuggestions();
        this.setupAutoResize();
        this.checkServerStatus();
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

    async checkServerStatus() {
        try {
            const response = await fetch(`${this.backendUrl}/status`);
            const data = await response.json();
            
            if (data.status === 'ready') {
                this.statusIndicator.textContent = 'Online';
                this.statusIndicator.className = 'status online';
                if (data.html) {
                    this.addMessage(data.html, 'assistant');
                }
                this.enableInput();
            } else {
                this.statusIndicator.textContent = 'Initializing...';
                this.statusIndicator.className = 'status initializing';
                this.disableInput();
                setTimeout(() => this.checkServerStatus(), 5000);
            }
        } catch (error) {
            console.error('Server status check failed:', error);
            this.statusIndicator.textContent = 'Offline';
            this.statusIndicator.className = 'status offline';
            this.addMessage('Unable to connect to the server. Please try again later.', 'assistant');
            this.disableInput();
            setTimeout(() => this.checkServerStatus(), 10000);
        }
    }

    enableInput() {
        this.userInput.disabled = false;
        this.sendButton.disabled = false;
        document.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.disabled = false;
        });
    }

    disableInput() {
        this.userInput.disabled = true;
        this.sendButton.disabled = true;
        document.querySelectorAll('.suggestion-btn').forEach(btn => {
            btn.disabled = true;
        });
    }

    async handleUserInput() {
        const message = this.userInput.value.trim();
        if (!message) return;

        this.disableInput();

        this.addMessage(message, 'user');
        this.userInput.value = '';
        this.userInput.style.height = 'auto';

        this.showTypingIndicator();

        try {
            const eventSource = new EventSource(`${this.backendUrl}/query?message=${encodeURIComponent(message)}`);
            
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'update' || data.type === 'final') {
                    this.hideTypingIndicator();
                    
                    // Create a temporary div to check if content is HTML
                    const temp = document.createElement('div');
                    temp.innerHTML = data.content;
                    
                    // Add the message
                    this.addMessage(data.content, 'assistant');
                    
                    if (data.type === 'final') {
                        setTimeout(() => {
                            this.addMessage("What else would you like to know?", 'assistant');
                        }, 500);
                        eventSource.close();
                        this.enableInput();
                    }
                }
            };

            eventSource.onerror = (error) => {
                console.error('EventSource failed:', error);
                this.hideTypingIndicator();
                this.addMessage('Sorry, there was an error processing your request.', 'assistant');
                eventSource.close();
                this.enableInput();
            };

        } catch (error) {
            console.error('Error:', error);
            this.hideTypingIndicator();
            this.addMessage('Sorry, there was an error processing your request.', 'assistant');
            this.enableInput();
        }
    }

    addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Check if the content contains HTML tags
        if (content.includes('<div') || content.includes('<style')) {
            // If it's HTML content, insert it directly
            messageContent.innerHTML = content;
        } else {
            // If it's plain text, escape it
            messageContent.innerHTML = `<p>${this.escapeHtml(content)}</p>`;
        }
        
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

document.addEventListener('DOMContentLoaded', () => {
    new StockResearchAssistant();
});