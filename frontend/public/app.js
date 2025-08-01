class DocAIApp {
  constructor() {
      this.currentPage = 'home';
      this.apiBaseUrl = 'http://localhost:8000';
      this.appointments = [];
      this.isLoading = false;
      this.init();
  }

  init() {
      this.setupNavigation();
      this.setupEventListeners();
      this.loadInitialData();
  }

  setupNavigation() {
      // Smooth scrolling for navigation links
      document.querySelectorAll('.nav-link').forEach(link => {
          link.addEventListener('click', (e) => {
              e.preventDefault();
              const targetId = link.getAttribute('href').substring(1);
              const targetElement = document.getElementById(targetId);
              
              if (targetElement) {
                  // Update URL
                  history.pushState(null, null, `#${targetId}`);
                  
                  targetElement.scrollIntoView({
                      behavior: 'smooth',
                      block: 'start'
                  });
                  
                  // Update active nav link
                  this.updateActiveNavLink(link);
                  this.currentPage = targetId;
                  
                  // Load appointments when appointments section is accessed
                  if (targetId === 'appointments') {
                      this.loadAppointments();
                  }
              }
          });
      });
  }

  setupEventListeners() {
      // Service card click handlers
      document.querySelectorAll('.service-card').forEach((card, index) => {
          card.addEventListener('click', () => {
              this.handleServiceClick(index);
          });
      });

      // Appointments section buttons
      const bookNewBtn = document.querySelector('button[onclick="openChat()"]');
      if (bookNewBtn) {
          bookNewBtn.addEventListener('click', (e) => {
              e.preventDefault();
              if (window.chat) {
                  window.chat.openChat();
              }
          });
      }
  }

  updateActiveNavLink(activeLink) {
      document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
      activeLink.classList.add('active');
  }

  async loadInitialData() {
      // Load appointments if we're on the appointments page
      if (window.location.hash === '#appointments') {
          this.loadAppointments();
      }
  }

  async loadAppointments() {
      const container = document.getElementById('appointmentsContainer');
      if (!container) return;

      try {
          // Show loading state
          container.innerHTML = `
              <div class="loading-appointments">
                  <div class="spinner"></div>
                  <p>Loading appointments...</p>
              </div>
          `;

          console.log('Loading appointments from:', `${this.apiBaseUrl}/api/appointments`);
          
          const response = await fetch(`${this.apiBaseUrl}/api/appointments`, {
              method: 'GET',
              headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json'
              }
          });
          
          if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
          }
          
          const appointments = await response.json();
          console.log('Loaded appointments:', appointments);
          
          this.appointments = appointments;
          this.displayAppointments(appointments);
          
      } catch (error) {
          console.error('Error loading appointments:', error);
          container.innerHTML = `
              <div class="error-appointments">
                  <i class="fas fa-exclamation-triangle"></i>
                  <h3>Unable to load appointments</h3>
                  <p>There was an error loading your appointments: ${error.message}</p>
                  <p class="error-details">Please check if the backend server is running on port 8000.</p>
                  <button class="btn-primary" onclick="app.loadAppointments()">
                      <i class="fas fa-refresh"></i>
                      Try Again
                  </button>
              </div>
          `;
      }
  }

  displayAppointments(appointments) {
      const container = document.getElementById('appointmentsContainer');
      if (!container) return;

      if (appointments.length === 0) {
          container.innerHTML = `
              <div class="no-appointments">
                  <i class="fas fa-calendar-plus"></i>
                  <h3>No appointments scheduled</h3>
                  <p>Book your first appointment with our AI assistant!</p>
                  <button class="btn-primary" onclick="openChat()">
                      <i class="fas fa-plus"></i>
                      Book Appointment
                  </button>
              </div>
          `;
          return;
      }

      container.innerHTML = appointments.map(apt => `
          <div class="appointment-card" data-appointment-id="${apt.id}">
              <div class="appointment-header">
                  <div class="appointment-info">
                      <h4>Dr. ${apt.doctor_name || 'Unknown'}</h4>
                      <p class="appointment-specialty">${apt.specialization || 'General Medicine'}</p>
                  </div>
                  <span class="appointment-status status-${apt.status}">${this.formatStatus(apt.status)}</span>
              </div>
              <div class="appointment-details">
                  <div class="detail-row">
                      <i class="fas fa-user"></i>
                      <span>Patient: ${apt.patient_name || 'Unknown'}</span>
                  </div>
                  <div class="detail-row">
                      <i class="fas fa-calendar"></i>
                      <span>${this.formatDate(apt.appointment_date)}</span>
                  </div>
                  <div class="detail-row">
                      <i class="fas fa-clock"></i>
                      <span>${this.formatTime(apt.appointment_time)}</span>
                  </div>
                  <div class="detail-row">
                      <i class="fas fa-stethoscope"></i>
                      <span>${apt.reason || 'General consultation'}</span>
                  </div>
              </div>
              <div class="appointment-actions">
                  <button class="btn-outline btn-sm" onclick="app.rescheduleAppointment(${apt.id})">
                      <i class="fas fa-calendar-alt"></i> Reschedule
                  </button>
                  <button class="btn-primary btn-sm" onclick="app.viewAppointment(${apt.id})">
                      <i class="fas fa-eye"></i> View Details
                  </button>
                  <button class="btn-danger btn-sm" onclick="app.cancelAppointment(${apt.id})">
                      <i class="fas fa-times"></i> Cancel
                  </button>
              </div>
          </div>
      `).join('');
  }

  formatDate(dateString) {
      if (!dateString) return 'Date TBD';
      
      try {
          return new Date(dateString).toLocaleDateString('en-US', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric'
          });
      } catch (error) {
          console.warn('Error formatting date:', error);
          return dateString;
      }
  }

  formatTime(timeString) {
      if (!timeString) return 'Time TBD';
      
      try {
          // Handle different time formats
          if (timeString.includes(':')) {
              const [hours, minutes] = timeString.split(':');
              const date = new Date();
              date.setHours(parseInt(hours), parseInt(minutes));
              return date.toLocaleTimeString('en-US', {
                  hour: 'numeric',
                  minute: '2-digit',
                  hour12: true
              });
          }
          return timeString;
      } catch (error) {
          console.warn('Error formatting time:', error);
          return timeString;
      }
  }

  formatStatus(status) {
      const statusMap = {
          'scheduled': 'Scheduled',
          'confirmed': 'Confirmed',
          'completed': 'Completed',
          'cancelled': 'Cancelled',
          'pending': 'Pending'
      };
      return statusMap[status] || status.charAt(0).toUpperCase() + status.slice(1);
  }

  async rescheduleAppointment(appointmentId) {
      try {
          const confirmed = await this.showConfirmDialog(
              'Reschedule Appointment',
              'Would you like to reschedule this appointment? Our AI assistant will help you find a new time slot.'
          );

          if (confirmed) {
              // Open chat with reschedule context
              if (window.chat) {
                  window.chat.openChat();
                  setTimeout(() => {
                      window.chat.sendSuggestion(`I want to reschedule appointment ID ${appointmentId}`);
                  }, 500);
              }
          }
      } catch (error) {
          console.error('Error in rescheduleAppointment:', error);
          this.showNotification('Error initiating reschedule process', 'error');
      }
  }

  async viewAppointment(appointmentId) {
      try {
          const appointment = this.appointments.find(apt => apt.id === appointmentId);
          if (!appointment) {
              this.showNotification('Appointment not found', 'error');
              return;
          }

          const modalContent = `
              <div class="appointment-details-modal">
                  <div class="detail-section">
                      <h4><i class="fas fa-user-md"></i> Doctor Information</h4>
                      <p><strong>Name:</strong> Dr. ${appointment.doctor_name || 'Unknown'}</p>
                      <p><strong>Specialization:</strong> ${appointment.specialization || 'General Medicine'}</p>
                  </div>
                  <div class="detail-section">
                      <h4><i class="fas fa-calendar-check"></i> Appointment Details</h4>
                      <p><strong>Date:</strong> ${this.formatDate(appointment.appointment_date)}</p>
                      <p><strong>Time:</strong> ${this.formatTime(appointment.appointment_time)}</p>
                      <p><strong>Status:</strong> <span class="status-badge status-${appointment.status}">${this.formatStatus(appointment.status)}</span></p>
                  </div>
                  <div class="detail-section">
                      <h4><i class="fas fa-user"></i> Patient Information</h4>
                      <p><strong>Name:</strong> ${appointment.patient_name || 'Unknown'}</p>
                      <p><strong>Reason:</strong> ${appointment.reason || 'General consultation'}</p>
                  </div>
                  ${appointment.notes ? `
                      <div class="detail-section">
                          <h4><i class="fas fa-sticky-note"></i> Notes</h4>
                          <p>${appointment.notes}</p>
                      </div>
                  ` : ''}
                  <div class="modal-actions">
                      <button class="btn-outline" onclick="app.rescheduleAppointment(${appointmentId})">
                          <i class="fas fa-calendar-alt"></i> Reschedule
                      </button>
                      <button class="btn-danger" onclick="app.cancelAppointment(${appointmentId})">
                          <i class="fas fa-times"></i> Cancel Appointment
                      </button>
                  </div>
              </div>
          `;

          const modal = this.createModal('Appointment Details', modalContent);
          this.showModal(modal);
      } catch (error) {
          console.error('Error viewing appointment:', error);
          this.showNotification('Error loading appointment details', 'error');
      }
  }

  async cancelAppointment(appointmentId) {
      try {
          const confirmed = await this.showConfirmDialog(
              'Cancel Appointment',
              'Are you sure you want to cancel this appointment? This action cannot be undone.'
          );

          if (confirmed) {
              // Show loading state
              this.showNotification('Cancelling appointment...', 'info');

              const response = await fetch(`${this.apiBaseUrl}/api/appointments/${appointmentId}`, {
                  method: 'DELETE',
                  headers: {
                      'Content-Type': 'application/json'
                  }
              });

              if (!response.ok) {
                  throw new Error(`Failed to cancel appointment: ${response.statusText}`);
              }

              this.showNotification('Appointment cancelled successfully', 'success');
              
              // Refresh the appointments list
              await this.loadAppointments();
              
              // Close any open modals
              this.closeModal();
          }
      } catch (error) {
          console.error('Error cancelling appointment:', error);
          this.showNotification(`Error cancelling appointment: ${error.message}`, 'error');
      }
  }

  // Contact form handling
  async submitContactForm(event) {
      event.preventDefault();
      
      const formData = new FormData(event.target);
      const contactData = {
          name: formData.get('name'),
          email: formData.get('email'),
          phone: formData.get('phone'),
          subject: formData.get('subject'),
          message: formData.get('message')
      };

      // Simulate form submission
      this.showNotification('Thank you for contacting us! We will get back to you within 2 hours.', 'success');
      event.target.reset();
  }

  callSupport() {
      window.open('tel:+15551234567');
  }

  scheduleCallback() {
      if (window.chat) {
          window.chat.openChat();
          setTimeout(() => {
              window.chat.sendSuggestion('I would like to schedule a callback');
          }, 500);
      }
  }

  // Utility methods
  showNotification(message, type = 'info') {
      const notification = document.createElement('div');
      notification.className = `notification notification-${type}`;
      notification.innerHTML = `
          <div class="notification-content">
              <i class="fas fa-${this.getNotificationIcon(type)}"></i>
              <span>${message}</span>
          </div>
          <button class="notification-close" onclick="this.parentElement.remove()">
              <i class="fas fa-times"></i>
          </button>
      `;

      notification.style.cssText = `
          position: fixed;
          top: 20px;
          right: 20px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          border-left: 4px solid ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
          padding: 15px;
          z-index: 10000;
          display: flex;
          align-items: center;
          gap: 10px;
          max-width: 400px;
      `;

      document.body.appendChild(notification);

      setTimeout(() => {
          if (notification.parentElement) {
              notification.remove();
          }
      }, 5000);
  }

  getNotificationIcon(type) {
      const icons = {
          'success': 'check-circle',
          'error': 'exclamation-circle',
          'warning': 'exclamation-triangle',
          'info': 'info-circle'
      };
      return icons[type] || 'info-circle';
  }

  createModal(title, content) {
      return `
          <div class="modal-overlay" onclick="app.closeModal()">
              <div class="modal-content" onclick="event.stopPropagation()">
                  <div class="modal-header">
                      <h3>${title}</h3>
                      <button class="modal-close" onclick="app.closeModal()">
                          <i class="fas fa-times"></i>
                      </button>
                  </div>
                  <div class="modal-body">
                      ${content}
                  </div>
              </div>
          </div>
      `;
  }

  showModal(modalHTML) {
      this.closeModal();
      
      const modalContainer = document.createElement('div');
      modalContainer.id = 'modalContainer';
      modalContainer.innerHTML = modalHTML;
      
      document.body.appendChild(modalContainer);
      document.body.style.overflow = 'hidden';
      
      setTimeout(() => {
          const overlay = modalContainer.querySelector('.modal-overlay');
          if (overlay) overlay.classList.add('show');
      }, 10);
  }

  closeModal() {
      const modalContainer = document.getElementById('modalContainer');
      if (modalContainer) {
          modalContainer.remove();
          document.body.style.overflow = '';
      }
  }

  async showConfirmDialog(title, message) {
      return new Promise((resolve) => {
          const modal = this.createModal(title, `
              <div class="confirm-dialog">
                  <p>${message}</p>
                  <div class="confirm-actions">
                      <button class="btn-outline" onclick="app.resolveConfirm(false)">Cancel</button>
                      <button class="btn-primary" onclick="app.resolveConfirm(true)">Confirm</button>
                  </div>
              </div>
          `);
          
          this.confirmResolver = resolve;
          this.showModal(modal);
      });
  }

  resolveConfirm(result) {
      if (this.confirmResolver) {
          this.confirmResolver(result);
          this.confirmResolver = null;
      }
      this.closeModal();
  }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  window.app = new DocAIApp();
});
