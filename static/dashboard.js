// Global variables
let firebaseApp = null;
let auth = null;
let database = null;
let currentUser = null;
let refreshInterval = null;
let authToken = null;

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
    timeframeSelect: null,
    leverageSelect: null,
    orderSize: null,
    stopLoss: null,
    takeProfit: null,
    
    // Control buttons
    startBotBtn: null,
    stopBotBtn: null,
    
    // Account stats
    totalBalance: null,
    totalTrades: null,
    winRate: null,
    totalPnl: null,
    
    // Purchase modal
    mobilePurchaseBtn: null,
    purchaseModal: null,
    purchaseModalClose: null,
    paymentAmount: null,
    paymentAddress: null,
    copyAddressBtn: null,
    transactionHash: null,
    confirmPaymentBtn: null,
    cancelPurchaseBtn: null,
    
    // Support modal
    mobileSupportBtn: null,
    supportModal: null,
    supportModalClose: null,
    supportSubject: null,
    supportMessage: null,
    sendSupportBtn: null,
    cancelSupportBtn: null,
    
    // Logout
    logoutBtn: null,
    mobileLogoutBtn: null,
    
    // Toast
    toast: null,
    toastMessage: null,
    toastClose: null,
    
    // Initialize all elements
    init: function() {
        this.loadingScreen = this.get('loading-screen');
        this.dashboard = this.get('dashboard');
        this.hamburgerMenu = this.get('hamburger-menu');
        this.mobileMenu = this.get('mobile-menu');
        this.mobileMenuClose = this.get('mobile-menu-close');
        
        // User info
        this.userName = this.get('user-name');
        this.subscriptionBadge = this.get('subscription-badge');
        this.subscriptionText = this.get('subscription-text');
        this.subStatusBadge = this.get('sub-status-badge');
        this.daysRemaining = this.get('days-remaining');
        this.subscriptionNote = this.get('subscription-note');
        
        // Bot status
        this.statusDot = this.get('status-dot');
        this.statusText = this.get('status-text');
        this.statusMessageText = this.get('status-message-text');
        
        // API
        this.apiStatusIndicator = this.get('api-status-indicator');
        this.manageApiBtn = this.get('manage-api-btn');
        this.mobileApiBtn = this.get('mobile-api-btn');
        this.apiModal = this.get('api-modal');
        this.apiModalClose = this.get('api-modal-close');
        this.apiForm = this.get('api-form');
        this.apiKey = this.get('api-key');
        this.apiSecret = this.get('api-secret');
        this.apiTestnet = this.get('api-testnet');
        this.saveApiBtn = this.get('save-api-btn');
        this.cancelApiBtn = this.get('cancel-api-btn');
        this.apiTestResult = this.get('api-test-result');
        
        // Trading settings
        this.tradingSettings = this.get('trading-settings');
        this.controlButtons = this.get('control-buttons');
        this.symbolSelect = this.get('symbol-select');
        this.timeframeSelect = this.get('timeframe-select');
        this.leverageSelect = this.get('leverage-select');
        this.orderSize = this.get('order-size');
        this.stopLoss = this.get('stop-loss');
        this.takeProfit = this.get('take-profit');
        
        // Control buttons
        this.startBotBtn = this.get('start-bot-btn');
        this.stopBotBtn = this.get('stop-bot-btn');
        
        // Account stats
        this.totalBalance = this.get('total-balance');
        this.totalTrades = this.get('total-trades');
        this.winRate = this.get('win-rate');
        this.totalPnl = this.get('total-pnl');
        
        // Purchase modal
        this.mobilePurchaseBtn = this.get('mobile-purchase-btn');
        this.purchaseModal = this.get('purchase-modal');
        this.purchaseModalClose = this.get('purchase-modal-close');
        this.paymentAmount = this.get('payment-amount');
        this.paymentAddress = this.get('payment-address');
        this.copyAddressBtn = this.get('copy-address-btn');
        this.transactionHash = this.get('transaction-hash');
        this.confirmPaymentBtn = this.get('confirm-payment-btn');
        this.cancelPurchaseBtn = this.get('cancel-purchase-btn');
        
        // Support modal
        this.mobileSupportBtn = this.get('mobile-support-btn');
        this.supportModal = this.get('support-modal');
        this.supportModalClose = this.get('support-modal-close');
        this.supportSubject = this.get('support-subject');
        this.supportMessage = this.get('support-message');
        this.sendSupportBtn = this.get('send-support-btn');
        this.cancelSupportBtn = this.get('cancel-support-btn');
        
        // Logout
        this.logoutBtn = this.get('logout-btn');
        this.mobileLogoutBtn = this.get('mobile-logout-btn');
        
        // Toast
        this.toast = this.get('toast');
        this.toastMessage = this.get('toast-message');
        this.toastClose = this.get('toast-close');
    }
};

