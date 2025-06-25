

// let isAuthenticated = false;

// function showStatus(message, type = 'info') {
//     const status = document.getElementById('status');
//     status.textContent = message;
//     status.className = `status ${type}`;
//     status.style.display = 'block';
    
//     if (type === 'success' || type === 'error') {
//         setTimeout(() => {
//             status.style.display = 'none';
//         }, 5000);
//     }
// }

// function updateStep(stepNumber) {
//     for (let i = 1; i <= 3; i++) {
//         const step = document.getElementById(`step${i}`);
//         step.classList.remove('active', 'completed');
        
//         if (i < stepNumber) {
//             step.classList.add('completed');
//         } else if (i === stepNumber) {
//             step.classList.add('active');
//         }
//     }
// }

// function setLoading(buttonId, textId, isLoading, loadingText = 'Processing...') {
//     const button = document.getElementById(buttonId);
//     const text = document.getElementById(textId);
    
//     if (isLoading) {
//         button.disabled = true;
//         text.innerHTML = `<span class="loading"></span>${loadingText}`;
//     } else {
//         button.disabled = false;
//         text.innerHTML = text.getAttribute('data-original') || text.textContent.replace(/Processing\\.\\.\\.|Signing in\\.\\.\\.|Sending\\.\\.\\.|Loading\\.\\.\\./, '');
//     }
// }

// function signIn() {
//     setLoading('signin-btn', 'signin-text', true, 'Redirecting...');
//     showStatus('Redirecting to Microsoft sign-in...', 'info');
//     window.location.href = '/signin';
// }

// async function sendEmail() {
//     const recipient = document.getElementById('recipient').value;
//     const subject = document.getElementById('subject').value;
//     const message = document.getElementById('message').value;

//     if (!recipient) {
//         showStatus('Please enter a recipient email address', 'error');
//         return;
//     }

//     if (!subject.trim()) {
//         showStatus('Please enter a subject', 'error');
//         return;
//     }

//     if (!message.trim()) {
//         showStatus('Please enter a message', 'error');
//         return;
//     }

//     setLoading('send-btn', 'send-text', true, 'Sending...');
//     showStatus('Sending email...', 'info');

//     try {
//         const url = `/send-mail/${encodeURIComponent(recipient)}?subject=${encodeURIComponent(subject)}&message=${encodeURIComponent(message)}`;
//         const response = await fetch(url, {
//             method: 'GET'
//         });

//         if (response.ok) {
//             const result = await response.json();
//             showStatus(`Email sent successfully to ${recipient}!`, 'success');
//             updateStep(3);
            
//             setTimeout(() => {
//                 document.getElementById('recipient').value = '';
//                 document.getElementById('subject').value = 'Wanna go out for lunch?';
//                 document.getElementById('message').value = 'I know a sweet spot that just opened around us!';
//             }, 2000);
//         } else {
//             const errorData = await response.json();
//             showStatus(`Failed to send email: ${errorData.error}`, 'error');
//         }
//     } catch (error) {
//         showStatus(`Error: ${error.message}`, 'error');
//     } finally {
//         setLoading('send-btn', 'send-text', false);
//     }
// }

// async function loadUserProfile() {
//     try {
//         const response = await fetch('/get-user-profile');
//         if (response.ok) {
//             const user = await response.json();
//             document.getElementById('user-name').textContent = user.displayName;
//             document.getElementById('user-email').textContent = user.email;
//             document.getElementById('user-title').textContent = user.jobTitle || '';
            
//             // Show user info section
//             document.getElementById('user-info-section').classList.remove('hidden');
//         }
//     } catch (error) {
//         console.log('Error loading user profile:', error);
//     }
// }

// async function viewEmails() {
//     showStatus('Loading recent emails...', 'info');
    
//     try {
//         const response = await fetch('/get-mails/10');
        
//         if (response.ok) {
//             const data = await response.json();
//             displayEmails(data.value || []);
            
//             document.getElementById('email-section').classList.add('hidden');
//             document.getElementById('emails-section').classList.remove('hidden');
//             showStatus('', 'info');
//         } else {
//             const errorText = await response.text();
//             showStatus(`Failed to fetch emails: ${errorText}`, 'error');
//         }
//     } catch (error) {
//         showStatus(`Error: ${error.message}`, 'error');
//     }
// }

// function displayEmails(emails) {
//     const emailsList = document.getElementById('emails-list');
//     emailsList.innerHTML = '';

//     if (emails.length === 0) {
//         emailsList.innerHTML = '<p style="color: #666; text-align: center;">No emails found.</p>';
//         return;
//     }

//     emails.forEach(email => {
//         const emailDiv = document.createElement('div');
//         emailDiv.style.cssText = `
//             border: 1px solid #e1e5e9;
//             border-radius: 8px;
//             padding: 15px;
//             margin-bottom: 10px;
//             background: #f8f9fa;
//             text-align: left;
//         `;

