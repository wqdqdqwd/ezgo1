# bot_manager.py

import asyncio
from typing import Dict
from app.bot_core import BotCore
from app.binance_client import BinanceClient
from app.firebase_manager import firebase_manager
from pydantic import BaseModel
from config import settings # settings nesnesi eklendi

# main.py'deki StartRequest modelini buraya da ekleyebiliriz
# Veya sadece dict olarak geçiş yapmaya devam edebiliriz.
# Temizlik için main.py'deki modeli doğrudan buraya geçirelim.
class StartRequest(BaseModel):
    symbol: str
    timeframe: str
    leverage: int
    order_size: float
    stop_loss: float
    take_profit: float

class BotManager:
    """
    Tüm aktif kullanıcı botlarını yöneten merkezi sınıf.
    Her kullanıcı için bir BotCore nesnesi oluşturur, başlatır ve durdurur.
    """
    def __init__(self):
        # Aktif botları kullanıcı UID'si ile eşleştirerek bir sözlükte tutar
        self.active_bots: Dict[str, BotCore] = {}

    async def start_bot_for_user(self, uid: str, bot_settings: StartRequest) -> Dict:
        """
        Belirtilen kullanıcı için botu başlatır.
        """
        # Bot zaten çalışıyorsa ve abonelik aktifse hata döndür
        if uid in self.active_bots and self.active_bots[uid].status["is_running"]:
            return {"error": "Bot zaten çalışıyor."}

        # Kullanıcının API anahtarlarını Firebase'den al
        user_data = firebase_manager.get_user_data(uid)
        if not user_data:
            return {"error": "Kullanıcı verisi bulunamadı."}
        
        api_key = user_data.get('binance_api_key')
        api_secret = user_data.get('binance_api_secret')

        if not api_key or not api_secret:
            return {"error": "Lütfen önce Binance API anahtarlarınızı kaydedin."}

        # Kullanıcıya özel Binance istemcisi ve BotCore nesnesi oluştur
        client = BinanceClient(api_key=api_key, api_secret=api_secret)
        
        # BotCore nesnesine tüm ayarları geçir
        # Burada bot_settings'ten gelen değerler yerine config.py'den gelenleri kullanıyoruz
        # Web arayüzünüzdeki değerler ile manuel olarak değiştirebilirsiniz
        final_settings = {
            "symbol": bot_settings.symbol,
            "timeframe": bot_settings.timeframe,
            "leverage": bot_settings.leverage,
            "order_size_usdt": bot_settings.order_size,
            "tp_pnl_percent": settings.TIMEFRAME_SETTINGS[bot_settings.timeframe]["TP_PNL"],
            "sl_pnl_percent": settings.TIMEFRAME_SETTINGS[bot_settings.timeframe]["SL_PNL"]
        }
        
        bot = BotCore(user_id=uid, binance_client=client, settings=final_settings)
        
        # Botu aktif botlar listesine ekle
        self.active_bots[uid] = bot
        
        # Botun başlangıç işlemini arka planda çalışacak bir görev olarak başlat
        asyncio.create_task(bot.start()) 
        
        # Botun başlangıç durumunu alması için kısa bir bekleme
        await asyncio.sleep(2) 
        
        return bot.status

    async def stop_bot_for_user(self, uid: str) -> Dict:
        """
        Belirtilen kullanıcı için çalışan botu durdurur.
        """
        if uid in self.active_bots and self.active_bots[uid].status["is_running"]:
            bot = self.active_bots[uid]
            await bot.stop()
            del self.active_bots[uid]
            print(f"BotManager: Kullanıcı {uid} için bot durduruldu ve hafızadan kaldırıldı.")
            return {"success": True, "message": "Bot başarıyla durduruldu."}
        print(f"BotManager: Kullanıcı {uid} için durdurulacak aktif bir bot bulunamadı.")
        return {"error": "Durdurulacak aktif bir bot bulunamadı."}

    def get_bot_status(self, uid: str) -> Dict:
        """
        Kullanıcının botunun anlık durumunu döndürür.
        """
        if uid in self.active_bots:
            return self.active_bots[uid].status
        return {"is_running": False, "symbol": None, "position_side": None, "status_message": "Bot başlatılmadı."}

    async def shutdown_all_bots(self):
        """
        Uygulama kapatılırken tüm aktif botları güvenli bir şekilde durdurur.
        """
        print("Tüm aktif botlar durduruluyor...")
        tasks = [
            bot.stop() for bot in self.active_bots.values() 
            if bot.status["is_running"]
        ]
        await asyncio.gather(*tasks)
        self.active_bots.clear() 
        print("Tüm botlar başarıyla durduruldu.")

# Projenin her yerinden erişmek için bir nesne oluştur
bot_manager = BotManager()