// TOKEN YÖNETİMİ - Backend ile uyumlu
async function getValidToken() {
    try {
        if (!currentUser) {
            throw new Error('User not authenticated');
        }
        
        // Mevcut token'ı kontrol et
        if (authToken) {
            try {
                const tokenParts = authToken.split('.');
                if (tokenParts.length === 3) {
                    const payload = JSON.parse(atob(tokenParts[1]));
                    const now = Math.floor(Date.now() / 1000);
                    
                    // Token 5 dakikadan fazla süresi varsa kullan
                    if (payload.exp && (payload.exp - now) > 300) {
                        return authToken;
                    }
                }
            } catch (e) {
                console.warn('Token parse error, getting new token:', e);
            }
        }
        
        // Yeni token al
        console.log('Getting fresh token...');
        authToken = await currentUser.getIdToken(true);
        localStorage.setItem('authToken', authToken);
        console.log('Fresh token obtained');
        return authToken;
        
    } catch (error) {
        console.error('Token error:', error);
        throw new Error('Authentication failed - please login again');
    }
}

// API İSTEK FONKSİYONU - Backend API'sine uygun
async function makeAuthenticatedRequest(endpoint, options = {}) {
    try {
        const token = await getValidToken();
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        };
        
        const finalOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...(options.headers || {})
            }
        };
        
        const fullUrl = `${API_BASE_URL}${endpoint}`;
        console.log('Making request to:', fullUrl);
        
        const response = await fetch(fullUrl, finalOptions);
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            let errorData;
            try {
                const errorText = await response.text();
                console.log('Error response text:', errorText);
                errorData = JSON.parse(errorText);
            } catch (e) {
                errorData = { detail: `HTTP ${response.status}: ${response.statusText}` };
            }
            
            if (response.status === 401) {
                console.log('401 error - clearing token and requiring re-auth');
                authToken = null;
                localStorage.removeItem('authToken');
                throw new Error('Session expired, please try again');
            }
            
            throw new Error(errorData.detail || errorData.message || `Request failed with status ${response.status}`);
        }
        
        const responseData = await response.json();
        console.log('Success response:', responseData);
        return responseData;
        
    } catch (error) {
        console.error('API Request failed:', error);
        throw error;
    }
}