//         const subject = email.subject || 'No Subject';
//         const sender = email.from?.emailAddress?.address || 'Unknown Sender';
//         const receivedTime = new Date(email.receivedDateTime).toLocaleString();
//         const preview = (email.bodyPreview || '').substring(0, 100) + '...';

//         emailDiv.innerHTML = `
//             <div style="font-weight: bold; color: #333; margin-bottom: 5px;">${subject}</div>
//             <div style="color: #0078d4; font-size: 14px; margin-bottom: 5px;">From: ${sender}</div>
//             <div style="color: #666; font-size: 12px; margin-bottom: 8px;">${receivedTime}</div>
//             <div style="color: #555; font-size: 14px;">${preview}</div>
//         `;

//         emailsList.appendChild(emailDiv);
//     });
// }

// function backToForm() {
//     document.getElementById('emails-section').classList.add('hidden');
//     document.getElementById('email-section').classList.remove('hidden');
// }

// function signOut() {
//     if (confirm('Are you sure you want to sign out?')) {
//         showStatus('Signing out...', 'info');
        
//         isAuthenticated = false;
//         updateStep(1);
        
//         document.getElementById('email-section').classList.add('hidden');
//         document.getElementById('emails-section').classList.add('hidden');
//         document.getElementById('user-info-section').classList.add('hidden');
//         document.getElementById('signin-section').classList.remove('hidden');
        
//         showStatus('Signed out successfully', 'success');
        
//         document.getElementById('recipient').value = '';
//         document.getElementById('subject').value = 'Wanna go out for lunch?';
//         document.getElementById('message').value = 'I know a sweet spot that just opened around us!';
        
//         // Clear user info
//         document.getElementById('user-name').textContent = 'Loading...';
//         document.getElementById('user-email').textContent = 'Loading...';
//         document.getElementById('user-title').textContent = '';
//     }
// }

// window.addEventListener('load', () => {
//     const urlParams = new URLSearchParams(window.location.search);
    
//     // Check for authentication success
//     if (urlParams.get('auth') === 'success') {
//         showStatus('Authentication successful! Welcome!', 'success');
//         isAuthenticated = true;
//         updateStep(2);
        
//         document.getElementById('signin-section').classList.add('hidden');
//         document.getElementById('email-section').classList.remove('hidden');
        
//         // Load user profile
//         loadUserProfile();
        
//         // Clean up URL
//         window.history.replaceState({}, document.title, '/app');
//     } else if (urlParams.get('auth') === 'error') {
//         showStatus('Authentication failed. Please try again.', 'error');
//         window.history.replaceState({}, document.title, '/app');
//     }
    
//     // If there's a code parameter, show processing message
//     if (urlParams.get('code')) {
//         showStatus('Processing authentication...', 'info');
//     }
// });

// document.addEventListener('DOMContentLoaded', () => {
//     document.getElementById('signin-text').setAttribute('data-original', 'Sign In with Microsoft');
//     document.getElementById('send-text').setAttribute('data-original', 'Send Email');
// });


function toggleRecipientMethod() {
    const method = document.getElementById('recipients-method').value;

    // Hide all recipient input groups
    document.getElementById('single-recipient-group').classList.add('hidden');
    document.getElementById('text-recipients-group').classList.add('hidden');
    document.getElementById('file-recipients-group').classList.add('hidden');
    document.getElementById('recipients-preview').classList.add('hidden');

    // Show the selected method
    switch(method) {
        case 'single':
            document.getElementById('single-recipient-group').classList.remove('hidden');
            break;
        case 'text':
            document.getElementById('text-recipients-group').classList.remove('hidden');
            break;
        case 'file':
            document.getElementById('file-recipients-group').classList.remove('hidden');
            break;
    }

    updateRecipientsPreview();
}

function updateRecipientsPreview() {
    const method = document.getElementById('recipients-method').value;
    const previewDiv = document.getElementById('recipients-preview');
    const listDiv = document.getElementById('recipients-list');
    const countDiv = document.getElementById('recipients-count');

    let recipients = [];

    switch(method) {
        case 'single':
            const singleEmail = document.getElementById('recipient').value.trim();
            if (singleEmail) {
                recipients = [{name: singleEmail.split('@')[0], email: singleEmail}];
            }
            break;
        case 'text':
            const textEmails = document.getElementById('recipients-text').value;
            const emails = parseEmailAddresses(textEmails);
            recipients = emails.map(email => ({name: email.split('@')[0], email: email}));
            break;
        case 'file':
            // File preview will be handled by file input change event
            return;
    }

    if (recipients.length > 0) {
        listDiv.innerHTML = recipients.map(recipient => 
            `<div style="margin: 4px 0; padding: 4px 8px; background: white; border-radius: 4px; border-left: 3px solid #0078d4;">
                <strong style="color: #333;">${recipient.name}</strong> 
                <span style="color: #666; font-size: 12px;">&lt;${recipient.email}&gt;</span>
            </div>`
        ).join('');
        countDiv.textContent = `Total recipients: ${recipients.length}`;
        previewDiv.classList.remove('hidden');
    } else {
        previewDiv.classList.add('hidden');
    }
}

