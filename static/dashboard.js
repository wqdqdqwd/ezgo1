// Dashboard.js - Firebase Direct Implementation
// API çağrıları yerine doğrudan Firebase kullanımı

// Payment notification function - API yerine Firebase
async function confirmPayment() {
    try {
        if (!elements.transactionHash) return;
        
        const transactionHash = elements.transactionHash.value.trim();
        
        if (!transactionHash) {
            showToast('Lütfen işlem hash\'ini girin', 'error');
            return;
        }
        
        if (elements.confirmPaymentBtn) {
            elements.confirmPaymentBtn.disabled = true;
            elements.confirmPaymentBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Bildiriliyor...';
        }
        
        // Firebase'e doğrudan yazma - API yerine
        const paymentNotification = {
            user_id: currentUser.uid,
            user_email: currentUser.email,
            transaction_hash: transactionHash,
            amount: 15,
            currency: 'USDT',
            status: 'pending',
            created_at: firebase.database.ServerValue.TIMESTAMP
        };
        
        // Firebase Realtime Database'e kaydet
        const notificationRef = database.ref('payment_notifications').push();
        await notificationRef.set(paymentNotification);
        
        showToast('Ödeme bildirimi gönderildi. Admin onayı bekleniyor.', 'success');
        closeModal('purchase-modal');
        
        if (elements.transactionHash) {
            elements.transactionHash.value = '';
        }
        
    } catch (error) {
        console.error('Payment confirmation error:', error);
        showToast(`Ödeme bildirimi hatası: ${error.message}`, 'error');
    } finally {
        if (elements.confirmPaymentBtn) {
            elements.confirmPaymentBtn.disabled = false;
            elements.confirmPaymentBtn.innerHTML = '<i class="fas fa-check"></i> Ödeme Bildir';
        }
    }
}

// Support message function - API yerine Firebase
async function sendSupportMessage() {
    try {
        if (!elements.supportSubject || !elements.supportMessage) return;
        
        const subject = elements.supportSubject.value;
        const message = elements.supportMessage.value.trim();
        
        if (!subject || !message) {
            showToast('Konu ve mesaj alanları gerekli', 'error');
            return;
        }
        
        if (elements.sendSupportBtn) {
            elements.sendSupportBtn.disabled = true;
            elements.sendSupportBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gönderiliyor...';
        }
        
        // Firebase'e doğrudan yazma - API yerine
        const supportMessage = {
            user_id: currentUser.uid,
            user_email: currentUser.email,
            subject: subject,
            message: message,
            status: 'open',
            created_at: firebase.database.ServerValue.TIMESTAMP
        };
        
        // Firebase Realtime Database'e kaydet
        const messageRef = database.ref('support_messages').push();
        await messageRef.set(supportMessage);
        
        showToast('Destek mesajınız gönderildi. En kısa sürede dönüş yapacağız.', 'success');
        closeModal('support-modal');
        
        if (elements.supportSubject) elements.supportSubject.value = '';
        if (elements.supportMessage) elements.supportMessage.value = '';
        
    } catch (error) {
        console.error('Support message error:', error);
        showToast(`Mesaj gönderme hatası: ${error.message}`, 'error');
    } finally {
        if (elements.sendSupportBtn) {
            elements.sendSupportBtn.disabled = false;
            elements.sendSupportBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Gönder';
        }
    }
}