// UTILITY FUNCTIONS
function showToast(message, type = 'info', duration = 5000) {
    if (!elements.toast || !elements.toastMessage) return;
    
    const toast = elements.toast;
    const toastIcon = toast.querySelector('.toast-icon');
    
    const iconClasses = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    
    const colors = {
        success: 'var(--success-color)',
        error: 'var(--danger-color)',
        warning: 'var(--warning-color)',
        info: 'var(--info-color)'
    };
    
    if (toastIcon) {
        toastIcon.className = `toast-icon ${iconClasses[type] || iconClasses.info}`;
        toastIcon.style.color = colors[type] || colors.info;
    }
    
    elements.toastMessage.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

function formatCurrency(amount) {
    return parseFloat(amount || 0).toFixed(2) + ' USDT';
}

function formatPercentage(value) {
    const num = parseFloat(value || 0);
    return (num >= 0 ? '+' : '') + num.toFixed(2) + '%';
}

// FIREBASE INITIALIZATION
async function initializeFirebase() {
    try {
        const response = await fetch(`${API_BASE_URL}/firebase-config`);
        const firebaseConfig = await response.json();
        
        firebaseApp = firebase.initializeApp(firebaseConfig);
        auth = firebase.auth();
        database = firebase.database();
        
        return true;
    } catch (error) {
        console.error('Firebase initialization failed:', error);
        return false;
    }
}

// AUTHENTICATION
async function checkAuth() {
    return new Promise((resolve) => {
        auth.onAuthStateChanged(async (user) => {
            if (user) {
                currentUser = user;
                console.log('User authenticated:', user.uid);
                
                try {
                    authToken = await user.getIdToken(true);
                    console.log('Token obtained successfully');
                    localStorage.setItem('authToken', authToken);
                    
                    await loadUserData();
                    resolve(true);
                } catch (tokenError) {
                    console.error('Token error:', tokenError);
                    showToast('Token alınamadı, tekrar giriş yapın', 'error');
                    logout();
                    resolve(false);
                }
            } else {
                console.log('User not authenticated, redirecting to login');
                window.location.href = '/login.html';
                resolve(false);
            }
        });
    });
}

// USER DATA LOADING - Backend API kullanarak
async function loadUserData() {
    try {
        if (!currentUser) return;
        
        // Backend'den kullanıcı profilini al
        const profileResponse = await makeAuthenticatedRequest('/user/profile', {
            method: 'GET'
        });
        
        if (profileResponse.success && profileResponse.profile) {
            updateUserInfo(profileResponse.profile);
            await loadAccountStats();
            await checkApiStatus(profileResponse.profile);
            await getBotStatus();
            await loadPaymentInfo();
        }
    } catch (error) {
        console.error('Error loading user data:', error);
        showToast('Kullanıcı verileri yüklenirken hata oluştu', 'error');
    }
}

// UPDATE USER INFO - Backend'den gelen veri ile
function updateUserInfo(userData) {
    if (elements.userName) {
        elements.userName.textContent = userData.email || 'Kullanıcı';
    }
    
    const subscriptionActive = userData.subscription_active || false;
    const subscriptionStatus = userData.subscription_status || 'trial';
    const subscriptionExpiry = userData.subscription_expiry;
    
    if (elements.subscriptionText) {
        elements.subscriptionText.textContent = subscriptionActive ? 'Premium' : 'Deneme';
    }
    
    if (subscriptionExpiry && elements.daysRemaining && elements.subscriptionNote) {
        const expiryDate = new Date(subscriptionExpiry);
        const today = new Date();
        const daysLeft = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));
        
        elements.daysRemaining.textContent = daysLeft > 0 ? `${daysLeft} gün` : 'Süresi dolmuş';
        
        if (daysLeft <= 0) {
            elements.subscriptionNote.textContent = 'Abonelik süresi dolmuş. Premium satın alın.';
            elements.subscriptionNote.style.color = 'var(--danger-color)';
        } else if (daysLeft <= 3) {
            elements.subscriptionNote.textContent = 'Aboneliğiniz yakında sona erecek.';
            elements.subscriptionNote.style.color = 'var(--warning-color)';
        } else {
            elements.subscriptionNote.textContent = 'Aboneliğiniz aktif durumda.';
            elements.subscriptionNote.style.color = 'var(--success-color)';
        }
    }
}

