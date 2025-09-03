import asyncio
from typing import Dict
from app.bot_core import BotCore
from app.binance_client import BinanceClient
from app.firebase_manager import firebase_manager
from pydantic import BaseModel
from .config import settings  # Bu satır güncellendi

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
        if uid in self.active_bots and self.active_bots[uid].status["is_running"]:
            return {"error": "Bot zaten çalışıyor."}

        user_data = firebase_manager.get_user_data(uid)
        if not user_data:
            return {"error": "Kullanıcı verisi bulunamadı."}
        
        api_key = user_data.get('binance_api_key')
        api_secret = user_data.get('binance_api_secret')

        if not api_key or not api_secret:
            return {"error": "Lütfen önce Binance API anahtarlarınızı kaydedin."}

        client = BinanceClient(api_key=api_key, api_secret=api_secret)
        await client.initialize() # İstemciyi başlatma
        
        # Sembol için hassasiyet bilgilerini al ve ayarlara ekle
        symbol_info = await client.get_symbol_info(bot_settings.symbol)
        if not symbol_info:
            return {"error": f"{bot_settings.symbol} için sembol bilgisi bulunamadı."}
            
        quantity_precision = 8
        price_precision = 8
        
        for f in symbol_info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                quantity_precision = int(abs(math.log10(float(f['stepSize']))))
            if f['filterType'] == 'PRICE_FILTER':
                price_precision = int(abs(math.log10(float(f['tickSize']))))

        # Pydantic modelini sözlüğe dönüştür ve hassasiyetleri ekle
        settings_dict = bot_settings.model_dump()
        settings_dict['quantity_precision'] = quantity_precision
        settings_dict['price_precision'] = price_precision
        
        bot = BotCore(user_id=uid, binance_client=client, settings=settings_dict)
        self.active_bots[uid] = bot
        
        asyncio.create_task(bot.start())
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

bot_manager = BotManager()
