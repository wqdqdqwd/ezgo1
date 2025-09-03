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
        orderSizeInput: document.getElementById('order-size-input'),
        orderSizeValue: document.getElementById('order-size-value'),
        symbolSelect: document.getElementById('symbol-select'),
        timeframeSelect: document.getElementById('timeframe-select'),
        tpInput: document.getElementById('tp-input'), // YENİ: TP girişi
        slInput: document.getElementById('sl-input'), // YENİ: SL girişi
        startBotButton: document.getElementById('start-bot-button'),
        stopBotButton: document.getElementById('stop-bot-button'),
        botStatusMessage: document.getElementById('bot-status-message'),
        tradeHistoryTable: document.getElementById('trade-history-table').querySelector('tbody'),
        pnlValue: document.getElementById('pnl-value'),
        balanceValue: document.getElementById('balance-value'),
        realtimePrice: document.getElementById('realtime-price'),

        // Settings elements
        apiKeyInput: document.getElementById('api-key-input'),
        apiSecretInput: document.getElementById('api-secret-input'),
        saveApiKeysButton: document.getElementById('save-api-keys-button'),
        apiKeyMessage: document.getElementById('api-key-message'),
        paymentAddress: document.getElementById('payment-address'),
        copyPaymentAddress: document.getElementById('copy-payment-address'),
        paymentModal: document.getElementById('payment-modal'),
        closePaymentModal: document.getElementById('close-payment-modal'),
        openPaymentModal: document.getElementById('open-payment-modal'),
        renewSubscriptionButton: document.getElementById('renew-subscription-button'),
        subscriptionStatus: document.getElementById('subscription-status'),

        // Loading and error states
        loadingSpinner: document.getElementById('loading-spinner'),
        errorModal: document.getElementById('error-modal'),
        errorMessage: document.getElementById('error-message'),
        closeErrorModal: document.getElementById('close-error-modal'),
    };

    /**
     * Firebase ve diğer global değişkenler.
     */
    let auth, db;
    let currentWebSocket;
    let userId;

    // Firebase'i başlat ve kullanıcının oturum durumunu dinle
    async function initializeApp() {
        console.log('Uygulama başlatılıyor...');
        showLoading(true);
        try {
            // Firebase konfigürasyonunu yükle
            const firebaseConfig = {
                apiKey: "YOUR_FIREBASE_WEB_API_KEY", // Bu değeri .env'den almalısın
                authDomain: "YOUR_FIREBASE_WEB_AUTH_DOMAIN",
                projectId: "YOUR_FIREBASE_WEB_PROJECT_ID",
                storageBucket: "YOUR_FIREBASE_WEB_STORAGE_BUCKET",
                messagingSenderId: "YOUR_FIREBASE_WEB_MESSAGING_SENDER_ID",
                appId: "YOUR_FIREBASE_WEB_APP_ID"
            };

            const app = firebase.initializeApp(firebaseConfig);
            auth = firebase.getAuth(app);
            db = firebase.getFirestore(app);

            console.log('Firebase başlatıldı');

            firebase.onAuthStateChanged(auth, async (user) => {
                showLoading(false);
                if (user) {
                    console.log('Auth state değişti: giriş yapıldı');
                    userId = user.uid;
                    UIElements.appContainer.classList.remove('hidden');
                    UIElements.authContainer.classList.add('hidden');
                    loadDashboardData();
                    setupEventListeners();
                } else {
                    console.log('Auth state değişti: çıkış yapıldı');
                    UIElements.appContainer.classList.add('hidden');
                    UIElements.authContainer.classList.remove('hidden');
                }
            });
            console.log('Uygulama başarıyla başlatıldı');
        } catch (error) {
            console.error('Uygulama başlatılırken hata oluştu:', error);
            showLoading(false);
            showErrorModal('Uygulama başlatılırken bir sorun oluştu. Lütfen konsol loglarını kontrol edin.', error);
        }
    }

    /**
     * WebSocket bağlantısını kurar ve fiyatları günceller.
     * @param {string} symbol - Sembol adı (örnek: BTCUSDT)
     * @param {string} timeframe - Zaman dilimi (örnek: 1m, 5m, 1h)
     */
    function updatePairPrice(symbol) {
        // Mevcut bağlantı varsa kapat
        if (currentWebSocket && currentWebSocket.readyState === WebSocket.OPEN) {
            currentWebSocket.close();
            console.log(`Chart WebSocket bağlantısı kapatıldı: ${symbol}`);
        }

        // Futures piyasası için doğru WebSocket URL'ini kullan
        const socket_url = `wss://fstream.binance.com/ws/${symbol.toLowerCase()}@ticker`;
        
        console.log(`Yeni WebSocket'e bağlanılıyor: ${socket_url}`);

        currentWebSocket = new WebSocket(socket_url);

        currentWebSocket.onopen = (event) => {
            console.log(`WebSocket bağlandı: ${symbol}`);
        };

        currentWebSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.c) { // 'c' son fiyatı temsil eder
                UIElements.realtimePrice.textContent = parseFloat(data.c).toFixed(2);
                UIElements.realtimePrice.style.color = (parseFloat(data.c) > parseFloat(data.o)) ? 'green' : 'red';
            }
        };

        currentWebSocket.onerror = (error) => {
            console.error('Price WebSocket hatası:', error);
            // Hata durumunda yeniden bağlanmayı deneyebilirsin, ancak şimdilik logluyoruz
        };

        currentWebSocket.onclose = (event) => {
            console.log('WebSocket bağlantısı kapatıldı:', event.reason);
        };
    }
    
    /**
     * Uygulama ekranlarını yönetir.
     * @param {string} pageId - Gösterilecek sayfanın ID'si
     */
    function showPage(pageId) {
        UIElements.appPages.forEach(page => {
            page.classList.add('hidden');
        });
        const activePage = document.getElementById(pageId);
        if (activePage) {
            activePage.classList.remove('hidden');
        }
        console.log(`${pageId} ekranı gösteriliyor`);
    }

    /**
     * Bot Dashboard'daki verileri ve durumu yükler.
     */
    async function loadDashboardData() {
        // Örnek olarak ilk yüklemede ETHUSDT'nin fiyatını çek
        updatePairPrice('ETHUSDT');
        
        // Bot durumu ve diğer verileri çekmek için backend API'sine istek at
        await getBotStatus();
        await getApiKeys();
        await getPaymentAddress();
        await getSubscriptionStatus();
    }

    /**
     * API anahtarlarını backend'e kaydeder.
     */
    async function saveApiKeys() {
        const apiKey = UIElements.apiKeyInput.value;
        const apiSecret = UIElements.apiSecretInput.value;
        if (!apiKey || !apiSecret) {
            UIElements.apiKeyMessage.textContent = 'Lütfen API anahtarlarını eksiksiz girin.';
            UIElements.apiKeyMessage.style.color = 'red';
            return;
        }

        const response = await fetch('/save-api-keys', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ uid: userId, api_key: apiKey, api_secret: apiSecret })
        });

        const result = await response.json();
        if (result.success) {
            UIElements.apiKeyMessage.textContent = 'API anahtarları başarıyla kaydedildi!';
            UIElements.apiKeyMessage.style.color = 'green';
        } else {
            UIElements.apiKeyMessage.textContent = 'Kaydetme başarısız: ' + result.error;
            UIElements.apiKeyMessage.style.color = 'red';
        }
    }

    /**
     * Firebase'den ödeme adresini çeker.
     */
    async function getPaymentAddress() {
        try {
            const docRef = firebase.doc(db, "settings", "payment");
            const docSnap = await firebase.getDoc(docRef);
            if (docSnap.exists()) {
                const data = docSnap.data();
                UIElements.paymentAddress.textContent = data.trc20_address;
            } else {
                UIElements.paymentAddress.textContent = 'Ödeme adresi bulunamadı.';
            }
        } catch (error) {
            console.error('Ödeme adresi alınırken hata:', error);
        }
    }

    /**
     * Abonelik durumunu Firebase'den çeker.
     */
    async function getSubscriptionStatus() {
        try {
            const docRef = firebase.doc(db, "users", userId);
            const docSnap = await firebase.getDoc(docRef);
            if (docSnap.exists()) {
                const userData = docSnap.data();
                const isActive = userData.subscription_end_date && userData.subscription_end_date.toDate() > new Date();
                UIElements.subscriptionStatus.textContent = isActive ? 'Aktif' : 'Pasif';
                UIElements.subscriptionStatus.style.color = isActive ? 'green' : 'red';
            } else {
                UIElements.subscriptionStatus.textContent = 'Durum bilinmiyor.';
            }
        } catch (error) {
            console.error('Abonelik durumu alınırken hata:', error);
        }
    }

    /**
     * Botu başlatır.
     */
    async function startBot() {
        const settings = {
            symbol: UIElements.symbolSelect.value,
            timeframe: UIElements.timeframeSelect.value,
            leverage: parseInt(UIElements.leverageInput.value),
            order_size: parseFloat(UIElements.orderSizeInput.value),
            take_profit: parseFloat(UIElements.tpInput.value), // YENİ: TP değerini al
            stop_loss: parseFloat(UIElements.slInput.value) // YENİ: SL değerini al
        };

        UIElements.startBotButton.disabled = true;
        UIElements.stopBotButton.disabled = false;
        
        const response = await fetch('/start-bot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: userId, settings: settings })
        });

        const result = await response.json();
        if (result.success) {
            UIElements.botStatusMessage.textContent = 'Bot başlatılıyor...';
        } else {
            UIElements.botStatusMessage.textContent = 'Bot başlatılamadı: ' + result.error;
            UIElements.startBotButton.disabled = false;
            UIElements.stopBotButton.disabled = true;
        }
    }
    
    /**
     * Botu durdurur.
     */
    async function stopBot() {
        UIElements.startBotButton.disabled = false;
        UIElements.stopBotButton.disabled = true;

        const response = await fetch('/stop-bot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: userId })
        });

        const result = await response.json();
        if (result.success) {
            UIElements.botStatusMessage.textContent = 'Bot durduruldu.';
        } else {
            UIElements.botStatusMessage.textContent = 'Bot durdurulamadı: ' + result.error;
        }
    }

    /**
     * Botun anlık durumunu backend'den çeker.
     */
    async function getBotStatus() {
        const response = await fetch('/bot-status?uid=' + userId);
        const status = await response.json();
        
        if (status.is_running) {
            UIElements.botStatusMessage.textContent = `Bot aktif: ${status.symbol}`;
            UIElements.startBotButton.disabled = true;
            UIElements.stopBotButton.disabled = false;
        } else {
            UIElements.botStatusMessage.textContent = 'Bot pasif.';
            UIElements.startBotButton.disabled = false;
            UIElements.stopBotButton.disabled = true;
        }
    }

    /**
     * Loading spinner'ı gösterir/gizler.
     * @param {boolean} show - Gösterilecekse true, gizlenecekse false.
     */
    function showLoading(show) {
        if (show) {
            UIElements.loadingSpinner.classList.remove('hidden');
        } else {
            UIElements.loadingSpinner.classList.add('hidden');
        }
    }

    /**
     * Hata modalını gösterir.
     * @param {string} message - Kullanıcıya gösterilecek hata mesajı.
     * @param {object} error - Konsola yazdırılacak hata objesi.
     */
    function showErrorModal(message, error) {
        UIElements.errorMessage.textContent = message;
        UIElements.errorModal.classList.remove('hidden');
        console.error("Hata Detayı:", error);
    }

    /**
     * Event listener'ları kurar.
     */
    function setupEventListeners() {
        console.log('Event listener\'lar kuruluyor');
        
        // Login butonu
        UIElements.loginButton.addEventListener('click', async () => {
            try {
                const email = UIElements.loginEmailInput.value;
                const password = UIElements.loginPasswordInput.value;
                await firebase.signInWithEmailAndPassword(auth, email, password);
            } catch (error) {
                UIElements.loginError.textContent = 'Giriş başarısız: ' + error.message;
            }
        });

        // Register butonu
        UIElements.registerButton.addEventListener('click', async () => {
            try {
                const email = UIElements.registerEmailInput.value;
                const password = UIElements.registerPasswordInput.value;
                await firebase.createUserWithEmailAndPassword(auth, email, password);
            } catch (error) {
                UIElements.registerError.textContent = 'Kayıt başarısız: ' + error.message;
            }
        });

        // Sayfa geçişleri
        UIElements.navButtons.forEach(button => {
            button.addEventListener('click', () => {
                const pageId = button.dataset.page;
                showPage(pageId);
            });
        });

        // Bot kontrol butonları
        UIElements.startBotButton.addEventListener('click', startBot);
        UIElements.stopBotButton.addEventListener('click', stopBot);
        
        // Dashboard ayar kaydırıcıları (sliders)
        UIElements.leverageInput.addEventListener('input', () => {
            UIElements.leverageValue.textContent = UIElements.leverageInput.value + 'x';
        });
        UIElements.orderSizeInput.addEventListener('input', () => {
            UIElements.orderSizeValue.textContent = UIElements.orderSizeInput.value + ' USDT';
        });

        // Sembol ve zaman dilimi değiştiğinde WebSocket'i güncelle
        UIElements.symbolSelect.addEventListener('change', (e) => updatePairPrice(e.target.value));
        UIElements.timeframeSelect.addEventListener('change', () => {}); // Şimdilik boş bırakıldı

        // API anahtarı kaydetme butonu
        UIElements.saveApiKeysButton.addEventListener('click', saveApiKeys);

        // Ödeme adresi kopyalama
        UIElements.copyPaymentAddress.addEventListener('click', () => {
            const address = UIElements.paymentAddress.textContent;
            navigator.clipboard.writeText(address).then(() => {
                // Modalsız uyarı mesajı
                const message = document.createElement('div');
                message.textContent = 'Ödeme adresi kopyalandı!';
                message.style.cssText = `
                    position: fixed;
                    bottom: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 5px;
                    z-index: 1000;
                    opacity: 0;
                    transition: opacity 0.5s;
                `;
                document.body.appendChild(message);
                
                setTimeout(() => {
                    message.style.opacity = 1;
                }, 10);

                setTimeout(() => {
                    message.style.opacity = 0;
                    setTimeout(() => message.remove(), 500);
                }, 2000);
            });
        });

        // Modal kapatma butonları
        UIElements.closePaymentModal.addEventListener('click', () => {
            UIElements.paymentModal.classList.add('hidden');
        });
        UIElements.closeErrorModal.addEventListener('click', () => {
            UIElements.errorModal.classList.add('hidden');
        });

        // Ödeme modalını aç
        UIElements.openPaymentModal.addEventListener('click', () => {
            UIElements.paymentModal.classList.remove('hidden');
        });

        // Login/Register ekranları arası geçiş
        UIElements.showRegisterLink.addEventListener('click', (e) => {
            e.preventDefault();
            UIElements.loginCard.classList.add('hidden');
            UIElements.registerCard.classList.remove('hidden');
        });
        UIElements.showLoginLink.addEventListener('click', (e) => {
            e.preventDefault();
            UIElements.registerCard.classList.add('hidden');
            UIElements.loginCard.classList.remove('hidden');
        });

    }

    // Uygulamayı başlat
    initializeApp();
});