// LOAD ACCOUNT STATS - İşlem geçmişinden hesapla
async function loadAccountStats() {
    try {
        const tradesResponse = await makeAuthenticatedRequest('/user/trades', {
            method: 'GET'
        });
        
        if (tradesResponse.success && tradesResponse.trades) {
            const trades = tradesResponse.trades;
            
            // İstatistikleri hesapla
            let totalTrades = trades.length;
            let winningTrades = 0;
            let totalPnl = 0;
            
            trades.forEach(trade => {
                const pnl = parseFloat(trade.pnl) || 0;
                totalPnl += pnl;
                if (pnl > 0) winningTrades++;
            });
            
            const winRate = totalTrades > 0 ? ((winningTrades / totalTrades) * 100).toFixed(1) : '0';
            
            // UI'yi güncelle
            if (elements.totalTrades) {
                elements.totalTrades.textContent = totalTrades.toString();
            }
            if (elements.winRate) {
                elements.winRate.textContent = winRate + '%';
            }
            if (elements.totalPnl) {
                elements.totalPnl.textContent = formatCurrency(totalPnl);
                elements.totalPnl.style.color = totalPnl >= 0 ? 'var(--success-color)' : 'var(--danger-color)';
            }
            
            // Bakiye bilgisi mock (gerçek Binance API'den alınabilir)
            if (elements.totalBalance) {
                elements.totalBalance.textContent = '--- USDT';
            }
        }
    } catch (error) {
        console.error('Error loading account stats:', error);
        // Hata durumunda varsayılan değerler
        if (elements.totalBalance) elements.totalBalance.textContent = '--- USDT';
        if (elements.totalTrades) elements.totalTrades.textContent = '0';
        if (elements.winRate) elements.winRate.textContent = '0%';
        if (elements.totalPnl) elements.totalPnl.textContent = '0.00 USDT';
    }
}

// API STATUS CHECK - Backend'den kontrol
async function checkApiStatus(userData = null) {
    try {
        if (!userData) {
            const profileResponse = await makeAuthenticatedRequest('/user/profile', {
                method: 'GET'
            });
            userData = profileResponse.success ? profileResponse.profile : null;
        }
        
        if (userData && userData.has_api_keys) {
            showApiConnected();
            if (elements.tradingSettings) {
                elements.tradingSettings.style.display = 'block';
            }
            if (elements.controlButtons) {
                elements.controlButtons.style.display = 'grid';
            }
            if (elements.statusMessageText) {
                elements.statusMessageText.textContent = 'API bağlantısı aktif. Bot ayarlarını yapın.';
            }
        } else {
            showApiNotConfigured();
        }
    } catch (error) {
        console.error('Error checking API status:', error);
        showApiError('API durumu kontrol edilemedi');
    }
}

