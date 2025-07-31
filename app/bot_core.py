import asyncio
import json
import websockets
import math
from datetime import datetime, timezone
from app.binance_client import BinanceClient
from app.trading_strategy import trading_strategy
from app.firebase_manager import firebase_manager # FirebaseManager'ı import et

class BotCore:
    def __init__(self, user_id: str, binance_client: BinanceClient, settings: dict):
        self.user_id = user_id
        self.binance_client = binance_client
        self.settings = settings  # Kullanıcıdan gelen tüm ayarlar
        self.status = {
            "is_running": False, 
            "symbol": self.settings.get('symbol'), 
            "position_side": None, 
            "status_message": "Bot başlatılmadı.",
            "last_check_time": datetime.now(timezone.utc).isoformat() # Son kontrol zamanı eklendi
        }
        self.klines = []
        self._stop_requested = False
        self.quantity_precision = 0
        self.price_precision = 0
        self.websocket_task = None
        self.subscription_check_interval = 60 # Abonelik kontrolü saniye cinsinden (örn: 60 saniye)

    def _get_precision_from_filter(self, symbol_info, filter_type, key):
        for f in symbol_info['filters']:
            if f['filterType'] == filter_type:
                size_str = f[key]
                if '.' in size_str: return len(size_str.split('.')[1].rstrip('0'))
                return 0
        return 0

    def _format_quantity(self, quantity: float):
        if self.quantity_precision == 0: return math.floor(quantity)
        factor = 10 ** self.quantity_precision
        return math.floor(quantity * factor) / factor

    async def start(self): # symbol argümanı kaldırıldı
        if self.status["is_running"]: return
        
        self._stop_requested = False
        self.status.update({"is_running": True, "status_message": f"{self.settings['symbol']} için başlatılıyor..."})
        
        # Abonelik kontrolünü bot başlatılırken de yap
        if not firebase_manager.is_subscription_active(self.user_id):
            self.status["status_message"] = "Bot başlatılamadı: Aboneliğiniz aktif değil veya süresi dolmuş."
            print(f"{self.user_id}: Abonelik aktif olmadığı için bot başlatılamadı.")
            await self.stop(); return

        if not await self.binance_client.initialize():
            self.status["status_message"] = "Binance bağlantısı kurulamadı. API anahtarlarınızı kontrol edin."
            await self.stop(); return

        symbol_info = await self.binance_client.get_symbol_info(self.settings['symbol'])
        if not symbol_info:
            self.status["status_message"] = f"{self.settings['symbol']} için borsa bilgileri alınamadı."
            await self.stop(); return
            
        self.quantity_precision = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
        self.price_precision = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')

        if not await self.binance_client.set_leverage(self.settings['symbol'], self.settings['leverage']):
            self.status["status_message"] = "Kaldıraç ayarlanamadı."
            await self.stop(); return

        self.klines = await self.binance_client.get_historical_klines(self.settings['symbol'], self.settings['timeframe'], limit=50)
        if not self.klines:
            self.status["status_message"] = "Geçmiş mum verisi alınamadı."
            await self.stop(); return

        self.status["status_message"] = f"{self.settings['symbol']} ({self.settings['timeframe']}) için sinyal bekleniyor..."
        ws_url = f"wss://fstream.binance.com/ws/{self.settings['symbol'].lower()}@kline_{self.settings['timeframe']}"
        self.websocket_task = asyncio.create_task(self._websocket_listener(ws_url))
        print(f"{self.user_id}: Bot başarıyla başlatıldı ve WebSocket dinleniyor.")

    async def _websocket_listener(self, ws_url: str):
        print(f"{self.user_id} için WebSocket bağlantısı kuruluyor: {ws_url}")
        last_subscription_check = datetime.now(timezone.utc)

        while not self._stop_requested:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    print(f"{self.user_id} için WebSocket bağlantısı başarılı.")
                    while not self._stop_requested:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                            await self._handle_websocket_message(message)

                            # Abonelik kontrolü ekle
                            current_time = datetime.now(timezone.utc)
                            if (current_time - last_subscription_check).total_seconds() >= self.subscription_check_interval:
                                if not firebase_manager.is_subscription_active(self.user_id):
                                    self.status["status_message"] = "Aboneliğiniz sona erdi, bot durduruluyor."
                                    print(f"{self.user_id}: Aboneliği sona erdiği için bot durdurma isteği.")
                                    await self.stop()
                                    return # Bot durdurulduğu için döngüden çık
                                last_subscription_check = current_time
                                self.status["last_check_time"] = current_time.isoformat() # UI'da göstermek için

                        except asyncio.TimeoutError:
                            await ws.ping()
                        except websockets.exceptions.ConnectionClosed:
                            print(f"{self.user_id} için WebSocket bağlantısı kapandı. Yeniden bağlanılacak.")
                            await asyncio.sleep(5)
                            break
                        except Exception as e:
                            print(f"{self.user_id} için WebSocket mesaj işleme hatası: {e}")
                            await asyncio.sleep(1) # Hata durumunda kısa bekleme

            except Exception as e:
                print(f"{self.user_id} için WebSocket bağlantı hatası: {e}. 5 saniye sonra tekrar denenecek.")
                await asyncio.sleep(5)
        print(f"{self.user_id} için WebSocket dinleyicisi durduruldu.")


    async def stop(self):
        if not self._stop_requested:
            self._stop_requested = True
            
            # Eğer açık pozisyon varsa kapat
            open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
            if open_positions:
                print(f"--> {self.user_id}: Bot durdurulurken açık pozisyonlar kapatılıyor...")
                await self.binance_client.close_open_position_and_orders(self.settings["symbol"])
                pnl = await self.binance_client.get_last_trade_pnl(self.settings["symbol"])
                firebase_manager.log_trade(self.user_id, {"symbol": self.settings["symbol"], "pnl": pnl, "status": "CLOSED_ON_BOT_STOP", "timestamp": datetime.now(timezone.utc)})
                await asyncio.sleep(1) # Pozisyonun kapanması için kısa bekleme

            if self.websocket_task and not self.websocket_task.done():
                self.websocket_task.cancel()
                try:
                    await self.websocket_task # Görevin iptal edilmesini bekle
                except asyncio.CancelledError:
                    print(f"{self.user_id}: WebSocket görevi iptal edildi.")
                except Exception as e:
                    print(f"{self.user_id}: WebSocket görevi iptal edilirken hata: {e}")

            if self.status["is_running"]:
                self.status.update({"is_running": False, "status_message": "Bot durduruldu."})
                print(f"{self.user_id} için bot durduruluyor...")
                await self.binance_client.close() # HTTP oturumunu kapat
                print(f"{self.user_id} için bot başarıyla durduruldu.")

    async def _handle_websocket_message(self, message: str):
        data = json.loads(message)
        if not data.get('k', {}).get('x', False): return # Sadece kapanmış mum çubuklarını işle
            
        # Klines listesini güncelle
        self.klines.pop(0)
        # Binance kline verisi formatına göre güncellendi
        self.klines.append([
            data['k']['t'],  # Open time
            data['k']['o'],  # Open
            data['k']['h'],  # High
            data['k']['l'],  # Low
            data['k']['c'],  # Close
            data['k']['v'],  # Volume
            data['k']['T'],  # Close time
            data['k']['q'],  # Quote asset volume
            data['k']['n'],  # Number of trades
            data['k']['V'],  # Taker buy base asset volume
            data['k']['Q'],  # Taker buy quote asset volume
            data['k']['B']   # Ignore (actual value varies, typically last_value_ignored)
        ])
        
        # Pozisyon kontrolü
        open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
        if self.status["position_side"] is not None and not open_positions:
            print(f"--> {self.user_id}: Pozisyon SL/TP ile veya manuel olarak kapandı.")
            pnl = await self.binance_client.get_last_trade_pnl(self.settings["symbol"])
            firebase_manager.log_trade(self.user_id, {"symbol": self.settings["symbol"], "pnl": pnl, "status": "CLOSED_BY_SL_TP_OR_MANUAL", "timestamp": datetime.now(timezone.utc)})
            self.status["position_side"] = None

        # Sinyal analizi
        signal = trading_strategy.analyze_klines(self.klines)
        if signal != "HOLD":
            print(f"{self.user_id} - Strateji analizi sonucu: {signal}")

        # Pozisyonu çevir veya aç
        if signal != "HOLD" and signal != self.status.get("position_side"):
            await self._flip_position(signal)

    async def _flip_position(self, new_signal: str):
        symbol = self.settings["symbol"]
        
        # Aboneliğin aktif olup olmadığını tekrar kontrol et
        if not firebase_manager.is_subscription_active(self.user_id):
            self.status["status_message"] = "Aboneliğiniz sona erdi, yeni pozisyon açılamıyor."
            print(f"{self.user_id}: Aboneliği sona erdiği için yeni pozisyon açılamadı.")
            await self.stop()
            return

        open_positions = await self.binance_client.get_open_positions(symbol)
        if open_positions:
            # Mevcut pozisyonu ve açık emirleri kapat
            print(f"--> {self.user_id}: Ters sinyal geldi. Mevcut {self.status['position_side']} pozisyonu kapatılıyor...")
            await self.binance_client.close_open_position_and_orders(symbol)
            pnl = await self.binance_client.get_last_trade_pnl(symbol)
            firebase_manager.log_trade(self.user_id, {"symbol": symbol, "pnl": pnl, "status": "CLOSED_BY_FLIP", "timestamp": datetime.now(timezone.utc)})
            await asyncio.sleep(1) # Pozisyonun kapanması için kısa bekleme

        print(f"--> {self.user_id}: Yeni {new_signal} pozisyonu açılıyor...")
        side = "BUY" if new_signal == "LONG" else "SELL"
        price = await self.binance_client.get_market_price(symbol)
        if not price:
            self.status["status_message"] = "Yeni pozisyon için fiyat alınamadı."
            print(f"{self.user_id}: {self.status['status_message']}")
            return
            
        quantity = self._format_quantity((self.settings['order_size']) / price)
        if quantity <= 0:
            self.status["status_message"] = f"Hesaplanan miktar çok düşük: {quantity}"
            print(f"{self.user_id}: {self.status['status_message']}")
            return

        order = await self.binance_client.create_order_with_tp_sl(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
            price_precision=self.price_precision,
            stop_loss_percent=self.settings['stop_loss'],
            take_profit_percent=self.settings['take_profit']
        )
        if order:
            self.status["position_side"] = new_signal
            self.status["status_message"] = f"Yeni {new_signal} pozisyonu {price} fiyattan açıldı."
        else:
            self.status["position_side"] = None
            self.status["status_message"] = "Yeni pozisyon açılamadı."
        print(f"{self.user_id}: {self.status['status_message']}")