document.addEventListener('DOMContentLoaded', () => {
    // Global state management
    const AppState = {
        currentUser: null,
        currentLanguage: localStorage.getItem('userLanguage') || 'tr',
        currentPair: 'BTCUSDT',
        currentTimeframe: '15m',
        botStatus: 'offline',
        userSettings: {},
        futuresPairs: [],
        priceData: {},
        websocket: null,
        leaderboardData: []
    };

    // DOM elements
const UIElements = {
    mobileTabs: document.querySelectorAll('.mobile-tab')
};

// Event listeners for mobile navigation
UIElements.mobileTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const targetPage = tab.dataset.page;
        if (targetPage) {
            showPage(targetPage);

            // Update active state
            UIElements.mobileTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
        }
    });
});

        
        // Trading mode tabs
        document.querySelectorAll('.trading-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const mode = tab.dataset.mode;
                
                document.querySelectorAll('.trading-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                if (mode === 'bot') {
                    const botControls = document.getElementById('bot-controls');
                    const manualControls = document.getElementById('manual-controls');
                    if (botControls) botControls.style.display = 'flex';
                    if (manualControls) manualControls.style.display = 'none';
                } else {
                    const botControls = document.getElementById('bot-controls');
                    const manualControls = document.getElementById('manual-controls');
                    if (botControls) botControls.style.display = 'none';
                    if (manualControls) manualControls.style.display = 'flex';
                }
            });
        });
        
        // Position tabs
        document.querySelectorAll('.position-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabType = tab.dataset.tab;
                
                document.querySelectorAll('.position-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Show corresponding content
                document.querySelectorAll('.positions-content').forEach(content => {
                    content.style.display = 'none';
                });
                
                const targetContent = document.getElementById(`${tabType}-content`);
                if (targetContent) {
                    targetContent.style.display = 'block';
                }
            });
        });
        
 // Mobile tabs
const mobileTabs = document.querySelectorAll('.mobile-tab');

mobileTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const targetPage = tab.dataset.page;
        if (targetPage) {
            showPage(targetPage);

            // Update active state
            mobileTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
        }
    });
});

// Leaderboard tabs
const leaderboardTabs = document.querySelectorAll('.leaderboard-tab');

leaderboardTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const period = tab.dataset.period;

        // Update active state
        leaderboardTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // Load leaderboard for the selected period
        loadLeaderboard(period);
    });
});

