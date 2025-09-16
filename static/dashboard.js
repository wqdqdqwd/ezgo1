// Global variables
let firebaseApp = null;
let auth = null;
let database = null;
let currentUser = null;
let refreshInterval = null;
let authToken = null;
let botStatusListener = null;
let settingsListener = null;

// API Base URL - Production için doğru URL
const API_BASE_URL = window.location.origin + '/api';

// DOM Elements - Güvenli erişim ile
const elements = {
    get: (id) => {
        const element = document.getElementById(id);
        if (!element) {
            console.warn(`Element not found: ${id}`);
        }
        return element;
    },

    // Cache variables
    loadingScreen: null,
    dashboard: null,
    hamburgerMenu: null,
    mobileMenu: null,
    mobileMenuClose: null,

    // User info
    userName: null,
    subscriptionBadge: null,
    subscriptionText: null,
    subStatusBadge: null,
    daysRemaining: null,
    subscriptionNote: null,

    // Bot status
    statusDot: null,
    statusText: null,
    statusMessageText: null,
    accountBalance: null,
    positionPnl: null,
    
    // API
    apiStatusIndicator: null,
    manageApiBtn: null,
    mobileApiBtn: null,
    apiModal: null,
    apiModalClose: null,
    apiForm: null,
    apiKey: null,
    apiSecret: null,
    apiTestnet: null,
    saveApiBtn: null,
    cancelApiBtn: null,
    apiTestResult: null,

    // Trading settings
    tradingSettings: null,
    controlButtons: null,
    symbolSelect: null,
    leverageInput: null,
    orderSizeInput: null,
    stopLossInput: null,
    takeProfitInput: null,
    startBotBtn: null,
    stopBotBtn: null,
    manageApiBtn: null,
    showApiModal: null,

    // Payment
    paymentAddress: null,
    copyAddressBtn: null,
    transactionHash: null,
    confirmPaymentBtn: null,
    paymentMessage: null,

    // Modals
    confirmModal: null,
    confirmModalMessage: null,
    confirmModalYes: null,
    confirmModalNo: null,
    
    // Support
    supportBtn: null,
    supportModal: null,
    supportModalClose: null,
    supportForm: null,
    supportMessage: null,
    sendSupportBtn: null,

    // Charts
    chart: null,

    // Log & History
    logContainer: null,
    tradesTableBody: null,

    // Other
    darkModeToggle: null,
    logoutBtn: null,
    userIdDisplay: null,
};

// --- UTILS ---
function showToast(message, type = 'info') {
    const toast = elements.get('toast');
    const toastMessage = elements.get('toast-message');
    const toastIcon = elements.get('toast-icon');

    if (!toast || !toastMessage || !toastIcon) return;

    toastMessage.textContent = message;
    toast.className = `toast show ${type}`;
    toastIcon.className = `toast-icon fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-times-circle' : 'fa-info-circle'}`;

    setTimeout(() => {
        toast.className = toast.className.replace('show', '');
    }, 5000);
}

function showConfirm(message, onConfirm) {
    if (!elements.confirmModal) return;
    elements.confirmModalMessage.textContent = message;
    elements.confirmModal.style.display = 'block';

    const handleConfirm = () => {
        onConfirm();
        elements.confirmModal.style.display = 'none';
        elements.confirmModalYes.removeEventListener('click', handleConfirm);
        elements.confirmModalNo.removeEventListener('click', handleCancel);
    };

    const handleCancel = () => {
        elements.confirmModal.style.display = 'none';
        elements.confirmModalYes.removeEventListener('click', handleConfirm);
        elements.confirmModalNo.removeEventListener('click', handleCancel);
    };

    elements.confirmModalYes.addEventListener('click', handleConfirm);
    elements.confirmModalNo.addEventListener('click', handleCancel);
}

function toggleModal(modalId, show) {
    const modal = elements.get(modalId);
    if (modal) {
        modal.style.display = show ? 'flex' : 'none';
    }
}

function bindDOM() {
    for (const key in elements) {
        if (key !== 'get') {
            elements[key] = elements.get(key)
        }
    }
}

