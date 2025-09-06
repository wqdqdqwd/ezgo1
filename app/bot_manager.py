import asyncio
from typing import Dict, List
from app.bot_core import BotCore
from app.binance_client import BinanceClient
from app.firebase_manager import firebase_manager
from pydantic import BaseModel

class StartRequest(BaseModel):
    symbol: str
    timeframe: str = "15m"
    leverage: int = 10
    order_size: float = 20.0
    stop_loss: float = 2.0
    take_profit: float = 4.0

class BotManager:
    """
    Çoklu kullanıcı botlarını yöneten merkezi sınıf.
    Her kullanıcı maksimum 4 farklı coin için bot çalıştırabilir.
    """
    
    def __init__(self):
        # Kullanıcı UID'si -> Bot listesi mapping
        self.user_bots: Dict[str, Dict[str, BotCore]] = {}
        self.max_bots_per_user = 4

    def get_user_active_bots(self, uid: str) -> Dict[str, BotCore]:
        """Kullanıcının aktif botlarını getirir"""
        return self.user_bots.get(uid, {})

    def get_total_active_bots(self) -> int:
        """Sistemdeki toplam aktif bot sayısını getirir"""
        total = 0
        for user_bots in self.user_bots.values():
            total += len(user_bots)
        return total

    async def start_bot_for_user(self, uid: str, bot_settings: StartRequest) -> Dict:
        """Kullanıcı için yeni bot başlatır"""
        try:
            # Kullanıcı bot sınırı kontrolü
            user_bots = self.get_user_active_bots(uid)
            if len(user_bots) >= self.max_bots_per_user:
                return {
                    "error": f"Maksimum {self.max_bots_per_user} bot çalıştırabilirsiniz. Önce bir botu durdurun."
                }

            # Aynı sembol için zaten bot çalışıyor mu kontrol et
            symbol = bot_settings.symbol.upper()
            if symbol in user_bots:
                return {"error": f"{symbol} için zaten bir bot çalışıyor."}

            # Kullanıcı verilerini al
            user_data = firebase_manager.get_user_data(uid)
            if not user_data:
                return {"error": "Kullanıcı verisi bulunamadı."}

            # API anahtarları kontrolü
            api_key = user_data.get('binance_api_key')
            api_secret = user_data.get('binance_api_secret')
            if not api_key or not api_secret:
                return {"error": "Lütfen önce Binance API anahtarlarınızı kaydedin."}

            # Abonelik kontrolü
            if not firebase_manager.is_subscription_active(uid):
                return {"error": "Aktif aboneliğiniz bulunmuyor. Lütfen aboneliğinizi yenileyin."}

            print(f"Kullanıcı {uid} için {symbol} botu başlatılıyor...")

            # Binance client oluştur
            try:
                # Testnet kontrolü
                environment = user_data.get('environment', 'LIVE')
                testnet = environment == 'TEST'
                
                client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
                
                # Bağlantıyı test et
                if not await client.initialize():
                    return {"error": "Binance API bağlantısı kurulamadı. API anahtarlarınızı kontrol edin."}
                    
            except Exception as e:
                return {"error": f"Binance client oluşturulamadı: {str(e)}"}

            # Bot ayarlarını hazırla
            settings = {
                "symbol": symbol,
                "timeframe": bot_settings.timeframe,
                "leverage": bot_settings.leverage,
                "order_size": bot_settings.order_size,
                "stop_loss": bot_settings.stop_loss,
                "take_profit": bot_settings.take_profit
            }

            # Bot oluştur ve başlat
            bot = BotCore(user_id=uid, binance_client=client, settings=settings)
            
            # Bot'u kullanıcının bot listesine ekle
            if uid not in self.user_bots:
                self.user_bots[uid] = {}
            self.user_bots[uid][symbol] = bot

            # Bot'u arka planda başlat
            asyncio.create_task(bot.start())
            
            # Başlangıç durumunu kontrol et
            await asyncio.sleep(2)
            
            # Eğer bot başlamamışsa temizle
            if not bot.status["is_running"]:
                await self._cleanup_bot(uid, symbol)
                return {"error": bot.status["status_message"]}

            print(f"✅ Kullanıcı {uid} için {symbol} botu başarıyla başlatıldı")
            
            return {
                "success": True,
                "message": f"{symbol} botu başarıyla başlatıldı",
                "symbol": symbol,
                "status": bot.status,
                "active_bots": len(self.user_bots[uid]),
                "max_bots": self.max_bots_per_user
            }

        except Exception as e:
            error_msg = f"Bot başlatılırken beklenmeyen hata: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}

    async def stop_bot_for_user(self, uid: str, symbol: str = None) -> Dict:
        """Kullanıcının belirtilen botunu durdurur"""
        try:
            user_bots = self.get_user_active_bots(uid)
            
            if not user_bots:
                return {"error": "Durdurulacak aktif bot bulunamadı."}

            if symbol:
                # Belirtilen sembol için botu durdur
                symbol = symbol.upper()
                if symbol not in user_bots:
                    return {"error": f"{symbol} için aktif bot bulunamadı."}
                
                bot = user_bots[symbol]
                await bot.stop()
                await self._cleanup_bot(uid, symbol)
                
                print(f"✅ Kullanıcı {uid} - {symbol} botu durduruldu")
                return {
                    "success": True,
                    "message": f"{symbol} botu durduruldu",
                    "active_bots": len(self.get_user_active_bots(uid))
                }
            else:
                # Tüm botları durdur
                stopped_bots = []
                for symbol, bot in list(user_bots.items()):
                    await bot.stop()
                    stopped_bots.append(symbol)
                
                # Kullanıcının tüm botlarını temizle
                if uid in self.user_bots:
                    del self.user_bots[uid]
                
                print(f"✅ Kullanıcı {uid} - Tüm botlar durduruldu: {stopped_bots}")
                return {
                    "success": True,
                    "message": f"Tüm botlar durduruldu ({len(stopped_bots)} bot)",
                    "stopped_bots": stopped_bots,
                    "active_bots": 0
                }

        except Exception as e:
            error_msg = f"Bot durdurulurken hata: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}

    def get_bot_status(self, uid: str, symbol: str = None) -> Dict:
        """Kullanıcının bot durumunu getirir"""
        try:
            user_bots = self.get_user_active_bots(uid)
            
            if symbol:
                # Belirtilen sembol için durum
                symbol = symbol.upper()
                if symbol in user_bots:
                    bot = user_bots[symbol]
                    return {
                        "symbol": symbol,
                        "status": bot.status,
                        "active_bots": len(user_bots),
                        "max_bots": self.max_bots_per_user
                    }
                else:
                    return {
                        "symbol": symbol,
                        "status": {
                            "is_running": False,
                            "status_message": "Bot çalışmıyor",
                            "position_side": None
                        },
                        "active_bots": len(user_bots),
                        "max_bots": self.max_bots_per_user
                    }
            else:
                # Tüm botların durumu
                all_bots_status = {}
                for sym, bot in user_bots.items():
                    all_bots_status[sym] = bot.status
                
                return {
                    "active_bots": len(user_bots),
                    "max_bots": self.max_bots_per_user,
                    "bots": all_bots_status,
                    "can_start_new": len(user_bots) < self.max_bots_per_user
                }

        except Exception as e:
            print(f"Durum alınırken hata: {e}")
            return {
                "error": f"Durum alınamadı: {str(e)}",
                "active_bots": 0,
                "max_bots": self.max_bots_per_user
            }

    async def get_available_symbols(self, uid: str) -> List[Dict]:
        """Kullanıcı için mevcut sembol listesini getirir"""
        try:
            # Kullanıcı API anahtarlarını al
            user_data = firebase_manager.get_user_data(uid)
            if not user_data:
                return []

            api_key = user_data.get('binance_api_key')
            api_secret = user_data.get('binance_api_secret')
            if not api_key or not api_secret:
                return []

            # Testnet kontrolü
            environment = user_data.get('environment', 'LIVE')
            testnet = environment == 'TEST'

            # Geçici client oluştur
            client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
            
            if await client.initialize():
                symbols = await client.get_available_symbols("USDT")
                await client.close()
                
                # Popüler coinleri öne çıkar
                popular_coins = ['BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'DOT', 'AVAX', 'MATIC', 'LINK', 'UNI']
                
                # Sıralama: önce popüler coinler, sonra alfabetik
                def sort_key(symbol_info):
                    base_asset = symbol_info['baseAsset']
                    if base_asset in popular_coins:
                        return (0, popular_coins.index(base_asset))
                    else:
                        return (1, base_asset)
                
                return sorted(symbols, key=sort_key)
            else:
                await client.close()
                return []

        except Exception as e:
            print(f"Sembol listesi alınamadı: {e}")
            return []

    async def _cleanup_bot(self, uid: str, symbol: str):
        """Bot'u kullanıcının listesinden temizler"""
        try:
            if uid in self.user_bots and symbol in self.user_bots[uid]:
                del self.user_bots[uid][symbol]
                
                # Eğer kullanıcının hiç botu kalmadıysa, kullanıcıyı da sil
                if not self.user_bots[uid]:
                    del self.user_bots[uid]
                    
        except Exception as e:
            print(f"Bot temizliği sırasında hata: {e}")

    async def shutdown_all_bots(self):
        """Tüm aktif botları güvenli şekilde durdurur"""
        print("🔄 Tüm aktif botlar durduruluyor...")
        
        total_bots = 0
        for uid, user_bots in list(self.user_bots.items()):
            for symbol, bot in list(user_bots.items()):
                try:
                    if bot.status["is_running"]:
                        await bot.stop()
                        total_bots += 1
                except Exception as e:
                    print(f"Bot durdurulamadı ({uid}/{symbol}): {e}")
        
        # Tüm botları temizle
        self.user_bots.clear()
        
        print(f"✅ {total_bots} bot başarıyla durduruldu")

    def get_system_stats(self) -> Dict:
        """Sistem istatistiklerini getirir"""
        total_users = len(self.user_bots)
        total_bots = self.get_total_active_bots()
        
        user_bot_counts = {}
        for uid, user_bots in self.user_bots.items():
            user_bot_counts[uid] = len(user_bots)
        
        return {
            "total_users_with_bots": total_users,
            "total_active_bots": total_bots,
            "max_bots_per_user": self.max_bots_per_user,
            "user_bot_counts": user_bot_counts,
            "system_capacity": total_users * self.max_bots_per_user
        }

# Global bot manager instance
bot_manager = BotManager()
