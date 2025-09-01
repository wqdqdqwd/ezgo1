document.addEventListener('DOMContentLoaded', () => {

    /**
     * Gerekli tüm DOM elementlerini tek bir obje içinde toplar.
     * Bu, kod içinde elementlere erişimi kolaylaştırır ve düzeni artırır.
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
    };

    let statusInterval = null; 
    let priceUpdateInterval = null; 
    let currentWebSocket = null; // WebSocket referansını takip etmek için
    const API_BASE_URL = ''; 
    const WEBSOCKET_URL = 'wss://stream.binance.com:9443/ws/'; 

    const firebaseServices = {
        auth: null,
        database: null,
    };

    /**
     * Sunucu ile iletişim kuran merkezi fonksiyon.
     * Firebase'den alınan kimlik doğrulama jetonunu her isteğe ekler.
     */
    async function fetchApi(endpoint, options = {}) {
        const user = firebaseServices.auth.currentUser;
        if (!user) {
            console.error("API isteği için kullanıcı bulunamadı. Kullanıcı giriş yapmamış.");
            return null;
        }

        try {
            const idToken = await user.getIdToken(); 
            
            const headers = {
                'Authorization': `Bearer ${idToken}`,
                'Content-Type': 'application/json',
                ...options.headers,
            };

            const response = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, headers });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                console.error(`API Hatası (${response.status}) - ${endpoint}:`, errorData.detail || response.statusText);
                if (UIElements.statusMessage) {
                    UIElements.statusMessage.textContent = `Hata: ${errorData.detail || 'Bilinmeyen bir hata oluştu.'}`;
                }
                return null;
            }

            return response.json();
        } catch (error) {
            console.error("Ağ veya fetch hatası:", error);
            if (UIElements.statusMessage) {
                UIElements.statusMessage.textContent = "Ağ bağlantısı hatası oluştu. Lütfen internet bağlantınızı kontrol edin.";
            }
            return null;
        }
    }

    /**
     * WebSocket bağlantısını güvenli bir şekilde kapatır
     */
    function closeWebSocket() {
        if (currentWebSocket) {
            try {
                currentWebSocket.close();
            } catch (e) {
                console.warn("WebSocket kapatılırken hata:", e);
            }
            currentWebSocket = null;
        }
    }

    /**
     * Kullanıcı arayüzünü (UI) güncelleyen fonksiyonlar.
     */
    const UIActions = {
        /**
         * Kimlik doğrulama ekranını gösterir ve uygulama ekranını gizler.
         */
        showAuthScreen: () => {
            UIElements.authContainer.style.display = 'flex';
            UIElements.appContainer.style.display = 'none';
            
            // Tüm interval'ları ve WebSocket bağlantılarını temizle
            if (statusInterval) {
                clearInterval(statusInterval);
                statusInterval = null;
            }
            if (priceUpdateInterval) {
                clearInterval(priceUpdateInterval);
                priceUpdateInterval = null;
            }
            closeWebSocket();
        },

        /**
         * Uygulama ekranını gösterir, kimlik doğrulama ekranını gizler ve gerekli güncellemeleri başlatır.
         */
        showAppScreen: async () => {
            UIElements.authContainer.style.display = 'none';
            UIElements.appContainer.style.display = 'flex';
            
            UIActions.generateChartBars(); 
            
            await UIActions.updateUserProfile();
            await UIActions.updateApiKeysStatus();
            await UIActions.updateBotStatus();

            // Önceki interval'ları temizle
            if (statusInterval) clearInterval(statusInterval);
            if (priceUpdateInterval) clearInterval(priceUpdateInterval);

            // Yeni interval'ları başlat
            statusInterval = setInterval(UIActions.updateBotStatus, 8000); 
            priceUpdateInterval = setInterval(UIActions.updatePairPrice, 5000); 
        },

        /**
         * Giriş ve kayıt formları arasında geçiş yapar.
         * @param {boolean} showRegister - True ise kayıt formunu, false ise giriş formunu gösterir.
         */
        toggleAuthForms: (showRegister) => {
            UIElements.loginCard.style.display = showRegister ? 'none' : 'block';
            UIElements.registerCard.style.display = showRegister ? 'block' : 'none';
            
            // Hata mesajlarını temizle
            UIElements.loginError.style.display = 'none';
            UIElements.registerError.style.display = 'none';
            UIElements.loginError.textContent = '';
            UIElements.registerError.textContent = '';
        },
        
        /**
         * Analiz grafiği için rastgele çubuklar oluşturur.
         */
        generateChartBars: () => {
            if (!UIElements.chartContainer) return;
            
            UIElements.chartContainer.innerHTML = '';
            const numberOfBars = 30; 
            for (let i = 0; i < numberOfBars; i++) {
                const bar = document.createElement('div');
                bar.classList.add('chart-bar');
                if (Math.random() > 0.45) { 
                    bar.classList.add('up'); 
                    bar.style.backgroundColor = 'var(--success-color)';
                } else {
                    bar.classList.add('down'); 
                    bar.style.backgroundColor = 'var(--danger-color)';
                }
                bar.style.height = `${Math.random() * 70 + 20}%`; 
                bar.style.flexGrow = 1; 
                UIElements.chartContainer.appendChild(bar);
            }
        },

        /**
         * Kullanıcı profil bilgilerini API'den alır ve UI'ı günceller.
         */
        updateUserProfile: async () => {
            const profile = await fetchApi('/api/user-profile');
            if (!profile) return;

            // UI elemanlarının varlığını kontrol et
            if (UIElements.userEmailSpan) {
                UIElements.userEmailSpan.textContent = profile.email || 'N/A';
            }

            const statusMap = {
                'active': 'Aktif', 
                'trial': 'Deneme Sürümü', 
                'expired': 'Süresi Dolmuş',
                'inactive': 'Aktif Değil'
            };
            const subscriptionStatusText = statusMap[profile.subscription_status] || 'Bilinmiyor';
            
            if (UIElements.subscriptionStatusSpan) {
                UIElements.subscriptionStatusSpan.innerHTML = `<span class="status-badge ${profile.subscription_status || 'inactive'}">${subscriptionStatusText}</span>`;
            }
            
            if (UIElements.subscriptionExpirySpan) {
                UIElements.subscriptionExpirySpan.textContent = profile.subscription_expiry 
                    ? new Date(profile.subscription_expiry).toLocaleDateString('tr-TR')
                    : 'N/A';
            }
            
            if (UIElements.registerDateSpan) {
                UIElements.registerDateSpan.textContent = profile.registration_date
                    ? new Date(profile.registration_date).toLocaleDateString('tr-TR')
                    : 'N/A';
            }

            if (UIElements.paymentAddressCode) {
                UIElements.paymentAddressCode.textContent = profile.payment_address || 'Yükleniyor...';
            }
            
            if (UIElements.paymentInfoDiv) {
                UIElements.paymentInfoDiv.style.display = (profile.subscription_status === 'expired' || !profile.subscription_status) ? 'block' : 'none';
            }

            if (UIElements.ipListElement && profile.server_ips) {
                UIElements.ipListElement.innerHTML = profile.server_ips?.length
                    ? profile.server_ips.map(ip => `<div class="ip-item">${ip}</div>`).join('')
                    : '<div class="ip-item loading">Sunucu IP adresi bulunamadı.</div>';
            }

            // Bot başlatma koşullarını kontrol et
            const canStartBot = UIActions.validateBotSettings(profile);
            
            if (UIElements.startButton) {
                // Bot çalışıyor mu kontrolü - eğer bot çalışıyorsa buton her zaman disabled olmalı
                const isBotRunning = UIElements.botStatusText && UIElements.botStatusText.textContent === 'ONLINE';
                UIElements.startButton.disabled = isBotRunning || !canStartBot;
            }

            // API durumunu güncelle
            UIActions.updateApiStatus(profile.has_api_keys);
        },

        /**
         * Bot ayarlarının geçerliliğini kontrol eder
         */
        validateBotSettings: (profile) => {
            if (!UIElements.orderSizeInput || !UIElements.leverageInput) return false;
            
            const currentOrderSize = parseFloat(UIElements.orderSizeInput.value) || 0;
            const currentLeverage = parseInt(UIElements.leverageInput.value, 10) || 0;
            const currentTP = parseFloat(UIElements.tpInput?.value) || 0;
            const currentSL = parseFloat(UIElements.slInput?.value) || 0;

            const hasApiKeys = profile && profile.has_api_keys;
            const hasValidSubscription = profile && ['active', 'trial'].includes(profile.subscription_status);
            const isOrderSizeValid = currentOrderSize >= 10;
            const isLeverageValid = currentLeverage >= 1 && currentLeverage <= 125;
            const areTPSLValid = currentTP > 0 && currentSL > 0 && currentTP > currentSL;

            return hasApiKeys && hasValidSubscription && isOrderSizeValid && isLeverageValid && areTPSLValid;
        },

        /**
         * API durumunu günceller
         */
        updateApiStatus: (hasApiKeys) => {
            if (UIElements.apiStatusIndicator && UIElements.apiStatusText) {
                UIElements.apiStatusIndicator.classList.toggle('active', hasApiKeys);
                UIElements.apiStatusIndicator.classList.toggle('inactive', !hasApiKeys);
                UIElements.apiStatusText.textContent = hasApiKeys ? 'CONFIGURED' : 'NOT CONFIGURED';
                UIElements.apiStatusText.classList.toggle('text-success', hasApiKeys);
                UIElements.apiStatusText.classList.toggle('text-muted', !hasApiKeys);
            }
        },

        /**
         * Botun mevcut durumunu API'den alır ve UI'ı günceller.
         */
        updateBotStatus: async () => {
            const data = await fetchApi('/api/status');
            if (!data) {
                if (UIElements.botStatusIndicator) {
                    UIElements.botStatusIndicator.classList.remove('active');
                    UIElements.botStatusIndicator.classList.add('inactive');
                }
                if (UIElements.botStatusText) {
                    UIElements.botStatusText.textContent = 'ERROR';
                    UIElements.botStatusText.classList.remove('text-success');
                    UIElements.botStatusText.classList.add('text-danger');
                }
                if (UIElements.startButton) UIElements.startButton.disabled = true; 
                if (UIElements.stopButton) UIElements.stopButton.disabled = true;
                if (UIElements.statusMessage) {
                    UIElements.statusMessage.textContent = "Bot durumu alınamadı. Lütfen tekrar deneyin.";
                }
                return;
            }

            if (UIElements.statusMessage) {
                UIElements.statusMessage.textContent = data.status_message;
            }
            
            const isRunning = data.is_running;

            if (UIElements.botStatusIndicator) {
                UIElements.botStatusIndicator.classList.toggle('active', isRunning);
                UIElements.botStatusIndicator.classList.toggle('inactive', !isRunning);
            }
            
            if (UIElements.botStatusText) {
                UIElements.botStatusText.textContent = isRunning ? 'ONLINE' : 'OFFLINE';
                UIElements.botStatusText.classList.toggle('text-success', isRunning);
                UIElements.botStatusText.classList.toggle('text-muted', !isRunning);
            }

            if (UIElements.stopButton) {
                UIElements.stopButton.disabled = !isRunning;
            }
            
            if (isRunning) {
                if (UIElements.startButton) UIElements.startButton.disabled = true;
            } else {
                await UIActions.updateUserProfile(); 
            }

            // Input'ları bot çalışırken devre dışı bırak
            const inputsToToggle = [
                UIElements.symbolInput, UIElements.leverageInput, UIElements.tpInput, 
                UIElements.slInput, UIElements.orderSizeInput
            ].filter(el => el); // Null/undefined olanları filtrele
            
            inputsToToggle.forEach(el => {
                if (el) el.disabled = isRunning;
            });
        },

        /**
         * Seçilen paritenin anlık fiyatını Binance WebSocket API'sından alır ve UI'ı günceller.
         */
        updatePairPrice: () => {
            if (!UIElements.symbolInput || !UIElements.pairPrice) return;

            // Mevcut WebSocket bağlantısını kapat
            closeWebSocket();

            const symbol = UIElements.symbolInput.value.toLowerCase();
            if (!symbol) return;

            try {
                currentWebSocket = new WebSocket(`${WEBSOCKET_URL}${symbol}@ticker`);

                currentWebSocket.onopen = () => {
                    console.log(`WebSocket connected for ${symbol}`);
                };

                currentWebSocket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data && data.c && UIElements.pairPrice) {
                            const price = parseFloat(data.c).toFixed(2);
                            UIElements.pairPrice.textContent = `$${price}`;
                        }
                    } catch (e) {
                        console.error("WebSocket mesaj parse hatası:", e);
                    }
                };

                currentWebSocket.onerror = (error) => {
                    console.error('WebSocket Error:', error);
                    if (UIElements.pairPrice) {
                        UIElements.pairPrice.textContent = 'Fiyat Yok';
                    }
                };

                currentWebSocket.onclose = () => {
                    console.log(`WebSocket disconnected for ${symbol}`);
                };

            } catch (error) {
                console.error("WebSocket oluşturma hatası:", error);
                if (UIElements.pairPrice) {
                    UIElements.pairPrice.textContent = 'Bağlantı Hatası';
                }
            }
        },

        /**
         * API anahtar durumunu günceller.
         */
        updateApiKeysStatus: async () => {
            const profile = await fetchApi('/api/user-profile');
            if (profile) {
                UIActions.updateApiStatus(profile.has_api_keys);
            }
        },

        /**
         * Bir butonun yükleme durumunu ayarlar.
         * @param {boolean} isLoading - Yükleme durumu (true/false).
         * @param {HTMLElement} button - Etkilenecek buton elementi.
         */
        setLoadingState: (isLoading, button) => {
            if (button) {
                button.disabled = isLoading;
                if (isLoading) {
                    button.dataset.originalText = button.innerHTML;
                    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yükleniyor...';
                } else if (button.dataset.originalText) {
                    button.innerHTML = button.dataset.originalText;
                    delete button.dataset.originalText;
                }
            }
            if (UIElements.statusMessage && isLoading) {
                UIElements.statusMessage.textContent = "İşlem yapılıyor, lütfen bekleyin...";
            }
        },

        /**
         * Hata mesajını gösterir
         */
        showError: (element, message) => {
            if (element) {
                element.textContent = message;
                element.style.display = 'block';
                element.classList.add('error');
                element.classList.remove('success');
            }
        },

        /**
         * Başarı mesajını gösterir
         */
        showSuccess: (element, message) => {
            if (element) {
                element.textContent = message;
                element.style.display = 'block';
                element.classList.add('success');
                element.classList.remove('error');
            }
        }
    };

    /**
     * Kullanıcı eylemlerine yanıt veren olay dinleyicileri (event listeners).
     */
    function setupEventListeners() {
        // Navigation clicks
        UIElements.navButtons.forEach(button => {
            button.addEventListener('click', () => {
                const pageId = button.dataset.page;
                UIElements.navButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                UIElements.appPages.forEach(page => page.classList.toggle('active', page.id === pageId));
            });
        });

        // Leverage slider input
        if (UIElements.leverageInput && UIElements.leverageValue) {
            UIElements.leverageInput.addEventListener('input', (e) => {
                UIElements.leverageValue.textContent = `${e.target.value}x`;
                UIActions.updateUserProfile(); // Ayar değişikliğinde butonu güncelle
            });
        }

        // Order size input
        if (UIElements.orderSizeInput) {
            UIElements.orderSizeInput.addEventListener('input', () => {
                UIActions.updateUserProfile(); // Ayar değişikliğinde butonu güncelle
            });
        }

        // TP/SL inputs
        if (UIElements.tpInput) {
            UIElements.tpInput.addEventListener('input', UIActions.updateUserProfile);
        }
        if (UIElements.slInput) {
            UIElements.slInput.addEventListener('input', UIActions.updateUserProfile);
        }

        // Toggle auth forms
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

        // Login button click
        if (UIElements.loginButton) {
            UIElements.loginButton.addEventListener('click', async () => {
                UIElements.loginError.style.display = 'none';
                const email = UIElements.loginEmailInput?.value?.trim();
                const password = UIElements.loginPasswordInput?.value?.trim();
                
                if (!email || !password) {
                    UIActions.showError(UIElements.loginError, "Lütfen e-posta ve şifrenizi girin.");
                    return;
                }
                
                UIActions.setLoadingState(true, UIElements.loginButton);
                try {
                    await firebaseServices.auth.signInWithEmailAndPassword(email, password);
                } catch (error) {
                    let errorMessage = "Giriş yaparken bir hata oluştu.";
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
                            errorMessage = "Çok fazla başarısız deneme. Lütfen daha sonra tekrar deneyin.";
                            break;
                    }
                    UIActions.showError(UIElements.loginError, errorMessage);
                } finally {
                    UIActions.setLoadingState(false, UIElements.loginButton);
                }
            });
        }

        // Register button click
        if (UIElements.registerButton) {
            UIElements.registerButton.addEventListener('click', async () => {
                UIElements.registerError.style.display = 'none';
                const email = UIElements.registerEmailInput?.value?.trim();
                const password = UIElements.registerPasswordInput?.value?.trim();
                
                if (!email || !password) {
                    UIActions.showError(UIElements.registerError, "Lütfen e-posta ve şifrenizi girin.");
                    return;
                }
                
                if (password.length < 6) {
                    UIActions.showError(UIElements.registerError, "Şifre en az 6 karakter olmalıdır.");
                    return;
                }
                
                UIActions.setLoadingState(true, UIElements.registerButton);
                try {
                    await firebaseServices.auth.createUserWithEmailAndPassword(email, password);
                } catch (error) {
                    let errorMessage = "Hesap oluşturulurken bir hata oluştu.";
                    switch (error.code) {
                        case 'auth/weak-password': 
                            errorMessage = 'Şifre en az 6 karakter olmalıdır.'; 
                            break;
                        case 'auth/email-already-in-use': 
                            errorMessage = 'Bu e-posta adresi zaten kullanılıyor.'; 
                            break;
                        case 'auth/invalid-email':
                            errorMessage = "Geçersiz e-posta adresi.";
                            break;
                    }
                    UIActions.showError(UIElements.registerError, errorMessage);
                } finally {
                    UIActions.setLoadingState(false, UIElements.registerButton);
                }
            });
        }

        // Logout button click
        if (UIElements.logoutButton) {
            UIElements.logoutButton.addEventListener('click', async () => { 
                try {
                    await firebaseServices.auth.signOut(); 
                } catch (error) {
                    console.error("Çıkış yaparken hata:", error);
                    alert("Çıkış yapılırken bir hata oluştu.");
                }
            });
        }
        
        // Save API Keys button click
        if (UIElements.saveKeysButton) {
            UIElements.saveKeysButton.addEventListener('click', async () => {
                const apiKey = UIElements.apiKeyInput?.value?.trim();
                const apiSecret = UIElements.apiSecretInput?.value?.trim();

                if (!apiKey || !apiSecret) {
                    UIActions.showError(UIElements.apiKeysStatus, "Lütfen hem API Key hem de API Secret girin.");
                    return;
                }

                UIActions.setLoadingState(true, UIElements.saveKeysButton);
                const result = await fetchApi('/api/save-keys', { 
                    method: 'POST', 
                    body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret }) 
                });
                
                if (result && result.success) {
                    UIActions.showSuccess(UIElements.apiKeysStatus, "API Anahtarları başarıyla kaydedildi!");
                    if (UIElements.apiKeyInput) UIElements.apiKeyInput.value = ''; 
                    if (UIElements.apiSecretInput) UIElements.apiSecretInput.value = '';
                    await UIActions.updateUserProfile(); 
                } else {
                    UIActions.showError(UIElements.apiKeysStatus, result?.detail || "API Anahtarları kaydedilirken hata oluştu.");
                }
                UIActions.setLoadingState(false, UIElements.saveKeysButton);
            });
        }

        // Start Bot button click
        if (UIElements.startButton) {
            UIElements.startButton.addEventListener('click', async () => {
                const botSettings = {
                    symbol: UIElements.symbolInput?.value?.trim()?.toUpperCase() || 'BTCUSDT',
                    leverage: parseInt(UIElements.leverageInput?.value, 10) || 10,
                    order_size: parseFloat(UIElements.orderSizeInput?.value) || 20,
                    stop_loss: parseFloat(UIElements.slInput?.value) || 2,
                    take_profit: parseFloat(UIElements.tpInput?.value) || 4,
                    timeframe: "15m"
                };

                // Validation
                if (!botSettings.symbol || botSettings.symbol.length < 3) {
                    alert('Lütfen geçerli bir trading paritesi (örn: BTCUSDT) girin.');
                    return;
                }
                if (isNaN(botSettings.leverage) || botSettings.leverage < 1 || botSettings.leverage > 125) {
                    alert('Kaldıraç 1 ile 125 arasında bir değer olmalıdır.');
                    return;
                }
                if (isNaN(botSettings.order_size) || botSettings.order_size < 10) {
                    alert('İşlem büyüklüğü en az 10 USDT olmalıdır.');
                    return;
                }
                if (isNaN(botSettings.stop_loss) || botSettings.stop_loss <= 0) {
                    alert('Stop Loss yüzdesi pozitif bir değer olmalıdır.');
                    return;
                }
                if (isNaN(botSettings.take_profit) || botSettings.take_profit <= 0) {
                    alert('Take Profit yüzdesi pozitif bir değer olmalıdır.');
                    return;
                }
                if (botSettings.take_profit <= botSettings.stop_loss) {
                    alert('Take Profit yüzdesi Stop Loss yüzdesinden büyük olmalıdır.');
                    return;
                }
                
                UIActions.setLoadingState(true, UIElements.startButton);
                const result = await fetchApi('/api/start', { 
                    method: 'POST', 
                    body: JSON.stringify(botSettings) 
                });
                
                if (result && result.success) {
                    if (UIElements.statusMessage) {
                        UIElements.statusMessage.textContent = "Bot başarıyla başlatıldı!";
                        UIElements.statusMessage.classList.remove('error');
                        UIElements.statusMessage.classList.add('success');
                    }
                } else {
                    if (UIElements.statusMessage) {
                        UIElements.statusMessage.textContent = result?.detail || "Bot başlatılırken bir hata oluştu.";
                        UIElements.statusMessage.classList.remove('success');
                        UIElements.statusMessage.classList.add('error');
                    }
                }
                await UIActions.updateBotStatus(); 
                UIActions.setLoadingState(false, UIElements.startButton);
            });
        }

        // Stop Bot button click
        if (UIElements.stopButton) {
            UIElements.