// API Keys kaydetme function - Firebase ile
async function saveApiKeys() {
    try {
        if (!elements.apiKey || !elements.apiSecret) return;
        
        const apiKey = elements.apiKey.value.trim();
        const apiSecret = elements.apiSecret.value.trim();
        const useTestnet = elements.apiTestnet ? elements.apiTestnet.checked : false;
        
        if (!apiKey || !apiSecret) {
            showToast('API Key ve Secret alanları gerekli', 'error');
            return;
        }
        
        if (elements.saveApiBtn) {
            elements.saveApiBtn.disabled = true;
            elements.saveApiBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Kaydediliyor...';
        }
        
        // Basit encryption (production'da daha güçlü encryption kullanın)
        const encryptedApiKey = btoa(apiKey); // Base64 encoding - basic encryption
        const encryptedApiSecret = btoa(apiSecret);
        
        // Firebase'e doğrudan yazma
        const userRef = database.ref(`users/${currentUser.uid}`);
        await userRef.update({
            binance_api_key: encryptedApiKey,
            binance_api_secret: encryptedApiSecret,
            api_keys_set: true,
            use_testnet: useTestnet,
            last_updated: firebase.database.ServerValue.TIMESTAMP,
            updated_by: currentUser.email
        });
        
        if (elements.apiTestResult) {
            elements.apiTestResult.style.display = 'block';
            elements.apiTestResult.className = 'api-test-result success';
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
        
    } catch (error) {
        console.error('API save error:', error);
        if (elements.apiTestResult) {
            elements.apiTestResult.style.display = 'block';
            elements.apiTestResult.className = 'api-test-result error';
            elements.apiTestResult.innerHTML = `
                <i class="fas fa-times-circle"></i>
                <span>Hata: ${error.message}</span>
            `;
        }
        showToast(`API kaydı başarısız: ${error.message}`, 'error');
    } finally {
        if (elements.saveApiBtn) {
            elements.saveApiBtn.disabled = false;
            elements.saveApiBtn.innerHTML = '<i class="fas fa-save"></i> Kaydet';
        }
    }
}

// Firebase ile API durumu kontrolü
async function checkApiStatus() {
    try {
        if (!currentUser) return;
        
        const userRef = database.ref(`users/${currentUser.uid}`);
        const snapshot = await userRef.once('value');
        const userData = snapshot.val();
        
        if (userData && userData.api_keys_set && userData.binance_api_key && userData.binance_api_secret) {
            showApiConnected();
            if (elements.tradingSettings) {
                elements.tradingSettings.style.display = 'block';
            }
            if (elements.controlButtons) {
                elements.controlButtons.style.display = 'grid';
            }
            if (elements.statusMessageText) {
                elements.statusMessageText.textContent = 'API bağlantısı aktif. Bot ayarlarını yapılandırıp başlatabilirsiniz.';
            }
        } else {
            showApiNotConfigured();
        }
    } catch (error) {
        console.error('API status check failed:', error);
        showApiError('API durumu kontrol edilemedi');
    }
}

// Payment info yükleme - Firebase veya static data ile
async function loadPaymentInfo() {
    try {
        // Static payment info - gerçek production'da Firebase'den çekin
        const paymentInfo = {
            amount: '$15/Ay',
            trc20Address: 'TYDzsYUEpvnYmQk4zGP9sWWcTEd2MiAtW6' // Örnek TRC20 adresi
        };
        
        if (elements.paymentAmount) {
            elements.paymentAmount.textContent = paymentInfo.amount;
        }
        if (elements.paymentAddress) {
            elements.paymentAddress.textContent = paymentInfo.trc20Address;
        }
    } catch (error) {
        console.error('Error loading payment info:', error);
        if (elements.paymentAddress) {
            elements.paymentAddress.textContent = 'Adres yüklenemedi';
        }
    }
}

// Bot control functions - Firebase ile
async function startBot() {
    try {
        if (!currentUser) {
            showToast('Giriş yapmalısınız', 'error');
            return;
        }
        
        if (elements.startBotBtn) {
            elements.startBotBtn.disabled = true;
            elements.startBotBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Başlatılıyor...';
        }
        
        const botConfig = {
            symbol: elements.symbolSelect ? elements.symbolSelect.value : 'BTCUSDT',
            timeframe: elements.timeframeSelect ? elements.timeframeSelect.value : '15m',
            leverage: elements.leverageSelect ? parseInt(elements.leverageSelect.value) : 5,
            order_size: elements.orderSize ? parseFloat(elements.orderSize.value) : 35,
            stop_loss: elements.stopLoss ? parseFloat(elements.stopLoss.value) : 2,
            take_profit: elements.takeProfit ? parseFloat(elements.takeProfit.value) : 4,
            started_at: firebase.database.ServerValue.TIMESTAMP,
            started_by: currentUser.email
        };
        
        // Firebase'e bot durumu kaydet
        const botRef = database.ref(`users/${currentUser.uid}`);
        await botRef.update({
            bot_active: true,
            bot_config: botConfig,
            last_updated: firebase.database.ServerValue.TIMESTAMP
        });
        
        updateBotStatus(true);
        showToast('Bot başarıyla başlatıldı! (Demo Mode)', 'success');
        
    } catch (error) {
        console.error('Bot start error:', error);
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
        if (!currentUser) {
            showToast('Giriş yapmalısınız', 'error');
            return;
        }
        
        if (elements.stopBotBtn) {
            elements.stopBotBtn.disabled = true;
            elements.stopBotBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Durduruluyor...';
        }
        
        // Firebase'e bot durumu kaydet
        const botRef = database.ref(`users/${currentUser.uid}`);
        await botRef.update({
            bot_active: false,
            bot_stopped_at: firebase.database.ServerValue.TIMESTAMP,
            last_updated: firebase.database.ServerValue.TIMESTAMP
        });
        
        updateBotStatus(false);
        showToast('Bot başarıyla durduruldu!', 'success');
        
    } catch (error) {
        console.error('Bot stop error:', error);
        showToast(`Bot durdurma hatası: ${error.message}`, 'error');
    } finally {
        if (elements.stopBotBtn) {
            elements.stopBotBtn.disabled = false;
            elements.stopBotBtn.innerHTML = '<i class="fas fa-stop"></i> Bot\'u Durdur';
        }
    }
}

// Firebase config çekme function
async function getFirebaseConfig() {
    // Gerçek production'da backend'den çekin
    // Şu anda static config dönüyor
    return {
        apiKey: process.env.FIREBASE_API_KEY,
        authDomain: process.env.FIREBASE_AUTH_DOMAIN,
        databaseURL: process.env.FIREBASE_DATABASE_URL,
        projectId: process.env.FIREBASE_PROJECT_ID,
        storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
        messagingSenderId: process.env.FIREBASE_MESSAGING_SENDER_ID,
        appId: process.env.FIREBASE_APP_ID
    };
}