function showApiNotConfigured() {
    if (elements.apiStatusIndicator) {
        elements.apiStatusIndicator.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <span>API anahtarları gerekli</span>
        `;
        elements.apiStatusIndicator.className = 'api-status-indicator error';
    }
    
    if (elements.manageApiBtn) {
        elements.manageApiBtn.textContent = 'API Anahtarlarını Ekle';
    }
    
    if (elements.statusMessageText) {
        elements.statusMessageText.textContent = 'Bot\'u çalıştırmak için API anahtarlarınızı eklemelisiniz.';
    }
}

function showApiConnected() {
    if (elements.apiStatusIndicator) {
        elements.apiStatusIndicator.innerHTML = `
            <i class="fas fa-check-circle"></i>
            <span>API bağlantısı aktif</span>
        `;
        elements.apiStatusIndicator.className = 'api-status-indicator connected';
    }
    
    if (elements.manageApiBtn) {
        elements.manageApiBtn.textContent = 'API Ayarlarını Düzenle';
    }
}

function showApiError(message) {
    if (elements.apiStatusIndicator) {
        elements.apiStatusIndicator.innerHTML = `
            <i class="fas fa-times-circle"></i>
            <span>API bağlantı hatası</span>
        `;
        elements.apiStatusIndicator.className = 'api-status-indicator error';
    }
    
    if (elements.manageApiBtn) {
        elements.manageApiBtn.textContent = 'API Anahtarlarını Düzenle';
    }
    
    if (elements.statusMessageText) {
        elements.statusMessageText.textContent = message;
    }
}

// BOT STATUS - Backend API'den
async function getBotStatus() {
    try {
        const result = await makeAuthenticatedRequest('/bot/status', {
            method: 'GET'
        });
        
        if (result.success && result.status) {
            updateBotStatus(result.status.is_running || false, result.status);
        } else {
            updateBotStatus(false);
        }
        
    } catch (error) {
        console.error('Bot status error:', error);
        updateBotStatus(false);
        
        if (!error.message.includes('Session expired')) {
            console.warn('Bot durumu kontrol edilemedi:', error.message);
        }
    }
}

function updateBotStatus(isRunning, statusData = null) {
    if (!elements.statusDot || !elements.statusText || !elements.statusMessageText) return;
    
    if (isRunning) {
        elements.statusDot.classList.add('active');
        elements.statusText.textContent = 'Çalışıyor';
        elements.statusMessageText.textContent = statusData?.status_message || 'Bot aktif olarak çalışıyor.';
        
        if (elements.startBotBtn) elements.startBotBtn.disabled = true;
        if (elements.stopBotBtn) elements.stopBotBtn.disabled = false;
    } else {
        elements.statusDot.classList.remove('active');
        elements.statusText.textContent = 'Durduruldu';
        elements.statusMessageText.textContent = statusData?.status_message || 'Bot durduruldu.';
        
        if (elements.startBotBtn) elements.startBotBtn.disabled = false;
        if (elements.stopBotBtn) elements.stopBotBtn.disabled = true;
    }
}

// PAYMENT INFO
async function loadPaymentInfo() {
    try {
        const paymentInfo = await makeAuthenticatedRequest('/payment-info', {
            method: 'GET'
        });
        
        if (elements.paymentAmount) {
            elements.paymentAmount.textContent = paymentInfo.amount || '$15/Ay';
        }
        if (elements.paymentAddress) {
            elements.paymentAddress.textContent = paymentInfo.trc20Address || 'Yükleniyor...';
        }
    } catch (error) {
        console.error('Error loading payment info:', error);
        if (elements.paymentAddress) {
            elements.paymentAddress.textContent = 'Adres yüklenemedi';
        }
    }
}

// BOT CONTROL FUNCTIONS - Backend ile uyumlu
async function startBot() {
    try {
        if (!elements.startBotBtn) return;
        
        const botConfig = {
            symbol: elements.symbolSelect ? elements.symbolSelect.value : 'BTCUSDT',
            timeframe: elements.timeframeSelect ? elements.timeframeSelect.value : '15m',
            leverage: elements.leverageSelect ? parseInt(elements.leverageSelect.value) : 5,
            order_size: elements.orderSize ? parseFloat(elements.orderSize.value) : 35,
            stop_loss: elements.stopLoss ? parseFloat(elements.stopLoss.value) : 2,
            take_profit: elements.takeProfit ? parseFloat(elements.takeProfit.value) : 4,
            strategy: 'EMA_CROSS'
        };
        
        console.log('Bot config:', botConfig);
        
        // Validation
        if (!botConfig.symbol || botConfig.leverage < 1 || botConfig.order_size < 10) {
            throw new Error('Geçersiz bot yapılandırması');
        }
        
        elements.startBotBtn.disabled = true;
        elements.startBotBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Başlatılıyor...';
        
        const result = await makeAuthenticatedRequest('/bot/start', {
            method: 'POST',
            body: JSON.stringify(botConfig)
        });
        
        if (result.success) {
            updateBotStatus(true, result.status);
            showToast('Bot başarıyla başlatıldı!', 'success');
            startRealTimeUpdates();
        } else {
            throw new Error(result.message || 'Bot başlatılamadı');
        }
        
    } catch (error) {
        console.error('Start bot error:', error);
        showToast(`Bot başlatma hatası: ${error.message}`, 'error');
    } finally {
        if (elements.startBotBtn) {
            elements.startBotBtn.disabled = false;
            elements.startBotBtn.innerHTML = '<i class="fas fa-play"></i> Bot\'u Başlat';
        }
    }
}

async function stopBot() {
    try {
        if (!elements.stopBotBtn) return;
        
        elements.stopBotBtn.disabled = true;
        elements.stopBotBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Durduruluyor...';
        
        const result = await makeAuthenticatedRequest('/bot/stop', {
            method: 'POST'
        });
        
        if (result.success) {
            updateBotStatus(false);
            showToast('Bot başarıyla durduruldu!', 'success');
            stopRealTimeUpdates();
        } else {
            throw new Error(result.message || 'Bot durdurulamadı');
        }
        
    } catch (error) {
        console.error('Stop bot error:', error);
        showToast(`Bot durdurma hatası: ${error.message}`, 'error');
    } finally {
        if (elements.stopBotBtn) {
            elements.stopBotBtn.disabled = false;
            elements.stopBotBtn.innerHTML = '<i class="fas fa-stop"></i> Bot\'u Durdur';
        }
    }
}

// REAL-TIME UPDATES
function startRealTimeUpdates() {
    if (refreshInterval) clearInterval(refreshInterval);
    
    refreshInterval = setInterval(async () => {
        await loadAccountStats();
        await getBotStatus();
    }, 30000); // 30 saniyede bir güncelle
}

function stopRealTimeUpdates() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// API KEYS MANAGEMENT - Backend API kullanarak
async function saveApiKeys() {
    try {
        if (!elements.apiKey || !elements.apiSecret) return;
        
        const apiKey = elements.apiKey.value.trim();
        const apiSecret = elements.apiSecret.value.trim();
        
        if (!apiKey || !apiSecret) {
            showToast('API Key ve Secret alanları gerekli', 'error');
            return;
        }
        
        if (apiKey.length < 20 || apiSecret.length < 20) {
            showToast('API Key ve Secret çok kısa görünüyor', 'error');
            return;
        }
        
        if (elements.saveApiBtn) {
            elements.saveApiBtn.disabled = true;
            elements.saveApiBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Kaydediliyor...';
        }
        
        const result = await makeAuthenticatedRequest('/user/api-keys', {
            method: 'POST',
            body: JSON.stringify({
                api_key: apiKey,
                api_secret: apiSecret
            })
        });
        
        if (result.success) {
            if (elements.apiTestResult) {
                elements.apiTestResult.style.display = 'block';
                elements.apiTestResult.className = 'status-message success';
                elements.apiTestResult.innerHTML = `
                    <i class="fas fa-check-circle"></i>
                    <span>API anahtarları başarıyla kaydedildi!</span>
                `;
            }
            
            setTimeout(() => {
                closeModal('api-modal');
                checkApiStatus();
            }, 2000);
            
            showToast('API anahtarları başarıyla kaydedildi!', 'success');
        } else {
            throw new Error(result.message || 'API anahtarları kaydedilemedi');
        }
        
    } catch (error) {
        console.error('API save error:', error);
        if (elements.apiTestResult) {
            elements.apiTestResult.style.display = 'block';
            elements.apiTestResult.className = 'status-message error';
            elements.apiTestResult.innerHTML = `
                <i class="fas fa-times-circle"></i>
                <span>Hata: ${error.message}</span>
            `;
        }
        showToast(`API kaydı başarısız: ${error.message}`, 'error');
    } finally {
        if (elements.saveApiBtn) {
            elements.saveApiBtn.disabled = false;
            elements.saveApiBtn.innerHTML = '<i class="fas fa-save"></i> Kaydet ve Test Et';
        }
    }
}

// PAYMENT FUNCTIONS
async function copyAddress() {
    try {
        if (elements.paymentAddress) {
            await navigator.clipboard.writeText(elements.paymentAddress.textContent);
            if (elements.copyAddressBtn) {
                elements.copyAddressBtn.innerHTML = '<i class="fas fa-check"></i> Kopyalandı';
                setTimeout(() => {
                    elements.copyAddressBtn.innerHTML = '<i class="fas fa-copy"></i> Kopyala';
                }, 2000);
            }
            showToast('Adres panoya kopyalandı', 'success');
        }
    } catch (error) {
        showToast('Kopyalama başarısız', 'error');
    }
}

async function confirmPayment() {
    try {
        if (!elements.transactionHash) return;
        
        const transactionHash = elements.transactionHash.value.trim();
        
        if (!transactionHash) {
            showToast('Lütfen işlem hash\'ini girin', 'error');
            return;
        }
        
        if (transactionHash.length < 20) {
            showToast('Geçersiz işlem hash\'i', 'error');
            return;
        }
        
        if (elements.confirmPaymentBtn) {
            elements.confirmPaymentBtn.disabled = true;
            elements.confirmPaymentBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Kontrol ediliyor...';
        }
        
        const result = await makeAuthenticatedRequest('/payment/confirm', {
            method: 'POST',
            body: JSON.stringify({
                transaction_hash: transactionHash
            })
        });
        
        if (result.success) {
            showToast('Ödeme başarıyla doğrulandı!', 'success');
            closeModal('purchase-modal');
            await loadUserData(); // Kullanıcı bilgilerini yeniden yükle
        } else {
            throw new Error(result.message || 'Ödeme doğrulanamadı');
        }
        
    } catch (error) {
        console.error('Payment confirmation error:', error);
        showToast(`Ödeme doğrulama hatası: ${error.message}`, 'error');
    } finally {
        if (elements.confirmPaymentBtn) {
            elements.confirmPaymentBtn.disabled = false;
            elements.confirmPaymentBtn.innerHTML = '<i class="fas fa-check"></i> Ödememi Doğrula';
        }
    }
}

// SUPPORT FUNCTIONS
async function sendSupportMessage() {
    try {
        if (!elements.supportSubject || !elements.supportMessage) return;
        
        const subject = elements.supportSubject.value.trim();
        const message = elements.supportMessage.value.trim();
        
        if (!subject || !message) {
            showToast('Lütfen konu ve mesaj alanlarını doldurun', 'error');
            return;
        }
        
        if (elements.sendSupportBtn) {
            elements.sendSupportBtn.disabled = true;
            elements.sendSupportBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gönderiliyor...';
        }
        
        const result = await makeAuthenticatedRequest('/support/message', {
            method: 'POST',
            body: JSON.stringify({
                subject: subject,
                message: message
            })
        });
        
        if (result.success) {
            showToast('Destek mesajınız gönderildi!', 'success');
            closeModal('support-modal');
            
            // Form alanlarını temizle
            elements.supportSubject.value = '';
            elements.supportMessage.value = '';
        } else {
            throw new Error(result.message || 'Mesaj gönderilemedi');
        }
        
    } catch (error) {
        console.error('Support message error:', error);
        showToast(`Mesaj gönderme hatası: ${error.message}`, 'error');
    } finally {
        if (elements.sendSupportBtn) {
            elements.sendSupportBtn.disabled = false;
            elements.sendSupportBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Mesajı Gönder';
        }
    }
}

// MODAL FUNCTIONS
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        setTimeout(() => modal.classList.add('show'), 10);
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => modal.style.display = 'none', 300);
    }
}

// LOGOUT FUNCTION
function logout() {
    try {
        if (auth && currentUser) {
            auth.signOut();
        }
        
        // Token ve kullanıcı bilgilerini temizle
        authToken = null;
        currentUser = null;
        localStorage.removeItem('authToken');
        
        // Real-time güncellemeleri durdur
        stopRealTimeUpdates();
        
        // Login sayfasına yönlendir
        window.location.href = '/login.html';
        
    } catch (error) {
        console.error('Logout error:', error);
        // Hata olsa bile login sayfasına yönlendir
        window.location.href = '/login.html';
    }
}

// MOBILE MENU FUNCTIONS
function toggleMobileMenu() {
    if (elements.mobileMenu) {
        elements.mobileMenu.classList.toggle('show');
    }
}

function closeMobileMenu() {
    if (elements.mobileMenu) {
        elements.mobileMenu.classList.remove('show');
    }
}

// EVENT LISTENERS SETUP
function setupEventListeners() {
    // Mobile menu
    if (elements.hamburgerMenu) {
        elements.hamburgerMenu.addEventListener('click', toggleMobileMenu);
    }
    if (elements.mobileMenuClose) {
        elements.mobileMenuClose.addEventListener('click', closeMobileMenu);
    }
    
    // API modal
    if (elements.manageApiBtn) {
        elements.manageApiBtn.addEventListener('click', () => openModal('api-modal'));
    }
    if (elements.mobileApiBtn) {
        elements.mobileApiBtn.addEventListener('click', () => {
            openModal('api-modal');
            closeMobileMenu();
        });
    }
    if (elements.apiModalClose) {
        elements.apiModalClose.addEventListener('click', () => closeModal('api-modal'));
    }
    if (elements.cancelApiBtn) {
        elements.cancelApiBtn.addEventListener('click', () => closeModal('api-modal'));
    }
    if (elements.saveApiBtn) {
        elements.saveApiBtn.addEventListener('click', saveApiKeys);
    }
    
    // Bot control
    if (elements.startBotBtn) {
        elements.startBotBtn.addEventListener('click', startBot);
    }
    if (elements.stopBotBtn) {
        elements.stopBotBtn.addEventListener('click', stopBot);
    }
    
    // Purchase modal
    if (elements.mobilePurchaseBtn) {
        elements.mobilePurchaseBtn.addEventListener('click', () => {
            openModal('purchase-modal');
            closeMobileMenu();
        });
    }
    if (elements.purchaseModalClose) {
        elements.purchaseModalClose.addEventListener('click', () => closeModal('purchase-modal'));
    }
    if (elements.cancelPurchaseBtn) {
        elements.cancelPurchaseBtn.addEventListener('click', () => closeModal('purchase-modal'));
    }
    if (elements.copyAddressBtn) {
        elements.copyAddressBtn.addEventListener('click', copyAddress);
    }
    if (elements.confirmPaymentBtn) {
        elements.confirmPaymentBtn.addEventListener('click', confirmPayment);
    }
    
    // Support modal
    if (elements.mobileSupportBtn) {
        elements.mobileSupportBtn.addEventListener('click', () => {
            openModal('support-modal');
            closeMobileMenu();
        });
    }
    if (elements.supportModalClose) {
        elements.supportModalClose.addEventListener('click', () => closeModal('support-modal'));
    }
    if (elements.cancelSupportBtn) {
        elements.cancelSupportBtn.addEventListener('click', () => closeModal('support-modal'));
    }
    if (elements.sendSupportBtn) {
        elements.sendSupportBtn.addEventListener('click', sendSupportMessage);
    }
    
    // Logout
    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener('click', logout);
    }
    if (elements.mobileLogoutBtn) {
        elements.mobileLogoutBtn.addEventListener('click', () => {
            logout();
            closeMobileMenu();
        });
    }
    
    // Toast close
    if (elements.toastClose) {
        elements.toastClose.addEventListener('click', () => {
            if (elements.toast) {
                elements.toast.classList.remove('show');
            }
        });
    }
    
    // Modal background click to close
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('show');
                setTimeout(() => modal.style.display = 'none', 300);
            }
        });
    });
}

// INITIALIZATION
async function initApp() {
    try {
        console.log('Initializing app...');
        
        // DOM elementlerini başlat
        elements.init();
        
        // Event listener'ları kur
        setupEventListeners();
        
        // Firebase'i başlat
        const firebaseInitialized = await initializeFirebase();
        if (!firebaseInitialized) {
            showToast('Firebase başlatılamadı', 'error');
            return;
        }
        
        // Auth kontrolü
        const isAuthenticated = await checkAuth();
        if (isAuthenticated) {
            // Loading screen'i gizle, dashboard'u göster
            if (elements.loadingScreen) elements.loadingScreen.style.display = 'none';
            if (elements.dashboard) elements.dashboard.style.display = 'block';
            
            console.log('App initialized successfully');
        }
        
    } catch (error) {
        console.error('App initialization failed:', error);
        showToast('Uygulama başlatılamadı', 'error');
    }
}

// DOM ready event
document.addEventListener('DOMContentLoaded', initApp);

// Window error handler
window.addEventListener('error', (error) => {
    console.error('Global error:', error);
    showToast('Beklenmeyen bir hata oluştu', 'error');
});

// Unhandled promise rejection handler
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    showToast('Beklenmeyen bir hata oluştu', 'error');
});
