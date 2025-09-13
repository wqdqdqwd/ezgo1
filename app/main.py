# Bu kod mevcut app/main.py dosyasına eklenmeli

from pydantic import BaseModel
from typing import Optional
import os

# Yeni Pydantic modeller
class PaymentNotification(BaseModel):
    transaction_hash: str
    amount: float
    currency: str = "USDT"

class SupportMessage(BaseModel):
    subject: str
    message: str
    user_email: str

# Ödeme bilgilerini getir
@app.get("/api/payment-info")
async def get_payment_info():
    """Ödeme bilgilerini döndürür"""
    return {
        "success": True,
        "amount": "$15/Ay",
        "trc20Address": os.getenv("PAYMENT_TRC20_ADDRESS", "TMjSDNto6hoHUV9udDcXVAtuxxX6cnhhv3"),
        "botPriceUsd": os.getenv("BOT_PRICE_USD", "15")
    }

# Ödeme bildirimi
@app.post("/api/payment/notify")
async def notify_payment(
    request: Request,
    payment: PaymentNotification,
    current_user: dict = Depends(get_current_user)
):
    """Kullanıcıdan ödeme bildirimi alır ve admin'e iletir"""
    # Rate limiting manuel kontrol
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "3/hour")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        # Ödeme bildirimini Firebase'e kaydet
        payment_data = {
            "user_id": current_user['uid'],
            "user_email": current_user.get('email', ''),
            "transaction_hash": payment.transaction_hash,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "admin_notified": False
        }
        
        # Firebase Realtime Database'e kaydet
        payment_ref = firebase_manager.db.reference('payment_notifications').push()
        payment_ref.set(payment_data)
        
        logger.info("Payment notification received", 
                   user_id=current_user['uid'], 
                   transaction_hash=payment.transaction_hash,
                   amount=payment.amount)
        
        return {
            "success": True,
            "message": "Ödeme bildirimi alındı. Admin onayı bekleniyor.",
            "notification_id": payment_ref.key
        }
        
    except Exception as e:
        logger.error("Payment notification failed", 
                    user_id=current_user['uid'], 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Payment notification failed")

# Destek mesajı gönder
@app.post("/api/support/message")
async def send_support_message(
    request: Request,
    support: SupportMessage,
    current_user: dict = Depends(get_current_user)
):
    """Destek mesajı gönderir"""
    # Rate limiting manuel kontrol
    if RATE_LIMITING_ENABLED:
        try:
            await limiter.check_request_limit(request, "5/hour")
        except Exception:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        # Destek mesajını Firebase'e kaydet
        support_data = {
            "user_id": current_user['uid'],
            "user_email": support.user_email,
            "subject": support.subject,
            "message": support.message,
            "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "admin_response": None,
            "closed_at": None
        }
        
        # Firebase Realtime Database'e kaydet
        support_ref = firebase_manager.db.reference('support_messages').push()
        support_ref.set(support_data)
        
        logger.info("Support message received", 
                   user_id=current_user['uid'], 
                   subject=support.subject)
        
        return {
            "success": True,
            "message": "Destek mesajınız alındı. En kısa sürede dönüş yapacağız.",
            "ticket_id": support_ref.key
        }
        
    except Exception as e:
        logger.error("Support message failed", 
                    user_id=current_user['uid'], 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Support message failed")

# Admin endpoints

# Admin - Tüm kullanıcıları listele
@app.get("/api/admin/users")
async def get_all_users(current_user: dict = Depends(get_admin_user)):
    """Admin için tüm kullanıcıları listeler"""
    try:
        users_ref = firebase_manager.db.reference('users')
        users_snapshot = users_ref.get()
        
        if not users_snapshot:
            return {"success": True, "users": {}}
        
        # Hassas bilgileri filtrele
        filtered_users = {}
        for uid, user_data in users_snapshot.items():
            filtered_users[uid] = {
                "email": user_data.get('email'),
                "created_at": user_data.get('created_at'),
                "subscription_status": user_data.get('subscription_status'),
                "subscription_expiry": user_data.get('subscription_expiry'),
                "last_login": user_data.get('last_login'),
                "has_api_keys": bool(user_data.get('binance_api_key')),
                "total_trades": user_data.get('total_trades', 0),
                "total_pnl": user_data.get('total_pnl', 0)
            }
        
        return {"success": True, "users": filtered_users}
        
    except Exception as e:
        logger.error("Admin get users failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch users")

# Admin - Kullanıcı detaylarını getir
@app.get("/api/admin/user-details/{user_id}")
async def get_user_details(
    user_id: str,
    current_user: dict = Depends(get_admin_user)
):
    """Admin için kullanıcı detaylarını getirir"""
    try:
        user_ref = firebase_manager.db.reference(f'users/{user_id}')
        user_data = user_ref.get()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Hassas bilgileri filtrele
        filtered_data = {
            "email": user_data.get('email'),
            "created_at": user_data.get('created_at'),
            "subscription_status": user_data.get('subscription_status'),
            "subscription_expiry": user_data.get('subscription_expiry'),
            "last_login": user_data.get('last_login'),
            "has_api_keys": bool(user_data.get('binance_api_key')),
            "total_trades": user_data.get('total_trades', 0),
            "total_pnl": user_data.get('total_pnl', 0),
            "bot_status": user_data.get('bot_status', 'inactive'),
            "selected_pair": user_data.get('selected_pair', 'BTCUSDT'),
            "language": user_data.get('language', 'tr')
        }
        
        return {"success": True, "user": filtered_data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin get user details failed", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch user details")

# Admin - Kullanıcı aboneliğini aktifleştir
@app.post("/api/admin/activate-subscription")
async def activate_user_subscription(
    request: Request,
    current_user: dict = Depends(get_admin_user)
):
    """Admin tarafından kullanıcı aboneliğini aktifleştirir"""
    try:
        data = await request.json()
        user_id = data.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID required")
        
        # Kullanıcı var mı kontrol et
        user_ref = firebase_manager.db.reference(f'users/{user_id}')
        user_data = user_ref.get()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # 30 gün ekle
        from datetime import timedelta
        current_expiry = user_data.get('subscription_expiry')
        
        if current_expiry:
            try:
                current_expiry_date = datetime.fromisoformat(current_expiry)
                # Eğer süresi geçmişse bugünden başlat, değilse mevcut tarihten devam et
                start_date = max(datetime.now(timezone.utc), current_expiry_date)
            except:
                start_date = datetime.now(timezone.utc)
        else:
            start_date = datetime.now(timezone.utc)
        
        new_expiry = start_date + timedelta(days=30)
        
        # Kullanıcı verisini güncelle
        update_data = {
            "subscription_status": "active",
            "subscription_expiry": new_expiry.isoformat(),
            "updated_by_admin": current_user.get('email'),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        user_ref.update(update_data)
        
        logger.info("User subscription activated by admin", 
                   admin_email=current_user.get('email'),
                   target_user=user_id,
                   new_expiry=new_expiry.isoformat())
        
        return {
            "success": True,
            "message": "User subscription activated for 30 days",
            "new_expiry": new_expiry.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin activate subscription failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to activate subscription")

# Admin - Ödeme bildirimlerini listele
@app.get("/api/admin/payment-notifications")
async def get_payment_notifications(current_user: dict = Depends(get_admin_user)):
    """Admin için ödeme bildirimlerini listeler"""
    try:
        payments_ref = firebase_manager.db.reference('payment_notifications')
        payments_snapshot = payments_ref.order_by_child('created_at').get()
        
        if not payments_snapshot:
            return {"success": True, "notifications": []}
        
        notifications = []
        for notification_id, payment_data in payments_snapshot.items():
            notifications.append({
                "id": notification_id,
                "user_id": payment_data.get('user_id'),
                "user_email": payment_data.get('user_email'),
                "transaction_hash": payment_data.get('transaction_hash'),
                "amount": payment_data.get('amount'),
                "currency": payment_data.get('currency'),
                "status": payment_data.get('status'),
                "created_at": payment_data.get('created_at')
            })
        
        # En yeni önce gelsin
        notifications.reverse()
        
        return {"success": True, "notifications": notifications}
        
    except Exception as e:
        logger.error("Admin get payment notifications failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch payment notifications")

# Admin - Ödeme bildirimini onayla
@app.post("/api/admin/approve-payment/{notification_id}")
async def approve_payment(
    notification_id: str,
    current_user: dict = Depends(get_admin_user)
):
    """Admin tarafından ödeme bildirimini onaylar ve kullanıcıya gün ekler"""
    try:
        # Ödeme bildirimini getir
        payment_ref = firebase_manager.db.reference(f'payment_notifications/{notification_id}')
        payment_data = payment_ref.get()
        
        if not payment_data:
            raise HTTPException(status_code=404, detail="Payment notification not found")
        
        if payment_data.get('status') != 'pending':
            raise HTTPException(status_code=400, detail="Payment already processed")
        
        user_id = payment_data.get('user_id')
        
        # Kullanıcı aboneliğini aktifleştir
        user_ref = firebase_manager.db.reference(f'users/{user_id}')
        user_data = user_ref.get()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # 30 gün ekle
        from datetime import timedelta
        current_expiry = user_data.get('subscription_expiry')
        
        if current_expiry:
            try:
                current_expiry_date = datetime.fromisoformat(current_expiry)
                start_date = max(datetime.now(timezone.utc), current_expiry_date)
            except:
                start_date = datetime.now(timezone.utc)
        else:
            start_date = datetime.now(timezone.utc)
        
        new_expiry = start_date + timedelta(days=30)
        
        # Kullanıcı verisini güncelle
        user_ref.update({
            "subscription_status": "active",
            "subscription_expiry": new_expiry.isoformat(),
            "updated_by_admin": current_user.get('email'),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Ödeme bildirimini onayla
        payment_ref.update({
            "status": "approved",
            "approved_by": current_user.get('email'),
            "approved_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info("Payment approved by admin", 
                   admin_email=current_user.get('email'),
                   notification_id=notification_id,
                   user_id=user_id,
                   new_expiry=new_expiry.isoformat())
        
        return {
            "success": True,
            "message": "Payment approved and user subscription activated",
            "new_expiry": new_expiry.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin approve payment failed", 
                    notification_id=notification_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to approve payment")

# Admin - Destek mesajlarını listele
@app.get("/api/admin/support-messages")
async def get_support_messages(current_user: dict = Depends(get_admin_user)):
    """Admin için destek mesajlarını listeler"""
    try:
        messages_ref = firebase_manager.db.reference('support_messages')
        messages_snapshot = messages_ref.order_by_child('created_at').get()
        
        if not messages_snapshot:
            return {"success": True, "messages": []}
        
        messages = []
        for message_id, message_data in messages_snapshot.items():
            messages.append({
                "id": message_id,
                "user_id": message_data.get('user_id'),
                "user_email": message_data.get('user_email'),
                "subject": message_data.get('subject'),
                "message": message_data.get('message'),
                "status": message_data.get('status'),
                "created_at": message_data.get('created_at'),
                "admin_response": message_data.get('admin_response'),
                "closed_at": message_data.get('closed_at')
            })
        
        # En yeni önce gelsin
        messages.reverse()
        
        return {"success": True, "messages": messages}
        
    except Exception as e:
        logger.error("