function parseEmailAddresses(text) {
    if (!text) return [];

    // Split by common separators
    const separators = [',', ';', '\n', '\r\n', '\t'];
    let emails = [text];

    separators.forEach(sep => {
        const temp = [];
        emails.forEach(chunk => {
            temp.push(...chunk.split(sep));
        });
        emails = temp;
    });

    // Clean and validate
    const emailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g;
    const validEmails = [];

    emails.forEach(email => {
        const trimmed = email.trim();
        if (trimmed) {
            const matches = trimmed.match(emailRegex);
            if (matches) {
                validEmails.push(...matches);
            }
        }
    });

    return [...new Set(validEmails)]; // Remove duplicates
}

let isAuthenticated = false;

function showStatus(message, type = 'info') {
    const status = document.getElementById('status');
    status.textContent = message;
    status.className = `status ${type}`;
    status.style.display = 'block';
    
    if (type === 'success' || type === 'error') {
        setTimeout(() => {
            status.style.display = 'none';
        }, 5000);
    }
}

function updateStep(stepNumber) {
    for (let i = 1; i <= 3; i++) {
        const step = document.getElementById(`step${i}`);
        step.classList.remove('active', 'completed');
        
        if (i < stepNumber) {
            step.classList.add('completed');
        } else if (i === stepNumber) {
            step.classList.add('active');
        }
    }
}

function setLoading(buttonId, textId, isLoading, loadingText = 'Processing...') {
    const button = document.getElementById(buttonId);
    const text = document.getElementById(textId);
    
    if (isLoading) {
        button.disabled = true;
        text.innerHTML = `<span class="loading"></span>${loadingText}`;
    } else {
        button.disabled = false;
        text.innerHTML = text.getAttribute('data-original') || text.textContent.replace(/Processing\.\.\.|Signing in\.\.\.|Sending\.\.\.|Loading\.\.\./, '');
    }
}

function signIn() {
    setLoading('signin-btn', 'signin-text', true, 'Redirecting...');
    showStatus('Redirecting to Microsoft sign-in...', 'info');
    window.location.href = '/signin';
}

// Enhanced sendEmail function with multiple recipient support
async function sendEmail() {
    const method = document.getElementById('recipients-method').value;
    const subject = document.getElementById('subject').value;
    const message = document.getElementById('message').value;

    if (!subject.trim()) {
        showStatus('Please enter a subject', 'error');
        return;
    }

    if (!message.trim()) {
        showStatus('Please enter a message', 'error');
        return;
    }

    let recipients = [];
    let formData = new FormData();
    let useFormData = false;

    // Collect recipients based on method
    switch(method) {
        case 'single':
            const singleEmail = document.getElementById('recipient').value.trim();
            if (!singleEmail) {
                showStatus('Please enter a recipient email address', 'error');
                return;
            }
            recipients = [{name: singleEmail.split('@')[0], email: singleEmail}];
            break;
            
        case 'text':
            const textEmails = document.getElementById('recipients-text').value;
            const emails = parseEmailAddresses(textEmails);
            if (emails.length === 0) {
                showStatus('Please enter valid email addresses', 'error');
                return;
            }
            recipients = emails.map(email => ({name: email.split('@')[0], email: email}));
            break;
            
        case 'file':
            const fileInput = document.getElementById('recipients-file');
            if (!fileInput.files.length) {
                showStatus('Please select a file with recipients', 'error');
                return;
            }
            
            const file = fileInput.files[0];
            const allowedExtensions = ['txt', 'csv', 'xlsx', 'xls'];
            const fileExtension = file.name.split('.').pop().toLowerCase();
            
            if (!allowedExtensions.includes(fileExtension)) {
                showStatus('Please upload a valid file format (.txt, .csv, .xlsx, .xls)', 'error');
                return;
            }
            
            // Use FormData for file upload
            useFormData = true;
            formData.append('recipients_file', file);
            formData.append('subject', subject);
            formData.append('message', message);
            break;
    }

    setLoading('send-btn', 'send-text', true, 'Sending...');
    showStatus('Processing recipients and sending email(s)...', 'info');

    try {
        let response;

        if (useFormData) {
            // Send as form data for file upload
            response = await fetch('/send-mail', {
                method: 'POST',
                body: formData
            });
        } else {
            // Send as JSON for text/single recipient
            response = await fetch('/send-mail', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    recipients: recipients,
                    subject: subject,
                    message: message
                })
            });
        }

        if (response.ok) {
            const result = await response.json();
            if (result.campaign_id) {
                sessionStorage.setItem('campaign_id', result.campaign_id);
            }

            let statusMessage = `🎉 Successfully sent ${result.sent_count} email(s) out of ${result.total_recipients} recipients`;
            
            if (result.invalid_recipients && result.invalid_recipients.length > 0) {
                statusMessage += `\n❌ Invalid emails: ${result.invalid_recipients.join(', ')}`;
            }
            
            if (result.failed_recipients && result.failed_recipients.length > 0) {
                statusMessage += `\n⚠️ Failed to send to: ${result.failed_recipients.join(', ')}`;
            }
            
            showStatus(statusMessage, 'success');
            updateStep(3);
            
            // Reset form after successful send
            setTimeout(() => {
                document.getElementById('recipient').value = '';
                document.getElementById('recipients-text').value = '';
                document.getElementById('recipients-file').value = '';
                document.getElementById('subject').value = 'Wanna go out for lunch?';
                document.getElementById('message').value = 'Hi {name},\n\nI know a sweet spot that just opened around us! Would you like to join me for lunch?\n\nBest regards';
                document.getElementById('recipients-method').value = 'single';
                toggleRecipientMethod();
            }, 3000);
        } else {
            const errorData = await response.json();
            showStatus(`❌ Failed to send email: ${errorData.error}`, 'error');
        }
    } catch (error) {
        showStatus(`❌ Error: ${error.message}`, 'error');
    } finally {
        setLoading('send-btn', 'send-text', false);
    }
}