function formatDate(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString('tr-TR', {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function updateBotStatusUI(statusData) {
    const isRunning = statusData?.is_running;
    const message = statusData?.status_message || 'Durum bilgisi alınamadı.';
    const accountBalance = statusData?.account_balance !== undefined ? parseFloat(statusData.account_balance).toFixed(2) : '---';
    const positionPnl = statusData?.position_pnl !== undefined ? parseFloat(statusData.position_pnl).toFixed(2) : '---';

    if (elements.statusDot) {
        elements.statusDot.className = `status-dot ${isRunning ? 'running' : 'stopped'}`;
    }
    if (elements.statusText) {
        elements.statusText.textContent = isRunning ? 'Bot Çalışıyor' : 'Bot Durduruldu';
    }
    if (elements.statusMessageText) {
        elements.statusMessageText.textContent = message;
    }
    if (elements.accountBalance) {
        elements.accountBalance.textContent = accountBalance;
    }
    if (elements.positionPnl) {
        elements.positionPnl.textContent = positionPnl;
        if (positionPnl !== '---') {
            elements.positionPnl.classList.toggle('text-green-500', positionPnl >= 0);
            elements.positionPnl.classList.toggle('text-red-500', positionPnl < 0);
        }
    }
    if (elements.startBotBtn && elements.stopBotBtn) {
        elements.startBotBtn.disabled = isRunning;
        elements.stopBotBtn.disabled = !isRunning;
    }
}

// --- FIREBASE AND AUTH ---
async function initializeFirebase() {
    try {
        const firebaseConfig = JSON.parse(__firebase_config);
        firebaseApp = firebase.initializeApp(firebaseConfig);
        auth = firebase.auth();
        database = firebase.database();
        
        await new Promise((resolve) => {
            const unsub = auth.onAuthStateChanged(user => {
                currentUser = user;
                if (!currentUser) {
                    window.location.href = '/login';
                } else {
                    if (elements.userIdDisplay) {
                        elements.userIdDisplay.textContent = currentUser.uid;
                    }
                    resolve();
                }
                unsub(); // Tek bir kez dinle
            });
        });

    } catch (error) {
        console.error("Firebase başlatılamadı:", error);
        showToast("Sistem başlatılamadı. Lütfen sayfayı yenileyin.", "error");
        elements.loadingScreen.innerHTML = `
            <div class="loading-content">
                <div class="loading-logo">
                    <i class="fas fa-exclamation-triangle" style="color: var(--danger);"></i>
                    <span>Hata</span>
                </div>
                <p>Uygulama başlatılırken hata oluştu. İnternet bağlantınızı kontrol edin.</p>
                <button class="btn btn-primary" onclick="location.reload()">Tekrar Dene</button>
            </div>
        `;
    }
}

// --- FIREBASE REALTIME DB LISTENERS ---
async function setupDatabaseListeners() {
    if (!currentUser || !database) return;

    const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
    const userDbRef = database.ref(`artifacts/${appId}/users/${currentUser.uid}`);

    // Bot durumu dinleme
    if (botStatusListener) userDbRef.child('bot_status').off('value', botStatusListener);
    botStatusListener = userDbRef.child('bot_status').on('value', (snapshot) => {
        const statusData = snapshot.val();
        console.log("Bot durumu güncellendi:", statusData);
        updateBotStatusUI(statusData);
    });

    // Ayarları dinleme
    if (settingsListener) userDbRef.child('settings').off('value', settingsListener);
    settingsListener = userDbRef.child('settings').on('value', (snapshot) => {
        const settingsData = snapshot.val();
        console.log("Ayarlar güncellendi:", settingsData);
        loadSettingsToUI(settingsData);
    });

    // İşlem geçmişini dinleme
    const tradesRef = userDbRef.child('trades').orderByKey().limitToLast(50);
    tradesRef.on('child_added', (snapshot) => {
        const trade = snapshot.val();
        addTradeToUI(trade);
    });
}

function loadSettingsToUI(settings) {
    if (!settings) return;

    if (elements.apiKey) elements.apiKey.value = settings.apiKey || '';
    if (elements.apiSecret) elements.apiSecret.value = settings.apiSecret || '';
    if (elements.apiTestnet) elements.apiTestnet.checked = settings.testnet || false;

    if (elements.symbolSelect) elements.symbolSelect.value = settings.symbol || 'BTCUSDT';
    if (elements.leverageInput) elements.leverageInput.value = settings.leverage || 10;
    if (elements.orderSizeInput) elements.orderSizeInput.value = settings.orderSize || 35;
    if (elements.stopLossInput) elements.stopLossInput.value = settings.stopLoss || 0.8;
    if (elements.takeProfitInput) elements.takeProfitInput.value = settings.takeProfit || 1;
}

function addTradeToUI(trade) {
    if (!elements.tradesTableBody) return;

    const row = document.createElement('tr');
    row.innerHTML = `
        <td class="px-6 py-4 whitespace-nowrap">${formatDate(trade.timestamp)}</td>
        <td class="px-6 py-4 whitespace-nowrap">${trade.symbol}</td>
        <td class="px-6 py-4 whitespace-nowrap">
            <span class="status-badge ${trade.side === 'LONG' ? 'bg-green-500' : 'bg-red-500'}">
                ${trade.side}
            </span>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">${parseFloat(trade.entryPrice).toFixed(2)}</td>
        <td class="px-6 py-4 whitespace-nowrap">${parseFloat(trade.exitPrice).toFixed(2)}</td>
        <td class="px-6 py-4 whitespace-nowrap">${parseFloat(trade.realizedPnl).toFixed(2)}</td>
    `;
    elements.tradesTableBody.prepend(row);
}


// --- API FUNCTIONS ---
async function saveAndTestAPI(event) {
    event.preventDefault();
    if (!currentUser) return;

    const apiKey = elements.apiKey.value.trim();
    const apiSecret = elements.apiSecret.value.trim();
    const testnet = elements.apiTestnet.checked;

    if (!apiKey || !apiSecret) {
        showToast("API anahtar ve gizli anahtar boş bırakılamaz.", "error");
        return;
    }

    if (elements.saveApiBtn) {
        elements.saveApiBtn.disabled = true;
        elements.saveApiBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Kaydediliyor...';
    }

    const payload = {
        apiKey,
        apiSecret,
        testnet
    };

    try {
        // Ayarları Realtime Database'e kaydet
        const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
        await database.ref(`artifacts/${appId}/users/${currentUser.uid}/settings`).update(payload);

        showToast("API ayarları kaydedildi.", "success");
        toggleModal('api-modal', false);
    } catch (error) {
        console.error("API ayarları kaydedilirken hata:", error);
        showToast("API ayarları kaydedilemedi: " + error.message, "error");
    } finally {
        if (elements.saveApiBtn) {
            elements.saveApiBtn.disabled = false;
            elements.saveApiBtn.innerHTML = '<i class="fas fa-save"></i> Kaydet ve Test Et';
        }
    }
}


async function startBot() {
    if (!currentUser) return;
    
    // UI'dan ayarları al
    const symbol = elements.symbolSelect.value;
    const leverage = parseInt(elements.leverageInput.value, 10);
    const orderSize = parseFloat(elements.orderSizeInput.value);
    const stopLoss = parseFloat(elements.stopLossInput.value);
    const takeProfit = parseFloat(elements.takeProfitInput.value);

    const payload = {
        symbol,
        leverage,
        orderSize,
        stopLoss,
        takeProfit
    };

    try {
        showToast("Bot başlatılıyor...", "info");
        const response = await fetch(`${API_BASE_URL}/start-bot`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok) {
            showToast(result.message, "success");
        } else {
            showToast(result.detail || result.message, "error");
        }
    } catch (error) {
        console.error("Bot başlatma hatası:", error);
        showToast("Bot başlatılırken bir hata oluştu: " + error.message, "error");
    }
}

async function stopBot() {
    if (!currentUser) return;
    
    showConfirm("Botu durdurmak istediğinize emin misiniz?", async () => {
        try {
            showToast("Bot durduruluyor...", "info");
            const response = await fetch(`${API_BASE_URL}/stop-bot`, {
                method: 'POST'
            });

            const result = await response.json();

            if (response.ok) {
                showToast(result.message, "success");
            } else {
                showToast(result.detail || result.message, "error");
            }
        } catch (error) {
            console.error("Bot durdurma hatası:", error);
            showToast("Bot durdurulurken bir hata oluştu: " + error.message, "error");
        }
    });
}

// --- EVENT LISTENERS ---
function initializeEventListeners() {
    // Hamburger menü
    if (elements.hamburgerMenu) {
        elements.hamburgerMenu.addEventListener('click', () => {
            if (elements.mobileMenu) elements.mobileMenu.classList.add('active');
        });
    }

    if (elements.mobileMenuClose) {
        elements.mobileMenuClose.addEventListener('click', () => {
            if (elements.mobileMenu) elements.mobileMenu.classList.remove('active');
        });
    }
    
    // API Modal
    if (elements.manageApiBtn) {
        elements.manageApiBtn.addEventListener('click', () => toggleModal('api-modal', true));
    }
    if (elements.apiModalClose) {
        elements.apiModalClose.addEventListener('click', () => toggleModal('api-modal', false));
    }
    if (elements.cancelApiBtn) {
        elements.cancelApiBtn.addEventListener('click', () => toggleModal('api-modal', false));
    }

    // Support Modal
    if (elements.supportBtn) {
        elements.supportBtn.addEventListener('click', () => toggleModal('support-modal', true));
    }
    if (elements.supportModalClose) {
        elements.supportModalClose.addEventListener('click', () => toggleModal('support-modal', false));
    }
    if (elements.cancelSupportBtn) {
        elements.cancelSupportBtn.addEventListener('click', () => toggleModal('support-modal', false));
    }
    
    // Form actions
    if (elements.apiForm) {
        elements.apiForm.addEventListener('submit', saveAndTestAPI);
    }
    
    if (elements.startBotBtn) {
        elements.startBotBtn.addEventListener('click', startBot);
    }
    
    if (elements.stopBotBtn) {
        elements.stopBotBtn.addEventListener('click', stopBot);
    }

    // Logout
    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                await auth.signOut();
                window.location.href = '/';
            } catch (error) {
                console.error("Çıkış hatası:", error);
                showToast("Çıkış yapılırken bir hata oluştu.", "error");
            }
        });
    }

    // Toggle Dark Mode
    if (elements.darkModeToggle) {
        elements.darkModeToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
            }
        });
    }
}

