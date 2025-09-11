document.addEventListener('DOMContentLoaded', () => {
    // Global application state
    const AppState = {
        currentUser: null,
        isAuthenticated: false,
        apiConnected: false,
        botRunning: false,
        userSettings: {},
        accountData: {},
        positions: [],
        recentTrades: [],
        tradingPairs: [],
        websocketConnection: null,
        refreshInterval: null
    };

    // API Configuration
    const API_CONFIG = {
        baseUrl: '/api/v1',
        endpoints: {
            auth: '/auth',
            user: '/user',
            trading: '/trading',
            binance: '/binance'
        },
        timeout: 10000
    };

    // UI Elements
    const UIElements = {
        // Loading
        loadingScreen: document.getElementById('loading-screen'),
        dashboard: document.getElementById('dashboard'),
        
        // User Info
        userName: document.getElementById('user-name'),
        subscriptionText: document.getElementById('subscription-text'),
        subscriptionBadge: document.getElementById('subscription-badge'),
        
        // API Status
        apiStatus: document.getElementById('api-status'),
        apiStatusIndicator: document.getElementById('api-status-indicator'),
        manageApiBtn: document.getElementById('manage-api-btn'),
        
        // Trading Settings
        tradingSettings: document.getElementById('trading-settings'),
        symbolSelect: document.getElementById('symbol-select'),
        timeframeSelect: document.getElementById('timeframe-select'),
        leverageSelect: document.getElementById('leverage-select'),
        orderSize: document.getElementById('order-size'),
        stopLoss: document.getElementById('stop-loss'),
        takeProfit: document.getElementById('take-profit'),
        maxDailyTrades: document.getElementById('max-daily-trades'),
        autoCompound: document.getElementById('auto-compound'),
        
        // Control Buttons
        controlButtons: document.getElementById('control-buttons'),
        startBotBtn: document.getElementById('start-bot-btn'),
        stopBotBtn: document.getElementById('stop-bot-btn'),
        
        // Status
        botStatus: document.getElementById('bot-status'),
        statusDot: document.getElementById('status-dot'),
        statusText: document.getElementById('status-text'),
        statusMessageText: document.getElementById('status-message-text'),
        
        // Account Info
        totalBalance: document.getElementById('total-balance'),
        availableBalance: document.getElementById('available-balance'),
        totalTrades: document.getElementById('total-trades'),
        winRate: document.getElementById('win-rate'),
        totalPnl: document.getElementById('total-pnl'),
        uptime: document.getElementById('uptime'),
        subStatusBadge: document.getElementById('sub-status-badge'),
        daysRemaining: document.getElementById('days-remaining'),
        subscriptionNote: document.getElementById('subscription-note'),
        
        // Positions
        positionsContainer: document.getElementById('positions-container'),
        refreshPositionsBtn: document.getElementById('refresh-positions-btn'),
        
        // Activity
        activityList: document.getElementById('activity-list'),
        refreshActivityBtn: document.getElementById('refresh-activity-btn'),
        
        // Refresh Buttons
        refreshAccountBtn: document.getElementById('refresh-account-btn'),
        
        // Modal
        apiModal: document.getElementById('api-modal'),
        modalClose: document.getElementById('modal-close'),
        apiForm: document.getElementById('api-form'),
        apiKey: document.getElementById('api-key'),
        apiSecret: document.getElementById('api-secret'),
        apiTestnet: document.getElementById('api-testnet'),
        saveApiBtn: document.getElementById('save-api'),
        cancelApiBtn: document.getElementById('cancel-api'),
        apiTestResult: document.getElementById('api-test-result'),
        
        // Notification
        notificationToast: document.getElementById('notification-toast'),
        
        // Settings and Logout
        settingsBtn: document.getElementById('settings-btn'),
        logoutBtn: document.getElementById('logout-btn')
    };

    // Utility Functions
    const Utils = {
        async makeApiCall(endpoint, options = {}) {
            const token = localStorage.getItem('authToken');
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                    ...(token && { 'Authorization': `Bearer ${token}` })
                },
                timeout: API_CONFIG.timeout
            };

            const mergedOptions = {
                ...defaultOptions,
                ...options,
                headers: { ...defaultOptions.headers, ...options.headers }
            };

            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), mergedOptions.timeout);
                
                const response = await fetch(API_CONFIG.baseUrl + endpoint, {
                    ...mergedOptions,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return await response.json();
                }
                
                return await response.text();
            } catch (error) {
                if (error.name === 'AbortError') {
                    throw new Error('Request timeout');
                }
                throw error;
            }
        },

        showNotification(message, type = 'info', duration = 5000) {
            const toast = UIElements.notificationToast;
            const icon = toast.querySelector('.toast-icon');
            const messageEl = toast.querySelector('.toast-message');
            
            // Set icon based on type
            const icons = {
                success: 'fas fa-check-circle',
                error: 'fas fa-exclamation-circle',
                warning: 'fas fa-exclamation-triangle',
                info: 'fas fa-info-circle'
            };
            
            icon.className = `toast-icon ${icons[type] || icons.info}`;
            messageEl.textContent = message;
            
            // Set color based on type
            const colors = {
                success: 'var(--success-color)',
                error: 'var(--danger-color)',
                warning: 'var(--warning-color)',
                info: 'var(--info-color)'
            };
            
            icon.style.color = colors[type] || colors.info;
            
            toast.classList.add('show');
            
            setTimeout(() => {
                toast.classList.remove('show');
            }, duration);
        },

        formatCurrency(amount, currency = 'USDT') {
            const num = parseFloat(amount) || 0;
            return `${num.toLocaleString('tr-TR', { 
                minimumFractionDigits: 2, 
                maximumFractionDigits: 2 
            })} ${currency}`;
        },

        formatPercentage(value) {
            const num = parseFloat(value) || 0;
            const sign = num >= 0 ? '+' : '';
            return `${sign}${num.toFixed(2)}%`;
        },

        formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleString('tr-TR');
        },

        debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    };

    // Authentication Functions
    const Auth = {
        async checkAuthStatus() {
            try {
                const token = localStorage.getItem('authToken');
                if (!token) {
                    throw new Error('No token found');
                }

                const userInfo = await Utils.makeApiCall('/auth/verify');
                AppState.currentUser = userInfo;
                AppState.isAuthenticated = true;
                
                UIElements.userName.textContent = userInfo.email || 'Kullanıcı';
                
                return true;
            } catch (error) {
                console.error('Auth check failed:', error);
                AppState.isAuthenticated = false;
                this.redirectToLogin();
                return false;
            }
        },

        redirectToLogin() {
            Utils.showNotification('Oturum süresi doldu. Lütfen tekrar giriş yapın.', 'warning');
            setTimeout(() => {
                window.location.href = '/login.html';
            }, 2000);
        },

        async logout() {
            try {
                await Utils.makeApiCall('/auth/logout', { method: 'POST' });
            } catch (error) {
                console.error('Logout error:', error);
            } finally {
                localStorage.removeItem('authToken');
                AppState.isAuthenticated = false;
                AppState.currentUser = null;
                window.location.href = '/login.html';
            }
        }
    };

    // API Management Functions
    const ApiManager = {
        async checkApiStatus() {
            try {
                UIElements.statusMessageText.textContent = 'API bağlantısı kontrol ediliyor...';
                
                const response = await Utils.makeApiCall('/user/api-status');
                
                if (response.hasApiKeys) {
                    if (response.isConnected) {
                        this.showApiConnected();
                        await this.loadTradingPairs();
                        UIElements.tradingSettings.style.display = 'block';
                        UIElements.controlButtons.style.display = 'grid';
                        UIElements.statusMessageText.textContent = 'Bot hazır. Ayarları yapılandırıp başlatabilirsiniz.';
                        AppState.apiConnected = true;
                    } else {
                        this.showApiError('API anahtarları geçersiz veya bağlantı hatası');
                    }
                } else {
                    this.showApiNotConfigured();
                }
            } catch (error) {
                console.error('API status check failed:', error);
                this.showApiError('API durumu kontrol edilemedi');
            }
        },

        showApiNotConfigured() {
            UIElements.apiStatusIndicator.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <span>API anahtarları gerekli</span>
            `;
            UIElements.apiStatusIndicator.className = 'api-status-indicator error';
            UIElements.manageApiBtn.style.display = 'inline-flex';
            UIElements.manageApiBtn.textContent = 'API Anahtarlarını Ekle';
            UIElements.statusMessageText.textContent = 'Bot\'u çalıştırmak için API anahtarlarınızı eklemelisiniz.';
        },

        showApiConnected() {
            UIElements.apiStatusIndicator.innerHTML = `
                <i class="fas fa-check-circle"></i>
                <span>API bağlantısı aktif</span>
            `;
            UIElements.apiStatusIndicator.className = 'api-status-indicator connected';
            UIElements.manageApiBtn.style.display = 'inline-flex';
            UIElements.manageApiBtn.textContent = 'API Ayarlarını Düzenle';
        },

        showApiError(message) {
            UIElements.apiStatusIndicator.innerHTML = `
                <i class="fas fa-times-circle"></i>
                <span>API bağlantı hatası</span>
            `;
            UIElements.apiStatusIndicator.className = 'api-status-indicator error';
            UIElements.manageApiBtn.style.display = 'inline-flex';
            UIElements.manageApiBtn.textContent = 'API Anahtarlarını Düzenle';
            UIElements.statusMessageText.textContent = message;
        },

        async saveApiKeys(apiKey, apiSecret, useTestnet = false) {
            try {
                UIElements.saveApiBtn.disabled = true;
                UIElements.saveApiBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Test ediliyor...';

                const response = await Utils.makeApiCall('/user/api-keys', {
                    method: 'POST',
                    body: JSON.stringify({
                        apiKey,
                        apiSecret,
                        useTestnet
                    })
                });

                if (response.success) {
                    UIElements.apiTestResult.style.display = 'block';
                    UIElements.apiTestResult.className = 'api-test-result success';
                    UIElements.apiTestResult.innerHTML = `
                        <i class="fas fa-check-circle"></i>
                        API anahtarları başarıyla kaydedildi ve test edildi!
                    `;
                    
                    setTimeout(() => {
                        this.closeModal();
                        this.checkApiStatus();
                    }, 2000);
                    
                    Utils.showNotification('API anahtarları başarıyla kaydedildi!', 'success');
                } else {
                    throw new Error(response.message || 'API anahtarları kaydedilemedi');
                }
            } catch (error) {
                console.error('API keys save failed:', error);
                UIElements.apiTestResult.style.display = 'block';
                UIElements.apiTestResult.className = 'api-test-result error';
                UIElements.apiTestResult.innerHTML = `
                    <i class="fas fa-times-circle"></i>
                    Hata: ${error.message}
                `;
                Utils.showNotification(`API kaydı başarısız: ${error.message}`, 'error');
            } finally {
                UIElements.saveApiBtn.disabled = false;
                UIElements.saveApiBtn.innerHTML = '<i class="fas fa-save"></i> Kaydet ve Test Et';
            }
        },

        async loadTradingPairs() {
            try {
                const pairs = await Utils.makeApiCall('/trading/pairs');
                AppState.tradingPairs = pairs;
                
                UIElements.symbolSelect.innerHTML = '';
                pairs.forEach(pair => {
                    const option = document.createElement('option');
                    option.value = pair.symbol;
                    option.textContent = `${pair.baseAsset}/${pair.quoteAsset}`;
                    UIElements.symbolSelect.appendChild(option);
                });
                
                // Set default to BTCUSDT if available
                const btcOption = pairs.find(p => p.symbol === 'BTCUSDT');
                if (btcOption) {
                    UIElements.symbolSelect.value = 'BTCUSDT';
                }
            } catch (error) {
                console.error('Failed to load trading pairs:', error);
                Utils.showNotification('Trading çiftleri yüklenemedi', 'error');
            }
        },

        openModal() {
            UIElements.apiModal.classList.add('show');
            UIElements.apiTestResult.style.display = 'none';
            
            // Load existing API info if available
            this.loadExistingApiInfo();
        },

        closeModal() {
            UIElements.apiModal.classList.remove('show');
            UIElements.apiForm.reset();
            UIElements.apiTestResult.style.display = 'none';
        },

        async loadExistingApiInfo() {
            try {
                const apiInfo = await Utils.makeApiCall('/user/api-info');
                if (apiInfo.hasKeys) {
                    UIElements.apiKey.value = apiInfo.maskedApiKey || '';
                    UIElements.apiTestnet.checked = apiInfo.useTestnet || false;
                    
                    // Show that keys exist
                    UIElements.apiSecret.placeholder = 'Mevcut secret korunuyor (değiştirmek için yeni girin)';
                }
            } catch (error) {
                console.error('Failed to load API info:', error);
            }
        }
    };

    // Data Loading Functions
    const DataLoader = {
        async loadUserProfile() {
            try {
                const profile = await Utils.makeApiCall('/user/profile');
                
                UIElements.userName.textContent = profile.email || 'Kullanıcı';
                
                if (profile.subscription) {
                    UIElements.subscriptionText.textContent = profile.subscription.plan || 'Premium';
                    UIElements.subStatusBadge.textContent = profile.subscription.status || 'Aktif';
                    
                    if (profile.subscription.expiryDate) {
                        const expiryDate = new Date(profile.subscription.expiryDate);
                        const today = new Date();
                        const daysLeft = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));
                        
                        UIElements.daysRemaining.textContent = daysLeft > 0 ? `${daysLeft} gün kaldı` : 'Süresi dolmuş';
                        
                        if (daysLeft <= 7 && daysLeft > 0) {
                            UIElements.subscriptionNote.textContent = 'Aboneliğiniz yakında sona erecek. Yenilemeyi unutmayın!';
                            UIElements.subscriptionNote.style.color = 'var(--warning-color)';
                        } else if (daysLeft <= 0) {
                            UIElements.subscriptionNote.textContent = 'Abonelik süresi dolmuş. Lütfen yenileyin.';
                            UIElements.subscriptionNote.style.color = 'var(--danger-color)';
                        } else {
                            UIElements.subscriptionNote.textContent = 'Aboneliğiniz aktif durumda.';
                            UIElements.subscriptionNote.style.color = 'var(--success-color)';
                        }
                    }
                }
            } catch (error) {
                console.error('Failed to load user profile:', error);
                Utils.showNotification('Kullanıcı profili yüklenemedi', 'error');
            }
        },

        async loadAccountData() {
            try {
                const accountData = await Utils.makeApiCall('/user/account');
                AppState.accountData = accountData;
                
                UIElements.totalBalance.textContent = Utils.formatCurrency(accountData.totalBalance);
                UIElements.availableBalance.textContent = Utils.formatCurrency(accountData.availableBalance);
                
                // Load stats
                const stats = await Utils.makeApiCall('/user/stats');
                
                UIElements.totalTrades.textContent = stats.totalTrades || '0';
                UIElements.winRate.textContent = Utils.formatPercentage(stats.winRate || 0);
                UIElements.totalPnl.textContent = Utils.formatCurrency(stats.totalPnl || 0);
                
                // Calculate uptime
                if (stats.botStartTime) {
                    const startTime = new Date(stats.botStartTime);
                    const now = new Date();
                    const uptimeHours = Math.floor((now - startTime) / (1000 * 60 * 60));
                    UIElements.uptime.textContent = `${uptimeHours}h`;
                }
                
                // Color P&L based on positive/negative
                const pnlValue = parseFloat(stats.totalPnl || 0);
                if (pnlValue > 0) {
                    UIElements.totalPnl.style.color = 'var(--success-color)';
                } else if (pnlValue < 0) {
                    UIElements.totalPnl.style.color = 'var(--danger-color)';
                } else {
                    UIElements.totalPnl.style.color = 'var(--text-primary)';
                }
                
            } catch (error) {
                console.error('Failed to load account data:', error);
                Utils.showNotification('Hesap verileri yüklenemedi', 'error');
            }
        },

        async loadPositions() {
            try {
                const positions = await Utils.makeApiCall('/user/positions');
                AppState.positions = positions;
                
                this.renderPositions(positions);
            } catch (error) {
                console.error('Failed to load positions:', error);
                UIElements.positionsContainer.innerHTML = `
                    <div class="error-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h3>Pozisyonlar Yüklenemedi</h3>
                        <p>Pozisyon verileri alınırken hata oluştu</p>
                        <button class="btn btn-primary btn-sm" onclick="location.reload()">Tekrar Dene</button>
                    </div>
                `;
            }
        },

        renderPositions(positions) {
            if (!positions || positions.length === 0) {
                UIElements.positionsContainer.innerHTML = `
                    <div class="no-positions">
                        <div class="no-position-icon">
                            <i class="fas fa-chart-line"></i>
                        </div>
                        <h3>Açık Pozisyon Yok</h3>
                        <p>Bot başlatıldığında pozisyonlar burada görünecek</p>
                    </div>
                `;
                return;
            }

            const positionsHTML = positions.map(position => {
                const pnlClass = position.unrealizedPnl >= 0 ? 'profit' : 'loss';
                const sideClass = position.positionSide.toLowerCase();
                
                return `
                    <div class="position-item">
                        <div class="position-header">
                            <span class="position-symbol">${position.symbol}</span>
                            <span class="position-side ${sideClass}">${position.positionSide}</span>
                        </div>
                        <div class="position-stats">
                            <div class="position-stat">
                                <div class="stat-label">Boyut</div>
                                <div class="stat-value">${Math.abs(position.positionAmt)} ${position.symbol.replace('USDT', '')}</div>
                            </div>
                            <div class="position-stat">
                                <div class="stat-label">Giriş Fiyatı</div>
                                <div class="stat-value">$${parseFloat(position.entryPrice).toFixed(2)}</div>
                            </div>
                            <div class="position-stat">
                                <div class="stat-label">Güncel Fiyat</div>
                                <div class="stat-value">$${parseFloat(position.markPrice).toFixed(2)}</div>
                            </div>
                            <div class="position-stat">
                                <div class="stat-label">P&L</div>
                                <div class="stat-value ${pnlClass}">${Utils.formatCurrency(position.unrealizedPnl)}</div>
                            </div>
                        </div>
                        <button class="btn btn-danger btn-sm" onclick="closePosition('${position.symbol}', '${position.positionSide}')">
                            <i class="fas fa-times"></i> Pozisyonu Kapat
                        </button>
                    </div>
                `;
            }).join('');

            UIElements.positionsContainer.innerHTML = positionsHTML;
        },

        async loadRecentActivity() {
            try {
                const trades = await Utils.makeApiCall('/user/recent-trades?limit=10');
                AppState.recentTrades = trades;
                
                this.renderRecentActivity(trades);
            } catch (error) {
                console.error('Failed to load recent activity:', error);
                UIElements.activityList.innerHTML = `
                    <div class="error-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Son işlemler yüklenemedi</p>
                    </div>
                `;
            }
        },

        renderRecentActivity(trades) {
            if (!trades || trades.length === 0) {
                UIElements.activityList.innerHTML = `
                    <div class="no-activity">
                        <div class="activity-icon info">
                            <i class="fas fa-info-circle"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">Henüz işlem yok</div>
                            <div class="activity-time">Bot başladığında işlemler burada görünecek</div>
                        </div>
                    </div>
                `;
                return;
            }

            const tradesHTML = trades.map(trade => {
                const sideClass = trade.side === 'BUY' ? 'success' : 'warning';
                const icon = trade.side === 'BUY' ? 'fa-arrow-up' : 'fa-arrow-down';
                
                return `
                    <div class="activity-item">
                        <div class="activity-icon ${sideClass}">
                            <i class="fas ${icon}"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">
                                ${trade.side} ${trade.symbol} - ${Utils.formatCurrency(trade.quoteQty)}
                            </div>
                            <div class="activity-time">${Utils.formatDate(trade.time)}</div>
                        </div>
                    </div>
                `;
            }).join('');

            UIElements.activityList.innerHTML = tradesHTML;
        }
    };

    // Bot Control Functions
    const BotController = {
        async startBot() {
            try {
                if (!AppState.apiConnected) {
                    Utils.showNotification('Önce API anahtarlarınızı yapılandırın', 'error');
                    return;
                }

                UIElements.startBotBtn.disabled = true;
                UIElements.startBotBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Başlatılıyor...';

                const botConfig = {
                    symbol: UIElements.symbolSelect.value,
                    timeframe: UIElements.timeframeSelect.value,
                    leverage: parseInt(UIElements.leverageSelect.value),
                    orderSize: parseFloat(UIElements.orderSize.value),
                    stopLoss: parseFloat(UIElements.stopLoss.value),
                    takeProfit: parseFloat(UIElements.takeProfit.value),
                    maxDailyTrades: parseInt(UIElements.maxDailyTrades.value),
                    autoCompound: UIElements.autoCompound.checked
                };

                const response = await Utils.makeApiCall('/bot/start', {
                    method: 'POST',
                    body: JSON.stringify(botConfig)
                });

                if (response.success) {
                    AppState.botRunning = true;
                    this.updateBotStatus(true);
                    Utils.showNotification('Bot başarıyla başlatıldı!', 'success');
                    
                    // Start regular data updates
                    this.startDataRefresh();
                } else {
                    throw new Error(response.message || 'Bot başlatılamadı');
                }
            } catch (error) {
                console.error('Failed to start bot:', error);
                Utils.showNotification(`Bot başlatma hatası: ${error.message}`, 'error');
            } finally {
                UIElements.startBotBtn.disabled = false;
                UIElements.startBotBtn.innerHTML = '<i class="fas fa-play"></i> Bot\'u Başlat';
            }
        },

        async stopBot() {
            try {
                UIElements.stopBotBtn.disabled = true;
                UIElements.stopBotBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Durduruluyor...';

                const response = await Utils.makeApiCall('/bot/stop', {
                    method: 'POST'
                });

                if (response.success) {
                    AppState.botRunning = false;
                    this.updateBotStatus(false);
                    Utils.showNotification('Bot başarıyla durduruldu!', 'success');
                    
                    // Stop data refresh
                    if (AppState.refreshInterval) {
                        clearInterval(AppState.refreshInterval);
                        AppState.refreshInterval = null;
                    }
                } else {
                    throw new Error(response.message || 'Bot durdurulamadı');
                }
            } catch (error) {
                console.error('Failed to stop bot:', error);
                Utils.showNotification(`Bot durdurma hatası: ${error.message}`, 'error');
            } finally {
                UIElements.stopBotBtn.disabled = false;
                UIElements.stopBotBtn.innerHTML = '<i class="fas fa-stop"></i> Bot\'u Durdur';
            }
        },

        updateBotStatus(isRunning) {
            if (isRunning) {
                UIElements.statusDot.className = 'status-dot active';
                UIElements.statusText.textContent = 'Çalışıyor';
                UIElements.statusMessageText.textContent = 'Bot aktif olarak çalışıyor. İşlemler otomatik gerçekleştiriliyor.';
                UIElements.startBotBtn.disabled = true;
                UIElements.stopBotBtn.disabled = false;
            } else {
                UIElements.statusDot.className = 'status-dot';
                UIElements.statusText.textContent = 'Durduruldu';
                UIElements.statusMessageText.textContent = 'Bot durduruldu. Başlatmak için ayarları kontrol edin.';
                UIElements.startBotBtn.disabled = false;
                UIElements.stopBotBtn.disabled = true;
            }
        },

        async getBotStatus() {
            try {
                const status = await Utils.makeApiCall('/bot/status');
                AppState.botRunning = status.isRunning;
                this.updateBotStatus(status.isRunning);
                
                if (status.isRunning) {
                    this.startDataRefresh();
                }
            } catch (error) {
                console.error('Failed to get bot status:', error);
            }
        },

        startDataRefresh() {
            if (AppState.refreshInterval) {
                clearInterval(AppState.refreshInterval);
            }
            
            // Refresh data every 30 seconds when bot is running
            AppState.refreshInterval = setInterval(async () => {
                await DataLoader.loadAccountData();
                await DataLoader.loadPositions();
                await DataLoader.loadRecentActivity();
            }, 30000);
        }
    };

    // Global Functions for HTML onclick events
    window.closePosition = async (symbol, positionSide) => {
        if (!confirm(`${symbol} ${positionSide} pozisyonunu kapatmak istediğinizden emin misiniz?`)) {
            return;
        }

        try {
            const response = await Utils.makeApiCall('/trading/close-position', {
                method: 'POST',
                body: JSON.stringify({ symbol, positionSide })
            });

            if (response.success) {
                Utils.showNotification('Pozisyon başarıyla kapatıldı!', 'success');
                await DataLoader.loadPositions();
                await DataLoader.loadAccountData();
            } else {
                throw new Error(response.message || 'Pozisyon kapatılamadı');
            }
        } catch (error) {
            console.error('Failed to close position:', error);
            Utils.showNotification(`Pozisyon kapatma hatası: ${error.message}`, 'error');
        }
    };

    // Event Listeners
    function initializeEventListeners() {
        // Modal Events
        UIElements.manageApiBtn?.addEventListener('click', () => {
            ApiManager.openModal();
        });

        UIElements.modalClose?.addEventListener('click', () => {
            ApiManager.closeModal();
        });

        UIElements.cancelApiBtn?.addEventListener('click', () => {
            ApiManager.closeModal();
        });

        // Close modal on backdrop click
        UIElements.apiModal?.addEventListener('click', (e) => {
            if (e.target === UIElements.apiModal) {
                ApiManager.closeModal();
            }
        });

        // API Form Submission
        UIElements.apiForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const apiKey = UIElements.apiKey.value.trim();
            const apiSecret = UIElements.apiSecret.value.trim();
            const useTestnet = UIElements.apiTestnet.checked;

            if (!apiKey || !apiSecret) {
                Utils.showNotification('API Key ve Secret alanları gerekli', 'error');
                return;
            }

            await ApiManager.saveApiKeys(apiKey, apiSecret, useTestnet);
        });

        // Bot Control Events
        UIElements.startBotBtn?.addEventListener('click', () => {
            BotController.startBot();
        });

        UIElements.stopBotBtn?.addEventListener('click', () => {
            BotController.stopBot();
        });

        // Refresh Events
        UIElements.refreshAccountBtn?.addEventListener('click', () => {
            DataLoader.loadAccountData();
        });

        UIElements.refreshPositionsBtn?.addEventListener('click', () => {
            DataLoader.loadPositions();
        });

        UIElements.refreshActivityBtn?.addEventListener('click', () => {
            DataLoader.loadRecentActivity();
        });

        // Settings Events
        UIElements.settingsBtn?.addEventListener('click', () => {
            Utils.showNotification('Ayarlar sayfası geliştirilmekte...', 'info');
        });

        // Logout Event
        UIElements.logoutBtn?.addEventListener('click', () => {
            if (confirm('Çıkış yapmak istediğinizden emin misiniz?')) {
                Auth.logout();
            }
        });

        // Toast Close Event
        UIElements.notificationToast?.querySelector('.toast-close')?.addEventListener('click', () => {
            UIElements.notificationToast.classList.remove('show');
        });

        // Auto-save settings
        const settingsInputs = [
            UIElements.symbolSelect,
            UIElements.timeframeSelect,
            UIElements.leverageSelect,
            UIElements.orderSize,
            UIElements.stopLoss,
            UIElements.takeProfit,
            UIElements.maxDailyTrades,
            UIElements.autoCompound
        ];

        settingsInputs.forEach(input => {
            if (input) {
                input.addEventListener('change', Utils.debounce(() => {
                    // Auto-save user settings
                    const settings = {
                        symbol: UIElements.symbolSelect?.value,
                        timeframe: UIElements.timeframeSelect?.value,
                        leverage: UIElements.leverageSelect?.value,
                        orderSize: UIElements.orderSize?.value,
                        stopLoss: UIElements.stopLoss?.value,
                        takeProfit: UIElements.takeProfit?.value,
                        maxDailyTrades: UIElements.maxDailyTrades?.value,
                        autoCompound: UIElements.autoCompound?.checked
                    };
                    
                    localStorage.setItem('userSettings', JSON.stringify(settings));
                }, 1000));
            }
        });
    }

    // Initialize Application
    async function initializeApp() {
        try {
            // Show loading screen
            UIElements.loadingScreen.style.display = 'flex';

            // Check authentication
            const isAuthenticated = await Auth.checkAuthStatus();
            if (!isAuthenticated) {
                return;
            }

            // Load user profile
            await DataLoader.loadUserProfile();

            // Check API status
            await ApiManager.checkApiStatus();

            // Load initial data
            await Promise.all([
                DataLoader.loadAccountData(),
                DataLoader.loadPositions(),
                DataLoader.loadRecentActivity()
            ]);

            // Get bot status
            await BotController.getBotStatus();

            // Load saved settings
            const savedSettings = localStorage.getItem('userSettings');
            if (savedSettings) {
                try {
                    const settings = JSON.parse(savedSettings);
                    if (settings.symbol && UIElements.symbolSelect) UIElements.symbolSelect.value = settings.symbol;
                    if (settings.timeframe && UIElements.timeframeSelect) UIElements.timeframeSelect.value = settings.timeframe;
                    if (settings.leverage && UIElements.leverageSelect) UIElements.leverageSelect.value = settings.leverage;
                    if (settings.orderSize && UIElements.orderSize) UIElements.orderSize.value = settings.orderSize;
                    if (settings.stopLoss && UIElements.stopLoss) UIElements.stopLoss.value = settings.stopLoss;
                    if (settings.takeProfit && UIElements.takeProfit) UIElements.takeProfit.value = settings.takeProfit;
                    if (settings.maxDailyTrades && UIElements.maxDailyTrades) UIElements.maxDailyTrades.value = settings.maxDailyTrades;
                    if (typeof settings.autoCompound === 'boolean' && UIElements.autoCompound) UIElements.autoCompound.checked = settings.autoCompound;
                } catch (error) {
                    console.error('Failed to load saved settings:', error);
                }
            }

            // Initialize event listeners
            initializeEventListeners();

            // Hide loading screen and show dashboard
            UIElements.loadingScreen.style.display = 'none';
            UIElements.dashboard.classList.remove('hidden');

            Utils.showNotification('Dashboard başarıyla yüklendi!', 'success');
        } catch (error) {
            console.error('App initialization failed:', error);
            UIElements.loadingScreen.innerHTML = `
                <div class="loading-content">
                    <div class="loading-logo">
                        <i class="fas fa-exclamation-triangle" style="color: var(--danger-color);"></i>
                        <span>Hata</span>
                    </div>
                    <p>Uygulama başlatılırken hata oluştu</p>
                    <button class="btn btn-primary" onclick="location.reload()">Tekrar Dene</button>
                </div>
            `;
        }
    }

    // Start the application
    initializeApp();
});
