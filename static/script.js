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
                UIElements.statusMessage.textContent = `Hata: ${errorData.detail || 'Bilinmeyen bir hata oluştu.'}`;
                return null;
            }

            return response.json();
        } catch (error) {
            console.error("Ağ veya fetch hatası:", error);
            UIElements.statusMessage.textContent = "Ağ bağlantısı hatası oluştu. Lütfen internet bağlantınızı kontrol edin.";
            return null;
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
            if (statusInterval) clearInterval(statusInterval);
            if (priceUpdateInterval) clearInterval(priceUpdateInterval);
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

            // Clear previous intervals to prevent duplicates
            if (statusInterval) clearInterval(statusInterval);
            if (priceUpdateInterval) clearInterval(priceUpdateInterval);

            // Start periodic updates
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
            // Clear any previous error messages when toggling
            UIElements.loginError.textContent = '';
            UIElements.registerError.textContent = '';
        },
        
        /**
         * Analiz grafiği için rastgele çubuklar oluşturur.
         */
        generateChartBars: () => {
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

            UIElements.userEmailSpan.textContent = profile.email || 'N/A';
            const statusMap = {
                'active': 'Aktif', 
                'trial': 'Deneme Sürümü', 
                'expired': 'Süresi Dolmuş',
                'inactive': 'Aktif Değil'
            };
            const subscriptionStatusText = statusMap[profile.subscription_status] || 'Bilinmiyor';
            UIElements.subscriptionStatusSpan.innerHTML = `<span class="status-badge ${profile.subscription_status}">${subscriptionStatusText}</span>`;
            
            UIElements.subscriptionExpirySpan.textContent = profile.subscription_expiry 
                ? new Date(profile.subscription_expiry).toLocaleDateString('tr-TR')
                : 'N/A';
            
            UIElements.registerDateSpan.textContent = profile.registration_date
                ? new Date(profile.registration_date).toLocaleDateString('tr-TR')
                : 'N/A';

            UIElements.paymentAddressCode.textContent = profile.payment_address || 'Yükleniyor...';
            UIElements.paymentInfoDiv.style.display = (profile.subscription_status === 'expired' || !profile.subscription_status) ? 'block' : 'none';

            UIElements.ipListElement.innerHTML = profile.server_ips?.length
                ? profile.server_ips.map(ip => `<li class="ip-item">${ip}</li>`).join('')
                : '<li class="ip-item loading">Sunucu IP adresi bulunamadı.</li>';

            // Enable/disable start button based on subscription and API keys and valid settings
            // Yeni kontrol eklendi: Ayarlar geçerli olmalı
            const areSettingsValid = 
                parseFloat(UIElements.orderSizeInput.value) >= 10 && // Min işlem büyüklüğü 10 USDT
                parseInt(UIElements.leverageInput.value, 10) >= 1 && // Min kaldıraç 1x
                parseInt(UIElements.leverageInput.value, 10) <= 125; // Max kaldıraç 125x

            const canStartBot = profile.has_api_keys && ['active', 'trial'].includes(profile.subscription_status) && areSettingsValid;
            
            if (!UIElements.startButton.disabled) { 
                UIElements.startButton.disabled = !canStartBot;
            }

            // Update API status on API page
            const apiConfigured = profile.has_api_keys;
            UIElements.apiStatusIndicator.classList.toggle('active', apiConfigured);
            UIElements.apiStatusIndicator.classList.toggle('inactive', !apiConfigured);
            UIElements.apiStatusText.textContent = apiConfigured ? 'CONFIGURED' : 'NOT CONFIGURED';
            UIElements.apiStatusText.classList.toggle('text-success', apiConfigured);
            UIElements.apiStatusText.classList.toggle('text-muted', !apiConfigured);
        },

        /**
         * Botun mevcut durumunu API'den alır ve UI'ı günceller.
         */
        updateBotStatus: async () => {
            const data = await fetchApi('/api/status');
            if (!data) {
                UIElements.botStatusIndicator.classList.remove('active');
                UIElements.botStatusIndicator.classList.add('inactive');
                UIElements.botStatusText.textContent = 'ERROR';
                UIElements.botStatusText.classList.remove('text-success');
                UIElements.botStatusText.classList.add('text-danger');
                UIElements.startButton.disabled = true; 
                UIElements.stopButton.disabled = true;
                UIElements.statusMessage.textContent = "Bot durumu alınamadı. Lütfen tekrar deneyin.";
                return;
            }

            UIElements.statusMessage.textContent = data.status_message;
            const isRunning = data.is_running;

            UIElements.botStatusIndicator.classList.toggle('active', isRunning);
            UIElements.botStatusIndicator.classList.toggle('inactive', !isRunning);
            UIElements.botStatusText.textContent = isRunning ? 'ONLINE' : 'OFFLINE';
            UIElements.botStatusText.classList.toggle('text-success', isRunning);
            UIElements.botStatusText.classList.toggle('text-muted', !isRunning);

            UIElements.stopButton.disabled = !isRunning;
            
            if (isRunning) {
                UIElements.startButton.disabled = true;
            } else {
                await UIActions.updateUserProfile(); 
            }

            const inputsToToggle = [
                UIElements.symbolInput, UIElements.leverageInput, UIElements.tpInput, 
                UIElements.slInput, UIElements.orderSizeInput
            ];
            inputsToToggle.forEach(el => el.disabled = isRunning);
        },

        /**
         * İşlem büyüklüğü inputunu günceller.
         * @param {string} value - Yeni işlem büyüklüğü değeri.
         */
        updateOrderSizeInput: (value) => {
            UIElements.orderSizeInput.value = value;
        },

        /**
         * Seçilen paritenin anlık fiyatını Binance WebSocket API'sından alır ve UI'ı günceller.
         */
        updatePairPrice: () => {
            // Mevcut WebSocket bağlantısını kapat (varsa)
            if (UIElements.pairPrice.dataset.currentWs) {
                try {
                    const oldWs = JSON.parse(UIElements.pairPrice.dataset.currentWs);
                    if (oldWs && oldWs.readyState === WebSocket.OPEN) {
                        oldWs.close();
                    }
                } catch (e) {
                    console.warn("Mevcut WebSocket kapatılırken hata:", e);
                }
                UIElements.pairPrice.dataset.currentWs = null;
            }

            const symbol = UIElements.symbolInput.value.toLowerCase();
            const ws = new WebSocket(`${WEBSOCKET_URL}${symbol}@ticker`);

            ws.onopen = () => { /* console.log(`WebSocket connected for ${symbol}`); */ };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data && data.c) { // 'c' is the last price
                    const price = parseFloat(data.c).toFixed(2);
                    UIElements.pairPrice.textContent = `$${price}`;
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket Error:', error);
                UIElements.pairPrice.textContent = 'Fiyat Yok';
                ws.close(); 
            };

            ws.onclose = () => { /* console.log(`WebSocket disconnected for ${symbol}`); */ };

            // Store the current WebSocket instance for future closing
            UIElements.pairPrice.dataset.currentWs = JSON.stringify(ws);
        },

        /**
         * API anahtar durumunu günceller.
         */
        updateApiKeysStatus: async () => {
            const profile = await fetchApi('/api/user-profile');
            if (profile) {
                const apiConfigured = profile.has_api_keys;
                UIElements.apiStatusIndicator.classList.toggle('active', apiConfigured);
                UIElements.apiStatusIndicator.classList.toggle('inactive', !apiConfigured);
                UIElements.apiStatusText.textContent = apiConfigured ? 'CONFIGURED' : 'NOT CONFIGURED';
                UIElements.apiStatusText.classList.toggle('text-success', apiConfigured);
                UIElements.apiStatusText.classList.toggle('text-muted', !apiConfigured);
            }
        },

        /**
         * Bir butonun yükleme durumunu ayarlar.
         * @param {boolean} isLoading - Yükleme durumu (true/false).
         * @param {HTMLElement} button - Etkilenecek buton elementi.
         */
        setLoadingState: (isLoading, button) => {
            if(button) {
                button.disabled = isLoading;
            }
            UIElements.statusMessage.textContent = isLoading ? "İşlem yapılıyor, lütfen bekleyin..." : "";
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
        UIElements.leverageInput.addEventListener('input', (e) => {
            UIElements.leverageValue.textContent = `${e.target.value}x`;
            UIActions.updateUserProfile(); // Ayar değişikliğinde butonu güncelle
        });

        // Order size input
        UIElements.orderSizeInput.addEventListener('input', (e) => {
            UIActions.updateUserProfile(); // Ayar değişikliğinde butonu güncelle
        });

        // TP/SL inputs (though not used in canStartBot, good practice for full validation later)
        UIElements.tpInput.addEventListener('input', UIActions.updateUserProfile);
        UIElements.slInput.addEventListener('input', UIActions.updateUserProfile);

        // Toggle auth forms
        UIElements.showRegisterLink.addEventListener('click', (e) => { 
            e.preventDefault(); 
            UIActions.toggleAuthForms(true); 
        });
        UIElements.showLoginLink.addEventListener('click', (e) => { 
            e.preventDefault(); 
            UIActions.toggleAuthForms(false); 
        });

        // Login button click
        UIElements.loginButton.addEventListener('click', async () => {
            UIElements.loginError.textContent = "";
            const email = UIElements.loginEmailInput.value;
            const password = UIElements.loginPasswordInput.value;
            if (!email || !password) {
                UIElements.loginError.textContent = "Lütfen e-posta ve şifrenizi girin.";
                return;
            }
            UIActions.setLoadingState(true, UIElements.loginButton);
            try {
                await firebaseServices.auth.signInWithEmailAndPassword(email, password);
            } catch (error) {
                let errorMessage = "Giriş yaparken bir hata oluştu.";
                if (error.code === 'auth/user-not-found' || error.code === 'auth/wrong-password') {
                    errorMessage = "Hatalı e-posta veya şifre.";
                } else if (error.code === 'auth/invalid-email') {
                    errorMessage = "Geçersiz e-posta adresi.";
                }
                UIElements.loginError.textContent = errorMessage;
            } finally {
                UIActions.setLoadingState(false, UIElements.loginButton);
            }
        });

        // Register button click
        UIElements.registerButton.addEventListener('click', async () => {
            UIElements.registerError.textContent = "";
            const email = UIElements.registerEmailInput.value;
            const password = UIElements.registerPasswordInput.value;
            if (!email || !password) {
                UIElements.registerError.textContent = "Lütfen e-posta ve şifrenizi girin.";
                return;
            }
            UIActions.setLoadingState(true, UIElements.registerButton);
            try {
                await firebaseServices.auth.createUserWithEmailAndPassword(email, password);
            } catch (error) {
                let errorMessage = "Hesap oluşturulurken bir hata oluştu.";
                if (error.code === 'auth/weak-password') { 
                    errorMessage = 'Şifre en az 6 karakter olmalıdır.'; 
                } else if (error.code === 'auth/email-already-in-use') { 
                    errorMessage = 'Bu e-posta adresi zaten kullanılıyor.'; 
                } else if (error.code === 'auth/invalid-email') {
                    errorMessage = "Geçersiz e-posta adresi.";
                }
                UIElements.registerError.textContent = errorMessage;
            } finally {
                UIActions.setLoadingState(false, UIElements.registerButton);
            }
        });

        // Logout button click
        UIElements.logoutButton.addEventListener('click', async () => { 
            try {
                await firebaseServices.auth.signOut(); 
            } catch (error) {
                console.error("Çıkış yaparken hata:", error);
                alert("Çıkış yapılırken bir hata oluştu.");
            }
        });
        
        // Save API Keys button click
        UIElements.saveKeysButton.addEventListener('click', async () => {
            UIElements.apiKeysStatus.style.display = 'block';
            UIElements.apiKeysStatus.textContent = "Kaydediliyor...";
            UIElements.apiKeysStatus.classList.remove('error', 'success');

            const apiKey = UIElements.apiKeyInput.value.trim();
            const apiSecret = UIElements.apiSecretInput.value.trim();

            if (!apiKey || !apiSecret) {
                UIElements.apiKeysStatus.textContent = "Lütfen hem API Key hem de API Secret girin.";
                UIElements.apiKeysStatus.classList.add('error');
                return;
            }

            UIActions.setLoadingState(true, UIElements.saveKeysButton);
            const result = await fetchApi('/api/save-keys', { 
                method: 'POST', 
                body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret }) 
            });
            
            if (result && result.success) {
                UIElements.apiKeysStatus.textContent = "API Anahtarları başarıyla kaydedildi!";
                UIElements.apiKeysStatus.classList.add('success');
                UIElements.apiKeyInput.value = ''; 
                UIElements.apiSecretInput.value = '';
                await UIActions.updateUserProfile(); 
            } else {
                UIElements.apiKeysStatus.textContent = result?.detail || "API Anahtarları kaydedilirken hata oluştu.";
                UIElements.apiKeysStatus.classList.remove('success');
                UIElements.apiKeysStatus.classList.add('error');
            }
            UIActions.setLoadingState(false, UIElements.saveKeysButton);
        });

        // Start Bot button click
        UIElements.startButton.addEventListener('click', async () => {
            const botSettings = {
                symbol: UIElements.symbolInput.value.trim().toUpperCase(),
                leverage: parseInt(UIElements.leverageInput.value, 10),
                order_size: parseFloat(UIElements.orderSizeInput.value),
                stop_loss: parseFloat(UIElements.slInput.value),
                take_profit: parseFloat(UIElements.tpInput.value),
                timeframe: "15m" // Varsayılan timeframe eklendi
            };

            // Basic validation (Updated to match backend's StartRequest model)
            if (!botSettings.symbol || botSettings.symbol.length < 3) {
                alert('Lütfen geçerli bir trading paritesi (örn: BTCUSDT) girin.');
                return;
            }
            if (isNaN(botSettings.leverage) || botSettings.leverage < 1 || botSettings.leverage > 125) { // Updated to 125
                alert('Kaldıraç 1 ile 125 arasında bir değer olmalıdır.');
                return;
            }
            if (isNaN(botSettings.order_size) || botSettings.order_size < 10) { // Updated to 10
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
                UIElements.statusMessage.textContent = "Bot başarıyla başlatıldı!";
                UIElements.statusMessage.classList.remove('error');
                UIElements.statusMessage.classList.add('success');
            } else {
                UIElements.statusMessage.textContent = result?.detail || "Bot başlatılırken bir hata oluştu.";
                UIElements.statusMessage.classList.remove('success');
                UIElements.statusMessage.classList.add('error');
            }
            await UIActions.updateBotStatus(); 
            UIActions.setLoadingState(false, UIElements.startButton);
        });

        // Stop Bot button click
        UIElements.stopButton.addEventListener('click', async () => { 
            UIActions.setLoadingState(true, UIElements.stopButton);
            const result = await fetchApi('/api/stop', { method: 'POST' }); 
            if (result && result.success) {
                UIElements.statusMessage.textContent = "Bot başarıyla durduruldu!";
                UIElements.statusMessage.classList.remove('error');
                UIElements.statusMessage.classList.add('success');
            } else {
                UIElements.statusMessage.textContent = result?.detail || "Bot durdurulurken bir hata oluştu.";
                UIElements.statusMessage.classList.remove('success');
                UIElements.statusMessage.classList.add('error');
            }
            await UIActions.updateBotStatus(); 
            UIActions.setLoadingState(false, UIElements.stopButton);
        });

        // Pair Card click (to change symbol)
        UIElements.pairCard.addEventListener('click', () => {
            if (UIElements.symbolInput.disabled) { 
                alert("Bot çalışırken parite değiştirilemez. Lütfen botu durdurun.");
                return;
            }
            const newSymbol = prompt('Yeni parite girin (örn: ETHUSDT):', UIElements.symbolInput.value);
            if (newSymbol && newSymbol.trim()) {
                const formattedSymbol = newSymbol.trim().toUpperCase();
                UIElements.symbolInput.value = formattedSymbol;
                UIElements.pairSymbol.textContent = formattedSymbol;
                UIActions.updatePairPrice(); 
            }
        });

        // Copy to clipboard function
        window.copyToClipboard = (elementId) => {
            const element = document.getElementById(elementId);
            if (!element) return;

            let textToCopy = element.textContent;
            const tempTextArea = document.createElement('textarea');
            tempTextArea.value = textToCopy;
            document.body.appendChild(tempTextArea);
            tempTextArea.select();
            document.execCommand('copy');
            document.body.removeChild(tempTextArea);

            const originalText = element.textContent;
            element.textContent = 'Kopyalandı!';
            setTimeout(() => {
                element.textContent = originalText;
            }, 1500);
        };
    }

    /**
     * Uygulamayı başlatan ana fonksiyon.
     */
    async function initializeApp() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/firebase-config`);
            if (!response.ok) throw new Error('Firebase yapılandırması alınamadı.');
            
            const firebaseConfig = await response.json();
            if (!firebaseConfig.apiKey) throw new Error('Sunucudan eksik Firebase yapılandırması alındı.');
            
            firebase.initializeApp(firebaseConfig);
            firebaseServices.auth = firebase.auth();
            firebaseServices.database = firebase.database(); 

            // Kullanıcının oturum durumunu dinle
            firebaseServices.auth.onAuthStateChanged(user => {
                if (user) {
                    UIActions.showAppScreen();
                } else {
                    UIActions.showAuthScreen();
                }
            });

            setupEventListeners();
            UIActions.updatePairPrice(); 

        } catch (error) {
            console.error("Uygulama başlatılamadı:", error);
            document.body.innerHTML = `<div style="color: #1A1A1A; text-align: center; padding: 2rem;">
                                            <h1>Uygulama başlatılamadı.</h1>
                                            <p>Lütfen daha sonra tekrar deneyin veya yönetici ile iletişime geçin.</p>
                                            <p style="font-size: 0.8em; color: #666;">Hata Detayı: ${error.message}</p>
                                        </div>`;
        }
    }

    initializeApp();
});