// --- INITIALIZATION ---
async function initializeDashboard() {
    try {
        // 1. DOM elemanlarını bağla
        bindDOM();

        // 2. Firebase ve kimlik doğrulama başlat
        await initializeFirebase();
        
        // 3. Veritabanı dinleyicilerini kur
        await setupDatabaseListeners();

        // 4. Loading ekranını gizle, dashboard'u göster
        if (elements.loadingScreen) elements.loadingScreen.style.display = 'none';
        if (elements.dashboard) elements.dashboard.classList.remove('hidden');

        showToast("Dashboard başarıyla yüklendi!", "success");

        // 5. Olay dinleyicilerini başlat
        initializeEventListeners();
        
        // 6. Başlangıç teması kontrolü
        if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
            if (elements.darkModeToggle) elements.darkModeToggle.checked = true;
        } else {
            document.documentElement.classList.remove('dark');
            if (elements.darkModeToggle) elements.darkModeToggle.checked = false;
        }

    } catch (error) {
        console.error("Dashboard başlatma hatası:", error);
        if (elements.loadingScreen) {
            elements.loadingScreen.innerHTML = `
                <div class="loading-content">
                    <div class="loading-logo">
                        <i class="fas fa-exclamation-triangle" style="color: var(--danger);"></i>
                        <span>Hata</span>
                    </div>
                    <p>Dashboard başlatılırken kritik bir hata oluştu. Lütfen konsolu kontrol edin.</p>
                    <button class="btn btn-primary" onclick="location.reload()">Tekrar Dene</button>
                </div>
            `;
        }
    }
}

// Başlangıç
document.addEventListener('DOMContentLoaded', initializeDashboard);
