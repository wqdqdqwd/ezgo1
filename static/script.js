document.addEventListener('DOMContentLoaded', () => {
    console.log('Script yüklendi - DOM hazır');

    /**
     * Gerekli tüm DOM elementlerini tek bir obje içinde toplar.
     */
    const UIElements = {
        authContainer: document.getElementById('auth-container'),
        appContainer: document.getElementById('app-container'),
        loginCard: document.getElementById('login-card'),
        registerCard: document.getElementById('register-card'),
        loginButton: document.getElementById('login-button'),
        loginEmailInput: document.getElementById('login-email'),
        loginPasswordInput: document.getElementById('login-password'),
        loginError: document.getElementById('login-error'),
        registerButton: document.getElementById('register-button'),
        registerEmailInput: document.getElementById('register-email'),
        registerPasswordInput: document.getElementById('register-password'),
        registerError: document.getElementById('register-error'),
        showRegisterLink: document.getElementById('show-register-link'),
        showLoginLink: document.getElementById('show-login-link'),

        // Navigation elements
        navButtons: document.querySelectorAll('.sidebar-nav .nav-item, .mobile-nav-grid .mobile-nav-item'),
        appPages: document.querySelectorAll('.main-content .page'),

        // Bot Dashboard elements
        leverageInput: document.getElementById('leverage-input'),
        leverageValue: document.getElementById('leverage-value'),
        symbolInput: document.getElementById('symbol-input'),
        tpInput: document.getElementById('tp-input'),
        slInput: document.getElementById('sl-input'),
        orderSizeInput: document.getElementById('order-size-input'),
        chartContainer: document.getElementById('analysis-chart-container'),
        startButton: document.getElementById('start-button'),
        stopButton: document.getElementById('stop-button'),
        statusMessage: document.getElementById('status-message'),
        pairCard: document.querySelector('.pair-card'),
        pairSymbol: document.querySelector('.pair-symbol'),
        pairPrice: document.querySelector('.pair-price'), 
        botStatusIndicator: document.getElementById('bot-status-indicator'),
        botStatusText: document.getElementById('bot-status-text'),

        // API Page elements
        apiKeyInput: document.getElementById('api-key-input'),
        apiSecretInput: document.getElementById('api-secret-input'),
        ipListElement: document.getElementById('ip-list'),
        saveKeysButton: document.getElementById('save-keys-button'),
        apiKeysStatus: document.getElementById('api-keys-status'),
        apiStatusIndicator: document.getElementById('api-status-indicator'),
        apiStatusText: document.getElementById('api-status-text'),

        // Settings Page elements
        userEmailSpan: document.getElementById('user-email'),
        subscriptionStatusSpan: document.getElementById('subscription-status'),
        subscriptionExpirySpan: document.getElementById('subscription-expiry'),
        registerDateSpan: document.getElementById('register-date'), 
        paymentInfoDiv: document.getElementById('payment-info'),
        paymentAddressCode: document.getElementById('payment-address'),
        logoutButton: document.getElementById('logout-button'),
        
        // New elements
        timeframeSelect: document.getElementById('timeframe-select'),
        botRequirements: document.getElementById('bot-requirements'),
        greenCandlesSpan: document.getElementById('green-candles'),
        redCandlesSpan: document.getElementById('red-candles'),
        trendDirectionSpan: document.getElementById('trend-direction'),
        totalTradesSpan: document.getElementById('total-trades'),
        winRateSpan: document.getElementById('win-rate'),
        totalPnlSpan: document.getElementById('total-pnl'),
        uptimeSpan: document.getElementById('uptime'),
    };

    // Global variables
    let statusInterval = null; 
    let priceUpdateInterval = null; 
    let currentWebSocket = null;
    let chartWebSocket = null;
    const API_BASE_URL = '';
    const WEBSOCKET_URL = 'wss://stream.binance.com:9443/ws/';

    const firebaseServices = {
        auth: null,
        database: null,
    };

    // User settings state (per user)
    let userSettings = {
        leverage: 10,
        orderSize: 20,
        tp: 4,
        sl: 2,
        symbol: 'BTCUSDT',
        timeframe: '15m'
    };

    /**
     * Sunucu ile iletişim kuran merkezi fonksiyon
     */
    async function fetchApi(endpoint, options = {}) {
        try {
            const user = firebaseServices.auth?.currentUser;
            if (!user) {
                console.error("API isteği için kullanıcı bulunamadı");
                return null;
            }

            const idToken = await user.getIdToken();
            
            const headers = {
                'Authorization': `Bearer ${idToken}`,
                'Content-Type': 'application/json',
                ...options.headers,
            };

            const response = await fetch(`${API_BASE_URL}${endpoint}`, { 
                ...options, 
                headers 
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    detail: `HTTP ${response.status}: ${response.statusText}` 
                }));
                console.error(`API Hatası (${response.status}) - ${endpoint}:`, errorData);
                throw new Error(errorData.detail || 'Sunucu hatası');
            }

            return await response.json();
        } catch (error) {
            console.error("API isteği hatası:", error);
            if (UIElements.statusMessage) {
                UIElements.statusMessage.textContent = `Hata: ${error.message}`;
                UIElements.statusMessage.classList.add('error');
            }
            return null;
        }
    }

    /**
     * WebSocket bağlantılarını güvenli kapatma
     */
    function closeAllWebSockets() {
        if (currentWebSocket) {
            try {
                currentWebSocket.close();
            } catch (e) {
                console.warn("Price WebSocket kapatma hatası:", e);
            }
            currentWebSocket = null;
        }
        
        if (chartWebSocket) {
            try {
                chartWebSocket.close();
            } catch (e) {
                console.warn("Chart WebSocket kapatma hatası:", e);
            }
            chartWebSocket = null;
        }
    }

    /**
     * Kullanıcı ayarlarını sunucudan yükle
     */
    async function loadUserSettings() {
        try {
            const profile = await fetchApi('/api/user-profile');
            if (profile && profile.settings) {
                userSettings = {
                    leverage: profile.settings.leverage || 10,
                    orderSize: profile.settings.orderSize || 20,
                    tp: profile.settings.tp || 4,
                    sl: profile.settings.sl || 2,
                    symbol: profile.settings.symbol || 'BTCUSDT',
                    timeframe: profile.settings.timeframe || '15m'
                };
                
                // UI'ı güncelle
                updateUIWithSettings();
            }
        } catch (error) {
            console.error("Kullanıcı ayarları yüklenemedi:", error);
        }
    }

    /**
     * Kullanıcı ayarlarını UI'a uygula
     */
    function updateUIWithSettings() {
        if (UIElements.leverageInput) {
            UIElements.leverageInput.value = userSettings.leverage;
        }
        if (UIElements.leverageValue) {
            UIElements.leverageValue.textContent = `${userSettings.leverage}x`;
        }
        if (UIElements.orderSizeInput) {
            UIElements.orderSizeInput.value = userSettings.orderSize;
        }
        if (UIElements.tpInput) {
            UIElements.tpInput.value = userSettings.tp;
        }
        if (UIElements.slInput) {
            UIElements.slInput.value = userSettings.sl;
        }
        if (UIElements.symbolInput) {
            UIElements.symbolInput.value = userSettings.symbol;
        }
        if (UIElements.pairSymbol) {
            UIElements.pairSymbol.textContent = userSettings.symbol;
        }
    }

    /**
     * Kullanıcı ayarlarını sunucuya kaydet
     */
    async function saveUserSettings() {
        try {
            await fetchApi('/api/save-user-settings', {
                method: 'POST',
                body: JSON.stringify({ settings: userSettings })
            });
        } catch (error) {
            console.error("Kullanıcı ayarları kaydedilemedi:", error);
        }
    }

    /**
     * UI İşlemleri
     */
    const UIActions = {
        showAuthScreen: () => {
            console.log('Auth ekranı gösteriliyor');
            if (UIElements.authContainer) UIElements.authContainer.style.display = 'flex';
            if (UIElements.appContainer) UIElements.appContainer.style.display = 'none';
            
            // Tüm interval'ları ve WebSocket'leri temizle
            if (statusInterval) {
                clearInterval(statusInterval);
                statusInterval = null;
            }
            if (priceUpdateInterval) {
                clearInterval(priceUpdateInterval);
                priceUpdateInterval = null;
            }
            closeAllWebSockets();
        },

        showAppScreen: async () => {
            console.log('App ekranı gösteriliyor');
            if (UIElements.authContainer) UIElements.authContainer.style.display = 'none';
            if (UIElements.appContainer) UIElements.appContainer.style.display = 'flex';
            
            // Kullanıcı ayarlarını yükle
            await loadUserSettings();
            
            UIActions.generateRealTimeChart();
            await UIActions.updateUserProfile();
            await UIActions.updateBotStatus();

            // Interval'ları temizle ve yeniden başlat
            if (statusInterval) clearInterval(statusInterval);
            if (priceUpdateInterval) clearInterval(priceUpdateInterval);

            statusInterval = setInterval(UIActions.updateBotStatus, 8000);
            priceUpdateInterval = setInterval(UIActions.updatePairPrice, 5000);
        },

        toggleAuthForms: (showRegister) => {
            if (UIElements.loginCard) {
                UIElements.loginCard.style.display = showRegister ? 'none' : 'block';
            }
            if (UIElements.registerCard) {
                UIElements.registerCard.style.display = showRegister ? 'block' : 'none';
            }
            
            // Hata mesajlarını temizle
            if (UIElements.loginError) {
                UIElements.loginError.style.display = 'none';
                UIElements.loginError.textContent = '';
            }
            if (UIElements.registerError) {
                UIElements.registerError.style.display = 'none';
                UIElements.registerError.textContent = '';
            }
        },

        generateRealTimeChart: () => {
            if (!UIElements.chartContainer || !userSettings.symbol) return;

            // Önceki chart WebSocket'ini kapat
            if (chartWebSocket) {
                chartWebSocket.close();
                chartWebSocket = null;
            }

            UIElements.chartContainer.innerHTML = '<div class="chart-loading"><i class="fas fa-spinner fa-spin"></i><span>Grafik yükleniyor...</span></div>';
            
            // Kline data için WebSocket bağlantısı
            const symbol = userSettings.symbol.toLowerCase();
            const timeframe = userSettings.timeframe || '15m';
            
            try {
                chartWebSocket = new WebSocket(`${WEBSOCKET_URL}${symbol}@kline_${timeframe}`);
                
                let candleData = [];
                let greenCount = 0;
                let redCount = 0;
                
                chartWebSocket.onopen = () => {
                    console.log(`Chart WebSocket bağlandı: ${symbol} ${timeframe}`);
                };
                
                chartWebSocket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.k) {
                            const kline = data.k;
                            const open = parseFloat(kline.o);
                            const close = parseFloat(kline.c);
                            const high = parseFloat(kline.h);
                            const low = parseFloat(kline.l);
                            const isGreen = close >= open;
                            
                            // Son 30 mumu sakla
                            if (candleData.length >= 30) {
                                const removed = candleData.shift();
                                if (removed.isGreen) greenCount--; else redCount--;
                            }
                            
                            candleData.push({ open, close, high, low, isGreen });
                            if (isGreen) greenCount++; else redCount++;
                            
                            // Chart ve istatistikleri güncelle
                            UIActions.updateChartDisplay(candleData);
                            UIActions.updateChartStats(greenCount, redCount, candleData);
                        }
                    } catch (e) {
                        console.error("Chart WebSocket parse hatası:", e);
                    }
                };
                
                chartWebSocket.onerror = (error) => {
                    console.error('Chart WebSocket hatası:', error);
                    UIActions.generateStaticChart(); // Fallback
                };
                
                chartWebSocket.onclose = () => {
                    console.log('Chart WebSocket bağlantısı kapandı');
                };
                
            } catch (error) {
                console.error("Chart WebSocket oluşturma hatası:", error);
                UIActions.generateStaticChart(); // Fallback
            }
        },

        updateChartDisplay: (candleData) => {
            if (!UIElements.chartContainer || !candleData.length) return;
            
            UIElements.chartContainer.innerHTML = '';
            
            // Fiyat aralığını hesapla
            const allPrices = candleData.flatMap(c => [c.high, c.low]);
            const minPrice = Math.min(...allPrices);
            const maxPrice = Math.max(...allPrices);
            const priceRange = maxPrice - minPrice;
            
            candleData.forEach(candle => {
                const bar = document.createElement('div');
                bar.classList.add('chart-bar');
                
                // Mumun yüksekliğini fiyat aralığına göre hesapla
                const bodySize = Math.abs(candle.close - candle.open);
                const bodyHeight = priceRange > 0 ? (bodySize / priceRange) * 70 + 10 : 30;
                
                bar.style.backgroundColor = candle.isGreen ? 'var(--success-color)' : 'var(--danger-color)';
                bar.style.height = `${Math.min(bodyHeight, 90)}%`;
                bar.style.flex = '1';
                bar.title = `O: ${candle.open.toFixed(4)} H: ${candle.high.toFixed(4)} L: ${candle.low.toFixed(4)} C: ${candle.close.toFixed(4)}`;
                
                UIElements.chartContainer.appendChild(bar);
            });
        },

        updateChartStats: (greenCount, redCount, candleData) => {
            if (UIElements.greenCandlesSpan) {
                UIElements.greenCandlesSpan.textContent = greenCount;
            }
            if (UIElements.redCandlesSpan) {
                UIElements.redCandlesSpan.textContent = redCount;
            }
            
            // Trend analizi
            if (UIElements.trendDirectionSpan && candleData.length >= 5) {
                const recent = candleData.slice(-5);
                const upTrend = recent.filter(c => c.isGreen).length;
                let trend = 'Nötr';
                
                if (upTrend >= 4) trend = 'Boğa';
                else if (upTrend <= 1) trend = 'Ayı';
                
                UIElements.trendDirectionSpan.textContent = trend;
                UIElements.trendDirectionSpan.className = 'stat-value ' + 
                    (trend === 'Boğa' ? 'text-success' : trend === 'Ayı' ? 'text-danger' : 'text-muted');
            }
        },

        generateStaticChart: () => {
            if (!UIElements.chartContainer) return;
            
            UIElements.chartContainer.innerHTML = '';
            for (let i = 0; i < 30; i++) {
                const bar = document.createElement('div');
                bar.classList.add('chart-bar');
                bar.style.backgroundColor = Math.random() > 0.5 ? 'var(--success-color)' : 'var(--danger-color)';
                bar.style.height = `${Math.random() * 70 + 20}%`;
                bar.style.flex = '1';
                UIElements.chartContainer.appendChild(bar);
            }
        },

        updateUserProfile: async () => {
            try {
                const profile = await fetchApi('/api/user-profile');
                if (!profile) return;

                // UI elemanlarını güvenli güncelle
                if (UIElements.userEmailSpan) {
                    UIElements.userEmailSpan.textContent = profile.email || 'N/A';
                }

                const statusMap = {
                    'active': 'Aktif',
                    'trial': 'Deneme Sürümü',
                    'expired': 'Süresi Dolmuş',
                    'inactive': 'Aktif Değil'
                };

                if (UIElements.subscriptionStatusSpan) {
                    const statusText = statusMap[profile.subscription_status] || 'Bilinmiyor';
                    const statusClass = profile.subscription_status || 'inactive';
                    UIElements.subscriptionStatusSpan.innerHTML = `<span class="status-badge ${statusClass}">${statusText}</span>`;
                }

                if (UIElements.subscriptionExpirySpan && profile.subscription_expiry) {
                    UIElements.subscriptionExpirySpan.textContent = new Date(profile.subscription_expiry).toLocaleDateString('tr-TR');
                }

                if (UIElements.registerDateSpan && profile.registration_date) {
                    UIElements.registerDateSpan.textContent = new Date(profile.registration_date).toLocaleDateString('tr-TR');
                }

                if (UIElements.paymentAddressCode && profile.payment_address) {
                    UIElements.paymentAddressCode.textContent = profile.payment_address;
                }

                if (UIElements.paymentInfoDiv) {
                    const shouldShowPayment = ['expired', 'inactive'].includes(profile.subscription_status);
                    UIElements.paymentInfoDiv.style.display = shouldShowPayment ? 'block' : 'none';
                }

                if (UIElements.ipListElement && profile.server_ips) {
                    UIElements.ipListElement.innerHTML = profile.server_ips.length 
                        ? profile.server_ips.map(ip => `<div class="ip-item">${ip}</div>`).join('')
                        : '<div class="ip-item loading">IP adresi bulunamadı.</div>';
                }

                // Bot gereksinimleri kontrolü
                UIActions.updateBotRequirements(profile);

                // Bot başlatma durumunu kontrol et
                const canStart = UIActions.validateBotSettings(profile);
                const isBotRunning = UIElements.botStatusText?.textContent === 'ONLINE';
                
                if (UIElements.startButton) {
                    UIElements.startButton.disabled = isBotRunning || !canStart;
                }

                // API durumunu güncelle
                UIActions.updateApiStatus(profile.has_api_keys);

                // Trading stats güncelle (eğer mevcut ise)
                if (profile.stats) {
                    UIActions.updateTradingStats(profile.stats);
                }
                
            } catch (error) {
                console.error("Profil güncelleme hatası:", error);
            }
        },

        updateBotRequirements: (profile) => {
            if (!UIElements.botRequirements) return;

            const hasApiKeys = profile?.has_api_keys;
            const hasValidSubscription = profile && ['active', 'trial'].includes(profile.subscription_status);
            const hasValidSettings = UIActions.validateBotSettings(profile);

            // Requirements listesini güncelle
            const reqApi = document.getElementById('req-api');
            const reqSubscription = document.getElementById('req-subscription');
            const reqSettings = document.getElementById('req-settings');

            if (reqApi) {
                reqApi.innerHTML = hasApiKeys 
                    ? '<i class="fas fa-check text-success"></i> Binance API anahtarları'
                    : '<i class="fas fa-times text-danger"></i> Binance API anahtarları';
                reqApi.classList.toggle('completed', hasApiKeys);
            }

            if (reqSubscription) {
                reqSubscription.innerHTML = hasValidSubscription 
                    ? '<i class="fas fa-check text-success"></i> Aktif abonelik'
                    : '<i class="fas fa-times text-danger"></i> Aktif abonelik';
                reqSubscription.classList.toggle('completed', hasValidSubscription);
            }

            if (reqSettings) {
                reqSettings.innerHTML = hasValidSettings 
                    ? '<i class="fas fa-check text-success"></i> Geçerli ayarlar'
                    : '<i class="fas fa-times text-danger"></i> Geçerli ayarlar';
                reqSettings.classList.toggle('completed', hasValidSettings);
            }

            // Requirements panelini göster/gizle
            const allValid = hasApiKeys && hasValidSubscription && hasValidSettings;
            UIElements.botRequirements.style.display = allValid ? 'none' : 'block';
        },

        updateTradingStats: (stats) => {
            if (UIElements.totalTradesSpan && stats.total_trades !== undefined) {
                UIElements.totalTradesSpan.textContent = stats.total_trades;
            }
            if (UIElements.winRateSpan && stats.win_rate !== undefined) {
                UIElements.winRateSpan.textContent = `${(stats.win_rate * 100).toFixed(1)}%`;
            }
            if (UIElements.totalPnlSpan && stats.total_pnl !== undefined) {
                const pnl = stats.total_pnl;
                UIElements.totalPnlSpan.textContent = `${pnl.toFixed(2)}`;
                UIElements.totalPnlSpan.classList.toggle('text-success', pnl >= 0);
                UIElements.totalPnlSpan.classList.toggle('text-danger', pnl < 0);
            }
            if (UIElements.uptimeSpan && stats.uptime_hours !== undefined) {
                UIElements.uptimeSpan.textContent = `${stats.uptime_hours.toFixed(1)}h`;
            }
        },

        validateBotSettings: (profile) => {
            const hasApiKeys = profile?.has_api_keys;
            const hasValidSubscription = profile && ['active', 'trial'].includes(profile.subscription_status);
            const isOrderSizeValid = userSettings.orderSize >= 10;
            const isLeverageValid = userSettings.leverage >= 1 && userSettings.leverage <= 125;
            const areTPSLValid = userSettings.tp > 0 && userSettings.sl > 0 && userSettings.tp > userSettings.sl;

            return hasApiKeys && hasValidSubscription && isOrderSizeValid && isLeverageValid && areTPSLValid;
        },

        updateApiStatus: (hasApiKeys) => {
            if (UIElements.apiStatusIndicator) {
                UIElements.apiStatusIndicator.classList.toggle('active', hasApiKeys);
                UIElements.apiStatusIndicator.classList.toggle('inactive', !hasApiKeys);
            }
            if (UIElements.apiStatusText) {
                UIElements.apiStatusText.textContent = hasApiKeys ? 'CONFIGURED' : 'NOT CONFIGURED';
                UIElements.apiStatusText.classList.toggle('text-success', hasApiKeys);
                UIElements.apiStatusText.classList.toggle('text-muted', !hasApiKeys);
            }
        },

        updateBotStatus: async () => {
            try {
                const data = await fetchApi('/api/status');
                if (!data) {
                    UIActions.setBotStatus(false, 'ERROR', 'Bot durumu alınamadı');
                    return;
                }

                const isRunning = data.is_running;
                const statusText = isRunning ? 'ONLINE' : 'OFFLINE';
                
                UIActions.setBotStatus(isRunning, statusText, data.status_message);
                
                if (UIElements.stopButton) {
                    UIElements.stopButton.disabled = !isRunning;
                }
                
                if (!isRunning) {
                    await UIActions.updateUserProfile();
                }

                // Input'ları bot çalışırken devre dışı bırak
                const inputs = [UIElements.leverageInput, UIElements.orderSizeInput, UIElements.tpInput, UIElements.slInput];
                inputs.forEach(input => {
                    if (input) input.disabled = isRunning;
                });
                
            } catch (error) {
                console.error("Bot status güncelleme hatası:", error);
                UIActions.setBotStatus(false, 'ERROR', 'Bağlantı hatası');
            }
        },

        setBotStatus: (isRunning, statusText, message) => {
            if (UIElements.botStatusIndicator) {
                UIElements.botStatusIndicator.classList.toggle('active', isRunning);
                UIElements.botStatusIndicator.classList.toggle('inactive', !isRunning);
            }
            if (UIElements.botStatusText) {
                UIElements.botStatusText.textContent = statusText;
                UIElements.botStatusText.classList.toggle('text-success', isRunning);
                UIElements.botStatusText.classList.toggle('text-muted', !isRunning);
                UIElements.botStatusText.classList.toggle('text-danger', statusText === 'ERROR');
            }
            if (UIElements.statusMessage && message) {
                UIElements.statusMessage.textContent = message;
            }
        },

        updatePairPrice: () => {
            if (!UIElements.pairPrice || !userSettings.symbol) return;

            // Mevcut fiyat WebSocket'ini kapat
            if (currentWebSocket) {
                currentWebSocket.close();
                currentWebSocket = null;
            }

            try {
                const symbol = userSettings.symbol.toLowerCase();
                currentWebSocket = new WebSocket(`${WEBSOCKET_URL}${symbol}@ticker`);

                currentWebSocket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data?.c && UIElements.pairPrice) {
                            const price = parseFloat(data.c);
                            UIElements.pairPrice.textContent = `$${price.toLocaleString('en-US', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 8
                            })}`;
                        }
                    } catch (e) {
                        console.error("Price WebSocket parse hatası:", e);
                    }
                };

                currentWebSocket.onerror = (error) => {
                    console.error('Price WebSocket hatası:', error);
                    if (UIElements.pairPrice) {
                        UIElements.pairPrice.textContent = 'Fiyat Yok';
                    }
                };

            } catch (error) {
                console.error("Price WebSocket oluşturma hatası:", error);
                if (UIElements.pairPrice) {
                    UIElements.pairPrice.textContent = 'Bağlantı Hatası';
                }
            }
        },

        setLoadingState: (isLoading, button) => {
            if (!button) return;
            
            button.disabled = isLoading;
            if (isLoading) {
                button.dataset.originalText = button.innerHTML;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yükleniyor...';
            } else if (button.dataset.originalText) {
                button.innerHTML = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        },

        showError: (element, message) => {
            if (!element) return;
            element.textContent = message;
            element.style.display = 'block';
            element.classList.add('error');
            element.classList.remove('success');
        },

        showSuccess: (element, message) => {
            if (!element) return;
            element.textContent = message;
            element.style.display = 'block';
            element.classList.add('success');
            element.classList.remove('error');
        }
    };

    /**
     * Event Listeners
     */
    function setupEventListeners() {
        console.log('Event listener\'lar kuruluyor');

        // Navigation
        UIElements.navButtons.forEach(button => {
            button.addEventListener('click', () => {
                const pageId = button.dataset.page;
                UIElements.navButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                UIElements.appPages.forEach(page => {
                    page.classList.toggle('active', page.id === pageId);
                });
            });
        });

        // Timeframe select
        if (UIElements.timeframeSelect) {
            UIElements.timeframeSelect.addEventListener('change', (e) => {
                userSettings.timeframe = e.target.value;
                saveUserSettings();
                UIActions.generateRealTimeChart(); // Grafik'i yeni timeframe ile güncelle
            });
        }

        // Settings inputs - kullanıcı başına ayarlar
        if (UIElements.leverageInput) {
            UIElements.leverageInput.addEventListener('input', (e) => {
                const value = parseInt(e.target.value, 10);
                userSettings.leverage = value;
                if (UIElements.leverageValue) {
                    UIElements.leverageValue.textContent = `${value}x`;
                }
                saveUserSettings();
                UIActions.updateUserProfile();
            });
        }

        if (UIElements.orderSizeInput) {
            UIElements.orderSizeInput.addEventListener('input', (e) => {
                userSettings.orderSize = parseFloat(e.target.value) || 20;
                saveUserSettings();
                UIActions.updateUserProfile();
            });
        }

        if (UIElements.tpInput) {
            UIElements.tpInput.addEventListener('input', (e) => {
                userSettings.tp = parseFloat(e.target.value) || 4;
                saveUserSettings();
                UIActions.updateUserProfile();
            });
        }

        if (UIElements.slInput) {
            UIElements.slInput.addEventListener('input', (e) => {
                userSettings.sl = parseFloat(e.target.value) || 2;
                saveUserSettings();
                UIActions.updateUserProfile();
            });
        }

        // Auth form toggles
        if (UIElements.showRegisterLink) {
            UIElements.showRegisterLink.addEventListener('click', (e) => {
                e.preventDefault();
                UIActions.toggleAuthForms(true);
            });
        }

        if (UIElements.showLoginLink) {
            UIElements.showLoginLink.addEventListener('click', (e) => {
                e.preventDefault();
                UIActions.toggleAuthForms(false);
            });
        }

        // Login
        if (UIElements.loginButton) {
            UIElements.loginButton.addEventListener('click', async () => {
                const email = UIElements.loginEmailInput?.value?.trim();
                const password = UIElements.loginPasswordInput?.value?.trim();

                if (!email || !password) {
                    UIActions.showError(UIElements.loginError, "E-posta ve şifre gerekli.");
                    return;
                }

                UIActions.setLoadingState(true, UIElements.loginButton);
                try {
                    await firebaseServices.auth.signInWithEmailAndPassword(email, password);
                } catch (error) {
                    let errorMessage = "Giriş hatası.";
                    switch (error.code) {
                        case 'auth/user-not-found':
                        case 'auth/wrong-password':
                        case 'auth/invalid-credential':
                            errorMessage = "Hatalı e-posta veya şifre.";
                            break;
                        case 'auth/invalid-email':
                            errorMessage = "Geçersiz e-posta adresi.";
                            break;
                        case 'auth/too-many-requests':
                            errorMessage = "Çok fazla deneme. Lütfen bekleyin.";
                            break;
                    }
                    UIActions.showError(UIElements.loginError, errorMessage);
                } finally {
                    UIActions.setLoadingState(false, UIElements.loginButton);
                }
            });
        }

        // Register
        if (UIElements.registerButton) {
            UIElements.registerButton.addEventListener('click', async () => {
                const email = UIElements.registerEmailInput?.value?.trim();
                const password = UIElements.registerPasswordInput?.value?.trim();

                if (!email || !password) {
                    UIActions.showError(UIElements.registerError, "E-posta ve şifre gerekli.");
                    return;
                }

                if (password.length < 6) {
                    UIActions.showError(UIElements.registerError, "Şifre en az 6 karakter olmalı.");
                    return;
                }

                UIActions.setLoadingState(true, UIElements.registerButton);
                try {
                    await firebaseServices.auth.createUserWithEmailAndPassword(email, password);
                } catch (error) {
                    let errorMessage = "Kayıt hatası.";
                    switch (error.code) {
                        case 'auth/email-already-in-use':
                            errorMessage = "Bu e-posta zaten kullanılıyor.";
                            break;
                        case 'auth/weak-password':
                            errorMessage = "Şifre çok zayıf.";
                            break;
                        case 'auth/invalid-email':
                            errorMessage = "Geçersiz e-posta.";
                            break;
                    }
                    UIActions.showError(UIElements.registerError, errorMessage);
                } finally {
                    UIActions.setLoadingState(false, UIElements.registerButton);
                }
            });
        }

        // Logout
        if (UIElements.logoutButton) {
            UIElements.logoutButton.addEventListener('click', async () => {
                try {
                    await firebaseServices.auth.signOut();
                } catch (error) {
                    console.error("Çıkış hatası:", error);
                    alert("Çıkış yapılamadı.");
                }
            });
        }

        // API Keys
        if (UIElements.saveKeysButton) {
            UIElements.saveKeysButton.addEventListener('click', async () => {
                const apiKey = UIElements.apiKeyInput?.value?.trim();
                const apiSecret = UIElements.apiSecretInput?.value?.trim();

                if (!apiKey || !apiSecret) {
                    UIActions.showError(UIElements.apiKeysStatus, "API Key ve Secret gerekli.");
                    return;
                }

                UIActions.setLoadingState(true, UIElements.saveKeysButton);
                const result = await fetchApi('/api/save-keys', {
                    method: 'POST',
                    body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret })
                });

                if (result?.success) {
                    UIActions.showSuccess(UIElements.apiKeysStatus, "API anahtarları kaydedildi!");
                    if (UIElements.apiKeyInput) UIElements.apiKeyInput.value = '';
                    if (UIElements.apiSecretInput) UIElements.apiSecretInput.value = '';
                    await UIActions.updateUserProfile();
                } else {
                    UIActions.showError(UIElements.apiKeysStatus, result?.detail || "Kayıt başarısız.");
                }
                UIActions.setLoadingState(false, UIElements.saveKeysButton);
            });
        }

        // Bot Start
        if (UIElements.startButton) {
            UIElements.startButton.addEventListener('click', async () => {
                const botSettings = {
                    symbol: userSettings.symbol,
                    leverage: userSettings.leverage,
                    order_size: userSettings.orderSize,
                    stop_loss: userSettings.sl,
                    take_profit: userSettings.tp,
                    timeframe: userSettings.timeframe
                };

                // Validation
                if (botSettings.leverage < 1 || botSettings.leverage > 125) {
                    alert('Kaldıraç 1-125 arasında olmalı.');
                    return;
                }
                if (botSettings.order_size < 10) {
                    alert('İşlem büyüklüğü minimum 10 USDT.');
                    return;
                }
                if (botSettings.take_profit <= botSettings.stop_loss) {
                    alert('Take Profit, Stop Loss\'tan büyük olmalı.');
                    return;
                }

                UIActions.setLoadingState(true, UIElements.startButton);
                const result = await fetchApi('/api/start', {
                    method: 'POST',
                    body: JSON.stringify(botSettings)
                });

                if (result?.success) {
                    if (UIElements.statusMessage) {
                        UIElements.statusMessage.textContent = "Bot başlatıldı!";
                        UIElements.statusMessage.classList.add('success');
                        UIElements.statusMessage.classList.remove('error');
                    }
                } else {
                    if (UIElements.statusMessage) {
                        UIElements.statusMessage.textContent = result?.detail || "Bot başlatılamadı.";
                        UIElements.statusMessage.classList.add('error');
                        UIElements.statusMessage.classList.remove('success');
                    }
                }
                
                await UIActions.updateBotStatus();
                UIActions.setLoadingState(false, UIElements.startButton);
            });
        }

        // Bot Stop
        if (UIElements.stopButton) {
            UIElements.stopButton.addEventListener('click', async () => {
                UIActions.setLoadingState(true, UIElements.stopButton);
                const result = await fetchApi('/api/stop', { method: 'POST' });

                if (result?.success) {
                    if (UIElements.statusMessage) {
                        UIElements.statusMessage.textContent = "Bot durduruldu!";
                        UIElements.statusMessage.classList.add('success');
                        UIElements.statusMessage.classList.remove('error');
                    }
                } else {
                    if (UIElements.statusMessage) {
                        UIElements.statusMessage.textContent = result?.detail || "Bot durdurulamadı.";
                        UIElements.statusMessage.classList.add('error');
                        UIElements.statusMessage.classList.remove('success');
                    }
                }
                
                await UIActions.updateBotStatus();
                UIActions.setLoadingState(false, UIElements.stopButton);
            });
        }

        // Pair change
        if (UIElements.pairCard) {
            UIElements.pairCard.addEventListener('click', () => {
                if (UIElements.leverageInput?.disabled) {
                    alert("Bot çalışırken parite değiştirilemez.");
                    return;
                }
                
                const newSymbol = prompt('Yeni parite (örn: ETHUSDT):', userSettings.symbol);
                if (newSymbol?.trim()) {
                    userSettings.symbol = newSymbol.trim().toUpperCase();
                    if (UIElements.symbolInput) UIElements.symbolInput.value = userSettings.symbol;
                    if (UIElements.pairSymbol) UIElements.pairSymbol.textContent = userSettings.symbol;
                    saveUserSettings();
                    UIActions.updatePairPrice();
                    UIActions.generateRealTimeChart();
                }
            });
        }

        // Enter key support
        const loginInputs = [UIElements.loginEmailInput, UIElements.loginPasswordInput].filter(Boolean);
        loginInputs.forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') UIElements.loginButton?.click();
            });
        });

        const registerInputs = [UIElements.registerEmailInput, UIElements.registerPasswordInput].filter(Boolean);
        registerInputs.forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') UIElements.registerButton?.click();
            });
        });
    }

    /**
     * Copy to clipboard fonksiyonu
     */
    window.copyToClipboard = (elementId) => {
        const element = document.getElementById(elementId);
        if (!element) return;

        const textToCopy = element.textContent;

        if (navigator.clipboard?.writeText) {
            navigator.clipboard.writeText(textToCopy).then(() => {
                showCopySuccess(element);
            }).catch(() => {
                fallbackCopy(element, textToCopy);
            });
        } else {
            fallbackCopy(element, textToCopy);
        }
    };

    function showCopySuccess(element) {
        const originalText = element.textContent;
        element.textContent = 'Kopyalandı!';
        setTimeout(() => {
            element.textContent = originalText;
        }, 1500);
    }

    function fallbackCopy(element, textToCopy) {
        const tempTextArea = document.createElement('textarea');
        tempTextArea.value = textToCopy;
        tempTextArea.style.position = 'fixed';
        tempTextArea.style.left = '-9999px';
        document.body.appendChild(tempTextArea);
        tempTextArea.select();
        
        try {
            document.execCommand('copy');
            showCopySuccess(element);
        } catch (err) {
            console.error('Copy hatası:', err);
            alert('Kopyalama başarısız. Manuel olarak kopyalayın.');
        } finally {
            document.body.removeChild(tempTextArea);
        }
    }

    /**
     * Cleanup function
     */
    window.addEventListener('beforeunload', () => {
        if (statusInterval) clearInterval(statusInterval);
        if (priceUpdateInterval) clearInterval(priceUpdateInterval);
        closeAllWebSockets();
    });

    /**
     * Ana başlatma fonksiyonu
     */
    async function initializeApp() {
        console.log('Uygulama başlatılıyor...');
        
        try {
            // Firebase config al
            const response = await fetch(`${API_BASE_URL}/api/firebase-config`);
            if (!response.ok) {
                throw new Error(`Firebase config alınamadı: ${response.status}`);
            }

            const firebaseConfig = await response.json();
            if (!firebaseConfig?.apiKey) {
                throw new Error('Firebase config eksik.');
            }

            // Firebase başlat
            firebase.initializeApp(firebaseConfig);
            firebaseServices.auth = firebase.auth();
            firebaseServices.database = firebase.database();

            console.log('Firebase başlatıldı');

            // Auth state listener
            firebaseServices.auth.onAuthStateChanged(async (user) => {
                console.log('Auth state değişti:', user ? 'giriş yapıldı' : 'çıkış yapıldı');
                if (user) {
                    await UIActions.showAppScreen();
                } else {
                    UIActions.showAuthScreen();
                }
            });

            // Event listeners kur
            setupEventListeners();
            
            console.log('Uygulama başarıyla başlatıldı');

        } catch (error) {
            console.error("Uygulama başlatma hatası:", error);
            
            // Hata sayfası göster
            document.body.innerHTML = `
                <div style="
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    padding: 2rem;
                    background: linear-gradient(135deg, #1e3a8a, #3b82f6);
                    font-family: 'Inter', sans-serif;
                ">
                    <div style="
                        background: white;
                        padding: 2rem;
                        border-radius: 0.75rem;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
                        max-width: 500px;
                        width: 100%;
                        text-align: center;
                    ">
                        <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: #ef4444; margin-bottom: 1rem;"></i>
                        <h1 style="font-size: 1.5rem; margin-bottom: 1rem; color: #111827;">Bağlantı Hatası</h1>
                        <p style="color: #6b7280; margin-bottom: 1.5rem; line-height: 1.6;">
                            Sistem başlatılamadı. Lütfen internet bağlantınızı kontrol edin ve sayfayı yenileyin.
                        </p>
                        <button onclick="location.reload()" style="
                            background: #3b82f6;
                            color: white;
                            border: none;
                            padding: 0.75rem 1.5rem;
                            border-radius: 0.5rem;
                            font-weight: 600;
                            cursor: pointer;
                            font-size: 1rem;
                        ">
                            <i class="fas fa-redo"></i> Sayfayı Yenile
                        </button>
                        <details style="margin-top: 1rem; text-align: left;">
                            <summary style="cursor: pointer; color: #3b82f6;">Teknik Detay</summary>
                            <code style="font-size: 0.8rem; color: #374151; margin-top: 0.5rem; display: block;">${error.message}</code>
                        </details>
                    </div>
                </div>
            `;
        }
    }

    // Uygulamayı başlat
    initializeApp();
});