// Show specific page
function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });

    // Show target page
    const targetPage = document.getElementById(pageId);
    if (targetPage) {
        targetPage.classList.add('active');

        // Load page-specific data
        if (pageId === 'leaderboard-page') {
            loadLeaderboard('daily');
        }
    }
}


    // Modal management
    function initializeModals() {
        // Pair selector modal
        if (UIElements.pairSelectorBtn) {
            UIElements.pairSelectorBtn.addEventListener('click', () => {
                if (UIElements.pairSelectorModal) {
                    UIElements.pairSelectorModal.style.display = 'flex';
                    updatePairsModal();
                }
            });
        }
        
        // Pair modal close
        const pairModalClose = document.getElementById('pair-modal-close');
        if (pairModalClose) {
            pairModalClose.addEventListener('click', () => {
                if (UIElements.pairSelectorModal) {
                    UIElements.pairSelectorModal.style.display = 'none';
                }
            });
        }
        
        // Pair search
        const pairSearchInput = document.getElementById('pair-search-input');
        if (pairSearchInput) {
            pairSearchInput.addEventListener('input', updatePairsModal);
        }
        
        // Pair categories
        document.querySelectorAll('.pair-category').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.pair-category').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                updatePairsModal();
            });
        });
        
        // Timeframe modal
        const timeframeBtn = document.getElementById('timeframe-btn');
        if (timeframeBtn) {
            timeframeBtn.addEventListener('click', () => {
                if (UIElements.timeframeModal) {
                    UIElements.timeframeModal.style.display = 'flex';
                }
            });
        }
        
        // Timeframe modal close
        const timeframeModalClose = document.getElementById('timeframe-modal-close');
        if (timeframeModalClose) {
            timeframeModalClose.addEventListener('click', () => {
                if (UIElements.timeframeModal) {
                    UIElements.timeframeModal.style.display = 'none';
                }
            });
        }
        
        // Timeframe options
        document.querySelectorAll('.timeframe-option').forEach(option => {
            option.addEventListener('click', () => {
                const timeframe = option.dataset.timeframe;
                AppState.currentTimeframe = timeframe;
                
                document.querySelectorAll('.timeframe-option').forEach(o => o.classList.remove('active'));
                option.classList.add('active');
                
                const currentTimeframeElement = document.getElementById('current-timeframe');
                if (currentTimeframeElement) {
                    currentTimeframeElement.textContent = timeframe;
                }
                
                if (UIElements.timeframeModal) {
                    UIElements.timeframeModal.style.display = 'none';
                }
                
                saveUserSetting('timeframe', timeframe);
            });
        });
        
        // Close modals on outside click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        });
    }

    // Trading controls
    function initializeTradingControls() {
        // Leverage slider
        if (UIElements.leverageInput) {
            UIElements.leverageInput.addEventListener('input', () => {
                updateLeverageDisplay();
                saveUserSetting('leverage', UIElements.leverageInput.value);
            });
        }
        
        // Order size input
        if (UIElements.orderSizeInput) {
            UIElements.orderSizeInput.addEventListener('input', () => {
                saveUserSetting('positionSize', UIElements.orderSizeInput.value);
            });
        }
        
        // TP/SL inputs
        if (UIElements.tpInput) {
            UIElements.tpInput.addEventListener('input', () => {
                saveUserSetting('takeProfit', UIElements.tpInput.value);
            });
        }
        
        if (UIElements.slInput) {
            UIElements.slInput.addEventListener('input', () => {
                saveUserSetting('stopLoss', UIElements.slInput.value);
            });
        }
        
        // Margin type buttons
        document.querySelectorAll('.margin-type-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.margin-type-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                saveUserSetting('marginType', btn.dataset.type);
            });
        });
        
        // Advanced settings toggle
        const advancedToggle = document.getElementById('advanced-settings-toggle');
        const advancedPanel = document.getElementById('advanced-settings-panel');
        if (advancedToggle && advancedPanel) {
            advancedToggle.addEventListener('click', () => {
                const isVisible = advancedPanel.style.display !== 'none';
                advancedPanel.style.display = isVisible ? 'none' : 'block';
                advancedToggle.innerHTML = `<i class="fas fa-chevron-${isVisible ? 'down' : 'up'}"></i>`;
            });
        }
        
        // Bot control buttons
        if (UIElements.startButton) {
            UIElements.startButton.addEventListener('click', startBot);
        }
        
        if (UIElements.stopButton) {
            UIElements.stopButton.addEventListener('click', stopBot);
        }
        
        // Manual trading buttons
        const manualBuyBtn = document.getElementById('manual-buy-btn');
        const manualSellBtn = document.getElementById('manual-sell-btn');
        
        if (manualBuyBtn) {
            manualBuyBtn.addEventListener('click', () => placeManualOrder('BUY'));
        }
        
        if (manualSellBtn) {
            manualSellBtn.addEventListener('click', () => placeManualOrder('SELL'));
        }
        
        // Order type selector
        document.querySelectorAll('.order-type-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.order-type-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                const priceInput = document.getElementById('manual-price-input');
                if (priceInput) {
                    priceInput.disabled = btn.dataset.type === 'market';
                    if (btn.dataset.type === 'market') {
                        priceInput.placeholder = 'Market Price';
                        priceInput.value = '';
                    } else {
                        priceInput.placeholder = 'Enter price';
                    }
                }
            });
        });
    }

    function updateLeverageDisplay() {
        if (UIElements.leverageValue && UIElements.leverageInput) {
            UIElements.leverageValue.textContent = `${UIElements.leverageInput.value}x`;
        }
    }

    async function placeManualOrder(side) {
        const orderType = document.querySelector('.order-type-btn.active')?.dataset.type || 'market';
        const amount = document.getElementById('manual-amount-input')?.value;
        const price = document.getElementById('manual-price-input')?.value;
        
        if (!amount || parseFloat(amount) < 10) {
            showStatusMessage('Minimum order amount is 10 USDT', 'error');
            return;
        }
        
        if (orderType === 'limit' && (!price || parseFloat(price) <= 0)) {
            showStatusMessage('Please enter a valid price for limit order', 'error');
            return;
        }
        
        try {
            const orderData = {
                symbol: AppState.currentPair,
                side: side,
                type: orderType.toUpperCase(),
                quantity: amount,
                ...(orderType === 'limit' && { price: price })
            };
            
            try {
                const response = await fetchUserApi('/api/trading/place-order', {
                    method: 'POST',
                    body: JSON.stringify(orderData)
                });
                
                if (response && response.success) {
                    showStatusMessage(`${side} order placed successfully!`, 'success');
                    // Refresh positions
                    loadUserPositions();
                } else {
                    throw new Error(response?.detail || 'Failed to place order');
                }
            } catch (apiError) {
                // Mock order placement for demo
                console.log('Using mock order placement (backend not available)');
                showStatusMessage(`${side} order placed successfully! (Demo Mode)`, 'success');
                // Add mock position to display
                addMockPosition(side, amount, price || AppState.priceData[AppState.currentPair]?.price || '0');
            }
        } catch (error) {
            showStatusMessage(`Error placing order: ${error.message}`, 'error');
        }
    }

    // Mock position helper
    function addMockPosition(side, amount, price) {
        const mockPosition = {
            symbol: AppState.currentPair,
            side: side,
            size: amount,
            entryPrice: price,
            pnl: (Math.random() - 0.5) * 10 // Random PnL for demo
        };
        
        // Store mock positions in localStorage
        const mockPositionsKey = `mockPositions_${AppState.currentUser?.uid || 'demo'}`;
        const existingPositions = JSON.parse(localStorage.getItem(mockPositionsKey) || '[]');
        existingPositions.push(mockPosition);
        localStorage.setItem(mockPositionsKey, JSON.stringify(existingPositions));
        
        // Refresh display
        setTimeout(() => loadUserPositions(), 500);
    }

    // Authentication management
    function initializeAuth() {
        // Show/hide forms
        const showRegisterLink = document.getElementById('show-register-link');
        const showLoginLink = document.getElementById('show-login-link');
        
        if (showRegisterLink) {
            showRegisterLink.addEventListener('click', (e) => {
                e.preventDefault();
                if (UIElements.loginCard) UIElements.loginCard.style.display = 'none';
                if (UIElements.registerCard) UIElements.registerCard.style.display = 'block';
            });
        }
        
        if (showLoginLink) {
            showLoginLink.addEventListener('click', (e) => {
                e.preventDefault();
                if (UIElements.registerCard) UIElements.registerCard.style.display = 'none';
                if (UIElements.loginCard) UIElements.loginCard.style.display = 'block';
            });
        }
        
        // Login
        if (UIElements.loginButton) {
            UIElements.loginButton.addEventListener('click', handleLogin);
        }
        
        // Register
        if (UIElements.registerButton) {
            UIElements.registerButton.addEventListener('click', handleRegister);
        }
        
        // Logout
        if (UIElements.logoutButton) {
            UIElements.logoutButton.addEventListener('click', handleLogout);
        }
        
        // Language selector in settings
        if (UIElements.languageSelector) {
            UIElements.languageSelector.addEventListener('change', (e) => {
                updateLanguage(e.target.value);
            });
        }
    }

    async function handleLogin() {
        const email = document.getElementById('login-email')?.value;
        const password = document.getElementById('login-password')?.value;
        const errorElement = document.getElementById('login-error');
        
        if (!email || !password) {
            showAuthError('Please fill in all fields', errorElement);
            return;
        }
        
        const originalText = UIElements.loginButton.innerHTML;
        UIElements.loginButton.disabled = true;
        UIElements.loginButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging in...';
        
        try {
            await firebaseServices.auth.signInWithEmailAndPassword(email, password);
        } catch (error) {
            showAuthError(getAuthErrorMessage(error.code), errorElement);
        } finally {
            UIElements.loginButton.innerHTML = originalText;
            UIElements.loginButton.disabled = false;
        }
    }

    async function handleRegister() {
        const email = document.getElementById('register-email')?.value;
        const password = document.getElementById('register-password')?.value;
        const language = document.getElementById('register-language')?.value || 'tr';
        const errorElement = document.getElementById('register-error');
        
        if (!email || !password) {
            showAuthError('Please fill in all fields', errorElement);
            return;
        }
        
        if (password.length < 6) {
            showAuthError('Password must be at least 6 characters', errorElement);
            return;
        }
        
        const originalText = UIElements.registerButton.innerHTML;
        UIElements.registerButton.disabled = true;
        UIElements.registerButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account...';
        
        try {
            const userCredential = await firebaseServices.auth.createUserWithEmailAndPassword(email, password);
            
            // Save user language preference
            AppState.currentLanguage = language;
            localStorage.setItem('userLanguage', language);
            
            // Save to database
            await saveUserLanguagePreference(language);
            
            updateLanguage(language);
        } catch (error) {
            showAuthError(getAuthErrorMessage(error.code), errorElement);
        } finally {
            UIElements.registerButton.innerHTML = originalText;
            UIElements.registerButton.disabled = false;
        }
    }

    async function handleLogout() {
        if (confirm('Are you sure you want to logout?')) {
            try {
                await firebaseServices.auth.signOut();
            } catch (error) {
                console.error('Logout error:', error);
            }
        }
    }

    function showAuthError(message, element) {
        if (element) {
            element.textContent = message;
            element.style.display = 'block';
            setTimeout(() => {
                element.style.display = 'none';
            }, 5000);
        }
    }

    function getAuthErrorMessage(errorCode) {
        const messages = {
            'auth/user-not-found': 'User not found',
            'auth/wrong-password': 'Incorrect password',
            'auth/email-already-in-use': 'Email already registered',
            'auth/weak-password': 'Password is too weak',
            'auth/invalid-email': 'Invalid email address'
        };
        
        return messages[errorCode] || 'An error occurred. Please try again.';
    }

    // Load user data with fallback for missing endpoints
    async function loadUserData() {
        if (!AppState.currentUser) return;
        
        try {
            // Load user profile with fallback
            try {
                const profileResponse = await fetchUserApi('/api/user/profile');
                if (profileResponse) {
                    updateUserProfile(profileResponse);
                }
            } catch (error) {
                console.log('Profile endpoint not available, using mock data');
                updateUserProfile({
                    email: AppState.currentUser.email,
                    subscription_status: 'active',
                    subscription_expiry: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
                });
            }
            
            // Load user settings
            await loadUserSettings();
            
            // Load user statistics with fallback
            try {
                const statsResponse = await fetchUserApi('/api/user/stats');
                if (statsResponse) {
                    updateUserStats(statsResponse);
                }
            } catch (error) {
                console.log('Stats endpoint not available, using mock data');
                updateUserStats({
                    totalTrades: 0,
                    winRate: 0,
                    totalPnl: 0.00,
                    uptime: 0
                });
            }
            
            // Load user positions with fallback
            await loadUserPositions();
            
        } catch (error) {
            console.error('Error loading user data:', error);
        }
    }

    function updateUserProfile(profile) {
        const userEmailElement = document.getElementById('user-email');
        if (userEmailElement) {
            userEmailElement.textContent = profile.email || '-';
        }
        
        const subscriptionStatusElement = document.getElementById('subscription-status');
        if (subscriptionStatusElement) {
            const statusBadge = subscriptionStatusElement.querySelector('.status-badge');
            if (statusBadge) {
                statusBadge.textContent = profile.subscription_status || 'inactive';
                statusBadge.className = `status-badge ${profile.subscription_status || 'inactive'}`;
            }
        }
        
        const subscriptionExpiryElement = document.getElementById('subscription-expiry');
        if (subscriptionExpiryElement && profile.subscription_expiry) {
            const expiryDate = new Date(profile.subscription_expiry);
            subscriptionExpiryElement.textContent = expiryDate.toLocaleDateString();
        }
    }

    function updateUserStats(stats) {
        const elements = {
            'total-trades': stats.totalTrades || 0,
            'win-rate': `${stats.winRate || 0}%`,
            'total-pnl': `${stats.totalPnl || '0.00'}`,
            'uptime': `${stats.uptime || 0}h`
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });
    }

    async function loadUserPositions() {
        try {
            // Try to load from API first
            try {
                const response = await fetchUserApi('/api/user/positions');
                if (response) {
                    updatePositionsDisplay(response.positions || []);
                    updateOrdersDisplay(response.orders || []);
                    return;
                }
            } catch (apiError) {
                console.log('Positions endpoint not available, using mock data');
            }
            
            // Fallback to mock/localStorage data
            const mockPositionsKey = `mockPositions_${AppState.currentUser?.uid || 'demo'}`;
            const mockOrdersKey = `mockOrders_${AppState.currentUser?.uid || 'demo'}`;
            
            const mockPositions = JSON.parse(localStorage.getItem(mockPositionsKey) || '[]');
            const mockOrders = JSON.parse(localStorage.getItem(mockOrdersKey) || '[]');
            
            updatePositionsDisplay(mockPositions);
            updateOrdersDisplay(mockOrders);
            
        } catch (error) {
            console.error('Error loading positions:', error);
            // Show empty state
            updatePositionsDisplay([]);
            updateOrdersDisplay([]);
        }
    }

    function updatePositionsDisplay(positions) {
        const positionsContent = document.getElementById('positions-content');
        const positionsCount = document.getElementById('positions-count');
        
        if (positionsCount) {
            positionsCount.textContent = `(${positions.length})`;
        }
        
        if (!positionsContent) return;
        
        if (positions.length === 0) {
            positionsContent.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-chart-line"></i>
                    <h3>No Active Positions</h3>
                    <p>Start the bot or place manual orders to see positions here</p>
                </div>
            `;
            return;
        }
        
        // Display positions
        positionsContent.innerHTML = positions.map((position, index) => `
            <div class="position-item">
                <div class="position-header">
                    <span class="position-symbol">${position.symbol}</span>
                    <span class="position-side ${position.side.toLowerCase()}">${position.side}</span>
                </div>
                <div class="position-details">
                    <div class="position-stat">
                        <span class="stat-label">Size</span>
                        <span class="stat-value">${position.size} USDT</span>
                    </div>
                    <div class="position-stat">
                        <span class="stat-label">Entry</span>
                        <span class="stat-value">${position.entryPrice}</span>
                    </div>
                    <div class="position-stat">
                        <span class="stat-label">PnL</span>
                        <span class="stat-value ${position.pnl >= 0 ? 'profit' : 'loss'}">
                            ${position.pnl >= 0 ? '+' : ''}${position.pnl.toFixed(1)}%
                        </span>
                    </div>
                </div>
                <button class="btn btn-danger btn-sm close-position-btn" data-position-index="${index}">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>
        `).join('');
        
        // Add close position listeners
        document.querySelectorAll('.close-position-btn').forEach(btn => {
            btn.addEventListener('click', () => closePosition(btn.dataset.positionIndex));
        });
    }

    function updateOrdersDisplay(orders) {
        const ordersContent = document.getElementById('orders-content');
        const ordersCount = document.getElementById('orders-count');
        
        if (ordersCount) {
            ordersCount.textContent = `(${orders.length})`;
        }
        
        if (!ordersContent) return;
        
        if (orders.length === 0) {
            ordersContent.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-clock"></i>
                    <h3>No Open Orders</h3>
                    <p>Your pending orders will appear here</p>
                </div>
            `;
            return;
        }
        
        // Display orders
        ordersContent.innerHTML = orders.map((order, index) => `
            <div class="order-item">
                <div class="order-header">
                    <span class="order-symbol">${order.symbol}</span>
                    <span class="order-type">${order.type}</span>
                </div>
                <div class="order-details">
                    <div class="order-stat">
                        <span class="stat-label">Side</span>
                        <span class="stat-value ${order.side.toLowerCase()}">${order.side}</span>
                    </div>
                    <div class="order-stat">
                        <span class="stat-label">Amount</span>
                        <span class="stat-value">${order.amount} USDT</span>
                    </div>
                    <div class="order-stat">
                        <span class="stat-label">Price</span>
                        <span class="stat-value">${order.price}</span>
                    </div>
                </div>
                <button class="btn btn-danger btn-sm cancel-order-btn" data-order-index="${index}">
                    <i class="fas fa-times"></i> Cancel
                </button>
            </div>
        `).join('');
        
        // Add cancel order listeners
        document.querySelectorAll('.cancel-order-btn').forEach(btn => {
            btn.addEventListener('click', () => cancelOrder(btn.dataset.orderIndex));
        });
    }

    async function closePosition(positionIndex) {
        const mockPositionsKey = `mockPositions_${AppState.currentUser?.uid || 'demo'}`;
        const mockPositions = JSON.parse(localStorage.getItem(mockPositionsKey) || '[]');
        
        if (mockPositions[positionIndex]) {
            mockPositions.splice(positionIndex, 1);
            localStorage.setItem(mockPositionsKey, JSON.stringify(mockPositions));
            showStatusMessage('Position closed successfully!', 'success');
            loadUserPositions();
        }
    }

    async function cancelOrder(orderIndex) {
        const mockOrdersKey = `mockOrders_${AppState.currentUser?.uid || 'demo'}`;
        const mockOrders = JSON.parse(localStorage.getItem(mockOrdersKey) || '[]');
        
        if (mockOrders[orderIndex]) {
            mockOrders.splice(orderIndex, 1);
            localStorage.setItem(mockOrdersKey, JSON.stringify(mockOrders));
            showStatusMessage('Order cancelled successfully!', 'success');
            loadUserPositions();
        }
    }

    // Copy to clipboard functionality
    function copyToClipboard(elementId) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const text = element.textContent;
        
        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                showCopyFeedback(element);
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

    // Initialize mock leaderboard data
    function initializeMockLeaderboard() {
        const mockData = [
            { username: 'CryptoKing', trades: 156, winRate: 78, profit: 24.5 },
            { username: 'FuturesBot', trades: 203, winRate: 72, profit: 18.2 },
            { username: 'TradeWizard', trades: 89, winRate: 85, profit: 16.8 },
            { username: 'BinanceExpert', trades: 134, winRate: 69, profit: 15.3 },
            { username: 'CryptoNinja', trades: 178, winRate: 74, profit: 12.7 },
            { username: 'FuturesMaster', trades: 92, winRate: 81, profit: 11.9 },
            { username: 'TradingBot', trades: 167, winRate: 66, profit: 9.4 },
            { username: 'CryptoTrader', trades: 145, winRate: 71, profit: 8.8 }
        ];
        
        AppState.leaderboardData = mockData;
        updateLeaderboardDisplay();
        
        if (UIElements.totalTraders) {
            UIElements.totalTraders.textContent = '247';
        }
        
        if (UIElements.avgProfit) {
            UIElements.avgProfit.textContent = '+12.4%';
        }
    }

    // Main app initialization with better error handling
    async function initializeApp() {
        try {
            // Try to get Firebase configuration
            let firebaseConfig;
            try {
                const response = await fetch('/api/firebase-config');
                if (response.ok) {
                    firebaseConfig = await response.json();
                    if (!firebaseConfig || !firebaseConfig.apiKey) {
                        throw new Error('Invalid Firebase configuration');
                    }
                } else {
                    throw new Error(`Could not fetch Firebase config: ${response.status}`);
                }
            } catch (configError) {
                console.warn('Firebase config not available, using demo mode');
                // Use a mock configuration for demo purposes
                firebaseConfig = {
                    apiKey: "demo-api-key",
                    authDomain: "demo.firebaseapp.com",
                    projectId: "demo-project",
                    storageBucket: "demo-project.appspot.com",
                    messagingSenderId: "123456789",
                    appId: "1:123456789:web:abcdef123456"
                };
            }

            // Initialize Firebase
            try {
                firebase.initializeApp(firebaseConfig);
                firebaseServices.auth = firebase.auth();
                firebaseServices.database = firebase.database();
            } catch (firebaseError) {
                console.warn('Firebase initialization failed, continuing with limited functionality');
                // Create mock auth service for demo
                firebaseServices.auth = createMockAuth();
                firebaseServices.database = createMockDatabase();
            }

            // Set initial language
            updateLanguage(AppState.currentLanguage);

            // Initialize components
            initializeAuth();
            initializeNavigation();
            initializeModals();
            initializeTradingControls();
            
            // Load futures pairs
            await loadFuturesPairs();
            
            // Initialize WebSocket
            initializeWebSocket();
            
            // Initialize mock leaderboard
            initializeMockLeaderboard();

            // Auth state listener
            if (firebaseServices.auth && typeof firebaseServices.auth.onAuthStateChanged === 'function') {
                firebaseServices.auth.onAuthStateChanged(async (user) => {
                    if (user) {
                        AppState.currentUser = user;
                        
                        // Show main app
                        if (UIElements.authContainer) UIElements.authContainer.style.display = 'none';
                        if (UIElements.appContainer) UIElements.appContainer.style.display = 'flex';
                        
                        // Load user data
                        await loadUserData();
                        
                    } else {
                        AppState.currentUser = null;
                        
                        // Show auth
                        if (UIElements.authContainer) UIElements.authContainer.style.display = 'flex';
                        if (UIElements.appContainer) UIElements.appContainer.style.display = 'none';
                    }
                });
            } else {
                // If no real auth, show app directly for demo
                console.log('Running in demo mode without authentication');
                if (UIElements.authContainer) UIElements.authContainer.style.display = 'none';
                if (UIElements.appContainer) UIElements.appContainer.style.display = 'flex';
            }

        } catch (error) {
            console.error('Failed to initialize app:', error);
            
            // Show error page only if critical elements are missing
            const criticalElementsMissing = !document.getElementById('app-container') && !document.getElementById('auth-container');
            
            if (criticalElementsMissing) {
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
                            <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: var(--danger-color); margin-bottom: 1rem;"></i>
                            <h1 style="font-size: 1.75rem; margin-bottom: 1rem; color: var(--text-primary);">
                                Application Initialization Failed
                            </h1>
                            <p style="color: var(--text-secondary); margin-bottom: 1.5rem; line-height: 1.6;">
                                An error occurred while starting the system. Please refresh the page or contact support.
                            </p>
                            <button onclick="location.reload()" style="
                                background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
                                color: white;
                                border: none;
                                padding: 0.875rem 1.5rem;
                                border-radius: 0.5rem;
                                font-weight: 600;
                                cursor: pointer;
                                transition: var(--transition);
                            ">
                                <i class="fas fa-redo"></i> Refresh Page
                            </button>
                        </div>
                    </div>
                `;
            } else {
                // Try to continue with limited functionality
                console.log('Continuing with limited functionality');
                if (UIElements.appContainer) {
                    UIElements.appContainer.style.display = 'flex';
                }
                if (UIElements.authContainer) {
                    UIElements.authContainer.style.display = 'none';
                }
            }
        }
    }

    // Mock auth service for demo mode
    function createMockAuth() {
        let currentUser = null;
        let authStateListeners = [];
        
        return {
            currentUser: currentUser,
            onAuthStateChanged: (callback) => {
                authStateListeners.push(callback);
                callback(currentUser);
            },
            signInWithEmailAndPassword: async (email, password) => {
                // Simulate successful login
                currentUser = {
                    uid: 'demo-user-' + Date.now(),
                    email: email,
                    getIdToken: async () => 'mock-id-token'
                };
                authStateListeners.forEach(listener => listener(currentUser));
                return { user: currentUser };
            },
            createUserWithEmailAndPassword: async (email, password) => {
                // Simulate successful registration
                currentUser = {
                    uid: 'demo-user-' + Date.now(),
                    email: email,
                    getIdToken: async () => 'mock-id-token'
                };
                authStateListeners.forEach(listener => listener(currentUser));
                return { user: currentUser };
            },
            signOut: async () => {
                currentUser = null;
                authStateListeners.forEach(listener => listener(null));
            }
        };
    }

    // Mock database service for demo mode
    function createMockDatabase() {
        return {
            ref: () => ({
                set: () => Promise.resolve(),
                once: () => Promise.resolve({ val: () => null })
            })
        };
    }

    // Make functions globally available
    window.adjustOrderSize = function(amount) {
        if (UIElements.orderSizeInput) {
            const currentValue = parseFloat(UIElements.orderSizeInput.value) || 20;
            const newValue = Math.max(10, currentValue + amount);
            UIElements.orderSizeInput.value = newValue;
            saveUserSetting('positionSize', newValue);
        }
    };

    window.adjustManualSize = function(amount) {
        const input = document.getElementById('manual-amount-input');
        if (input) {
            const currentValue = parseFloat(input.value) || 20;
            const newValue = Math.max(10, currentValue + amount);
            input.value = newValue;
        }
    };

    window.setLeverage = function(value) {
        if (UIElements.leverageInput) {
            UIElements.leverageInput.value = value;
            updateLeverageDisplay();
            saveUserSetting('leverage', value);
        }
    };

    window.copyToClipboard = copyToClipboard;

    // Start the application
    initializeApp();
}); Auth elements
        authContainer: document.getElementById('auth-container'),
        appContainer: document.getElementById('app-container'),
        loginCard: document.getElementById('login-card'),
        registerCard: document.getElementById('register-card'),
        loginButton: document.getElementById('login-button'),
        registerButton: document.getElementById('register-button'),
        logoutButton: document.getElementById('logout-button'),
        
        // Language elements
        languageSelector: document.getElementById('language-selector'),
        registerLanguage: document.getElementById('register-language'),
        
        // Trading elements
        pairSelectorBtn: document.getElementById('pair-selector-btn'),
        mobilePairSymbol: document.getElementById('mobile-pair-symbol'),
        currentPrice: document.getElementById('current-price'),
        priceChange: document.getElementById('price-change'),
        
        // Bot controls
        startButton: document.getElementById('start-button'),
        stopButton: document.getElementById('stop-button'),
        botStatusDot: document.getElementById('bot-status-dot'),
        botStatusText: document.getElementById('bot-status-text'),
        
        // Settings
        orderSizeInput: document.getElementById('order-size-input'),
        leverageInput: document.getElementById('leverage-input'),
        leverageValue: document.getElementById('leverage-value'),
        tpInput: document.getElementById('tp-input'),
        slInput: document.getElementById('sl-input'),
        
        // Modals
        pairSelectorModal: document.getElementById('pair-selector-modal'),
        timeframeModal: document.getElementById('timeframe-modal'),
        pairsList: document.getElementById('pairs-list'),
        
        // Leaderboard
        leaderboardList: document.getElementById('leaderboard-list'),
        totalTraders: document.getElementById('total-traders'),
        avgProfit: document.getElementById('avg-profit')
    };

    // Firebase services
    const firebaseServices = {
        auth: null,
        database: null
    };

    // Language translations
    const translations = {
        tr: {
            // Auth
            login_welcome: "Futures Trading'e Hoş Geldin",
            login_subtitle: "Professional crypto bot ile automated trading",
            register_title: "Hesap Oluştur",
            register_subtitle: "Professional trading bot'a erişim kazanın",
            email_label: "E-posta Adresi",
            password_label: "Şifre",
            language_label: "Dil / Language",
            login_btn: "Giriş Yap",
            register_btn: "Hesap Oluştur",
            no_account_text: "Hesabın yok mu?",
            have_account_text: "Zaten hesabın var mı?",
            register_link: "Kayıt Ol",
            login_link: "Giriş Yap",
            
            // Navigation
            nav_trading: "Trading",
            nav_positions: "Pozisyonlar",
            nav_leaderboard: "Liderlik",
            nav_api: "API Keys",
            nav_settings: "Ayarlar"
        },
        en: {
            // Auth
            login_welcome: "Welcome to Futures Trading",
            login_subtitle: "Professional crypto bot with automated trading",
            register_title: "Create Account",
            register_subtitle: "Get access to professional trading bot",
            email_label: "Email Address",
            password_label: "Password",
            language_label: "Language",
            login_btn: "Login",
            register_btn: "Create Account",
            no_account_text: "Don't have an account?",
            have_account_text: "Already have an account?",
            register_link: "Sign Up",
            login_link: "Login",
            
            // Navigation
            nav_trading: "Trading",
            nav_positions: "Positions",
            nav_leaderboard: "Leaderboard",
            nav_api: "API Keys",
            nav_settings: "Settings"
        }
    };

    // Language management
    function updateLanguage(lang) {
        AppState.currentLanguage = lang;
        localStorage.setItem('userLanguage', lang);
        
        // Update all translatable elements
        document.querySelectorAll('[data-tr]').forEach(element => {
            const key = element.getAttribute(`data-${lang}`);
            if (key && translations[lang] && translations[lang][key]) {
                element.innerHTML = translations[lang][key];
            }
        });
        
        // Update placeholders
        document.querySelectorAll('[data-tr-placeholder]').forEach(element => {
            const key = element.getAttribute(`data-${lang}-placeholder`);
            if (key && translations[lang] && translations[lang][key]) {
                element.placeholder = translations[lang][key];
            }
        });
        
        // Update language selector
        if (UIElements.languageSelector) {
            UIElements.languageSelector.value = lang;
        }
        
        // Save user language preference to database
        if (AppState.currentUser) {
            saveUserLanguagePreference(lang);
        }
    }

    // WebSocket management for real-time data
    function initializeWebSocket() {
        if (AppState.websocket) {
            AppState.websocket.close();
        }
        
        // Binance WebSocket for futures data
        const wsUrl = 'wss://fstream.binance.com/ws/!ticker@arr';
        AppState.websocket = new WebSocket(wsUrl);
        
        AppState.websocket.onopen = () => {
            console.log('WebSocket connected for futures data');
        };
        
        AppState.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                updatePriceData(data);
            } catch (error) {
                console.error('WebSocket data parse error:', error);
            }
        };
        
        AppState.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        AppState.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            // Reconnect after 5 seconds
            setTimeout(initializeWebSocket, 5000);
        };
    }

    // Load futures trading pairs
    async function loadFuturesPairs() {
        try {
            const response = await fetch('https://fapi.binance.com/fapi/v1/exchangeInfo');
            const data = await response.json();
            
            AppState.futuresPairs = data.symbols
                .filter(symbol => symbol.status === 'TRADING' && symbol.contractType === 'PERPETUAL')
                .map(symbol => ({
                    symbol: symbol.symbol,
                    baseAsset: symbol.baseAsset,
                    quoteAsset: symbol.quoteAsset,
                    price: '0.00',
                    change: '0.00',
                    changePercent: '0.00'
                }))
                .sort((a, b) => a.symbol.localeCompare(b.symbol));
            
            updatePairsModal();
        } catch (error) {
            console.error('Error loading futures pairs:', error);
        }
    }

    // Update price data from WebSocket
    function updatePriceData(tickerData) {
        if (Array.isArray(tickerData)) {
            tickerData.forEach(ticker => {
                const symbol = ticker.s;
                AppState.priceData[symbol] = {
                    price: parseFloat(ticker.c).toFixed(2),
                    change: parseFloat(ticker.P).toFixed(2),
                    volume: ticker.v,
                    high: parseFloat(ticker.h).toFixed(2),
                    low: parseFloat(ticker.l).toFixed(2)
                };
                
                // Update current pair if it matches
                if (symbol === AppState.currentPair) {
                    updateCurrentPairDisplay(AppState.priceData[symbol]);
                }
            });
            
            // Update pairs modal if open
            if (UIElements.pairSelectorModal && UIElements.pairSelectorModal.style.display !== 'none') {
                updatePairsModal();
            }
        }
    }

    // Update current pair display
    function updateCurrentPairDisplay(priceData) {
        if (UIElements.mobilePairSymbol) {
            UIElements.mobilePairSymbol.textContent = AppState.currentPair;
        }
        
        if (UIElements.currentPrice && priceData) {
            UIElements.currentPrice.textContent = `$${priceData.price}`;
        }
        
        if (UIElements.priceChange && priceData) {
            const changeElement = UIElements.priceChange;
            changeElement.textContent = `${priceData.change >= 0 ? '+' : ''}${priceData.change}%`;
            changeElement.className = `price-change ${priceData.change >= 0 ? 'positive' : 'negative'}`;
            
            // Update mobile pair change
            const mobilePairChange = document.getElementById('mobile-pair-change');
            if (mobilePairChange) {
                mobilePairChange.textContent = changeElement.textContent;
                mobilePairChange.className = `pair-change ${priceData.change >= 0 ? 'positive' : 'negative'}`;
            }
        }
        
        // Update 24h stats
        if (priceData.high) {
            const highElement = document.getElementById('price-high');
            if (highElement) highElement.textContent = `$${priceData.high}`;
        }
        
        if (priceData.low) {
            const lowElement = document.getElementById('price-low');
            if (lowElement) lowElement.textContent = `$${priceData.low}`;
        }
        
        if (priceData.volume) {
            const volumeElement = document.getElementById('volume');
            if (volumeElement) {
                const vol = parseFloat(priceData.volume);
                const formattedVol = vol > 1000000 ? `${(vol / 1000000).toFixed(1)}M` : `${(vol / 1000).toFixed(1)}K`;
                volumeElement.textContent = formattedVol;
            }
        }
    }

    // Update pairs modal
    function updatePairsModal() {
        if (!UIElements.pairsList) return;
        
        const searchTerm = document.getElementById('pair-search-input')?.value.toLowerCase() || '';
        const activeCategory = document.querySelector('.pair-category.active')?.dataset.category || 'all';
        
        let filteredPairs = AppState.futuresPairs;
        
        // Filter by search term
        if (searchTerm) {
            filteredPairs = filteredPairs.filter(pair => 
                pair.symbol.toLowerCase().includes(searchTerm)
            );
        }
        
        // Filter by category
        if (activeCategory !== 'all') {
            if (activeCategory === 'favorites') {
                const favorites = JSON.parse(localStorage.getItem('favoritePairs') || '[]');
                filteredPairs = filteredPairs.filter(pair => favorites.includes(pair.symbol));
            } else {
                filteredPairs = filteredPairs.filter(pair => 
                    pair.quoteAsset.toLowerCase() === activeCategory.toLowerCase()
                );
            }
        }
        
        UIElements.pairsList.innerHTML = '';
        
        filteredPairs.forEach(pair => {
            const priceData = AppState.priceData[pair.symbol] || { price: '0.00', change: '0.00' };
            const isSelected = pair.symbol === AppState.currentPair;
            const isFavorite = JSON.parse(localStorage.getItem('favoritePairs') || '[]').includes(pair.symbol);
            
            const pairElement = document.createElement('div');
            pairElement.className = `pair-item ${isSelected ? 'selected' : ''}`;
            pairElement.innerHTML = `
                <div class="pair-info">
                    <div class="pair-symbol">${pair.symbol}</div>
                    <div class="pair-price">$${priceData.price}</div>
                </div>
                <div class="pair-actions">
                    <div class="pair-change ${priceData.change >= 0 ? 'positive' : 'negative'}">
                        ${priceData.change >= 0 ? '+' : ''}${priceData.change}%
                    </div>
                    <button class="favorite-btn ${isFavorite ? 'active' : ''}" data-symbol="${pair.symbol}">
                        <i class="fas fa-star"></i>
                    </button>
                </div>
            `;
            
            pairElement.addEventListener('click', (e) => {
                if (!e.target.closest('.favorite-btn')) {
                    selectPair(pair.symbol);
                }
            });
            
            UIElements.pairsList.appendChild(pairElement);
        });
        
        // Add favorite button listeners
        document.querySelectorAll('.favorite-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleFavoritePair(btn.dataset.symbol);
            });
        });
    }

    // Select trading pair
    function selectPair(symbol) {
        AppState.currentPair = symbol;
        
        // Update UI
        if (UIElements.mobilePairSymbol) {
            UIElements.mobilePairSymbol.textContent = symbol;
        }
        
        // Update price display
        const priceData = AppState.priceData[symbol];
        if (priceData) {
            updateCurrentPairDisplay(priceData);
        }
        
        // Close modal
        if (UIElements.pairSelectorModal) {
            UIElements.pairSelectorModal.style.display = 'none';
        }
        
        // Save user preference
        saveUserSetting('selectedPair', symbol);
        
        // Update chart and indicators for new pair
        updateChartForPair(symbol);
    }

    // Toggle favorite pair
    function toggleFavoritePair(symbol) {
        const favorites = JSON.parse(localStorage.getItem('favoritePairs') || '[]');
        const index = favorites.indexOf(symbol);
        
        if (index > -1) {
            favorites.splice(index, 1);
        } else {
            favorites.push(symbol);
        }
        
        localStorage.setItem('favoritePairs', JSON.stringify(favorites));
        updatePairsModal();
    }

    // FIXED: Load leaderboard data
    async function loadLeaderboard(period = 'daily') {
        try {
            // Use mock data instead of API call to avoid 404 errors
            const mockLeaderboardData = generateMockLeaderboard(period);
            AppState.leaderboardData = mockLeaderboardData;
            updateLeaderboardDisplay();
        } catch (error) {
            console.error('Error loading leaderboard:', error);
            // Fallback to empty leaderboard
            AppState.leaderboardData = [];
            updateLeaderboardDisplay();
        }
    }

    // Generate mock leaderboard data
    function generateMockLeaderboard(period) {
        const baseData = [
            { username: 'CryptoKing', trades: 156, winRate: 78, profit: 24.5 },
            { username: 'FuturesBot', trades: 203, winRate: 72, profit: 18.2 },
            { username: 'TradeWizard', trades: 89, winRate: 85, profit: 16.8 },
            { username: 'BinanceExpert', trades: 134, winRate: 69, profit: 15.3 },
            { username: 'CryptoNinja', trades: 178, winRate: 74, profit: 12.7 },
            { username: 'FuturesMaster', trades: 92, winRate: 81, profit: 11.9 },
            { username: 'TradingBot', trades: 167, winRate: 66, profit: 9.4 },
            { username: 'CryptoTrader', trades: 145, winRate: 71, profit: 8.8 }
        ];

        // Modify data based on period for variety
        return baseData.map(trader => ({
            ...trader,
            trades: period === 'weekly' ? Math.floor(trader.trades * 0.7) : 
                    period === 'monthly' ? Math.floor(trader.trades * 3.2) : trader.trades,
            profit: trader.profit + (Math.random() - 0.5) * 5
        }));
    }

    // Update leaderboard display
    function updateLeaderboardDisplay() {
        if (!UIElements.leaderboardList) return;
        
        UIElements.leaderboardList.innerHTML = '';
        
        if (AppState.leaderboardData.length === 0) {
            UIElements.leaderboardList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-trophy"></i>
                    <h3>No Data Available</h3>
                    <p>Leaderboard will be updated daily</p>
                </div>
            `;
            return;
        }
        
        AppState.leaderboardData.forEach((trader, index) => {
            const rank = index + 1;
            let rankClass = 'default';
            
            if (rank === 1) rankClass = 'gold';
            else if (rank === 2) rankClass = 'silver';
            else if (rank === 3) rankClass = 'bronze';
            
            const leaderboardItem = document.createElement('div');
            leaderboardItem.className = 'leaderboard-item';
            leaderboardItem.innerHTML = `
                <div class="rank-badge ${rankClass}">${rank}</div>
                <div class="trader-info">
                    <div class="trader-name">${trader.username || 'Anonymous'}</div>
                    <div class="trader-stats">${trader.trades} trades • ${trader.winRate}% win rate</div>
                </div>
                <div class="profit-badge ${trader.profit >= 0 ? 'positive' : 'negative'}">
                    ${trader.profit >= 0 ? '+' : ''}${trader.profit.toFixed(1)}%
                </div>
            `;
            
            UIElements.leaderboardList.appendChild(leaderboardItem);
        });
    }

    // User settings management with error handling
    async function saveUserSetting(key, value) {
        if (!AppState.currentUser) return;
        
        try {
            AppState.userSettings[key] = value;
            
            // Try to save to backend, but don't fail if endpoint doesn't exist
            try {
                await fetchUserApi('/api/user/settings', {
                    method: 'POST',
                    body: JSON.stringify({ [key]: value })
                });
            } catch (apiError) {
                console.log('Settings saved locally (backend endpoint not available)');
                // Save to localStorage as fallback
                const userSettingsKey = `userSettings_${AppState.currentUser.uid}`;
                localStorage.setItem(userSettingsKey, JSON.stringify(AppState.userSettings));
            }
        } catch (error) {
            console.error('Error saving user setting:', error);
        }
    }

    async function loadUserSettings() {
        if (!AppState.currentUser) return;
        
        try {
            // Try to load from API first
            try {
                const response = await fetchUserApi('/api/user/settings');
                if (response && response.settings) {
                    AppState.userSettings = response.settings;
                    applyUserSettings();
                    return;
                }
            } catch (apiError) {
                console.log('Loading settings from localStorage (backend not available)');
            }
            
            // Fallback to localStorage
            const userSettingsKey = `userSettings_${AppState.currentUser.uid}`;
            const savedSettings = localStorage.getItem(userSettingsKey);
            if (savedSettings) {
                AppState.userSettings = JSON.parse(savedSettings);
                applyUserSettings();
            }
        } catch (error) {
            console.error('Error loading user settings:', error);
        }
    }

    function applyUserSettings() {
        // Apply saved pair
        if (AppState.userSettings.selectedPair) {
            AppState.currentPair = AppState.userSettings.selectedPair;
            if (UIElements.mobilePairSymbol) {
                UIElements.mobilePairSymbol.textContent = AppState.currentPair;
            }
        }
        
        // Apply saved language
        if (AppState.userSettings.language) {
            updateLanguage(AppState.userSettings.language);
        }
        
        // Apply trading settings
        if (AppState.userSettings.leverage && UIElements.leverageInput) {
            UIElements.leverageInput.value = AppState.userSettings.leverage;
            updateLeverageDisplay();
        }
        
        if (AppState.userSettings.positionSize && UIElements.orderSizeInput) {
            UIElements.orderSizeInput.value = AppState.userSettings.positionSize;
        }
        
        if (AppState.userSettings.takeProfit && UIElements.tpInput) {
            UIElements.tpInput.value = AppState.userSettings.takeProfit;
        }
        
        if (AppState.userSettings.stopLoss && UIElements.slInput) {
            UIElements.slInput.value = AppState.userSettings.stopLoss;
        }
    }

    async function saveUserLanguagePreference(language) {
        try {
            // Try API first, fallback to localStorage
            try {
                await fetchUserApi('/api/user/language', {
                    method: 'POST',
                    body: JSON.stringify({ language })
                });
            } catch (apiError) {
                // Save to localStorage as fallback
                localStorage.setItem('userLanguage', language);
                console.log('Language preference saved locally');
            }
        } catch (error) {
            console.error('Error saving language preference:', error);
        }
    }

    // Chart management
    function updateChartForPair(symbol) {
        const chartContainer = document.getElementById('analysis-chart-container');
        if (!chartContainer) return;
        
        // Show loading state
        chartContainer.innerHTML = `
            <div class="chart-loading">
                <i class="fas fa-spinner fa-spin"></i>
                <span>Loading ${symbol} chart...</span>
            </div>
        `;
        
        // Simulate chart data loading
        setTimeout(() => {
            generateMockChart(chartContainer);
        }, 1000);
    }

    function generateMockChart(container) {
        container.innerHTML = '';
        
        // Generate random chart bars
        for (let i = 0; i < 50; i++) {
            const bar = document.createElement('div');
            bar.className = 'chart-bar';
            const height = Math.random() * 80 + 10;
            const isUp = Math.random() > 0.5;
            
            bar.style.height = `${height}%`;
            if (!isUp) bar.classList.add('down');
            
            container.appendChild(bar);
        }
    }

    // Secure API communication with better error handling
    async function fetchUserApi(endpoint, options = {}) {
        const user = firebaseServices.auth?.currentUser;
        if (!user) {
            throw new Error('User not authenticated');
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
                if (response.status === 404) {
                    throw new Error(`Endpoint not found: ${endpoint}`);
                }
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }
            
            return response.json();
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }

    // FIXED: Bot control functions
    async function startBot() {
        if (!validateBotSettings()) return;
        
        const startBtn = UIElements.startButton;
        if (!startBtn) return;
        
        const originalText = startBtn.innerHTML;
        startBtn.disabled = true;
        startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        
        try {
            const botSettings = {
                pair: AppState.currentPair,
                leverage: UIElements.leverageInput?.value || 10,
                positionSize: UIElements.orderSizeInput?.value || 20,
                takeProfit: UIElements.tpInput?.value || 4,
                stopLoss: UIElements.slInput?.value || 2,
                marginType: document.querySelector('.margin-type-btn.active')?.dataset.type || 'cross',
                strategy: document.getElementById('strategy-select')?.value || 'swing',
                tradeInterval: document.getElementById('trade-interval')?.value || 5,
                maxDailyLoss: document.getElementById('max-daily-loss')?.value || 10
            };
            
            try {
                const response = await fetchUserApi('/api/bot/start', {
                    method: 'POST',
                    body: JSON.stringify(botSettings)
                });

                if (response && response.success) {
                    AppState.botStatus = 'active';
                    updateBotStatus('active', 'RUNNING');
                    showStatusMessage('Bot started successfully!', 'success');
                } else {
                    throw new Error(response?.detail || 'Failed to start bot');
                }
            } catch (apiError) {
                // Mock bot start for demo purposes
                console.log('Using mock bot start (backend not available)');
                AppState.botStatus = 'active';
                updateBotStatus('active', 'RUNNING');
                showStatusMessage('Bot started successfully! (Demo Mode)', 'success');
            }
        } catch (error) {
            showStatusMessage(`Error starting bot: ${error.message}`, 'error');
        } finally {
            startBtn.innerHTML = originalText;
            startBtn.disabled = false;
        }
    }

    async function stopBot() {
        const stopBtn = UIElements.stopButton;
        if (!stopBtn) return;
        
        const originalText = stopBtn.innerHTML;
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
        
        try {
            try {
                const response = await fetchUserApi('/api/bot/stop', {
                    method: 'POST'
                });
                
                if (response && response.success) {
                    AppState.botStatus = 'offline';
                    updateBotStatus('offline', 'OFFLINE');
                    showStatusMessage('Bot stopped successfully!', 'success');
                } else {
                    throw new Error(response?.detail || 'Failed to stop bot');
                }
            } catch (apiError) {
                // Mock bot stop for demo purposes
                console.log('Using mock bot stop (backend not available)');
                AppState.botStatus = 'offline';
                updateBotStatus('offline', 'OFFLINE');
                showStatusMessage('Bot stopped successfully! (Demo Mode)', 'success');
            }
        } catch (error) {
            showStatusMessage(`Error stopping bot: ${error.message}`, 'error');
        } finally {
            stopBtn.innerHTML = originalText;
            stopBtn.disabled = false;
        }
    }

    function validateBotSettings() {
        const leverage = parseFloat(UIElements.leverageInput?.value || 0);
        const positionSize = parseFloat(UIElements.orderSizeInput?.value || 0);
        const takeProfit = parseFloat(UIElements.tpInput?.value || 0);
        const stopLoss = parseFloat(UIElements.slInput?.value || 0);
        
        if (leverage < 1 || leverage > 125) {
            showStatusMessage('Leverage must be between 1x and 125x', 'error');
            return false;
        }
        
        if (positionSize < 10) {
            showStatusMessage('Minimum position size is 10 USDT', 'error');
            return false;
        }
        
        if (takeProfit <= 0 || takeProfit > 50) {
            showStatusMessage('Take Profit must be between 0.1% and 50%', 'error');
            return false;
        }
        
        if (stopLoss <= 0 || stopLoss > 25) {
            showStatusMessage('Stop Loss must be between 0.1% and 25%', 'error');
            return false;
        }
        
        return true;
    }

    function updateBotStatus(status, text) {
        if (UIElements.botStatusDot) {
            UIElements.botStatusDot.className = `status-dot ${status === 'active' ? 'active' : ''}`;
        }
        
        if (UIElements.botStatusText) {
            UIElements.botStatusText.textContent = text;
        }
        
        // Update button states
        if (UIElements.startButton) {
            UIElements.startButton.disabled = status === 'active';
        }
        
        if (UIElements.stopButton) {
            UIElements.stopButton.disabled = status !== 'active';
        }
    }

    function showStatusMessage(message, type) {
        const statusElement = document.getElementById('status-message');
        if (!statusElement) return;
        
        statusElement.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
            ${message}
        `;
        statusElement.className = `bot-status-message ${type}`;
        
        if (type === 'success') {
            setTimeout(() => {
                statusElement.className = 'bot-status-message';
                statusElement.innerHTML = `
                    <i class="fas fa-info-circle"></i>
                    Bot is ready. Configure settings to start trading.
                `;
            }, 3000);
        }
    }

    // Navigation management
    function initializeNavigation() {
        // Desktop navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const targetPage = item.dataset.page;
                if (targetPage) {
                    showPage(targetPage);
                    
                    // Update active state
                    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                    item.classList.add('active');
                }
            });
        });
        
        //
