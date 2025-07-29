class ChatInterface {
    constructor() {
        this.isOpen = false;
        this.apiBaseUrl = 'http://localhost:8000';  // Fixed port to match backend
        this.isTyping = false;
        this.sessionId = this.generateSessionId();
        this.init();
    }
  
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
  
    init() {
        this.setupEventListeners();
        this.initializeChat();
        this.setupChatInterface();
        console.log('Chat initialized with session ID:', this.sessionId);
    }
  
    setupChatInterface() {
        // Create chat interface if it doesn't exist
        if (!document.getElementById('chatContainer')) {
            this.createChatInterface();
        }
    }
  
    createChatInterface() {
        const chatHTML = `
            <div class="chat-container" id="chatContainer">
                <div class="chat-header">
                    <h3>AI Healthcare Assistant</h3>
                    <button class="chat-close" onclick="chat.closeChat()">×</button>
                </div>
                <div class="chat-messages" id="chatMessages"></div>
                <div class="chat-input-container">
                    <input type="text" id="chatInput" placeholder="Type your message...">
                    <button id="sendButton">Send</button>
                </div>
                <div class="chat-suggestions" id="chatSuggestions">
                    <button onclick="chat.sendSuggestion('I want to book an appointment')">Book Appointment</button>
                    <button onclick="chat.sendSuggestion('What doctors are available?')">Find Doctors</button>
                    <button onclick="chat.sendSuggestion('Show my appointments')">My Appointments</button>
                </div>
            </div>
            <div class="chat-toggle" id="chatToggle" onclick="chat.toggleChat()">
                💬
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', chatHTML);
    }
  
    setupEventListeners() {
        // Setup will be called after DOM is ready
        document.addEventListener('DOMContentLoaded', () => {
            this.attachEventListeners();
        });
        
        // If DOM is already ready
        if (document.readyState === 'complete' || document.readyState === 'interactive') {
            setTimeout(() => this.attachEventListeners(), 0);
        }
    }
  
    attachEventListeners() {
        const chatInput = document.getElementById('chatInput');
        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
  
        const sendButton = document.getElementById('sendButton');
        if (sendButton) {
            sendButton.addEventListener('click', () => this.sendMessage());
        }
    }
  
    initializeChat() {
        setTimeout(() => {
            this.addMessage(
                "Hello! I'm your AI healthcare assistant. I can help you book appointments with our doctors. What would you like to do today?\n\n• Book a new appointment\n• Find available doctors\n• Get help with scheduling",
                'ai'
            );
        }, 500);
    }
  
    openChat() {
        const container = document.getElementById('chatContainer');
        const toggle = document.getElementById('chatToggle');
        
        if (container && toggle) {
            container.classList.add('active');
            toggle.style.display = 'none';
            this.isOpen = true;
            
            // Focus on input
            setTimeout(() => {
                const input = document.getElementById('chatInput');
                if (input) input.focus();
            }, 300);
        }
    }
  
    closeChat() {
        const container = document.getElementById('chatContainer');
        const toggle = document.getElementById('chatToggle');
        
        if (container && toggle) {
            container.classList.remove('active');
            toggle.style.display = 'flex';
            this.isOpen = false;
        }
    }
  
    toggleChat() {
        if (this.isOpen) {
            this.closeChat();
        } else {
            this.openChat();
        }
    }
  
    sendSuggestion(message) {
        const input = document.getElementById('chatInput');
        if (input) {
            input.value = message;
            this.sendMessage();
        }
    }
  
    async sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        
        if (!message || this.isTyping) return;
  
        this.addMessage(message, 'user');
        input.value = '';
        
        this.showTypingIndicator();
        this.isTyping = true;
  
        try {
            console.log('Sending message to:', `${this.apiBaseUrl}/api/chat`);
            const response = await fetch(`${this.apiBaseUrl}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ 
                    message: message,
                    session_id: this.sessionId
                }),
            });
  
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
  
            const data = await response.json();
            console.log('Chat response:', data);
            
            this.hideTypingIndicator();
            this.isTyping = false;
  
            if (data.success) {
                this.addMessage(data.response, 'ai');
                
                // Update session ID if provided
                if (data.session_id) {
                    this.sessionId = data.session_id;
                }
                
                // Check if an appointment was booked
                if (data.appointment_booked) {
                    console.log('Appointment was booked, refreshing appointments list...');
                    this.showSuccessMessage("Appointment booked successfully!");
                    
                    // Refresh appointments list if it exists
                    setTimeout(() => {
                        this.refreshAppointmentsList();
                    }, 1000);
                }
                
                // Update suggestions based on context
                this.updateSuggestions(data.context);
                
            } else {
                this.addMessage('Sorry, I encountered an error. Please try again.', 'ai');
                console.error('Chat error:', data.error);
            }
  
        } catch (error) {
            console.error('Chat request failed:', error);
            this.hideTypingIndicator();
            this.isTyping = false;
            this.addMessage('Sorry, I could not connect to the server. Please check your connection and try again.', 'ai');
        }
    }
  
    addMessage(content, sender) {
        const messagesContainer = document.getElementById('chatMessages');
        if (!messagesContainer) return;
  
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}`;
        
        // Format message content
        const formattedContent = this.formatMessage(content);
        messageElement.innerHTML = formattedContent;
        
        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  
    formatMessage(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>')
            .replace(/• /g, '&bull; ');
    }
  
    showTypingIndicator() {
        const messagesContainer = document.getElementById('chatMessages');
        if (!messagesContainer) return;
  
        const indicator = document.createElement('div');
        indicator.id = 'typingIndicator';
        indicator.className = 'message ai typing';
        indicator.innerHTML = `
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
            AI is typing...
        `;
        
        messagesContainer.appendChild(indicator);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
  
    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
  
    showSuccessMessage(message) {
        // Create a success toast/notification
        const toast = document.createElement('div');
        toast.className = 'success-toast';
        toast.innerHTML = `
            <i class="fas fa-check-circle"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(toast);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }
  
    async refreshAppointmentsList() {
        try {
            console.log('Refreshing appointments list...');
            
            // Check if we're on a page with appointments
            const appointmentsContainer = document.getElementById('appointmentsContainer');
            const appointmentsList = document.getElementById('appointmentsList');
            
            if (appointmentsContainer && window.app && typeof window.app.loadAppointments === 'function') {
                // Use the main app's appointment loading function
                await window.app.loadAppointments();
                console.log('Appointments refreshed via main app');
            } else if (appointmentsList && typeof window.loadAppointments === 'function') {
                // Use the standalone loadAppointments function
                await window.loadAppointments();
                console.log('Appointments refreshed via standalone function');
            } else {
                // Manual refresh for any appointments display
                const response = await fetch(`${this.apiBaseUrl}/api/appointments`);
                if (response.ok) {
                    const appointments = await response.json();
                    console.log('Fetched updated appointments:', appointments);
                    
                    // Try to update any appointments display we can find
                    this.updateAppointmentsDisplay(appointments);
                }
            }
        } catch (error) {
            console.error('Error refreshing appointments:', error);
        }
    }
  
    updateAppointmentsDisplay(appointments) {
        // Try multiple possible appointment containers
        const containers = [
            document.getElementById('appointmentsList'),
            document.getElementById('appointmentsContainer'),
            document.querySelector('.appointments-list'),
            document.querySelector('[data-appointments]')
        ];
  
        containers.forEach(container => {
            if (container) {
                this.renderAppointments(container, appointments);
            }
        });
    }
  
    renderAppointments(container, appointments) {
        if (appointments.length === 0) {
            container.innerHTML = `
                <p style="text-align: center; color: var(--text-secondary);">
                    No upcoming appointments. 
                    <a href="#" onclick="chat.openChat()" style="color: var(--primary);">Book one now!</a>
                </p>
            `;
        } else {
            container.innerHTML = appointments.map(apt => `
                <div class="appointment-item" data-appointment-id="${apt.id}">
                    <div class="appointment-date">
                        <div style="font-size: 0.875rem;">${new Date(apt.date || apt.appointment_date).toLocaleDateString('en-US', { month: 'short' })}</div>
                        <div style="font-size: 1.5rem; font-weight: 700;">${new Date(apt.date || apt.appointment_date).getDate()}</div>
                    </div>
                    <div style="flex: 1;">
                        <h4 style="margin: 0; color: var(--text-primary);">
                            Dr. ${apt.doctor_name}
                        </h4>
                        <p style="color: var(--text-secondary); margin: 0;">
                            ${apt.specialization || apt.department} • ${apt.appointment_time}
                        </p>
                        <p style="color: var(--text-secondary); margin: 0;">
                            <i class="fas fa-user"></i> ${apt.patient_name}
                        </p>
                    </div>
                    <div>
                        <span class="btn btn-secondary" style="font-size: 0.875rem;">
                            ${apt.status}
                        </span>
                    </div>
                </div>
            `).join('');
        }
    }
  
    updateSuggestions(context) {
        const suggestionsContainer = document.getElementById('chatSuggestions');
        if (!suggestionsContainer || !context) return;
  
        // You can customize suggestions based on context
        // For now, keep default suggestions
    }
  }
  
  // Initialize chat when DOM is ready
  let chat;
  
  document.addEventListener('DOMContentLoaded', function() {
      chat = new ChatInterface();
      window.chat = chat; // Make it globally accessible
  });
  
  // Also initialize if DOM is already loaded
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
      setTimeout(() => {
          if (!window.chat) {
              chat = new ChatInterface();
              window.chat = chat;
          }
      }, 0);
  }
  
  // Global functions for compatibility
  function openChat() {
      if (window.chat) {
          window.chat.openChat();
      }
  }
  
  function closeChat() {
      if (window.chat) {
          window.chat.closeChat();
      }
  }