async function loadUserProfile() {
    try {
        const response = await fetch('/get-user-profile');
        if (response.ok) {
            const user = await response.json();
            document.getElementById('user-name').textContent = user.displayName;
            document.getElementById('user-email').textContent = user.email;
            document.getElementById('user-title').textContent = user.jobTitle || '';
            
            // Show user info section
            document.getElementById('user-info-section').classList.remove('hidden');
        }
    } catch (error) {
        console.log('Error loading user profile:', error);
    }
}

async function viewEmails() {
    showStatus('Loading recent emails...', 'info');
    
    try {
        const response = await fetch('/get-mails/10');
        
        if (response.ok) {
            const data = await response.json();
            displayEmails(data.value || []);
            
            document.getElementById('email-section').classList.add('hidden');
            document.getElementById('emails-section').classList.remove('hidden');
            showStatus('', 'info');
        } else {
            const errorText = await response.text();
            showStatus(`Failed to fetch emails: ${errorText}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    }
}

function displayEmails(emails) {
    const emailsList = document.getElementById('emails-list');
    emailsList.innerHTML = '';

    if (emails.length === 0) {
        emailsList.innerHTML = '<p style="color: #666; text-align: center;">No emails found.</p>';
        return;
    }

    emails.forEach(email => {
        const emailDiv = document.createElement('div');
        emailDiv.style.cssText = `
            border: 1px solid #e1e5e9;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            background: #f8f9fa;
            text-align: left;
        `;

        const subject = email.subject || 'No Subject';
        const sender = email.from?.emailAddress?.address || 'Unknown Sender';
        const receivedTime = new Date(email.receivedDateTime).toLocaleString();
        const preview = (email.bodyPreview || '').substring(0, 100) + '...';

        emailDiv.innerHTML = `
            <div style="font-weight: bold; color: #333; margin-bottom: 5px;">${subject}</div>
            <div style="color: #0078d4; font-size: 14px; margin-bottom: 5px;">From: ${sender}</div>
            <div style="color: #666; font-size: 12px; margin-bottom: 8px;">${receivedTime}</div>
            <div style="color: #555; font-size: 14px;">${preview}</div>
        `;

        emailsList.appendChild(emailDiv);
    });
}

function backToForm() {
    document.getElementById('emails-section').classList.add('hidden');
    document.getElementById('email-section').classList.remove('hidden');
}

function signOut() {
    if (confirm('Are you sure you want to sign out?')) {
        showStatus('Signing out...', 'info');
        
        isAuthenticated = false;
        updateStep(1);
        
        document.getElementById('email-section').classList.add('hidden');
        document.getElementById('emails-section').classList.add('hidden');
        document.getElementById('user-info-section').classList.add('hidden');
        document.getElementById('signin-section').classList.remove('hidden');
        
        showStatus('Signed out successfully', 'success');
        
        document.getElementById('recipient').value = '';
        document.getElementById('recipients-text').value = '';
        document.getElementById('recipients-file').value = '';
        document.getElementById('subject').value = 'Wanna go out for lunch?';
        document.getElementById('message').value = 'I know a sweet spot that just opened around us!';
        document.getElementById('recipients-method').value = 'single';
        toggleRecipientMethod();
        
        // Clear user info
        document.getElementById('user-name').textContent = 'Loading...';
        document.getElementById('user-email').textContent = 'Loading...';
        document.getElementById('user-title').textContent = '';
    }
}

// Add event listeners for real-time preview and file processing
document.addEventListener('DOMContentLoaded', () => {
    // Set original text attributes
    document.getElementById('signin-text').setAttribute('data-original', 'Sign In with Microsoft');
    document.getElementById('send-text').setAttribute('data-original', 'Send Email');
    
    // Add event listeners for recipient preview updates
    document.getElementById('recipient').addEventListener('input', updateRecipientsPreview);
    document.getElementById('recipients-text').addEventListener('input', updateRecipientsPreview);

    // File upload handling with preview
    document.getElementById('recipients-file').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            const listDiv = document.getElementById('recipients-list');
            const previewDiv = document.getElementById('recipients-preview');
            const countDiv = document.getElementById('recipients-count');
            
            showStatus('Processing file...', 'info');
            
            try {
                const fileExtension = file.name.split('.').pop().toLowerCase();
                let recipients = [];
                
                if (fileExtension === 'txt') {
                    const text = await file.text();
                    const emails = parseEmailAddresses(text);
                    recipients = emails.map(email => ({name: email.split('@')[0], email: email}));
                } else if (['csv', 'xlsx', 'xls'].includes(fileExtension)) {
                    // For Excel/CSV files, we'll show a preview message
                    // The actual processing will happen on the server
                    listDiv.innerHTML = `
                        <div style="text-align: center; padding: 20px; color: #666;">
                            <div style="font-size: 24px; margin-bottom: 10px;">📊</div>
                            <div>Excel/CSV file selected: <strong>${file.name}</strong></div>
                            <div style="font-size: 12px; margin-top: 5px;">File will be processed when you click "Send Email"</div>
                        </div>
                    `;
                    countDiv.textContent = `File size: ${(file.size / 1024).toFixed(1)} KB`;
                    previewDiv.classList.remove('hidden');
                    showStatus('File selected. Click "Send Email" to process and send.', 'success');
                    return;
                }
                
                if (recipients.length > 0) {
                    listDiv.innerHTML = recipients.slice(0, 10).map(recipient => 
                        `<div style="margin: 4px 0; padding: 4px 8px; background: white; border-radius: 4px; border-left: 3px solid #0078d4;">
                            <strong style="color: #333;">${recipient.name}</strong> 
                            <span style="color: #666; font-size: 12px;">&lt;${recipient.email}&gt;</span>
                        </div>`
                    ).join('') + (recipients.length > 10 ? `<div style="text-align: center; color: #666; font-size: 12px; margin-top: 8px;">... and ${recipients.length - 10} more</div>` : '');
                    
                    countDiv.textContent = `Total recipients: ${recipients.length}`;
                    previewDiv.classList.remove('hidden');
                    showStatus(`Found ${recipients.length} valid email addresses in file`, 'success');
                } else {
                    showStatus('No valid email addresses found in file', 'error');
                }
            } catch (error) {
                showStatus(`Error reading file: ${error.message}`, 'error');
                console.error('File processing error:', error);
            }
        }
    });
});

window.addEventListener('load', () => {
    const urlParams = new URLSearchParams(window.location.search);
    
    // Check for authentication success
    if (urlParams.get('auth') === 'success') {
        showStatus('Authentication successful! Welcome!', 'success');
        isAuthenticated = true;
        updateStep(2);
        
        document.getElementById('signin-section').classList.add('hidden');
        document.getElementById('email-section').classList.remove('hidden');
        
        // Load user profile
        loadUserProfile();
        
        // Clean up URL
        window.history.replaceState({}, document.title, '/app');
    } else if (urlParams.get('auth') === 'error') {
        showStatus('Authentication failed. Please try again.', 'error');
        window.history.replaceState({}, document.title, '/app');
    }
    
    // If there's a code parameter, show processing message
    if (urlParams.get('code')) {
        showStatus('Processing authentication...', 'info');
    }
});


// Email Tracking Variables
let trackingData = [];
let filteredTrackingData = [];
let currentPage = 1;
const itemsPerPage = 10;

// View Tracking Dashboard
// async function viewTracking() {
//     showStatus('Loading email tracking data...', 'info');
    
//     try {
//         const response = await fetch('/api/analytics/campaign/<campaign_id>');
        
//         if (response.ok) {
//             const data = await response.json();
//             trackingData = data.emails || [];
//             filteredTrackingData = [...trackingData];
            
//             updateTrackingSummary();
//             displayTrackingData();
            
//             document.getElementById('email-section').classList.add('hidden');
//             document.getElementById('emails-section').classList.add('hidden');
//             document.getElementById('tracking-section').classList.remove('hidden');
//             showStatus('', 'info');
//         } else {
//             const errorData = await response.json();
//             showStatus(`Failed to load tracking data: ${errorData.error}`, 'error');
//         }
//     } catch (error) {
//         showStatus(`Error: ${error.message}`, 'error');
//     }
// }
// async function viewTracking() {
//     showStatus('Loading email tracking data...', 'info');

//     const campaignId = sessionStorage.getItem('campaign_id');

//     if (!campaignId) {
//         showStatus('No campaign ID found. Please send a campaign first.', 'error');
//         return;
//     }

//     try {
//         const response = await fetch(`/api/analytics/campaign/${campaignId}`);

//         if (response.ok) {
//             const data = await response.json();
//             trackingData = data.tracking_data || [];
//             filteredTrackingData = [...trackingData];

//             updateTrackingSummary();      // Update summary UI (e.g., sent count, etc.)
//             displayTrackingData();        // Render email tracking details

//             // Toggle UI sections
//             document.getElementById('email-section')?.classList.add('hidden');
//             document.getElementById('emails-section')?.classList.add('hidden');
//             document.getElementById('tracking-section')?.classList.remove('hidden');

//             showStatus('', 'info');
//         } else {
//             const errorData = await response.json();
//             showStatus(`Failed to load tracking data: ${errorData.error}`, 'error');
//         }
//     } catch (error) {
//         showStatus(`Error: ${error.message}`, 'error');
//     }
// }
async function viewTracking() {
    showStatus('Loading email tracking data...', 'info');

    const campaignId = sessionStorage.getItem('campaign_id');

    if (!campaignId) {
        showStatus('No campaign ID found. Please send a campaign first.', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/analytics/campaign/${campaignId}`);

        if (response.ok) {
            const data = await response.json();

            // Convert recipients into enriched trackingData
            trackingData = data.recipients.map(r => ({
                tracking_id: r.tracking_id,
                recipient_name: r.name,
                recipient_email: r.email,
                subject: data.subject,
                opens: r.opens,
                clicks: r.clicks,
                opened_at: r.first_open,
                clicked_at: r.clicks > 0 ? r.first_open : null,
                opened: r.opens > 0,
                clicked: r.clicks > 0,
                sent_at: r.first_open || new Date().toISOString() // fallback
            }));

            filteredTrackingData = [...trackingData];

            updateTrackingSummary(data);
            displayTrackingData();

            document.getElementById('email-section').classList.add('hidden');
            document.getElementById('emails-section').classList.add('hidden');
            document.getElementById('tracking-section').classList.remove('hidden');
            showStatus('', 'info');
        } else {
            const errorData = await response.json();
            showStatus(`Failed to load tracking data: ${errorData.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    }
}


function updateTrackingSummary(campaignData) {
    const totalSent = campaignData.total_sent;
    const totalOpened = campaignData.unique_opens;
    const totalClicked = campaignData.unique_clicks;
    const openRate = campaignData.open_rate;

    document.getElementById('total-sent').textContent = totalSent;
    document.getElementById('total-opened').textContent = totalOpened;
    document.getElementById('total-clicked').textContent = totalClicked;
    document.getElementById('open-rate').textContent = `${openRate}%`;
}


// Display Tracking Data
// function displayTrackingData() {
//     const trackingList = document.getElementById('tracking-list');
//     const paginationDiv = document.getElementById('tracking-pagination');
    
//     if (filteredTrackingData.length === 0) {
//         trackingList.innerHTML = '<div class="no-data">📭 No tracking data available</div>';
//         paginationDiv.style.display = 'none';
//         return;
//     }

//     // Calculate pagination
//     const totalPages = Math.ceil(filteredTrackingData.length / itemsPerPage);
//     const startIndex = (currentPage - 1) * itemsPerPage;
//     const endIndex = startIndex + itemsPerPage;
//     const pageData = filteredTrackingData.slice(startIndex, endIndex);

//     // Display tracking items
//     trackingList.innerHTML = pageData.map(email => createTrackingItem(email)).join('');

//     // Update pagination
//     if (totalPages > 1) {
//         paginationDiv.style.display = 'flex';
//         document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
//         document.getElementById('prev-page').disabled = currentPage === 1;
//         document.getElementById('next-page').disabled = currentPage === totalPages;
//     } else {
//         paginationDiv.style.display = 'none';
//     }
// }
function displayTrackingData() {
    const trackingList = document.getElementById('tracking-list');
    const paginationDiv = document.getElementById('tracking-pagination');

    if (filteredTrackingData.length === 0) {
        trackingList.innerHTML = '<div class="no-data">📭 No tracking data available</div>';
        paginationDiv.style.display = 'none';
        return;
    }

    // Calculate pagination
    const totalPages = Math.ceil(filteredTrackingData.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const pageData = filteredTrackingData.slice(startIndex, endIndex);

    // Display tracking items
    trackingList.innerHTML = pageData.map(email => {
        const statusBadge = getStatusBadge(email);
        const activityTimeline = getActivityTimeline(email);

        return `
            <div class="tracking-item">
                <div class="tracking-header">
                    <div class="tracking-recipient">
                        <strong>${email.recipient_name || email.recipient_email.split('@')[0]}</strong>
                        <span class="recipient-email">&lt;${email.recipient_email}&gt;</span>
                    </div>
                    <div class="tracking-status">
                        ${statusBadge}
                    </div>
                </div>

                <div class="tracking-subject">
                    📧 ${email.subject}
                </div>

                <div class="tracking-details">
                    <div class="tracking-timeline">
                        ${activityTimeline}
                    </div>

                    <div class="tracking-actions">
                        <button class="btn-small" onclick="viewEmailDetails('${email.tracking_id}')" title="View Details">
                            👁️ Details
                        </button>
                        <button class="btn-small" onclick="resendEmail('${email.tracking_id}')" title="Resend Email">
                            🔄 Resend
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Update pagination controls
    if (totalPages > 1) {
        paginationDiv.style.display = 'flex';
        document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
        document.getElementById('prev-page').disabled = currentPage === 1;
        document.getElementById('next-page').disabled = currentPage === totalPages;
    } else {
        paginationDiv.style.display = 'none';
    }
}

// Create Tracking Item HTML
function createTrackingItem(email) {
    const sentTime = new Date(email.sent_at).toLocaleString();
    const openedTime = email.opened_at ? new Date(email.opened_at).toLocaleString() : null;
    const clickedTime = email.clicked_at ? new Date(email.clicked_at).toLocaleString() : null;
    
    const statusBadge = getStatusBadge(email);
    const activityTimeline = getActivityTimeline(email);

    return `
        <div class="tracking-item">
            <div class="tracking-header">
                <div class="tracking-recipient">
                    <strong>${email.recipient_name || email.recipient_email.split('@')[0]}</strong>
                    <span class="recipient-email">&lt;${email.recipient_email}&gt;</span>
                </div>
                <div class="tracking-status">
                    ${statusBadge}
                </div>
            </div>
            
            <div class="tracking-subject">
                📧 ${email.subject}
            </div>
            
            <div class="tracking-details">
                <div class="tracking-timeline">
                    ${activityTimeline}
                </div>
                
                <div class="tracking-actions">
                    <button class="btn-small" onclick="viewEmailDetails('${email.tracking_id}')" title="View Details">
                        👁️ Details
                    </button>
                    <button class="btn-small" onclick="resendEmail('${email.tracking_id}')" title="Resend Email">
                        🔄 Resend
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Get Status Badge
function getStatusBadge(email) {
    if (email.clicked) {
        return '<span class="status-badge status-clicked">🖱️ Clicked</span>';
    } else if (email.opened) {
        return '<span class="status-badge status-opened">👀 Opened</span>';
    } else {
        return '<span class="status-badge status-sent">📤 Sent</span>';
    }
}

// Get Activity Timeline
function getActivityTimeline(email) {
    const timeline = [];
    
    timeline.push(`
        <div class="timeline-item">
            <div class="timeline-icon">📤</div>
            <div class="timeline-content">
                <div class="timeline-title">Email Sent</div>
                <div class="timeline-time">${new Date(email.sent_at).toLocaleString()}</div>
            </div>
        </div>
    `);

    if (email.opened_at) {
        timeline.push(`
            <div class="timeline-item">
                <div class="timeline-icon">👀</div>
                <div class="timeline-content">
                    <div class="timeline-title">Email Opened</div>
                    <div class="timeline-time">${new Date(email.opened_at).toLocaleString()}</div>
                </div>
            </div>
        `);
    }

    if (email.clicked_at) {
        timeline.push(`
            <div class="timeline-item">
                <div class="timeline-icon">🖱️</div>
                <div class="timeline-content">
                    <div class="timeline-title">Link Clicked</div>
                    <div class="timeline-time">${new Date(email.clicked_at).toLocaleString()}</div>
                </div>
            </div>
        `);
    }

    return timeline.join('');
}

// Filter Tracking Data
function filterTrackingData() {
    const dateFilter = document.getElementById('date-filter').value;
    const statusFilter = document.getElementById('status-filter').value;
    
    filteredTrackingData = trackingData.filter(email => {
        // Date filter
        let passesDateFilter = true;
        if (dateFilter !== 'all') {
            const sentDate = new Date(email.sent_at);
            const now = new Date();
            
            switch (dateFilter) {
                case 'today':
                    passesDateFilter = sentDate.toDateString() === now.toDateString();
                    break;
                case 'week':
                    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    passesDateFilter = sentDate >= weekAgo;
                    break;
                case 'month':
                    const monthAgo = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
                    passesDateFilter = sentDate >= monthAgo;
                    break;
            }
        }

        // Status filter
        let passesStatusFilter = true;
        if (statusFilter !== 'all') {
            switch (statusFilter) {
                case 'sent':
                    passesStatusFilter = true; // All emails are sent
                    break;
                case 'opened':
                    passesStatusFilter = email.opened;
                    break;
                case 'clicked':
                    passesStatusFilter = email.clicked;
                    break;
                case 'not-opened':
                    passesStatusFilter = !email.opened;
                    break;
            }
        }

        return passesDateFilter && passesStatusFilter;
    });

    currentPage = 1;
    updateTrackingSummary();
    displayTrackingData();
}

// Refresh Tracking Data
async function refreshTrackingData() {
    showStatus('Refreshing tracking data...', 'info');
    await viewTracking();
}

// Change Page
function changePage(direction) {
    const totalPages = Math.ceil(filteredTrackingData.length / itemsPerPage);
    
    if (direction === 1 && currentPage < totalPages) {
        currentPage++;
    } else if (direction === -1 && currentPage > 1) {
        currentPage--;
    }
    
    displayTrackingData();
}

// View Email Details
async function viewEmailDetails(trackingId) {
    showStatus('Loading email details...', 'info');
    
    try {
        const response = await fetch(`/api/tracking/email/${trackingId}`);
        
        if (response.ok) {
            const emailData = await response.json();
            showEmailDetailsModal(emailData);
            showStatus('', 'info');
        } else {
            const errorData = await response.json();
            showStatus(`Failed to load email details: ${errorData.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    }
}

// Show Email Details Modal
function showEmailDetailsModal(emailData) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>📧 Email Details</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="email-detail-section">
                    <h4>📋 Basic Information</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <strong>Recipient:</strong> ${emailData.recipient_name || 'N/A'} &lt;${emailData.recipient_email}&gt;
                        </div>
                        <div class="detail-item">
                            <strong>Subject:</strong> ${emailData.subject}
                        </div>
                        <div class="detail-item">
                            <strong>Sent At:</strong> ${new Date(emailData.sent_at).toLocaleString()}
                        </div>
                        <div class="detail-item">
                            <strong>Tracking ID:</strong> ${emailData.tracking_id}
                        </div>
                    </div>
                </div>
                
                <div class="email-detail-section">
                    <h4>📊 Tracking Status</h4>
                    <div class="status-grid">
                        <div class="status-item ${emailData.opened ? 'status-active' : ''}">
                            <div class="status-icon">👀</div>
                            <div class="status-text">
                                <strong>Opened</strong>
                                <div>${emailData.opened_at ? new Date(emailData.opened_at).toLocaleString() : 'Not opened'}</div>
                            </div>
                        </div>
                        <div class="status-item ${emailData.clicked ? 'status-active' : ''}">
                            <div class="status-icon">🖱️</div>
                            <div class="status-text">
                                <strong>Clicked</strong>
                                <div>${emailData.clicked_at ? new Date(emailData.clicked_at).toLocaleString() : 'No clicks'}</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                ${emailData.message ? `
                <div class="email-detail-section">
                    <h4>💬 Message Preview</h4>
                    <div class="message-preview">${emailData.message.substring(0, 200)}${emailData.message.length > 200 ? '...' : ''}</div>
                </div>
                ` : ''}
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal()">Close</button>
                <button class="btn" onclick="resendEmail('${emailData.tracking_id}'); closeModal();">🔄 Resend Email</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('show'), 10);
}

// Close Modal
function closeModal() {
    const modal = document.querySelector('.modal-overlay');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);
    }
}

// Resend Email
async function resendEmail(trackingId) {
    if (!confirm('Are you sure you want to resend this email?')) {
        return;
    }

    showStatus('Resending email...', 'info');
    
    try {
        const response = await fetch(`/api/tracking/resend/${trackingId}`, {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            showStatus('Email resent successfully!', 'success');
            refreshTrackingData();
        } else {
            const errorData = await response.json();
            showStatus(`Failed to resend email: ${errorData.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    }
}

// Update the existing backToForm function to handle tracking section
function backToForm() {
    document.getElementById('emails-section').classList.add('hidden');
    document.getElementById('tracking-section').classList.add('hidden');
    document.getElementById('email-section').classList.remove('hidden');
}

// Add this to the existing DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', () => {
    // ... existing code ...
    
    // Close modal when clicking outside
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            closeModal();
        }
    });
    
    // Close modal with Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
});