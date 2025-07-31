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
        if (isLoading) {
            targetElement.innerHTML = `<tr><td colspan="5" class="text-center text-muted loading-message"><i class="fas fa-spinner fa-spin mr-2"></i> ${message}</td></tr>`;
            UIElements.tableErrorMessage.style.display = 'none';
        } else {
            // Yükleme bittiğinde bu mesajın JS tarafından doldurulması beklenir
        }
    }

    // Hata mesajını gösteren yardımcı fonksiyon
    function showErrorMessage(message) {
        UIElements.tableErrorMessage.textContent = message;
        UIElements.tableErrorMessage.style.display = 'block';
        UIElements.usersTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">${message}</td></tr>`;
    }

    /**
     * Backend ile güvenli iletişim kurmak için kullanılan yardımcı fonksiyon.
     * Firebase kimlik doğrulama jetonunu her isteğe ekler.
     */
    async function fetchAdminApi(endpoint, options = {}) {
        const user = firebaseServices.auth.currentUser;
        if (!user) {
            // Kullanıcı giriş yapmamışsa veya oturumu bitmişse ana sayfaya yönlendir
            alert("Oturumunuz sona erdi veya yetkiniz yok. Lütfen tekrar giriş yapın.");
            window.location.href = '/';
            return null;
        }
        try {
            // Jetonu zorla yenilemek yerine, Firebase'in yönetmesine izin ver
            // Ancak admin işlemleri için her zaman güncel bir jeton almak daha güvenli olabilir.
            const idToken = await user.getIdToken(true); 
            
            const headers = {
                'Authorization': `Bearer ${idToken}`,
                ...options.headers // Mevcut başlıkları koru
            };
            if (options.body && !(options.body instanceof FormData)) { // FormData kullanıldığında Content-Type'ı elle ayarlama
                headers['Content-Type'] = 'application/json';
            }
            
            const response = await fetch(endpoint, { ...options, headers });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                console.error(`Admin API Hatası (${response.status}) - ${endpoint}:`, errorData);
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
        UIElements.userCountSpan.textContent = 'Toplam Kullanıcı: Yükleniyor...';
        try {
            const response = await fetchAdminApi('/api/admin/users');
            if (!response || !response.users) {
                throw new Error("Kullanıcı verileri alınamadı.");
            }
            
            const users = response.users;
            UIElements.usersTableBody.innerHTML = ''; // Tabloyu temizle

            if (Object.keys(users).length === 0) {
                UIElements.usersTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Hiç kullanıcı bulunamadı.</td></tr>';
                UIElements.userCountSpan.textContent = 'Toplam Kullanıcı: 0';
                return;
            }

            let userCount = 0;
            for (const uid in users) {
                const user = users[uid];
                userCount++;
                const expiryDate = user.subscription_expiry 
                    ? new Date(user.subscription_expiry).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' })
                    : 'N/A';
                
                let statusBadgeClass = 'inactive';
                let statusDisplayText = 'Bilinmiyor';
                switch (user.subscription_status) {
                    case 'active':
                        statusBadgeClass = 'active';
                        statusDisplayText = 'Aktif';
                        break;
                    case 'trial':
                        statusBadgeClass = 'warning'; // 'trial' için yeni bir sınıf varsayıyorum
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
                    <td>${user.email || 'N/A'}</td>
                    <td><span class="status-badge ${statusBadgeClass}">${statusDisplayText}</span></td>
                    <td>${expiryDate}</td>
                    <td><span class="user-id-text">${uid}</span></td>
                    <td class="text-center">
                        <button class="btn btn-primary btn-sm activate-btn" data-uid="${uid}">
                            <i class="fas fa-plus"></i> 30 Gün Ekle
                        </button>
                    </td>
                `;
                UIElements.usersTableBody.appendChild(row);
            }
            UIElements.userCountSpan.textContent = `Toplam Kullanıcı: ${userCount}`;

            // Butonlara tıklama olaylarını ekle
            document.querySelectorAll('.activate-btn').forEach(button => {
                button.addEventListener('click', handleActivateSubscription);
            });

            UIElements.tableErrorMessage.style.display = 'none'; // Başarılı yüklemede hatayı gizle

        } catch (error) {
            console.error("Kullanıcıları yüklerken hata:", error);
            showErrorMessage(`Kullanıcılar yüklenemedi: ${error.message}`);
            UIElements.userCountSpan.textContent = 'Toplam Kullanıcı: Hata!';
        }
    }

    /**
     * Abonelik etkinleştirme butonuna tıklama olayını yönetir.
     */
    async function handleActivateSubscription(event) {
        const button = event.target.closest('.activate-btn');
        if (!button) return;

        const userIdToActivate = button.dataset.uid;
        if (!userIdToActivate) {
            alert('Kullanıcı ID bulunamadı.');
            return;
        }

        if (!confirm(`${userIdToActivate} ID'li kullanıcının aboneliğini 30 gün uzatmak istediğinizden emin misiniz?`)) {
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
                alert('Abonelik başarıyla 30 gün uzatıldı!');
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
     * Uygulamayı başlatan ana fonksiyon.
     */
    async function initializeApp() {
        UIElements.currentYearSpan.textContent = new Date().getFullYear();

        try {
            // Backend'den Firebase yapılandırmasını güvenli bir şekilde al
            const response = await fetch('/api/firebase-config');
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Firebase yapılandırması sunucudan alınamadı: ${errorText}`);
            }
            const firebaseConfig = await response.json();

            // Gelen anahtarlar eksikse hata ver
            if (!firebaseConfig.apiKey) {
                 throw new Error('Sunucudan gelen Firebase yapılandırması eksik.');
            }

            // Alınan yapılandırma ile Firebase'i başlat
            firebase.initializeApp(firebaseConfig);
            firebaseServices.auth = firebase.auth();

            // Kullanıcı oturum durumunu dinle
            firebaseServices.auth.onAuthStateChanged(async (user) => {
                if (user) {
                    // Kullanıcı giriş yapmışsa, admin yetkisini kontrol et ve kullanıcıları yükle
                    // Not: Gerçek admin yetkilendirme kontrolü backend'de yapılmalıdır.
                    // Frontend sadece UI'ı göstermek için basit bir kontrol yapabilir.
                    UIElements.adminContainer.style.display = 'flex'; // Admin panelini göster
                    await loadUsers(); // Kullanıcıları yükle
                } else {
                    // Giriş yapmamışsa ana sayfaya yönlendir
                    window.location.href = '/';
                }
            });

            // Olay dinleyicilerini ayarla
            UIElements.adminLogoutButton.addEventListener('click', handleLogout);

        } catch (error) {
            console.error("Admin paneli başlatılamadı:", error);
            document.body.innerHTML = `<div style="color: #ef4444; background-color: #fef2f2; border: 1px solid #fecaca; padding: 2rem; margin: 2rem auto; max-width: 600px; border-radius: 0.5rem; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);">
                <h1 style="font-size: 1.5rem; margin-bottom: 1rem; color: #b91c1c;">
                    <i class="fas fa-exclamation-triangle mr-2"></i> Yönetici Paneli Başlatılamadı
                </h1>
                <p style="color: #991b1b; margin-bottom: 1rem;">Lütfen daha sonra tekrar deneyin veya sistem yöneticisi ile iletişime geçin.</p>
                <p style="color: #dc2626; font-size: 0.9rem; font-family: monospace;">Hata Detayı: ${error.message}</p>
            </div>`;
        }
    }

    // Uygulamayı başlat
    initializeApp();
});