// Admin Panel JavaScript - Dashboard ile uyumlu modern sistem
document.addEventListener('DOMContentLoaded', () => {
    console.log('Admin panel starting...');

    // Global variables
    let firebaseApp = null;
    let auth = null;
    let database = null;
    let currentUser = null;

    // DOM Elements - Güvenli erişim ile
    const elements = {
        // Loading & container
        loadingScreen: document.getElementById('loading-screen'),
        adminContainer: document.getElementById('admin-container'),
        
        // Header elements
        refreshDataBtn: document.getElementById('refresh-data-btn'),
        adminLogoutButton: document.getElementById('admin-logout-button'),
        currentYear: document.getElementById('current-year'),
        
        // Stats counters
        totalUsersCount: document.getElementById('total-users-count'),
        activeUsersCount: document.getElementById('active-users-count'),
        trialUsersCount: document.getElementById('trial-users-count'),
        expiredUsersCount: document.getElementById('expired-users-count'),
        
        // Table elements
        usersTableBody: document.getElementById('users-table-body'),
        tableErrorMessage: document.getElementById('table-error-message'),
        tableSuccessMessage: document.getElementById('table-success-message'),
        errorText: document.getElementById('error-text'),
        successText: document.getElementById('success-text'),
        
        // Helper function to safely get elements
        get: (id) => {
            const element = document.getElementById(id);
            if (!element) {
                console.warn(`Element not found: ${id}`);
            }
            return element;
        }
    };

    // Initialize Firebase
    async function initializeFirebase() {
        try {
            console.log('Initializing Firebase...');
            const response = await fetch('/api/firebase-config');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const firebaseConfig = await response.json();
            
            if (!firebaseConfig || !firebaseConfig.apiKey) {
                throw new Error('Invalid Firebase configuration received');
            }

            firebaseApp = firebase.initializeApp(firebaseConfig);
            auth = firebase.auth();
            database = firebase.database();

            console.log('Firebase initialized successfully');
            return true;
        } catch (error) {
            console.error('Firebase initialization failed:', error);
            showError('Firebase başlatılamadı: ' + error.message);
            return false;
        }
    }

    // Authentication check with admin role verification
    async function checkAuth() {
        return new Promise((resolve) => {
            auth.onAuthStateChanged(async (user) => {
                if (user) {
                    try {
                        console.log('User authenticated:', user.email);
                        
                        // Get ID token to verify admin role
                        const idTokenResult = await user.getIdTokenResult(true);
                        
                        // Check if user has admin claims
                        const isAdmin = idTokenResult.claims.admin === true;
                        
                        if (isAdmin) {
                            currentUser = user;
                            console.log('Admin authenticated successfully:', user.email);
                            resolve(true);
                        } else {
                            console.warn('User is not admin:', user.email);
                            showError('Bu sayfaya erişim yetkiniz yok.');
                            setTimeout(() => {
                                window.location.href = '/login.html';
                            }, 2000);
                            resolve(false);
                        }
                    } catch (error) {
                        console.error('Admin verification failed:', error);
                        showError('Yetki kontrolü başarısız: ' + error.message);
                        resolve(false);
                    }
                } else {
                    console.log('No authenticated user, redirecting...');
                    window.location.href = '/login.html';
                    resolve(false);
                }
            });
        });
    }

    // Load users from Firebase Realtime Database
    async function loadUsers() {
        try {
            console.log('Loading users...');
            setLoadingState(true);
            hideMessages();

            const usersRef = database.ref('users');
            const snapshot = await usersRef.once('value');
            const usersData = snapshot.val();

            if (!usersData) {
                console.log('No users found');
                elements.usersTableBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center text-muted">
                            Henüz kullanıcı kaydı yok.
                        </td>
                    </tr>
                `;
                updateStats({ total: 0, active: 0, trial: 0, expired: 0 });
                return;
            }

            const users = Object.entries(usersData);
            console.log(`Found ${users.length} users`);
            
            renderUsers(users);
            
        } catch (error) {
            console.error('Error loading users:', error);
            showError('Kullanıcılar yüklenirken hata oluştu: ' + error.message);
        } finally {
            setLoadingState(false);
        }
    }

    // Render users in table with improved styling
    function renderUsers(users) {
        const stats = { total: 0, active: 0, trial: 0, expired: 0 };
        
        if (!users || users.length === 0) {
            elements.usersTableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-muted">
                        Kullanıcı bulunamadı.
                    </td>
                </tr>
            `;
            updateStats(stats);
            return;
        }

        const tableRows = users.map(([userId, userData]) => {
            stats.total++;

            // Calculate subscription status
            const subscriptionStatus = getSubscriptionStatus(userData);
            const expiryInfo = getExpiryInfo(userData);
            
            // Update stats based on status
            if (subscriptionStatus.status === 'active') {
                stats.active++;
            } else if (subscriptionStatus.status === 'trial') {
                stats.trial++;
            } else {
                stats.expired++;
            }

            return `
                <tr class="user-row fade-in">
                    <td>
                        <div class="user-info">
                            <div class="email-text" title="${userData.email || 'Bilinmiyor'}">${truncateText(userData.email || 'Bilinmiyor', 30)}</div>
                            ${userData.created_at ? `<div class="join-date">Katıldı: ${formatDate(userData.created_at)}</div>` : ''}
                            ${userData.full_name ? `<div class="user-language">${truncateText(userData.full_name, 20)}</div>` : ''}
                        </div>
                    </td>
                    <td>
                        <span class="status-badge ${subscriptionStatus.status}">
                            <i class="fas ${subscriptionStatus.icon}"></i>
                            ${subscriptionStatus.label}
                        </span>
                    </td>
                    <td>
                        <div class="expiry-info">
                            <div class="expiry-date">${expiryInfo.date}</div>
                            ${expiryInfo.remaining ? `<div class="days-remaining ${expiryInfo.class}">${expiryInfo.remaining}</div>` : ''}
                        </div>
                    </td>
                    <td>
                        <span class="user-id-text" title="Kopyalamak için tıklayın: ${userId}" onclick="copyToClipboard('${userId}')">
                            ${truncateText(userId, 12)}...
                        </span>
                    </td>
                    <td class="actions-cell">
                        <div class="action-buttons">
                            <button class="btn btn-success btn-sm" onclick="extendSubscription('${userId}', '${escapeHtml(userData.email || 'Bilinmiyor')}')" title="30 gün ekle">
                                <i class="fas fa-plus"></i>
                                <span class="btn-text">30 Gün</span>
                            </button>
                            <button class="btn btn-outline btn-sm" onclick="viewUserDetails('${userId}')" title="Detayları göster">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        elements.usersTableBody.innerHTML = tableRows;
        updateStats(stats);
    }

    // Get subscription status with improved logic
    function getSubscriptionStatus(userData) {
        const now = new Date();
        const expiryDate = userData.subscription_expiry ? new Date(userData.subscription_expiry) : null;
        
        if (!expiryDate) {
            return { status: 'inactive', label: 'Pasif', icon: 'fa-times' };
        }

        const isExpired = now > expiryDate;
        const subscriptionStatus = userData.subscription_status || 'trial';

        if (isExpired) {
            return { status: 'expired', label: 'Süresi Dolmuş', icon: 'fa-times-circle' };
        }

        switch (subscriptionStatus) {
            case 'active':
                return { status: 'active', label: 'Aktif', icon: 'fa-check-circle' };
            case 'trial':
                return { status: 'trial', label: 'Deneme', icon: 'fa-clock' };
            default:
                return { status: 'inactive', label: 'Pasif', icon: 'fa-times' };
        }
    }

    // Get expiry info with better formatting
    function getExpiryInfo(userData) {
        if (!userData.subscription_expiry) {
            return { date: 'Belirlenmemiş', remaining: null, class: '' };
        }

        const now = new Date();
        const expiryDate = new Date(userData.subscription_expiry);
        const diffTime = expiryDate - now;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        const formattedDate = expiryDate.toLocaleDateString('tr-TR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });

        let remaining = null;
        let remainingClass = '';

        if (diffDays > 0) {
            remaining = `${diffDays} gün kaldı`;
            remainingClass = diffDays <= 3 ? 'warning' : 'positive';
        } else if (diffDays === 0) {
            remaining = 'Bugün sona eriyor';
            remainingClass = 'warning';
        } else {
            remaining = `${Math.abs(diffDays)} gün önce doldu`;
            remainingClass = 'expired';
        }

        return {
            date: formattedDate,
            remaining: remaining,
            class: remainingClass
        };
    }

    // Update statistics with animation
    function updateStats(stats) {
        const counters = [
            { element: elements.totalUsersCount, value: stats.total },
            { element: elements.activeUsersCount, value: stats.active },
            { element: elements.trialUsersCount, value: stats.trial },
            { element: elements.expiredUsersCount, value: stats.expired }
        ];

        counters.forEach(({ element, value }) => {
            if (element) {
                // Animate counter
                animateCounter(element, value);
            }
        });
    }

    // Extend user subscription
    async function extendSubscription(userId, userEmail) {
        const confirmMessage = `${userEmail} kullanıcısının aboneliğini 30 gün uzatmak istediğinizden emin misiniz?\n\nKullanıcı ID: ${userId.substring(0, 10)}...`;
        
        if (!confirm(confirmMessage)) {
            return;
        }

        try {
            showLoadingMessage(`${userEmail} aboneliği uzatılıyor...`);

            const userRef = database.ref(`users/${userId}`);
            const snapshot = await userRef.once('value');
            const userData = snapshot.val();

            if (!userData) {
                throw new Error('Kullanıcı bulunamadı');
            }

            // Calculate new expiry date
            const now = new Date();
            const currentExpiry = userData.subscription_expiry ? new Date(userData.subscription_expiry) : now;
            const baseDate = currentExpiry > now ? currentExpiry : now;
            const newExpiryDate = new Date(baseDate.getTime() + (30 * 24 * 60 * 60 * 1000));

            // Update user data
            await userRef.update({
                subscription_expiry: newExpiryDate.toISOString(),
                subscription_status: 'active',
                last_updated: firebase.database.ServerValue.TIMESTAMP,
                updated_by: currentUser.email
            });

            showSuccess(`${userEmail} kullanıcısının aboneliği 30 gün uzatıldı!`);
            console.log('Subscription extended for user:', userId);

            // Reload users to show updated data
            setTimeout(() => {
                loadUsers();
            }, 1500);

        } catch (error) {
            console.error('Error extending subscription:', error);
            showError('Abonelik uzatılırken hata oluştu: ' + error.message);
        }
    }

    // View user details
    function viewUserDetails(userId) {
        showComingSoon(`Kullanıcı detayları: ${userId.substring(0, 10)}...`);
    }

    // Copy to clipboard with visual feedback
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            showSuccess(`Kullanıcı ID kopyalandı: ${text.substring(0, 10)}...`);
            
            // Visual feedback
            const elements = document.querySelectorAll(`[onclick*="${text}"]`);
            elements.forEach(el => {
                const originalBg = el.style.backgroundColor;
                el.style.backgroundColor = 'var(--success-color)';
                el.style.color = 'white';
                
                setTimeout(() => {
                    el.style.backgroundColor = originalBg;
                    el.style.color = '';
                }, 1000);
            });
            
        } catch (err) {
            console.error('Copy failed:', err);
            showError('Kopyalama başarısız');
        }
    }

    // Utility functions
    function truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    function formatDate(timestamp) {
        if (!timestamp) return 'Bilinmiyor';
        
        let date;
        if (typeof timestamp === 'number') {
            date = new Date(timestamp);
        } else if (typeof timestamp === 'string') {
            date = new Date(timestamp);
        } else {
            return 'Geçersiz tarih';
        }

        return date.toLocaleDateString('tr-TR', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    function setLoadingState(loading) {
        if (loading) {
            elements.usersTableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center loading-message">
                        <i class="fas fa-spinner fa-spin"></i>
                        Kullanıcılar yükleniyor...
                    </td>
                </tr>
            `;
        }
    }

    function showError(message) {
        hideMessages();
        if (elements.errorText && elements.tableErrorMessage) {
            elements.errorText.textContent = message;
            elements.tableErrorMessage.classList.remove('hidden');
            
            // Auto hide after 5 seconds
            setTimeout(hideMessages, 5000);
        }
    }

    function showSuccess(message) {
        hideMessages();
        if (elements.successText && elements.tableSuccessMessage) {
            elements.successText.textContent = message;
            elements.tableSuccessMessage.classList.remove('hidden');
            
            // Auto hide after 3 seconds
            setTimeout(hideMessages, 3000);
        }
    }

    function showLoadingMessage(message) {
        hideMessages();
        if (elements.errorText && elements.tableErrorMessage) {
            elements.errorText.textContent = message;
            elements.tableErrorMessage.classList.remove('hidden');
            elements.tableErrorMessage.className = 'status-message info';
            elements.tableErrorMessage.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${message}`;
        }
    }

    function hideMessages() {
        if (elements.tableErrorMessage) {
            elements.tableErrorMessage.classList.add('hidden');
        }
        if (elements.tableSuccessMessage) {
            elements.tableSuccessMessage.classList.add('hidden');
        }
        if (elements.tableErrorMessage) {
            elements.tableErrorMessage.className = 'status-message error hidden';
        }
    }

    function showComingSoon(feature) {
        alert(`${feature} özelliği yakında eklenecek!`);
    }

    function animateCounter(element, targetValue) {
        const startValue = parseInt(element.textContent) || 0;
        const duration = 1000; // 1 second
        const startTime = performance.now();
        
        function updateCounter(currentTime) {
            const elapsedTime = currentTime - startTime;
            const progress = Math.min(elapsedTime / duration, 1);
            
            // Easing function for smooth animation
            const easedProgress = 1 - Math.pow(1 - progress, 3);
            const currentValue = Math.round(startValue + (targetValue - startValue) * easedProgress);
            
            element.textContent = currentValue;
            
            if (progress < 1) {
                requestAnimationFrame(updateCounter);
            }
        }
        
        requestAnimationFrame(updateCounter);
    }

    // Logout function
    async function handleLogout() {
        if (confirm('Admin panelinden çıkış yapmak istediğinizden emin misiniz?')) {
            try {
                await auth.signOut();
                console.log('Admin logged out');
                window.location.href = '/login.html';
            } catch (error) {
                console.error('Logout error:', error);
                showError('Çıkış yapılırken hata oluştu.');
            }
        }
    }

    // Event listeners
    function setupEventListeners() {
        // Logout button
        if (elements.adminLogoutButton) {
            elements.adminLogoutButton.addEventListener('click', handleLogout);
        }

        // Refresh button
        if (elements.refreshDataBtn) {
            elements.refreshDataBtn.addEventListener('click', loadUsers);
        }

        // Set current year
        if (elements.currentYear) {
            elements.currentYear.textContent = new Date().getFullYear();
        }

        console.log('Event listeners setup complete');
    }

    // Main initialization function
    async function initializeApp() {
        try {
            console.log('Initializing admin panel...');
            
            // Show loading screen
            if (elements.loadingScreen) {
                elements.loadingScreen.style.display = 'flex';
            }

            // Initialize Firebase
            const firebaseInitialized = await initializeFirebase();
            if (!firebaseInitialized) {
                throw new Error('Firebase initialization failed');
            }

            // Check authentication and admin role
            const isAuthenticated = await checkAuth();
            if (!isAuthenticated) {
                return;
            }

            // Setup event listeners
            setupEventListeners();

            // Load initial data
            await loadUsers();

            // Hide loading screen and show admin panel
            if (elements.loadingScreen) {
                elements.loadingScreen.style.display = 'none';
            }
            if (elements.adminContainer) {
                elements.adminContainer.classList.remove('hidden');
                elements.adminContainer.classList.add('fade-in');
            }

            console.log('Admin panel initialized successfully');

        } catch (error) {
            console.error('Admin panel initialization failed:', error);
            
            // Show error screen
            if (elements.loadingScreen) {
                elements.loadingScreen.innerHTML = `
                    <div class="loading-content">
                        <div class="loading-logo">
                            <i class="fas fa-exclamation-triangle" style="color: var(--danger-color);"></i>
                            <span>Hata</span>
                        </div>
                        <p>Admin panel başlatılırken hata oluştu</p>
                        <button class="btn btn-primary" onclick="location.reload()" style="margin-top: 1rem;">
                            <i class="fas fa-redo"></i> Tekrar Dene
                        </button>
                    </div>
                `;
            }
        }
    }

    // Global functions for HTML onclick events
    window.loadUsers = loadUsers;
    window.extendSubscription = extendSubscription;
    window.viewUserDetails = viewUserDetails;
    window.copyToClipboard = copyToClipboard;
    window.showComingSoon = showComingSoon;

    // Start the application
    initializeApp();

    // Handle page visibility changes for auto refresh
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && currentUser) {
            console.log('Page became visible, refreshing data...');
            loadUsers();
        }
    });

    // Handle online/offline status
    window.addEventListener('online', () => {
        showSuccess('İnternet bağlantısı yeniden kuruldu');
        if (currentUser) {
            loadUsers();
        }
    });

    window.addEventListener('offline', () => {
        showError('İnternet bağlantısı kesildi');
    });

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (database && currentUser) {
            // Clean up Firebase listeners if any
            console.log('Cleaning up Firebase listeners...');
        }
    });
});
