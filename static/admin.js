document.addEventListener('DOMContentLoaded', () => {

    // DOM elementlerini tek bir obje içinde toplama
    const UIElements = {
        adminContainer: document.getElementById('admin-container'),
        adminLogoutButton: document.getElementById('admin-logout-button'),
        usersTableBody: document.getElementById('users-table-body'),
        userCountSpan: document.getElementById('user-count'),
        tableErrorMessage: document.getElementById('table-error-message'),
        currentYearSpan: document.getElementById('current-year'),
    };

    const firebaseServices = {
        auth: null,
    };

    // Yükleme durumunu yöneten yardımcı fonksiyon
    function setLoadingState(isLoading, message = "Lütfen bekleyin...", targetElement = UIElements.usersTableBody) {
        if (!targetElement) return;
        
        if (isLoading) {
            targetElement.innerHTML = `<tr><td colspan="5" class="text-center text-muted loading-message"><i class="fas fa-spinner fa-spin mr-2"></i> ${message}</td></tr>`;
            if (UIElements.tableErrorMessage) {
                UIElements.tableErrorMessage.style.display = 'none';
            }
        }
    }

    // Hata mesajını gösteren yardımcı fonksiyon
    function showErrorMessage(message) {
        if (UIElements.tableErrorMessage) {
            UIElements.tableErrorMessage.textContent = message;
            UIElements.tableErrorMessage.style.display = 'block';
        }
        if (UIElements.usersTableBody) {
            UIElements.usersTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">${message}</td></tr>`;
        }
    }

    // Başarı mesajını gösteren yardımcı fonksiyon
    function showSuccessMessage(message) {
        if (UIElements.tableErrorMessage) {
            UIElements.tableErrorMessage.textContent = message;
            UIElements.tableErrorMessage.style.display = 'block';
            UIElements.tableErrorMessage.classList.remove('error');
            UIElements.tableErrorMessage.classList.add('success');
            
            // 3 saniye sonra mesajı gizle
            setTimeout(() => {
                UIElements.tableErrorMessage.style.display = 'none';
                UIElements.tableErrorMessage.classList.remove('success');
            }, 3000);
        }
    }

    /**
     * Backend ile güvenli iletişim kurmak için kullanılan yardımcı fonksiyon.
     * Firebase kimlik doğrulama jetonunu her isteğe ekler.
     */
    async function fetchAdminApi(endpoint, options = {}) {
        const user = firebaseServices.auth?.currentUser;
        if (!user) {
            alert("Oturumunuz sona erdi veya yetkiniz yok. Lütfen tekrar giriş yapın.");
            window.location.href = '/';
            return null;
        }
        
        try {
            // Admin işlemleri için her zaman güncel jeton al
            const idToken = await user.getIdToken(true); 
            
            const headers = {
                'Authorization': `Bearer ${idToken}`,
                ...options.headers
            };
            
            // FormData kullanılmıyorsa Content-Type ekle
            if (options.body && !(options.body instanceof FormData)) {
                headers['Content-Type'] = 'application/json';
            }
            
            const response = await fetch(endpoint, { ...options, headers });
            
            if (!response.ok) {
                let errorData;
                try {
                    errorData = await response.json();
                } catch {
                    errorData = { detail: response.statusText };
                }
                
                console.error(`Admin API Hatası (${response.status}) - ${endpoint}:`, errorData);
                
                // Yetki hatası durumunda ana sayfaya yönlendir
                if (response.status === 401 || response.status === 403) {
                    alert("Yetkiniz bulunmuyor. Ana sayfaya yönlendiriliyorsunuz.");
                    window.location.href = '/';
                    return null;
                }
                
                throw new Error(errorData.detail || `Sunucu hatası: ${response.status}`);
            }
            
            return response.json();
        } catch (error) {
            console.error("Admin API isteği sırasında hata:", error);
            showErrorMessage(`API isteği başarısız: ${error.message}`);
            return null;
        }
    }

    /**
     * Kullanıcıları backend'den yükleyip tabloyu günceller.
     */
    async function loadUsers() {
        setLoadingState(true, "Kullanıcılar yükleniyor...");
        
        if (UIElements.userCountSpan) {
            UIElements.userCountSpan.textContent = 'Toplam Kullanıcı: Yükleniyor...';
        }
        
        try {
            const response = await fetchAdminApi('/api/admin/users');
            if (!response) {
                throw new Error("API isteği başarısız oldu.");
            }
            
            if (!response.users) {
                throw new Error("Kullanıcı verileri alınamadı.");
            }
            
            const users = response.users;
            
            if (!UIElements.usersTableBody) {
                throw new Error("Kullanıcı tablosu bulunamadı.");
            }
            
            UIElements.usersTableBody.innerHTML = ''; // Tabloyu temizle

            if (Object.keys(users).length === 0) {
                UIElements.usersTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Hiç kullanıcı bulunamadı.</td></tr>';
                if (UIElements.userCountSpan) {
                    UIElements.userCountSpan.textContent = 'Toplam Kullanıcı: 0';
                }
                return;
            }

            let userCount = 0;
            for (const uid in users) {
                const user = users[uid];
                userCount++;
                
                const expiryDate = user.subscription_expiry 
                    ? new Date(user.subscription_expiry).toLocaleString('tr-TR', { 
                        year: 'numeric',
                        month: '2-digit', 
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    })
                    : 'N/A';
                
                let statusBadgeClass = 'inactive';
                let statusDisplayText = 'Bilinmiyor';
                
                switch (user.subscription_status) {
                    case 'active':
                        statusBadgeClass = 'active';
                        statusDisplayText = 'Aktif';
                        break;
                    case 'trial':
                        statusBadgeClass = 'warning';
                        statusDisplayText = 'Deneme';
                        break;
                    case 'expired':
                        statusBadgeClass = 'inactive';
                        statusDisplayText = 'Süresi Dolmuş';
                        break;
                    default:
                        statusBadgeClass = 'inactive';
                        statusDisplayText = 'Bilinmiyor';
                }

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td title="${user.email || 'N/A'}">${(user.email || 'N/A').length > 25 ? (user.email || 'N/A').substring(0, 25) + '...' : (user.email || 'N/A')}</td>
                    <td><span class="status-badge ${statusBadgeClass}">${statusDisplayText}</span></td>
                    <td>${expiryDate}</td>
                    <td><span class="user-id-text" title="${uid}">${uid.length > 15 ? uid.substring(0, 15) + '...' : uid}</span></td>
                    <td class="text-center">
                        <button class="btn btn-primary btn-sm activate-btn" data-uid="${uid}" data-email="${user.email || 'N/A'}">
                            <i class="fas fa-plus"></i> 30 Gün Ekle
                        </button>
                    </td>
                `;
                UIElements.usersTableBody.appendChild(row);
            }
            
            if (UIElements.userCountSpan) {
                UIElements.userCountSpan.textContent = `Toplam Kullanıcı: ${userCount}`;
            }

            // Butonlara tıklama olaylarını ekle
            document.querySelectorAll('.activate-btn').forEach(button => {
                button.addEventListener('click', handleActivateSubscription);
            });

            if (UIElements.tableErrorMessage) {
                UIElements.tableErrorMessage.style.display = 'none';
            }

        } catch (error) {
            console.error("Kullanıcıları yüklerken hata:", error);
            showErrorMessage(`Kullanıcılar yüklenemedi: ${error.message}`);
            if (UIElements.userCountSpan) {
                UIElements.userCountSpan.textContent = 'Toplam Kullanıcı: Hata!';
            }
        }
    }

    /**
     * Abonelik etkinleştirme butonuna tıklama olayını yönetir.
     */
    async function handleActivateSubscription(event) {
        const button = event.target.closest('.activate-btn');
        if (!button) return;

        const userIdToActivate = button.dataset.uid;
        const userEmail = button.dataset.email || 'Bilinmeyen kullanıcı';
        
        if (!userIdToActivate) {
            alert('Kullanıcı ID bulunamadı.');
            return;
        }

        if (!confirm(`${userEmail} (${userIdToActivate.substring(0, 10)}...) kullanıcısının aboneliğini 30 gün uzatmak istediğinizden emin misiniz?`)) {
            return;
        }

        const originalButtonHtml = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İşleniyor...';

        try {
            const result = await fetchAdminApi('/api/admin/activate-subscription', {
                method: 'POST',
                body: JSON.stringify({ user_id: userIdToActivate })
            });

            if (result && result.success) {
                showSuccessMessage(`${userEmail} kullanıcısının aboneliği başarıyla 30 gün uzatıldı!`);
                await loadUsers(); // Tabloyu yenile
            } else {
                alert(`Abonelik uzatılamadı: ${result?.detail || 'Bilinmeyen bir hata.'}`);
            }
        } catch (error) {
            alert(`Abonelik uzatılırken bir hata oluştu: ${error.message}`);
        } finally {
            button.innerHTML = originalButtonHtml;
            button.disabled = false;
        }
    }

    /**
     * Çıkış yapma işlemini yönetir.
     */
    async function handleLogout() {
        if (confirm("Yönetici panelinden çıkış yapmak istediğinizden emin misiniz?")) {
            try {
                await firebaseServices.auth.signOut();
                // onAuthStateChanged listener will redirect to '/'
            } catch (error) {
                console.error("Çıkış yaparken hata:", error);
                alert("Çıkış yapılırken bir hata oluştu.");
            }
        }
    }

    /**
     * Sayfa yenilenmeden önce temizlik yapar
     */
    window.addEventListener('beforeunload', () => {
        // Herhangi bir aktif işlem varsa uyar
        const activeButtons = document.querySelectorAll('button:disabled');
        if (activeButtons.length > 0) {
            return "Aktif işlemler var. Sayfayı kapatmak istediğinizden emin misiniz?";
        }
    });

    /**
     * Uygulamayı başlatan ana fonksiyon.
     */
    async function initializeApp() {
        // Current year'ı ayarla
        if (UIElements.currentYearSpan) {
            UIElements.currentYearSpan.textContent = new Date().getFullYear();
        }

        try {
            // Backend'den Firebase yapılandırmasını güvenli bir şekilde al
            const response = await fetch('/api/firebase-config');
            if (!response.ok) {
                throw new Error(`Firebase yapılandırması sunucudan alınamadı: ${response.status} ${response.statusText}`);
            }
            
            const firebaseConfig = await response.json();

            // Gelen config'in geçerliliğini kontrol et
            if (!firebaseConfig || !firebaseConfig.apiKey) {
                throw new Error('Sunucudan gelen Firebase yapılandırması eksik veya geçersiz.');
            }

            // Firebase'i başlat
            firebase.initializeApp(firebaseConfig);
            firebaseServices.auth = firebase.auth();

            // Kullanıcı oturum durumunu dinle
            firebaseServices.auth.onAuthStateChanged(async (user) => {
                if (user) {
                    // Admin yetkisi kontrolü backend'de yapılır
                    if (UIElements.adminContainer) {
                        UIElements.adminContainer.style.display = 'flex';
                    }
                    await loadUsers();
                } else {
                    // Giriş yapmamışsa ana sayfaya yönlendir
                    window.location.href = '/';
                }
            });

            // Olay dinleyicilerini ayarla
            if (UIElements.adminLogoutButton) {
                UIElements.adminLogoutButton.addEventListener('click', handleLogout);
            }

        } catch (error) {
            console.error("Admin paneli başlatılamadı:", error);
            
            // Daha user-friendly hata sayfası
            document.body.innerHTML = `
                <div style="
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    padding: 2rem;
                    background-color: #f3f4f6;
                    font-family: 'Inter', sans-serif;
                ">
                    <div style="
                        background: white;
                        padding: 2rem;
                        border-radius: 0.75rem;
                        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
                        max-width: 600px;
                        width: 100%;
                        text-align: center;
                    ">
                        <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: #ef4444; margin-bottom: 1rem;"></i>
                        <h1 style="font-size: 1.5rem; margin-bottom: 1rem; color: #b91c1c;">
                            Yönetici Paneli Başlatılamadı
                        </h1>
                        <p style="color: #991b1b; margin-bottom: 1rem; line-height: 1.6;">
                            Sistem başlatılırken bir hata oluştu. Lütfen sayfayı yenileyin veya sistem yöneticisi ile iletişime geçin.
                        </p>
                        <details style="margin: 1rem 0; text-align: left;">
                            <summary style="cursor: pointer; color: #3b82f6; font-weight: 600; text-align: center;">Teknik Detaylar</summary>
                            <pre style="
                                background: #f9fafb;
                                padding: 1rem;
                                border-radius: 0.5rem;
                                font-size: 0.8rem;
                                color: #374151;
                                margin-top: 0.5rem;
                                white-space: pre-wrap;
                                word-break: break-word;
                            ">${error.message}</pre>
                        </details>
                        <div style="display: flex; gap: 1rem; justify-content: center; margin-top: 1.5rem;">
                            <button onclick="location.reload()" style="
                                background: #3b82f6;
                                color: white;
                                border: none;
                                padding: 0.75rem 1.5rem;
                                border-radius: 0.5rem;
                                font-weight: 600;
                                cursor: pointer;
                                transition: background-color 0.3s ease;
                            " onmouseover="this.style.backgroundColor='#2563eb'" onmouseout="this.style.backgroundColor='#3b82f6'">
                                <i class="fas fa-redo"></i> Sayfayı Yenile
                            </button>
                            <button onclick="window.location.href='/'" style="
                                background: #6b7280;
                                color: white;
                                border: none;
                                padding: 0.75rem 1.5rem;
                                border-radius: 0.5rem;
                                font-weight: 600;
                                cursor: pointer;
                                transition: background-color 0.3s ease;
                            " onmouseover="this.style.backgroundColor='#4b5563'" onmouseout="this.style.backgroundColor='#6b7280'">
                                <i class="fas fa-home"></i> Ana Sayfa
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    // Uygulamayı başlat
    initializeApp();
});
