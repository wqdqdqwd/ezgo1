document.addEventListener('DOMContentLoaded', () => {
    // Global state management
    const AppState = {
        currentUser: null,
        currentLanguage: localStorage.getItem('userLanguage') || 'tr',
        currentSymbol: 'BTCUSDT',
        currentTimeframe: '15m',
        activeBots: {},
        availableSymbols: [],
        priceData: {},
        websocket: null,
        maxBotsPerUser: 4
    };

    // DOM elements
    const UIElements = {
        // Auth elements
        authContainer: document.getElementById('auth-container'),
        appContainer: document.getElementById('app-container'),
        loginCard: document.getElementById('login-card'),
        registerCard: document.getElementById('register-card'),
        
        // Trading elements
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
        
        // Pair selector
        pairSelectorModal: document.getElementById('pair-selector-modal'),
        pairsList: document.getElementById('pairs-list'),
        pairSearchInput: document.getElementById('pair-search-input')
    };

    // Firebase services
    const firebaseServices = {
        auth: null,
        database: null
    };

    // Language translations
    const translations = {
        tr: {
            // Error messages
            max_bots_reached: "Maksimum 4 bot çalıştırabilirsiniz",
            bot_started: "Bot başarıyla başlatıldı",
            bot_stopped: "Bot durduruldu",
            select_symbol: "Lütfen bir sembol seçin",
            invalid_settings: "Ayarlar geçersiz",
            connection_error: "Bağlantı hatası",
            
            // Status messages
            bot_offline: "Çevrimdışı",
            bot_running: "Çalışıyor",
            loading: "Yükleniyor...",
            no_bots: "Aktif bot yok"
        },
        en: {
            // Error messages
            max_bots_reached: "Maximum 4 bots allowed",
            bot_started: "Bot started successfully",
            bot_stopped: "Bot stopped",
            select_symbol: "Please select a symbol",
            invalid_settings: "Invalid settings",
            connection_error: "Connection error",
            
            // Status messages
            bot_offline: "Offline",
            bot_running: "Running",
            loading: "Loading...",
            no_bots: "No active bots"
        }
    };

    // API Communication
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
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }
            
            return response.json();
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }

    // Initialize app
    async function initializeApp() {
        try {
            // Get Firebase configuration
            const response = await fetch('/api/firebase-config');
            if (!response.ok) {
                throw new Error('Could not fetch Firebase config');
            }
            
            const firebaseConfig = await response.json();
            
            // Initialize Firebase
            firebase.initializeApp(firebaseConfig);
            firebaseServices.auth = firebase.auth();
            firebaseServices.database = firebase.database();

            // Set initial language
            updateLanguage(AppState.currentLanguage);

            // Initialize components
            initializeAuth();
            initializeNavigation();
            initializeTradingControls();
            initializeModals();
            
            // Load available symbols
            await loadAvailableSymbols();

            // Auth state listener
            firebaseServices.auth.onAuthStateChanged(async (user) => {
                if (user) {
                    AppState.currentUser = user;
                    
                    // Show main app
                    UIElements.authContainer.style.display = 'none';
                    UIElements.appContainer.style.display = 'flex';
                    
                    // Load user data
                    await loadUserData();
                    
                    // Start status polling
                    startStatusPolling();
                    
                } else {
                    AppState.currentUser = null;
                    
                    // Show auth
                    UIElements.authContainer.style.display = 'flex';
                    UIElements.appContainer.style.display = 'none';
                    
                    // Stop polling
                    stopStatusPolling();
                }
            });

        } catch (error) {
            console.error('Failed to initialize app:', error);
            showErrorMessage('Uygulama başlatılamadı. Lütfen sayfayı yenileyin.');
        }
    }

    // Load available symbols
    async function loadAvailableSymbols() {
        try {
            if (!AppState.currentUser) return;
            
            const response = await fetchUserApi('/api/bot/symbols');
            
            if (response.success && response.symbols) {
                AppState.availableSymbols = response.symbols;
                updatePairsModal();
                console.log(`${response.symbols.length} sembol yüklendi`);
            }
        } catch (error) {
            console.error('Sembol listesi yüklenemedi:', error);
        }
    }

    // Update pairs modal
    function updatePairsModal() {
        if (!UIElements.pairsList) return;
        
        const searchTerm = UIElements.pairSearchInput?.value.toLowerCase() || '';
        
        let filteredSymbols = AppState.availableSymbols;
        
        // Filter by search term
        if (searchTerm) {
            filteredSymbols = filteredSymbols.filter(symbol => 
                symbol.symbol.toLowerCase().includes(searchTerm) ||
                symbol.baseAsset.toLowerCase().includes(searchTerm)
            );
        }
        
        UIElements.pairsList.innerHTML = '';
        
        if (filteredSymbols.length === 0) {
            UIElements.pairsList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-search"></i>
                    <p>Sembol bulunamadı</p>
                </div>
            `;
            return;
        }
        
        filteredSymbols.forEach(symbolInfo => {
            const symbol = symbolInfo.symbol;
            const isSelected = symbol === AppState.currentSymbol;
            
            const pairElement = document.createElement('div');
            pairElement.className = `pair-item ${isSelected ? 'selected' : ''}`;
            pairElement.innerHTML = `
                <div class="pair-info">
                    <div class="pair-symbol">${symbol}</div>
                    <div class="pair-description">${symbolInfo.baseAsset}/USDT</div>
                </div>
                <div class="pair-actions">
                    <button class="btn btn-sm btn-outline select-pair-btn" data-symbol="${symbol}">
                        ${isSelected ? 'Seçili' : 'Seç'}
                    </button>
                </div>
            `;
            
            UIElements.pairsList.appendChild(pairElement);
        });
        
        // Add event listeners
        document.querySelectorAll('.select-pair-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                selectSymbol(btn.dataset.symbol);
            });
        });
    }

    // Select symbol
    function selectSymbol(symbol) {
        AppState.currentSymbol = symbol;
        
        // Update UI
        if (UIElements.mobilePairSymbol) {
            UIElements.mobilePairSymbol.textContent = symbol;
        }
        
        // Close modal
        if (UIElements.pairSelectorModal) {
            UIElements.pairSelectorModal.style.display = 'none';
        }
        
        // Load price data for new symbol
        loadSymbolPrice(symbol);
        
        console.log(`Sembol seçildi: ${symbol}`);
    }

    // Load symbol price
    async function loadSymbolPrice(symbol) {
        try {
            const response = await fetchUserApi(`/api/market/ticker/${symbol}`);
            
            if (response.success && response.data) {
                const data = response.data;
                AppState.priceData[symbol] = data;
                
                // Update price display
                if (symbol === AppState.currentSymbol) {
                    updatePriceDisplay(data);
                }
            }
        } catch (error) {
            console.error(`${symbol} fiyat bilgisi alınamadı:`, error);
        }
    }

    // Update price display
    function updatePriceDisplay(data) {
        if (UIElements.currentPrice) {
            UIElements.currentPrice.textContent = `$${data.price}`;
        }
        
        if (UIElements.priceChange) {
            const changePercent = data.changePercent;
            UIElements.priceChange.textContent = `${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%`;
            UIElements.priceChange.className = `price-change ${changePercent >= 0 ? 'positive' : 'negative'}`;
        }
        
        // Update other price stats
        const priceHigh = document.getElementById('price-high');
        const priceLow = document.getElementById('price-low');
        const volume = document.getElementById('volume');
        
        if (priceHigh) priceHigh.textContent = `$${data.high}`;
        if (priceLow) priceLow.textContent = `$${data.low}`;
        if (volume) {
            const vol = data.volume;
            const formattedVol = vol > 1000000 ? `${(vol / 1000000).toFixed(1)}M` : `${(vol / 1000).toFixed(1)}K`;
            volume.textContent = formattedVol;
        }
    }

    // Bot management
    async function startBot() {
        if (!validateBotSettings()) return;
        
        const startBtn = UIElements.startButton;
        if (!startBtn) return;
        
        const originalText = startBtn.innerHTML;
        startBtn.disabled = true;
        startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Başlatılıyor...';
        
        try {
            const botSettings = {
                symbol: AppState.currentSymbol,
                timeframe: AppState.currentTimeframe,
                leverage: parseInt(UIElements.leverageInput?.value || 10),
                order_size: parseFloat(UIElements.orderSizeInput?.value || 20),
                take_profit: parseFloat(UIElements.tpInput?.value || 4),
                stop_loss: parseFloat(UIElements.slInput?.value || 2)
            };
            
            const response = await fetchUserApi('/api/bot/start', {
                method: 'POST',
                body: JSON.stringify(botSettings)
            });
            
            if (response.success) {
                showSuccessMessage(translations[AppState.currentLanguage].bot_started);
                await updateBotStatus();
            } else {
                throw new Error(response.error || 'Bot başlatılamadı');
            }
            
        } catch (error) {
            showErrorMessage(`Bot başlatılamadı: ${error.message}`);
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
        stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Durduruluyor...';
        
        try {
            const response = await fetchUserApi('/api/bot/stop', {
                method: 'POST',
                body: JSON.stringify({ symbol: AppState.currentSymbol })
            });
            
            if (response.success) {
                showSuccessMessage(translations[AppState.currentLanguage].bot_stopped);
                await updateBotStatus();
            } else {
                throw new Error(response.error || 'Bot durdurulamadı');
            }
            
        } catch (error) {
            showErrorMessage(`Bot durdurulamadı: ${error.message}`);
        } finally {
            stopBtn.innerHTML = originalText;
            stopBtn.disabled = false;
        }
    }

    function validateBotSettings() {
        const leverage = parseInt(UIElements.leverageInput?.value || 0);
        const orderSize = parseFloat(UIElements.orderSizeInput?.value || 0);
        const takeProfit = parseFloat(UIElements.tpInput?.value || 0);
        const stopLoss = parseFloat(UIElements.slInput?.value || 0);
        
        if (leverage < 1 || leverage > 125) {
            showErrorMessage('Kaldıraç 1-125 arasında olmalı');
            return false;
        }
        
        if (orderSize < 10) {
            showErrorMessage('Minimum işlem büyüklüğü 10 USDT');
            return false;
        }
        
        if (takeProfit <= stopLoss) {
            showErrorMessage('Take Profit, Stop Loss\'tan büyük olmalı');
            return false;
        }
        
        if (!AppState.currentSymbol) {
            showErrorMessage(translations[AppState.currentLanguage].select_symbol);
            return false;
        }
        
        return true;
    }

    // Status polling
    let statusPollInterval = null;

    function startStatusPolling() {
        stopStatusPolling();
        statusPollInterval = setInterval(updateBotStatus, 5000);
        updateBotStatus(); // İlk güncelleme
    }

    function stopStatusPolling() {
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
        }
    }

    async function updateBotStatus() {
        try {
            const response = await fetchUserApi('/api/bot/status');
            
            AppState.activeBots = response.bots || {};
            
            // Update UI based on current symbol
            const currentBotStatus = AppState.activeBots[AppState.currentSymbol];
            
            if (currentBotStatus && currentBotStatus.is_running) {
                updateBotStatusDisplay('active', 'ÇALIŞIYOR');
                if (UIElements.startButton) UIElements.startButton.disabled = true;
                if (UIElements.stopButton) UIElements.stopButton.disabled = false;
            } else {
                updateBotStatusDisplay('inactive', 'DURDURULMUŞ');
                if (UIElements.startButton) UIElements.startButton.disabled = false;
                if (UIElements.stopButton) UIElements.stopButton.disabled = true;
            }
            
            // Update status message
            const statusMessage = document.getElementById('status-message');
            if (statusMessage && currentBotStatus) {
                statusMessage.innerHTML = `
                    <i class="fas fa-info-circle"></i>
                    ${currentBotStatus.status_message || 'Bot hazır'}
                `;
            }
            
            // Update active bots counter
            const activeBotCount = Object.keys(AppState.activeBots).length;
            updateActiveBotsDisplay(activeBotCount);
            
        } catch (error) {
            console.error('Bot durumu güncellenemedi:', error);
        }
    }

    function updateBotStatusDisplay(status, text) {
        if (UIElements.botStatusDot) {
            UIElements.botStatusDot.className = `status-dot ${status === 'active' ? 'active' : ''}`;
        }
        
        if (UIElements.botStatusText) {
            UIElements.botStatusText.textContent = text;
        }
    }

    function updateActiveBotsDisplay(count) {
        // Update any bot count displays
        const botCountElements = document.querySelectorAll('.bot-count');
        botCountElements.forEach(element => {
            element.textContent = `${count}/${AppState.maxBotsPerUser}`;
        });
    }

    // Load user data
    async function loadUserData() {
        try {
            const response = await fetchUserApi('/api/user/profile');
            
            if (response) {
                updateUserProfile(response);
            }
            
            // Load available symbols
            await loadAvailableSymbols();
            
        } catch (error) {
            console.error('Kullanıcı verisi yüklenemedi:', error);
        }
    }

    function updateUserProfile(profile) {
        // Update profile information in UI
        const userEmailElement = document.getElementById('user-email');
        if (userEmailElement) {
            userEmailElement.textContent = profile.email || '-';
        }
        
    function updateUserProfile(profile) {
        // Update profile information in UI
        const userEmailElement = document.getElementById('user-email');
        if (userEmailElement) {
            userEmailElement.textContent = profile.email || '-';
        }
        
        // Update subscription status
        const subscriptionStatusElement = document.getElementById('subscription-status');
        if (subscriptionStatusElement) {
            const statusBadge = subscriptionStatusElement.querySelector('.status-badge');
            if (statusBadge) {
                statusBadge.textContent = profile.subscription_status || 'inactive';
                statusBadge.className = `status-badge ${profile.subscription_status || 'inactive'}`;
            }
        }
        
        // Update subscription expiry
        const subscriptionExpiryElement = document.getElementById('subscription-expiry');
        if (subscriptionExpiryElement && profile.subscription_expiry) {
            const expiryDate = new Date(profile.subscription_expiry);
            subscriptionExpiryElement.textContent = expiryDate.toLocaleDateString('tr-TR');
        }
        
        // Update stats
        if (profile.stats) {
            updateStatsDisplay(profile.stats);
        }
        
        // Update API keys status
        const apiStatus = document.getElementById('api-status-indicator');
        const apiStatusText = document.getElementById('api-status-text');
        if (apiStatus && apiStatusText) {
            if (profile.has_api_keys) {
                apiStatus.className = 'status-indicator active';
                apiStatusText.textContent = 'CONFIGURED';
            } else {
                apiStatus.className = 'status-indicator inactive';
                apiStatusText.textContent = 'NOT CONFIGURED';
            }
        }
    }

    function updateStatsDisplay(stats) {
        const elements = {
            'total-trades': stats.total_trades || 0,
            'win-rate': `${stats.win_rate || 0}%`,
            'total-pnl': `${stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl || '0.00'} USDT`,
            'uptime': `${stats.uptime_hours || 0}h`
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
                
                // Add color classes for PnL
                if (id === 'total-pnl') {
                    element.className = `stat-value ${stats.total_pnl >= 0 ? 'text-success' : 'text-danger'}`;
                }
            }
        });
    }

    // Initialize authentication
    function initializeAuth() {
        // Login/Register form switching
        const showRegisterLink = document.getElementById('show-register-link');
        const showLoginLink = document.getElementById('show-login-link');
        
        if (showRegisterLink) {
            showRegisterLink.addEventListener('click', (e) => {
                e.preventDefault();
                UIElements.loginCard.style.display = 'none';
                UIElements.registerCard.style.display = 'block';
            });
        }
        
        if (showLoginLink) {
            showLoginLink.addEventListener('click', (e) => {
                e.preventDefault();
                UIElements.registerCard.style.display = 'none';
                UIElements.loginCard.style.display = 'block';
            });
        }
        
        // Login button
        const loginButton = document.getElementById('login-button');
        if (loginButton) {
            loginButton.addEventListener('click', handleLogin);
        }
        
        // Register button
        const registerButton = document.getElementById('register-button');
        if (registerButton) {
            registerButton.addEventListener('click', handleRegister);
        }
        
        // Logout button
        const logoutButton = document.getElementById('logout-button');
        if (logoutButton) {
            logoutButton.addEventListener('click', handleLogout);
        }
    }

    async function handleLogin() {
        const email = document.getElementById('login-email')?.value;
        const password = document.getElementById('login-password')?.value;
        const errorElement = document.getElementById('login-error');
        
        if (!email || !password) {
            showAuthError('Lütfen tüm alanları doldurun', errorElement);
            return;
        }
        
        const loginButton = document.getElementById('login-button');
        const originalText = loginButton.innerHTML;
        loginButton.disabled = true;
        loginButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Giriş yapılıyor...';
        
        try {
            await firebaseServices.auth.signInWithEmailAndPassword(email, password);
        } catch (error) {
            showAuthError(getAuthErrorMessage(error.code), errorElement);
        } finally {
            loginButton.innerHTML = originalText;
            loginButton.disabled = false;
        }
    }

    async function handleRegister() {
        const email = document.getElementById('register-email')?.value;
        const password = document.getElementById('register-password')?.value;
        const language = document.getElementById('register-language')?.value || 'tr';
        const errorElement = document.getElementById('register-error');
        
        if (!email || !password) {
            showAuthError('Lütfen tüm alanları doldurun', errorElement);
            return;
        }
        
        if (password.length < 6) {
            showAuthError('Şifre en az 6 karakter olmalı', errorElement);
            return;
        }
        
        const registerButton = document.getElementById('register-button');
        const originalText = registerButton.innerHTML;
        registerButton.disabled = true;
        registerButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Hesap oluşturuluyor...';
        
        try {
            await firebaseServices.auth.createUserWithEmailAndPassword(email, password);
            
            // Set language preference
            AppState.currentLanguage = language;
            localStorage.setItem('userLanguage', language);
            updateLanguage(language);
            
        } catch (error) {
            showAuthError(getAuthErrorMessage(error.code), errorElement);
        } finally {
            registerButton.innerHTML = originalText;
            registerButton.disabled = false;
        }
    }

    async function handleLogout() {
        if (confirm('Çıkış yapmak istediğinizden emin misiniz?')) {
            try {
                await firebaseServices.auth.signOut();
            } catch (error) {
                console.error('Çıkış hatası:', error);
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
            'auth/user-not-found': 'Kullanıcı bulunamadı',
            'auth/wrong-password': 'Hatalı şifre',
            'auth/email-already-in-use': 'Bu e-posta adresi zaten kayıtlı',
            'auth/weak-password': 'Şifre çok zayıf',
            'auth/invalid-email': 'Geçersiz e-posta adresi'
        };
        
        return messages[errorCode] || 'Bir hata oluştu. Lütfen tekrar deneyin.';
    }

    // Initialize navigation
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
        
        // Mobile navigation
        document.querySelectorAll('.mobile-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const targetPage = tab.dataset.page;
                if (targetPage) {
                    showPage(targetPage);
                    
                    // Update active state
                    document.querySelectorAll('.mobile-tab').forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');
                }
            });
        });
    }

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
            if (pageId === 'api-page') {
                loadServerIPs();
            }
        }
    }

    // Initialize trading controls
    function initializeTradingControls() {
        // Leverage slider
        if (UIElements.leverageInput) {
            UIElements.leverageInput.addEventListener('input', updateLeverageDisplay);
        }
        
        // Bot control buttons
        if (UIElements.startButton) {
            UIElements.startButton.addEventListener('click', startBot);
        }
        
        if (UIElements.stopButton) {
            UIElements.stopButton.addEventListener('click', stopBot);
        }
        
        // API Keys form
        const saveKeysButton = document.getElementById('save-keys-button');
        if (saveKeysButton) {
            saveKeysButton.addEventListener('click', saveApiKeys);
        }
        
        // Language selector
        const languageSelector = document.getElementById('language-selector');
        if (languageSelector) {
            languageSelector.addEventListener('change', (e) => {
                updateLanguage(e.target.value);
            });
        }
    }

    function updateLeverageDisplay() {
        if (UIElements.leverageValue && UIElements.leverageInput) {
            UIElements.leverageValue.textContent = `${UIElements.leverageInput.value}x`;
        }
    }

    async function saveApiKeys() {
        const apiKeyInput = document.getElementById('api-key-input');
        const apiSecretInput = document.getElementById('api-secret-input');
        const statusElement = document.getElementById('api-keys-status');
        
        if (!apiKeyInput || !apiSecretInput) return;
        
        const apiKey = apiKeyInput.value.trim();
        const apiSecret = apiSecretInput.value.trim();
        
        if (!apiKey || !apiSecret) {
            showStatusMessage(statusElement, 'API Key ve Secret boş olamaz', 'error');
            return;
        }
        
        const saveButton = document.getElementById('save-keys-button');
        const originalText = saveButton.innerHTML;
        saveButton.disabled = true;
        saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Kaydediliyor...';
        
        try {
            const response = await fetchUserApi('/api/user/save-keys', {
                method: 'POST',
                body: JSON.stringify({
                    api_key: apiKey,
                    api_secret: apiSecret,
                    environment: 'LIVE' // Default to LIVE
                })
            });
            
            if (response.success) {
                showStatusMessage(statusElement, 'API anahtarları güvenli şekilde kaydedildi', 'success');
                
                // Clear inputs for security
                apiKeyInput.value = '';
                apiSecretInput.value = '';
                
                // Update API status
                const apiStatus = document.getElementById('api-status-indicator');
                const apiStatusText = document.getElementById('api-status-text');
                if (apiStatus && apiStatusText) {
                    apiStatus.className = 'status-indicator active';
                    apiStatusText.textContent = 'CONFIGURED';
                }
                
                // Reload available symbols
                await loadAvailableSymbols();
            } else {
                throw new Error(response.error || 'API anahtarları kaydedilemedi');
            }
            
        } catch (error) {
            showStatusMessage(statusElement, `Hata: ${error.message}`, 'error');
        } finally {
            saveButton.innerHTML = originalText;
            saveButton.disabled = false;
        }
    }

    // Initialize modals
    function initializeModals() {
        // Pair selector modal
        const pairSelectorBtn = document.getElementById('pair-selector-btn');
        if (pairSelectorBtn) {
            pairSelectorBtn.addEventListener('click', () => {
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
        if (UIElements.pairSearchInput) {
            UIElements.pairSearchInput.addEventListener('input', updatePairsModal);
        }
        
        // Close modals on outside click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        });
    }

    // Load server IPs
    async function loadServerIPs() {
        const ipList = document.getElementById('ip-list');
        if (!ipList) return;
        
        // Mock IP list - replace with actual API call if needed
        const mockIPs = [
            '18.156.158.53',
            '18.156.42.200', 
            '52.59.103.54'
        ];
        
        ipList.innerHTML = mockIPs.map(ip => `
            <div class="ip-item">
                <span>${ip}</span>
                <button class="btn-copy" onclick="copyToClipboard('${ip}')">
                    <i class="fas fa-copy"></i>
                </button>
            </div>
        `).join('');
    }

    // Helper functions
    function updateLanguage(lang) {
        AppState.currentLanguage = lang;
        localStorage.setItem('userLanguage', lang);
        
        // Update language selector
        const languageSelector = document.getElementById('language-selector');
        if (languageSelector) {
            languageSelector.value = lang;
        }
        
        console.log(`Dil değiştirildi: ${lang}`);
    }

    function showSuccessMessage(message) {
        showToast(message, 'success');
    }

    function showErrorMessage(message) {
        showToast(message, 'error');
    }

    function showToast(message, type = 'info') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        // Add to page
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Remove toast
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }

    function showStatusMessage(element, message, type) {
        if (!element) return;
        
        element.textContent = message;
        element.className = `status-message ${type}`;
        element.style.display = 'block';
        
        if (type === 'success') {
            setTimeout(() => {
                element.style.display = 'none';
            }, 5000);
        }
    }

    function copyToClipboard(text) {
        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                showSuccessMessage('Panoya kopyalandı');
            }).catch(() => {
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
            showSuccessMessage('Panoya kopyalandı');
        } catch (err) {
            showErrorMessage('Kopyalama başarısız');
        } finally {
            document.body.removeChild(textArea);
        }
    }

    // Global helper functions for HTML onclick events
    window.adjustOrderSize = function(amount) {
        if (UIElements.orderSizeInput) {
            const currentValue = parseFloat(UIElements.orderSizeInput.value) || 20;
            const newValue = Math.max(10, currentValue + amount);
            UIElements.orderSizeInput.value = newValue;
        }
    };

    window.setLeverage = function(value) {
        if (UIElements.leverageInput) {
            UIElements.leverageInput.value = value;
            updateLeverageDisplay();
        }
    };

    window.copyToClipboard = copyToClipboard;

    // Add CSS for toast notifications
    const toastCSS = `
        <style>
            .toast {
                position: fixed;
                top: 20px;
                right: 20px;
                background: var(--card-background);
                color: var(--text-primary);
                padding: 1rem 1.5rem;
                border-radius: 0.5rem;
                border: 1px solid var(--border-color);
                box-shadow: var(--box-shadow-lg);
                display: flex;
                align-items: center;
                gap: 0.75rem;
                z-index: 10000;
                transform: translateX(400px);
                transition: transform 0.3s ease;
                max-width: 350px;
            }
            .toast.show {
                transform: translateX(0);
            }
            .toast-success {
                border-left: 4px solid var(--success-color);
            }
            .toast-error {
                border-left: 4px solid var(--danger-color);
            }
            .toast i {
                font-size: 1.25rem;
            }
            .toast-success i {
                color: var(--success-color);
            }
            .toast-error i {
                color: var(--danger-color);
            }
        </style>
    `;
    
    document.head.insertAdjacentHTML('beforeend', toastCSS);

    // Start the application
    initializeApp();
});
