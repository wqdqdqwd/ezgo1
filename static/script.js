document.addEventListener('DOMContentLoaded', () => {
    console.log('Script yüklendi - DOM hazır');

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

        navButtons: document.querySelectorAll('.sidebar-nav .nav-item, .mobile-nav-grid .mobile-nav-item'),
        appPages: document.querySelectorAll('.main-content .page'),

        leverageInput: document.getElementById('leverage-input'),
        leverageValue: document.getElementById('leverage-value'),
        leverageRangeInput: document.getElementById('leverage-range-input'),
        orderSizeInput: document.getElementById('order-size-input'),
        stopLossInput: document.getElementById('stop-loss-input'),
        takeProfitInput: document.getElementById('take-profit-input'),
        startBotButton: document.getElementById('start-bot-button'),
        stopBotButton: document.getElementById('stop-bot-button'),
        botStatusIndicator: document.getElementById('bot-status-indicator'),
        botStatusMessage: document.getElementById('bot-status-message'),

        strategySelect: document.getElementById('strategy-select'),
        symbolSelect: document.getElementById('symbol-select'),
        timeframeSelect: document.getElementById('timeframe-select'),

        // Settings Page
        apiForm: document.getElementById('api-form'),
        binanceApiKeyInput: document.getElementById('binance-api-key'),
        binanceApiSecretInput: document.getElementById('binance-api-secret'),
        saveApiKeysButton: document.getElementById('save-api-keys'),
        apiSaveStatus: document.getElementById('api-save-status'),

        // Wallet Page
        walletBalance: document.getElementById('wallet-balance'),
        copyAddressButton: document.getElementById('copy-address-button'),
        paymentAddress: document.getElementById('payment-address'),
        paymentQrCode: document.getElementById('payment-qr-code'),

        // History Page
        historyList: document.getElementById('history-list'),

        // General
        loader: document.getElementById('loader'),
        authButtons: document.getElementById('auth-buttons'),
        userEmailDisplay: document.getElementById('user-email'),
        logoutButton: document.getElementById('logout-button'),

        // Mobile Nav
        mobileNavToggle: document.getElementById('mobile-nav-toggle'),
        mobileNavContainer: document.getElementById('mobile-nav-container'),

        // Modal elements
        modalContainer: document.getElementById('modal-container'),
        modalTitle: document.getElementById('modal-title'),
        modalBody: document.getElementById('modal-body'),
        modalConfirmButton: document.getElementById('modal-confirm'),
        modalCloseButton: document.getElementById('modal-close'),
    };

    const API_BASE_URL = window.location.origin;

    // Firebase
    const firebaseConfig = JSON.parse('{"apiKey":"AIzaSyBqF6...I","authDomain":"tradetalk-2f63f.firebaseapp.com","projectId":"tradetalk-2f63f","storageBucket":"tradetalk-2f63f.appspot.com","messagingSenderId":"41040333796","appId":"1:41040333796:web:15f2105156a5d7c3d195f2","measurementId":"G-Q04QG51GQC"}');
    let firebaseApp, auth, db;
    let authUser = null;

    const setupFirebase = () => {
        try {
            firebaseApp = firebase.initializeApp(firebaseConfig);
            auth = firebase.auth();
            db = firebase.firestore();
            console.log('Firebase başlatıldı');
        } catch (e) {
            console.error('Firebase başlatılamadı:', e);
            showErrorPage(e);
        }
    }

    // Modal
    const showModal = (title, bodyHtml, onConfirm = null) => {
        UIElements.modalTitle.innerText = title;
        UIElements.modalBody.innerHTML = bodyHtml;
        UIElements.modalContainer.classList.remove('hidden');

        if (onConfirm) {
            UIElements.modalConfirmButton.classList.remove('hidden');
            const newConfirmButton = UIElements.modalConfirmButton.cloneNode(true);
            UIElements.modalConfirmButton.parentNode.replaceChild(newConfirmButton, UIElements.modalConfirmButton);
            newConfirmButton.onclick = () => {
                onConfirm();
                UIElements.modalContainer.classList.add('hidden');
            };
            UIElements.modalConfirmButton = newConfirmButton;
        } else {
            UIElements.modalConfirmButton.classList.add('hidden');
        }
    };

    UIElements.modalCloseButton.onclick = () => {
        UIElements.modalContainer.classList.add('hidden');
    };

    // UI İşlevleri
    const showPage = (pageId) => {
        UIElements.appPages.forEach(page => {
            if (page.id === `${pageId}-page`) {
                page.classList.remove('hidden');
                page.classList.add('active-page');
            } else {
                page.classList.add('hidden');
                page.classList.remove('active-page');
            }
        });
        UIElements.navButtons.forEach(button => {
            if (button.dataset.page === pageId) {
                button.classList.add('bg-gray-700');
            } else {
                button.classList.remove('bg-gray-700');
            }
        });

        // Mobil menüyü kapat
        UIElements.mobileNavContainer.classList.add('hidden');
    };

    // WebSocket
    let wsChart, wsPrice;
    let reconnectIntervalChart = 1000;
    let reconnectIntervalPrice = 1000;

    const setupWebSocket = (symbol, timeframe) => {
        // Eski bağlantıları kapat
        if (wsChart) wsChart.close();
        if (wsPrice) wsPrice.close();

        const chartUrl = `wss://fstream.binance.com/ws/${symbol.toLowerCase()}@kline_${timeframe}`;
        const priceUrl = `wss://fstream.binance.com/ws/${symbol.toLowerCase()}@ticker`;

        // Chart WebSocket
        wsChart = new WebSocket(chartUrl);
        wsChart.onopen = () => {
            console.log(`Chart WebSocket bağlandı: ${symbol} ${timeframe}`);
            reconnectIntervalChart = 1000;
        };
        wsChart.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.k) {
                const kline = data.k;
                // TradingView veya benzeri kütüphane entegrasyonu buraya gelecek.
                // Şimdilik sadece logluyoruz.
            }
        };
        wsChart.onclose = () => {
            console.warn(`Chart WebSocket bağlantısı kesildi. Yeniden bağlanılıyor...`);
            setTimeout(() => {
                setupWebSocket(symbol, timeframe);
            }, reconnectIntervalChart);
            reconnectIntervalChart = Math.min(reconnectIntervalChart * 2, 60000); // 1 dakikaya kadar
        };
        wsChart.onerror = (error) => {
            console.error('Chart WebSocket hatası:', error);
            wsChart.close();
        };

        // Price WebSocket
        wsPrice = new WebSocket(priceUrl);
        wsPrice.onopen = () => {
            console.log(`Price WebSocket bağlandı: ${symbol}`);
            reconnectIntervalPrice = 1000;
        };
        wsPrice.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const price = parseFloat(data.c).toFixed(4); // Fiyatı 4 ondalık basamakla sınırla
            updatePairPrice(symbol, price);
        };
        wsPrice.onclose = () => {
            console.warn(`Price WebSocket bağlantısı kesildi. Yeniden bağlanılıyor...`);
            setTimeout(() => {
                setupWebSocket(symbol, timeframe);
            }, reconnectIntervalPrice);
            reconnectIntervalPrice = Math.min(reconnectIntervalPrice * 2, 60000); // 1 dakikaya kadar
        };
        wsPrice.onerror = (error) => {
            console.error('Price WebSocket hatası:', error);
            wsPrice.close();
        };
    };

    const updatePairPrice = (symbol, price) => {
        const priceElement = document.getElementById('price-value');
        if (priceElement) {
            priceElement.textContent = price;
        }
    };

    // Firebase Auth İşlemleri
    const handleLogin = async (e) => {
        e.preventDefault();
        UIElements.loginError.textContent = '';
        UIElements.loginButton.disabled = true;
        const email = UIElements.loginEmailInput.value;
        const password = UIElements.loginPasswordInput.value;
        try {
            await auth.signInWithEmailAndPassword(email, password);
            // onAuthStateChanged ile yönlendirme yapılacak
        } catch (error) {
            UIElements.loginError.textContent = `Giriş başarısız: ${error.message}`;
            console.error('Giriş hatası:', error);
        } finally {
            UIElements.loginButton.disabled = false;
        }
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        UIElements.registerError.textContent = '';
        UIElements.registerButton.disabled = true;
        const email = UIElements.registerEmailInput.value;
        const password = UIElements.registerPasswordInput.value;
        try {
            const userCredential = await auth.createUserWithEmailAndPassword(email, password);
            await firebase.firestore().collection('users').doc(userCredential.user.uid).set({
                email: email,
                createdAt: firebase.firestore.FieldValue.serverTimestamp()
            });
            // onAuthStateChanged ile yönlendirme yapılacak
        } catch (error) {
            UIElements.registerError.textContent = `Kayıt başarısız: ${error.message}`;
            console.error('Kayıt hatası:', error);
        } finally {
            UIElements.registerButton.disabled = false;
        }
    };

    const handleLogout = async () => {
        try {
            await auth.signOut();
        } catch (error) {
            console.error('Çıkış hatası:', error);
        }
    };

    // Bot İşlevleri
    const fetchBotStatus = async () => {
        if (!authUser) return;
        try {
            const response = await fetch(`${API_BASE_URL}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid: authUser.uid })
            });
            const status = await response.json();
            updateBotStatus(status);
        } catch (error) {
            console.error('Bot durumu çekilemedi:', error);
            updateBotStatus({ is_running: false, status_message: "Bot durumu alınamadı." });
        }
    };

    const updateBotStatus = (status) => {
        if (status.is_running) {
            UIElements.botStatusIndicator.classList.remove('bg-red-500');
            UIElements.botStatusIndicator.classList.add('bg-green-500');
            UIElements.startBotButton.classList.add('hidden');
            UIElements.stopBotButton.classList.remove('hidden');
            UIElements.botStatusMessage.textContent = `Bot Çalışıyor: ${status.status_message}`;
        } else {
            UIElements.botStatusIndicator.classList.remove('bg-green-500');
            UIElements.botStatusIndicator.classList.add('bg-red-500');
            UIElements.startBotButton.classList.remove('hidden');
            UIElements.stopBotButton.classList.add('hidden');
            UIElements.botStatusMessage.textContent = `Bot Durdu: ${status.status_message}`;
        }
    };

    const handleStartBot = async () => {
        const symbol = UIElements.symbolSelect.value;
        const timeframe = UIElements.timeframeSelect.value;
        const leverage = parseInt(UIElements.leverageInput.value);
        const orderSize = parseFloat(UIElements.orderSizeInput.value);
        const stopLoss = parseFloat(UIElements.stopLossInput.value);
        const takeProfit = parseFloat(UIElements.takeProfitInput.value);

        if (!symbol || !timeframe) {
            showModal('Hata', '<p>Lütfen bir sembol ve zaman dilimi seçin.</p>');
            return;
        }

        const payload = {
            uid: authUser.uid,
            symbol,
            timeframe,
            leverage,
            order_size: orderSize,
            stop_loss: stopLoss,
            take_profit: takeProfit
        };

        try {
            const response = await fetch(`${API_BASE_URL}/start-bot`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (result.error) {
                showModal('Hata', `<p>${result.error}</p>`);
            } else {
                updateBotStatus(result);
            }
        } catch (error) {
            console.error('Bot başlatma hatası:', error);
            showModal('Hata', `<p>Bot başlatılırken bir sorun oluştu. Lütfen konsolu kontrol edin.</p>`);
        }
    };

    const handleStopBot = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/stop-bot`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid: authUser.uid })
            });
            const result = await response.json();
            if (result.error) {
                showModal('Hata', `<p>${result.error}</p>`);
            } else {
                updateBotStatus({ is_running: false, status_message: "Bot başarıyla durduruldu." });
            }
        } catch (error) {
            console.error('Bot durdurma hatası:', error);
            showModal('Hata', `<p>Bot durdurulurken bir sorun oluştu. Lütfen konsolu kontrol edin.</p>`);
        }
    };

    // Firebase Auth Değişikliklerini Dinle
    auth.onAuthStateChanged(async (user) => {
        authUser = user;
        if (user) {
            UIElements.authContainer.classList.add('hidden');
            UIElements.appContainer.classList.remove('hidden');
            UIElements.userEmailDisplay.textContent = user.email;
            console.log('Auth state değişti: giriş yapıldı');

            // Kullanıcı API anahtarlarını kontrol et ve ayarları getir
            fetchApiKeys();
            // Bot durumunu çek
            fetchBotStatus();
            // Sembol ve zaman dilimine göre WebSocket bağlantılarını kur
            setupWebSocket(UIElements.symbolSelect.value, UIElements.timeframeSelect.value);

            // Bot ayarlarını Firebase'den yükle (Eğer varsa)
            await loadBotSettings(user.uid);
            await loadTransactions(user.uid);
        } else {
            UIElements.authContainer.classList.remove('hidden');
            UIElements.appContainer.classList.add('hidden');
            showPage('login');
            console.log('Auth state değişti: çıkış yapıldı');
        }
    });

    const loadBotSettings = async (uid) => {
        try {
            const settingsDoc = await db.collection('user_settings').doc(uid).get();
            if (settingsDoc.exists) {
                const settings = settingsDoc.data();
                UIElements.leverageInput.value = settings.leverage;
                UIElements.leverageRangeInput.value = settings.leverage;
                UIElements.orderSizeInput.value = settings.orderSize;
                UIElements.stopLossInput.value = settings.stopLoss;
                UIElements.takeProfitInput.value = settings.takeProfit;
                UIElements.leverageValue.textContent = settings.leverage;
                UIElements.symbolSelect.value = settings.symbol || 'LSKUSDT';
                UIElements.timeframeSelect.value = settings.timeframe || '5m';
            }
        } catch (error) {
            console.error("Bot ayarları yüklenemedi:", error);
        }
    };

    const saveBotSettings = async (uid) => {
        try {
            await db.collection('user_settings').doc(uid).set({
                leverage: parseInt(UIElements.leverageInput.value),
                orderSize: parseFloat(UIElements.orderSizeInput.value),
                stopLoss: parseFloat(UIElements.stopLossInput.value),
                takeProfit: parseFloat(UIElements.takeProfitInput.value),
                symbol: UIElements.symbolSelect.value,
                timeframe: UIElements.timeframeSelect.value,
            }, { merge: true });
            console.log("Bot ayarları kaydedildi.");
        } catch (error) {
            console.error("Bot ayarları kaydedilirken hata:", error);
        }
    };

    const loadTransactions = async (uid) => {
        try {
            const snapshot = await db.collection('users').doc(uid).collection('transactions').orderBy('timestamp', 'desc').get();
            UIElements.historyList.innerHTML = '';
            if (snapshot.empty) {
                UIElements.historyList.innerHTML = '<p class="text-gray-500">Henüz işlem yok.</p>';
                return;
            }
            snapshot.forEach(doc => {
                const data = doc.data();
                const transactionItem = document.createElement('div');
                transactionItem.className = 'bg-gray-800 p-4 rounded-lg flex justify-between items-center';
                const date = data.timestamp ? new Date(data.timestamp.seconds * 1000).toLocaleString() : 'N/A';
                const statusColor = data.status === 'success' ? 'text-green-400' : 'text-red-400';
                transactionItem.innerHTML = `
                    <div class="flex-1">
                        <p class="font-bold text-white">${data.type}</p>
                        <p class="text-sm text-gray-400">Tutar: ${data.amount} USDT</p>
                        <p class="text-xs text-gray-500">${date}</p>
                    </div>
                    <span class="font-semibold ${statusColor}">${data.status}</span>
                `;
                UIElements.historyList.appendChild(transactionItem);
            });
        } catch (error) {
            console.error("İşlemler yüklenirken hata:", error);
            UIElements.historyList.innerHTML = '<p class="text-red-400">İşlem geçmişi yüklenemedi.</p>';
        }
    };

    const fetchApiKeys = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/get-api-keys`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid: authUser.uid })
            });
            const data = await response.json();
            if (data.api_key) {
                UIElements.binanceApiKeyInput.value = data.api_key;
            }
            if (data.api_secret) {
                UIElements.binanceApiSecretInput.value = data.api_secret;
            }
        } catch (error) {
            console.error('API anahtarları çekilemedi:', error);
        }
    };

    const handleSaveApiKeys = async (e) => {
        e.preventDefault();
        UIElements.apiSaveStatus.textContent = 'Kaydediliyor...';
        const apiKey = UIElements.binanceApiKeyInput.value;
        const apiSecret = UIElements.binanceApiSecretInput.value;
        const payload = {
            uid: authUser.uid,
            api_key: apiKey,
            api_secret: apiSecret
        };
        try {
            const response = await fetch(`${API_BASE_URL}/save-api-keys`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (result.success) {
                UIElements.apiSaveStatus.textContent = 'Anahtarlar başarıyla kaydedildi!';
                UIElements.apiSaveStatus.classList.remove('text-red-500');
                UIElements.apiSaveStatus.classList.add('text-green-500');
            } else {
                UIElements.apiSaveStatus.textContent = `Hata: ${result.error}`;
                UIElements.apiSaveStatus.classList.remove('text-green-500');
                UIElements.apiSaveStatus.classList.add('text-red-500');
            }
        } catch (error) {
            UIElements.apiSaveStatus.textContent = 'Kaydetme hatası. Lütfen konsolu kontrol edin.';
            UIElements.apiSaveStatus.classList.remove('text-green-500');
            UIElements.apiSaveStatus.classList.add('text-red-500');
            console.error('API anahtarlarını kaydetme hatası:', error);
        }
    };

    const fetchPaymentAddress = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/get-payment-address`);
            const data = await response.json();
            if (data.address) {
                UIElements.paymentAddress.textContent = data.address;
                const qrCodeUrl = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${data.address}`;
                UIElements.paymentQrCode.innerHTML = `<img src="${qrCodeUrl}" alt="QR Kod">`;
            }
        } catch (error) {
            console.error('Ödeme adresi çekilemedi:', error);
        }
    };

    const handleError = (error) => {
        if (error.code === 'auth/invalid-email' || error.code === 'auth/wrong-password') {
            return 'Geçersiz e-posta veya parola.';
        }
        if (error.code === 'auth/email-already-in-use') {
            return 'Bu e-posta adresi zaten kullanılıyor.';
        }
        if (error.code === 'auth/user-not-found') {
            return 'Kullanıcı bulunamadı.';
        }
        return 'Bir hata oluştu. Lütfen tekrar deneyin.';
    };

    const showErrorPage = (error) => {
        UIElements.appContainer.innerHTML = `
            <div class="h-screen w-screen flex items-center justify-center bg-gray-900 text-white p-4">
                <div class="text-center">
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
    };

    const initializeApp = () => {
        console.log('Uygulama başlatılıyor...');
        try {
            setupFirebase();
            console.log('Event listener\'lar kuruluyor');

            // Auth form actions
            UIElements.loginButton.addEventListener('click', handleLogin);
            UIElements.registerButton.addEventListener('click', handleRegister);
            UIElements.showRegisterLink.addEventListener('click', () => {
                UIElements.loginCard.classList.add('hidden');
                UIElements.registerCard.classList.remove('hidden');
            });
            UIElements.showLoginLink.addEventListener('click', () => {
                UIElements.registerCard.classList.add('hidden');
                UIElements.loginCard.classList.remove('hidden');
            });

            // Navigation
            UIElements.navButtons.forEach(button => {
                button.addEventListener('click', () => {
                    const pageId = button.dataset.page;
                    showPage(pageId);
                    if (pageId === 'wallet') fetchPaymentAddress();
                    if (pageId === 'history' && authUser) loadTransactions(authUser.uid);
                    if (pageId === 'dashboard' && authUser) fetchBotStatus();
                });
            });

            // Bot Actions
            UIElements.startBotButton.addEventListener('click', handleStartBot);
            UIElements.stopBotButton.addEventListener('click', handleStopBot);
            UIElements.leverageRangeInput.addEventListener('input', (e) => {
                UIElements.leverageInput.value = e.target.value;
                UIElements.leverageValue.textContent = e.target.value;
            });
            UIElements.leverageInput.addEventListener('input', (e) => {
                let value = parseInt(e.target.value);
                if (value < 1) value = 1;
                if (value > 125) value = 125;
                UIElements.leverageRangeInput.value = value;
                UIElements.leverageValue.textContent = value;
                e.target.value = value;
            });
            UIElements.logoutButton.addEventListener('click', handleLogout);

            UIElements.symbolSelect.addEventListener('change', () => {
                if (authUser) {
                    setupWebSocket(UIElements.symbolSelect.value, UIElements.timeframeSelect.value);
                    saveBotSettings(authUser.uid);
                }
            });
            UIElements.timeframeSelect.addEventListener('change', () => {
                if (authUser) {
                    setupWebSocket(UIElements.symbolSelect.value, UIElements.timeframeSelect.value);
                    saveBotSettings(authUser.uid);
                }
            });
            document.querySelectorAll('#dashboard-page input').forEach(input => {
                input.addEventListener('change', () => {
                    if (authUser) saveBotSettings(authUser.uid);
                });
            });


            // Settings actions
            UIElements.apiForm.addEventListener('submit', handleSaveApiKeys);

            // Wallet actions
            UIElements.copyAddressButton.addEventListener('click', () => {
                const address = UIElements.paymentAddress.textContent;
                if (address) {
                    navigator.clipboard.writeText(address).then(() => {
                        showModal('Kopyalandı!', '<p>Adres panoya kopyalandı.</p>');
                    }).catch(err => {
                        console.error('Kopyalama hatası:', err);
                        showModal('Hata', '<p>Adres panoya kopyalanamadı.</p>');
                    });
                }
            });

            // Mobile nav toggle
            UIElements.mobileNavToggle.addEventListener('click', () => {
                UIElements.mobileNavContainer.classList.toggle('hidden');
            });

            console.log('Uygulama başarıyla başlatıldı');
        } catch (error) {
            console.error('Uygulama başlatma hatası:', error);
            showErrorPage(error);
        }
    };

    initializeApp();
});
