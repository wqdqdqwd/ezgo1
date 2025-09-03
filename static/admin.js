document.addEventListener('DOMContentLoaded', () => {

    // DOM elements in a single object
    const UIElements = {
        adminContainer: document.getElementById('admin-container'),
        adminLogoutButton: document.getElementById('admin-logout-button'),
        usersTableBody: document.getElementById('users-table-body'),
        userCountSpan: document.getElementById('user-count'),
        activeUsersCountSpan: document.getElementById('active-users-count'),
        trialUsersCountSpan: document.getElementById('trial-users-count'),
        expiredUsersCountSpan: document.getElementById('expired-users-count'),
        tableErrorMessage: document.getElementById('table-error-message'),
        currentYearSpan: document.getElementById('current-year'),
    };

    const firebaseServices = {
        auth: null,
    };

    // Loading state helper function
    function setLoadingState(isLoading, message = "Please wait...", targetElement = UIElements.usersTableBody) {
        if (!targetElement) return;
        
        if (isLoading) {
            targetElement.innerHTML = `<tr><td colspan="5" class="text-center text-muted loading-message"><i class="fas fa-spinner fa-spin mr-2"></i> ${message}</td></tr>`;
            if (UIElements.tableErrorMessage) {
                UIElements.tableErrorMessage.style.display = 'none';
            }
        }
    }

    // Error message helper function
    function showErrorMessage(message) {
        if (UIElements.tableErrorMessage) {
            UIElements.tableErrorMessage.textContent = message;
            UIElements.tableErrorMessage.style.display = 'block';
            UIElements.tableErrorMessage.className = 'status-message error';
        }
        if (UIElements.usersTableBody) {
            UIElements.usersTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">${message}</td></tr>`;
        }
    }

    // Success message helper function
    function showSuccessMessage(message) {
        if (UIElements.tableErrorMessage) {
            UIElements.tableErrorMessage.textContent = message;
            UIElements.tableErrorMessage.style.display = 'block';
            UIElements.tableErrorMessage.className = 'status-message success';
            
            setTimeout(() => {
                UIElements.tableErrorMessage.style.display = 'none';
            }, 3000);
        }
    }

    /**
     * Secure backend communication with Firebase auth token
     */
    async function fetchAdminApi(endpoint, options = {}) {
        const user = firebaseServices.auth?.currentUser;
        if (!user) {
            alert("Your session has expired or you don't have permission. Please login again.");
            window.location.href = '/';
            return null;
        }
        
        try {
            const idToken = await user.getIdToken(true); 
            
            const headers = {
                'Authorization': `Bearer ${idToken}`,
                'Content-Type': 'application/json',
                ...options.headers
            };
            
            const response = await fetch(endpoint, { ...options, headers });
            
            if (!response.ok) {
                let errorData;
                try {
                    errorData = await response.json();
                } catch {
                    errorData = { detail: response.statusText };
                }
                
                console.error(`Admin API Error (${response.status}) - ${endpoint}:`, errorData);
                
                if (response.status === 401 || response.status === 403) {
                    alert("You don't have permission to access this resource.");
                    window.location.href = '/';
                    return null;
                }
                
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }
            
            return response.json();
        } catch (error) {
            console.error("Admin API request error:", error);
            showErrorMessage(`API request failed: ${error.message}`);
            return null;
        }
    }

    /**
     * Load users from backend and update the table
     */
    async function loadUsers() {
        setLoadingState(true, "Loading users...");
        
        // Reset counters
        const counters = {
            total: 0,
            active: 0,
            trial: 0,
            expired: 0
        };

        try {
            const response = await fetchAdminApi('/api/admin/users');
            if (!response) {
                throw new Error("Failed to fetch users.");
            }
            
            if (!response.users) {
                throw new Error("No user data received.");
            }
            
            const users = response.users;
            
            if (!UIElements.usersTableBody) {
                throw new Error("Users table not found.");
            }
            
            UIElements.usersTableBody.innerHTML = '';

            if (Object.keys(users).length === 0) {
                UIElements.usersTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No users found.</td></tr>';
                updateCounters(counters);
                return;
            }

            for (const uid in users) {
                const user = users[uid];
                counters.total++;
                
                // Count by status
                switch (user.subscription_status) {
                    case 'active':
                        counters.active++;
                        break;
                    case 'trial':
                        counters.trial++;
                        break;
                    case 'expired':
                    case 'inactive':
                        counters.expired++;
                        break;
                }
                
                const expiryDate = user.subscription_expiry 
                    ? new Date(user.subscription_expiry).toLocaleString('tr-TR', { 
                        year: 'numeric',
                        month: '2-digit', 
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    })
                    : 'N/A';
                
                let statusBadgeClass = 'inactive';
                let statusDisplayText = 'Unknown';
                
                switch (user.subscription_status) {
                    case 'active':
                        statusBadgeClass = 'active';
                        statusDisplayText = 'Active';
                        break;
                    case 'trial':
                        statusBadgeClass = 'trial';
                        statusDisplayText = 'Trial';
                        break;
                    case 'expired':
                        statusBadgeClass = 'inactive';
                        statusDisplayText = 'Expired';
                        break;
                    case 'inactive':
                        statusBadgeClass = 'inactive';
                        statusDisplayText = 'Inactive';
                        break;
                }

                const row = document.createElement('tr');
                row.className = 'user-row';
                row.innerHTML = `
                    <td class="user-email" title="${user.email || 'N/A'}">
                        <div class="user-info">
                            <span class="email-text">${(user.email || 'N/A').length > 30 ? (user.email || 'N/A').substring(0, 30) + '...' : (user.email || 'N/A')}</span>
                            ${user.registration_date ? `<span class="join-date">Joined: ${new Date(user.registration_date).toLocaleDateString('tr-TR')}</span>` : ''}
                            ${user.language ? `<span class="user-language">Lang: ${user.language.toUpperCase()}</span>` : ''}
                        </div>
                    </td>
                    <td>
                        <span class="status-badge ${statusBadgeClass}">${statusDisplayText}</span>
                    </td>
                    <td class="expiry-cell">
                        <div class="expiry-info">
                            <span class="expiry-date">${expiryDate}</span>
                            ${user.subscription_expiry ? `<span class="days-remaining" data-expiry="${user.subscription_expiry}"></span>` : ''}
                        </div>
                    </td>
                    <td>
                        <span class="user-id-text" title="Click to copy ${uid}">
                            ${uid.length > 12 ? uid.substring(0, 12) + '...' : uid}
                        </span>
                    </td>
                    <td class="actions-cell">
                        <div class="action-buttons">
                            <button class="btn btn-success btn-sm activate-btn" data-uid="${uid}" data-email="${user.email || 'Unknown'}" title="Add 30 days">
                                <i class="fas fa-plus"></i> 
                                <span class="btn-text">30 Days</span>
                            </button>
                            <button class="btn btn-outline btn-sm user-details-btn" data-uid="${uid}" title="View details">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </td>
                `;
                UIElements.usersTableBody.appendChild(row);
            }
            
            updateCounters(counters);

            // Add event listeners to new buttons
            document.querySelectorAll('.activate-btn').forEach(button => {
                button.addEventListener('click', handleActivateSubscription);
            });

            document.querySelectorAll('.user-details-btn').forEach(button => {
                button.addEventListener('click', handleViewUserDetails);
            });

            // Add copy functionality to user IDs
            document.querySelectorAll('.user-id-text').forEach(element => {
                element.addEventListener('click', (e) => {
                    const fullId = e.target.getAttribute('title').replace('Click to copy ', '');
                    copyToClipboard(fullId);
                    showCopyFeedback(e.target);
                });
                element.style.cursor = 'pointer';
            });

            // Calculate days remaining
            updateDaysRemaining();

            if (UIElements.tableErrorMessage) {
                UIElements.tableErrorMessage.style.display = 'none';
            }

        } catch (error) {
            console.error("Error loading users:", error);
            showErrorMessage(`Failed to load users: ${error.message}`);
            updateCounters(counters);
        }
    }

    function updateCounters(counters) {
        if (UIElements.userCountSpan) {
            UIElements.userCountSpan.textContent = counters.total;
        }
        if (UIElements.activeUsersCountSpan) {
            UIElements.activeUsersCountSpan.textContent = counters.active;
        }
        if (UIElements.trialUsersCountSpan) {
            UIElements.trialUsersCountSpan.textContent = counters.trial;
        }
        if (UIElements.expiredUsersCountSpan) {
            UIElements.expiredUsersCountSpan.textContent = counters.expired;
        }
    }

    function updateDaysRemaining() {
        document.querySelectorAll('.days-remaining').forEach(element => {
            const expiryDate = element.dataset.expiry;
            if (!expiryDate) return;

            const now = new Date();
            const expiry = new Date(expiryDate);
            const diffTime = expiry - now;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

            if (diffDays > 0) {
                element.textContent = `(${diffDays} days left)`;
                element.className = 'days-remaining positive';
            } else if (diffDays === 0) {
                element.textContent = '(expires today)';
                element.className = 'days-remaining warning';
            } else {
                element.textContent = `(expired ${Math.abs(diffDays)} days ago)`;
                element.className = 'days-remaining expired';
            }
        });
    }

    /**
     * Handle subscription activation
     */
    async function handleActivateSubscription(event) {
        const button = event.target.closest('.activate-btn');
        if (!button) return;

        const userIdToActivate = button.dataset.uid;
        const userEmail = button.dataset.email || 'Unknown user';
        
        if (!userIdToActivate) {
            alert('User ID not found.');
            return;
        }

        if (!confirm(`Extend subscription for ${userEmail} (${userIdToActivate.substring(0, 10)}...) by 30 days?`)) {
            return;
        }

        const originalButtonHtml = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        try {
            const result = await fetchAdminApi('/api/admin/activate-subscription', {
                method: 'POST',
                body: JSON.stringify({ user_id: userIdToActivate })
            });

            if (result && result.success) {
                showSuccessMessage(`Successfully extended subscription for ${userEmail}!`);
                await loadUsers(); // Refresh table
            } else {
                alert(`Failed to extend subscription: ${result?.detail || 'Unknown error.'}`);
            }
        } catch (error) {
            alert(`Error extending subscription: ${error.message}`);
        } finally {
            button.innerHTML = originalButtonHtml;
            button.disabled = false;
        }
    }

    /**
     * Handle view user details
     */
    async function handleViewUserDetails(event) {
        const button = event.target.closest('.user-details-btn');
        if (!button) return;

        const userId = button.dataset.uid;
        if (!userId) return;

        try {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            const result = await fetchAdminApi(`/api/admin/user-details/${userId}`);
            
            if (result && result.user) {
                showUserDetailsModal(result.user, userId);
            } else {
                alert('Failed to load user details');
            }
        } catch (error) {
            alert(`Error loading user details: ${error.message}`);
        } finally {
            button.innerHTML = '<i class="fas fa-eye"></i>';
            button.disabled = false;
        }
    }

    function showUserDetailsModal(user, userId) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content user-details-modal">
                <div class="modal-header">
                    <h3><i class="fas fa-user"></i> User Details</h3>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="user-details-content">
                    <div class="detail-group">
                        <label>User ID:</label>
                        <code class="user-id-full">${userId}</code>
                    </div>
                    <div class="detail-group">
                        <label>Email:</label>
                        <span>${user.email || 'N/A'}</span>
                    </div>
                    <div class="detail-group">
                        <label>Language:</label>
                        <span>${user.language ? user.language.toUpperCase() : 'N/A'}</span>
                    </div>
                    <div class="detail-group">
                        <label>Registration Date:</label>
                        <span>${user.registration_date ? new Date(user.registration_date).toLocaleDateString('tr-TR') : 'N/A'}</span>
                    </div>
                    <div class="detail-group">
                        <label>Subscription Status:</label>
                        <span class="status-badge ${user.subscription_status || 'inactive'}">${user.subscription_status || 'inactive'}</span>
                    </div>
                    <div class="detail-group">
                        <label>Subscription Expiry:</label>
                        <span>${user.subscription_expiry ? new Date(user.subscription_expiry).toLocaleString('tr-TR') : 'N/A'}</span>
                    </div>
                    <div class="detail-group">
                        <label>Has API Keys:</label>
                        <span class="status-badge ${user.has_api_keys ? 'active' : 'inactive'}">${user.has_api_keys ? 'Yes' : 'No'}</span>
                    </div>
                    <div class="detail-group">
                        <label>Selected Pair:</label>
                        <span>${user.selected_pair || 'BTCUSDT'}</span>
                    </div>
                    <div class="detail-group">
                        <label>Bot Status:</label>
                        <span class="status-badge ${user.bot_status === 'active' ? 'active' : 'inactive'}">${user.bot_status || 'inactive'}</span>
                    </div>
                    ${user.last_login ? `
                        <div class="detail-group">
                            <label>Last Login:</label>
                            <span>${new Date(user.last_login).toLocaleString('tr-TR')}</span>
                        </div>
                    ` : ''}
                    ${user.total_trades ? `
                        <div class="detail-group">
                            <label>Total Trades:</label>
                            <span>${user.total_trades}</span>
                        </div>
                    ` : ''}
                    ${user.total_pnl ? `
                        <div class="detail-group">
                            <label>Total P&L:</label>
                            <span class="${user.total_pnl >= 0 ? 'text-success' : 'text-danger'}">${user.total_pnl >= 0 ? '+' : ''}${user.total_pnl}%</span>
                        </div>
                    ` : ''}
                </div>
                <div class="modal-actions">
                    <button class="btn btn-primary" onclick="this.closest('.modal').remove()">
                        <i class="fas fa-check"></i> Close
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        modal.style.display = 'flex';
        
        // Close on outside click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    /**
     * Handle logout
     */
    async function handleLogout() {
        if (confirm("Are you sure you want to logout from admin panel?")) {
            try {
                await firebaseServices.auth.signOut();
            } catch (error) {
                console.error("Logout error:", error);
                alert("Error during logout.");
            }
        }
    }

    /**
     * Copy to clipboard functionality
     */
    function copyToClipboard(text) {
        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                console.log('Text copied to clipboard');
            }).catch(err => {
                console.error('Could not copy text: ', err);
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    }

    function fallbackCopy(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        
        try {
            document.execCommand('copy');
        } catch (err) {
            console.error('Fallback copy failed: ', err);
        } finally {
            document.body.removeChild(textArea);
        }
    }

    function showCopyFeedback(element) {
        const originalText = element.textContent;
        const originalBg = element.style.backgroundColor;
        
        element.textContent = 'Copied!';
        element.style.backgroundColor = 'var(--success-color)';
        element.style.color = 'white';
        
        setTimeout(() => {
            element.textContent = originalText;
            element.style.backgroundColor = originalBg;
            element.style.color = '';
        }, 1000);
    }

    /**
     * Page cleanup before unload
     */
    window.addEventListener('beforeunload', () => {
        const activeButtons = document.querySelectorAll('button:disabled');
        if (activeButtons.length > 0) {
            return "There are active operations. Are you sure you want to close?";
        }
    });

    /**
     * Main app initialization function
     */
    async function initializeApp() {
        // Set current year
        if (UIElements.currentYearSpan) {
            UIElements.currentYearSpan.textContent = new Date().getFullYear();
        }

        try {
            // Get Firebase configuration from backend
            const response = await fetch('/api/firebase-config');
            if (!response.ok) {
                throw new Error(`Could not fetch Firebase config: ${response.status} ${response.statusText}`);
            }
            
            const firebaseConfig = await response.json();

            if (!firebaseConfig || !firebaseConfig.apiKey) {
                throw new Error('Invalid Firebase configuration received from server.');
            }

            // Initialize Firebase
            firebase.initializeApp(firebaseConfig);
            firebaseServices.auth = firebase.auth();

            // Listen to user auth state changes
            firebaseServices.auth.onAuthStateChanged(async (user) => {
                if (user) {
                    // Admin permission check is done on backend
                    if (UIElements.adminContainer) {
                        UIElements.adminContainer.style.display = 'flex';
                    }
                    await loadUsers();
                } else {
                    // Not logged in - redirect to main page
                    window.location.href = '/';
                }
            });

            // Setup event listeners
            if (UIElements.adminLogoutButton) {
                UIElements.adminLogoutButton.addEventListener('click', handleLogout);
            }

        } catch (error) {
            console.error("Failed to initialize admin panel:", error);
            
            // User-friendly error page
            document.body.innerHTML = `
                <div style="
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    padding: 2rem;
                    background: var(--background-color);
                    font-family: var(--font-family);
                    color: var(--text-primary);
                ">
                    <div style="
                        background: var(--card-background);
                        padding: 2.5rem;
                        border-radius: 1rem;
                        box-shadow: var(--box-shadow-lg);
                        max-width: 600px;
                        width: 100%;
                        text-align: center;
                        border: 1px solid var(--border-color);
                    ">
                        <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: var(--danger-color); margin-bottom: 1rem; animation: pulse 2s infinite;"></i>
                        <h1 style="font-size: 1.75rem; margin-bottom: 1rem; color: var(--text-primary);">
                            Admin Panel Initialization Failed
                        </h1>
                        <p style="color: var(--text-secondary); margin-bottom: 1.5rem; line-height: 1.6;">
                            An error occurred while starting the system. Please refresh the page or contact the system administrator.
                        </p>
                        <div style="display: flex; gap: 1rem; justify-content: center; margin-bottom: 1.5rem;">
                            <button onclick="location.reload()" style="
                                background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
                                color: white;
                                border: none;
                                padding: 0.875rem 1.5rem;
                                border-radius: 0.5rem;
                                font-weight: 600;
                                cursor: pointer;
                                transition: var(--transition);
                                box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.4);
                            " onmouseover="this.style.transform='translateY(-1px)'" onmouseout="this.style.transform='translateY(0)'">
                                <i class="fas fa-redo"></i> Refresh Page
                            </button>
                            <button onclick="window.location.href='/'" style="
                                background: var(--background-secondary);
                                color: var(--text-primary);
                                border: 1px solid var(--border-color);
                                padding: 0.875rem 1.5rem;
                                border-radius: 0.5rem;
                                font-weight: 600;
                                cursor: pointer;
                                transition: var(--transition);
                            " onmouseover="this.style.background='var(--card-background-secondary)'" onmouseout="this.style.background='var(--background-secondary)'">
                                <i class="fas fa-home"></i> Home Page
                            </button>
                        </div>
                        <details style="margin-top: 1.5rem; text-align: left;">
                            <summary style="cursor: pointer; color: var(--primary-color); font-weight: 600; text-align: center; margin-bottom: 0.75rem;">Technical Details</summary>
                            <pre style="
                                background: var(--background-color);
                                padding: 1rem;
                                border-radius: 0.5rem;
                                font-size: 0.8rem;
                                color: var(--text-secondary);
                                white-space: pre-wrap;
                                word-break: break-word;
                                border: 1px solid var(--border-color);
                            ">${error.message}</pre>
                        </details>
                    </div>
                </div>
            `;
        }
    }

    // Start the application
    initializeApp();
});
