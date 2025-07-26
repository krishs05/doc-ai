class ChatInterface {
  constructor() {
      this.isOpen = false;
      this.apiBaseUrl = 'http://localhost:5000';
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
      console.log('Chat initialized with session ID:', this.sessionId);
  }

  setupEventListeners() {
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

  async sendMessage() {
      const input = document.getElementById('chatInput');
      const message = input.value.trim();
      
      if (!message || this.isTyping) return;

      this.addMessage(message, 'user');
      input.value = '';
      
      this.showTypingIndicator();
      this.isTyping = true;

      try {
          const response = await fetch(`${this.apiBaseUrl}/api/chat`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              credentials: 'include',
              body: JSON.stringify({ 
                  message: message,
                  session_id: this.sessionId  // Include session ID
              }),
          });

          if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
          }

          const data = await response.json();
          
          this.hideTypingIndicator();
          this.isTyping = false;

          if (data.success) {
              this.addMessage(data.response, 'ai');
              
              // Update session ID if provided
              if (data.context?.session_id) {
                  this.sessionId = data.context.session_id;
              }
              
              // Update suggestions based on context
              this.updateSuggestions(data.context);
              
              console.log('Chat context:', data.context);
          } else {
              this.addMessage('Sorry, I encountered an error. Please try again.', 'ai');
              console.error('API Error:', data.error);
          }
      } catch (error) {
          console.error('Chat error:', error);
          this.hideTypingIndicator();
          this.isTyping = false;
          
          let errorMessage = 'Sorry, I cannot connect to the server right now. Please check if the backend server is running on port 5000.';
          this.addMessage(errorMessage, 'ai');
      }
  }

  updateSuggestions(context) {
      const suggestionsContainer = document.getElementById('chatSuggestions');
      if (!suggestionsContainer) return;

      let suggestions = [];

      if (context && context.step) {
          switch (context.step) {
              case 'need_name':
                  suggestions = ['My name is John Doe', 'I want to book an appointment'];
                  break;
              case 'need_phone':
                  suggestions = ['My phone is 8800554608', '8800554608'];
                  break;
              case 'need_specialty':
                  suggestions = ['I need a cardiologist', 'General checkup', 'Which doctors are available?'];
                  break;
              case 'select_doctor':
                  suggestions = ['1', '2', 'Dr. Smith'];
                  break;
              case 'select_time':
                  suggestions = ['1', '2', '3'];
                  break;
              default:
                  suggestions = ['📅 Book Appointment', '👨‍⚕️ Find Doctors', '🔄 Reschedule'];
          }
      } else {
          suggestions = ['📅 Book Appointment', '👨‍⚕️ Find Doctors', '❓ Help'];
      }

      suggestionsContainer.innerHTML = '';
      suggestions.forEach(suggestion => {
          const btn = document.createElement('button');
          btn.className = 'suggestion-btn';
          btn.textContent = suggestion;
          btn.onclick = () => this.sendSuggestion(suggestion);
          suggestionsContainer.appendChild(btn);
      });
  }

  addMessage(content, sender) {
      const messagesContainer = document.getElementById('chatMessages');
      if (!messagesContainer) return;

      const messageDiv = document.createElement('div');
      messageDiv.className = `message ${sender}-message`;
      
      messageDiv.innerHTML = `
          <div class="message-content">${this.formatMessage(content)}</div>
          <div class="message-time">${this.formatTime(new Date())}</div>
      `;

      messagesContainer.appendChild(messageDiv);
      this.scrollToBottom();

      // Add animation
      messageDiv.style.opacity = '0';
      messageDiv.style.transform = 'translateY(20px)';
      
      setTimeout(() => {
          messageDiv.style.transition = 'all 0.3s ease';
          messageDiv.style.opacity = '1';
          messageDiv.style.transform = 'translateY(0)';
      }, 50);
  }

  formatMessage(content) {
      // Escape HTML to prevent XSS
      content = content.replace(/&/g, '&amp;')
                      .replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;');
      
      // Format bold text
      content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      
      // Format bullet points
      content = content.replace(/^• (.*$)/gim, '<div class="bullet-point">• $1</div>');
      
      // Convert line breaks to <br>
      content = content.replace(/\n/g, '<br>');
      
      return content;
  }

  formatTime(date) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  showTypingIndicator() {
      this.hideTypingIndicator();
      
      const messagesContainer = document.getElementById('chatMessages');
      if (!messagesContainer) return;

      const typingDiv = document.createElement('div');
      typingDiv.className = 'message ai-message typing-message';
      typingDiv.id = 'typingIndicator';
      
      typingDiv.innerHTML = `
          <div class="message-content">
              <div class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
              </div>
          </div>
      `;

      messagesContainer.appendChild(typingDiv);
      this.scrollToBottom();
  }

  hideTypingIndicator() {
      const typingIndicator = document.getElementById('typingIndicator');
      if (typingIndicator) {
          typingIndicator.remove();
      }
  }

  scrollToBottom() {
      const messagesContainer = document.getElementById('chatMessages');
      if (messagesContainer) {
          setTimeout(() => {
              messagesContainer.scrollTop = messagesContainer.scrollHeight;
          }, 100);
      }
  }

  async clearConversation() {
      try {
          // Generate new session ID
          this.sessionId = this.generateSessionId();
          
          // Clear UI
          const messagesContainer = document.getElementById('chatMessages');
          if (messagesContainer) {
              messagesContainer.innerHTML = '';
          }
          
          // Reinitialize chat
          this.initializeChat();
          
          this.showNotification('Conversation cleared successfully!', 'success');
      } catch (error) {
          console.error('Error clearing conversation:', error);
      }
  }

  showNotification(message, type = 'info') {
      const notification = document.createElement('div');
      notification.className = `notification notification-${type}`;
      notification.innerHTML = message;
      notification.style.cssText = `
          position: fixed;
          top: 20px;
          right: 20px;
          padding: 15px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          z-index: 10000;
          border-left: 4px solid ${type === 'success' ? '#10b981' : '#3b82f6'};
      `;
      
      document.body.appendChild(notification);
      
      setTimeout(() => {
          if (notification.parentElement) {
              notification.remove();
          }
      }, 3000);
  }

  sendSuggestion(suggestion) {
      const input = document.getElementById('chatInput');
      if (input) {
          // Remove emoji from suggestion
          const cleanSuggestion = suggestion.replace(/^[\u{1F300}-\u{1F9FF}]\s*/u, '');
          input.value = cleanSuggestion;
          this.sendMessage();
      }
  }

  openChat() {
      const container = document.getElementById('chatContainer');
      const toggle = document.querySelector('.chat-toggle');
      
      if (container && toggle) {
          container.classList.remove('hidden');
          setTimeout(() => container.classList.add('show'), 10);
          toggle.style.display = 'none';
          this.isOpen = true;

          const input = document.getElementById('chatInput');
          if (input) {
              setTimeout(() => input.focus(), 300);
          }
      }
  }

  closeChat() {
      const container = document.getElementById('chatContainer');
      const toggle = document.querySelector('.chat-toggle');
      
      if (container && toggle) {
          container.classList.remove('show');
          setTimeout(() => {
              container.classList.add('hidden');
              toggle.style.display = 'flex';
          }, 300);
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
}

// Global functions
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

function toggleChat() {
  if (window.chat) {
      window.chat.toggleChat();
  }
}

function sendSuggestion(suggestion) {
  if (window.chat) {
      window.chat.sendSuggestion(suggestion);
  }
}

function sendMessage() {
  if (window.chat) {
      window.chat.sendMessage();
  }
}

// Initialize when DOM loads
document.addEventListener('DOMContentLoaded', () => {
  window.chat = new ChatInterface();
});