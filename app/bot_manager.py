import asyncio
from typing import Dict, Optional
from app.bot_core import BotCore
from app.binance_client import BinanceClient
from app.firebase_manager import firebase_manager
from app.utils.logger import get_logger
from pydantic import BaseModel, Field

logger = get_logger("bot_manager")

# Bot ayarları için model (Pydantic v2 syntax)
class StartRequest(BaseModel):
    symbol: str = Field(..., min_length=6, max_length=12)
    timeframe: str = Field(..., pattern=r'^(1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d)$')
    leverage: int = Field(..., ge=1, le=125)
    order_size: float = Field(..., ge=10.0, le=10000.0)
    stop_loss: float = Field(..., ge=0.1, le=50.0)
    take_profit: float = Field(..., ge=0.1, le=100.0)
    strategy: str = Field(default="EMA_CROSS", description="Trading strategy")

class BotManager:
    """
    Tüm aktif kullanıcı botlarını yöneten merkezi sınıf.
    Her kullanıcı için bir BotCore nesnesi oluşturur, başlatır ve durdurur.
    """
    def __init__(self):
        # Aktif botları kullanıcı UID'si ile eşleştirerek bir sözlükte tutar
        self.active_bots: Dict[str, BotCore] = {}
        logger.info("BotManager initialized")

    async def start_bot_for_user(self, uid: str, bot_settings: StartRequest) -> Dict:
        """
        Belirtilen kullanıcı için botu başlatır.
        """
        try:
            logger.info(f"Starting bot for user: {uid}")
            
            # Bot zaten çalışıyorsa hata döndür
            if uid in self.active_bots:
                current_bot = self.active_bots[uid]
                if hasattr(current_bot, 'status') and current_bot.status.get("is_running", False):
                    logger.warning(f"Bot already running for user: {uid}")
                    return {"error": "Bot zaten çalışıyor."}

            # Kullanıcının API anahtarlarını Firebase'den al
            logger.info(f"Getting user data for: {uid}")
            user_data = firebase_manager.get_user_data(uid)
            
            if not user_data:
                logger.error(f"User data not found for: {uid}")
                return {"error": "Kullanıcı verisi bulunamadı."}
            
            logger.info(f"User data retrieved for: {uid}")
            
            api_key = user_data.get('binance_api_key')
            api_secret = user_data.get('binance_api_secret')

            if not api_key or not api_secret:
                logger.error(f"API keys not found for user: {uid}")
                return {"error": "Lütfen önce Binance API anahtarlarınızı kaydedin."}

            logger.info(f"API keys found for user: {uid}")

            # Kullanıcıya özel Binance istemcisi oluştur
            try:
                client = BinanceClient(api_key=api_key, api_secret=api_secret)
                logger.info(f"Binance client created for user: {uid}")
            except Exception as e:
                logger.error(f"Failed to create Binance client for user {uid}: {str(e)}")
                return {"error": f"Binance bağlantısı kurulamadı: {str(e)}"}
            
            # BotCore nesnesine tüm ayarları geçir
            try:
                bot_settings_dict = bot_settings.model_dump()
                bot_settings_dict['user_id'] = uid  # Ensure user_id is included
                
                bot = BotCore(
                    user_id=uid, 
                    binance_client=client, 
                    settings=bot_settings_dict
                )
                logger.info(f"BotCore created for user: {uid}")
            except Exception as e:
                logger.error(f"Failed to create BotCore for user {uid}: {str(e)}")
                return {"error": f"Bot oluşturulamadı: {str(e)}"}
            
            # Botu aktif botlar listesine ekle
            self.active_bots[uid] = bot
            
            # Botun başlangıç işlemini arka planda çalışacak bir görev olarak başlat
            try:
                # Bot start metodunu çağır
                task = asyncio.create_task(bot.start())
                logger.info(f"Bot start task created for user: {uid}")
                
                # Botun başlangıç durumunu alması için kısa bir bekleme
                await asyncio.sleep(1)
                
                # Bot başlatma başarılı olup olmadığını kontrol et
                if hasattr(bot, 'status'):
                    status = bot.status
                else:
                    # Eğer status özelliği henüz oluşmadıysa varsayılan değerler
                    status = {
                        "is_running": True,
                        "symbol": bot_settings.symbol,
                        "position_side": "waiting",
                        "status_message": "Bot başlatıldı, sinyal bekleniyor...",
                        "last_check_time": None
                    }
                
                logger.info(f"Bot started successfully for user: {uid}")
                
                # Bot durumunu dictionary olarak döndür
                return {
                    "is_running": status.get("is_running", True),
                    "symbol": status.get("symbol", bot_settings.symbol),
                    "position_side": status.get("position_side", "waiting"),
                    "status_message": status.get("status_message", "Bot başlatıldı."),
                    "last_check_time": status.get("last_check_time", None),
                    "strategy": bot_settings.strategy,
                    "leverage": bot_settings.leverage,
                    "order_size": bot_settings.order_size
                }
                
            except Exception as e:
                logger.error(f"Failed to start bot for user {uid}: {str(e)}")
                # Hatalı bot'u listeden kaldır
                if uid in self.active_bots:
                    del self.active_bots[uid]
                return {"error": f"Bot başlatılamadı: {str(e)}"}

        except Exception as e:
            logger.error(f"Unexpected error starting bot for user {uid}: {str(e)}")
            # Hatalı bot'u listeden kaldır
            if uid in self.active_bots:
                del self.active_bots[uid]
            return {"error": f"Beklenmeyen hata: {str(e)}"}

    async def stop_bot_for_user(self, uid: str) -> Dict:
        """
        Belirtilen kullanıcı için çalışan botu durdurur.
        """
        try:
            logger.info(f"Stopping bot for user: {uid}")
            
            if uid in self.active_bots:
                bot = self.active_bots[uid]
                
                # Bot'un durumunu kontrol et
                if hasattr(bot, 'status') and bot.status.get("is_running", False):
                    try:
                        await bot.stop()
                        logger.info(f"Bot stopped for user: {uid}")
                    except Exception as e:
                        logger.error(f"Error stopping bot for user {uid}: {str(e)}")
                        # Hata olsa bile bot'u listeden kaldır
                        pass
                
                # Bot'u listeden kaldır
                del self.active_bots[uid]
                logger.info(f"Bot removed from active list for user: {uid}")
                
                return {"success": True, "message": "Bot başarıyla durduruldu."}
            else:
                logger.warning(f"No active bot found for user: {uid}")
                return {"error": "Durdurulacak aktif bir bot bulunamadı."}
                
        except Exception as e:
            logger.error(f"Error stopping bot for user {uid}: {str(e)}")
            return {"error": f"Bot durdurulamadı: {str(e)}"}

    def get_bot_status(self, uid: str) -> Dict:
        """
        Kullanıcının botunun anlık durumunu döndürür.
        """
        try:
            if uid in self.active_bots:
                bot = self.active_bots[uid]
                
                # Bot status'unu kontrol et
                if hasattr(bot, 'status') and bot.status:
                    status = bot.status
                    return {
                        "is_running": status.get("is_running", False),
                        "symbol": status.get("symbol", None),
                        "position_side": status.get("position_side", None),
                        "status_message": status.get("status_message", "Bot durumu bilinmiyor."),
                        "last_check_time": status.get("last_check_time", None),
                        "strategy": status.get("strategy", "Unknown"),
                        "leverage": status.get("leverage", 0),
                        "order_size": status.get("order_size", 0),
                        "total_pnl": status.get("total_pnl", 0),
                        "today_trades": status.get("today_trades", 0)
                    }
                else:
                    # Bot var ama status henüz oluşmamış
                    return {
                        "is_running": True,
                        "symbol": None,
                        "position_side": "initializing",
                        "status_message": "Bot başlatılıyor...",
                        "last_check_time": None
                    }
            
            # Eğer kullanıcı için çalışan bir bot yoksa
            return {
                "is_running": False, 
                "symbol": None, 
                "position_side": None, 
                "status_message": "Bot başlatılmadı.",
                "last_check_time": None,
                "strategy": None,
                "leverage": 0,
                "order_size": 0,
                "total_pnl": 0,
                "today_trades": 0
            }
            
        except Exception as e:
            logger.error(f"Error getting bot status for user {uid}: {str(e)}")
            return {
                "is_running": False,
                "symbol": None,
                "position_side": None,
                "status_message": f"Durum alınamadı: {str(e)}",
                "last_check_time": None
            }

    async def shutdown_all_bots(self):
        """
        Uygulama kapatılırken tüm aktif botları güvenli bir şekilde durdurur.
        """
        try:
            logger.info("Shutting down all active bots...")
            
            if not self.active_bots:
                logger.info("No active bots to shutdown")
                return
            
            # Tüm botları paralel olarak durdur
            tasks = []
            for uid, bot in self.active_bots.items():
                try:
                    if hasattr(bot, 'status') and bot.status.get("is_running", False):
                        tasks.append(bot.stop())
                        logger.info(f"Added shutdown task for user: {uid}")
                except Exception as e:
                    logger.error(f"Error preparing shutdown for user {uid}: {str(e)}")
            
            # Tüm shutdown işlemlerini bekle
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Shutdown completed for {len(tasks)} bots")
            
            # Tüm botları temizle
            self.active_bots.clear()
            logger.info("All bots shutdown completed successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            # Hata olsa bile botları temizle
            self.active_bots.clear()

    def get_active_bot_count(self) -> int:
        """Aktif bot sayısını döndürür"""
        return len(self.active_bots)

    def get_all_active_users(self) -> list:
        """Aktif bot'u olan kullanıcıların listesini döndürür"""
        return list(self.active_bots.keys())

# Projenin her yerinden erişmek için bir nesne oluştur
bot_manager = BotManager()
