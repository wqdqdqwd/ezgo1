import asyncio
import json
import websockets
import math
from datetime import datetime, timezone
from app.binance_client import BinanceClient
from app.trading_strategy import trading_strategy
from app.firebase_manager import firebase_manager

class BotCore:
    def __init__(self, user_id: str, binance_client: BinanceClient, settings: dict):
        self.user_id = user_id
        self.binance_client = binance_client
        self.settings = settings
        self.status = {
            "is_running": False,
            "symbol": self.settings.get('symbol'),
            "position_side": None,
            "status_message": "Bot başlatılmadı.",
            "last_check_time": datetime.now(timezone.utc).isoformat(),
            "account_balance": 0.0,
            "position_pnl": 0.0,
            "entry_price": 0.0,
            "current_price": 0.0
        }
        self.klines = []
        self._stop_requested = False
        self.quantity_precision = 0
        self.price_precision = 0
        self.step_size = 0.0
        self.websocket_task = None
        self.subscription_check_interval = 60

    def _get_precision_from_filter(self, symbol_info, filter_type, key):
        """Binance sembol filtresinden hassasiyet değerini alır"""
        for f in symbol_info['filters']:
            if f['filterType'] == filter_type:
                size_str = f[key]
                if '.' in size_str:
                    return len(size_str.split('.')[1].rstrip('0'))
                return 0
        return 0

    def _format_quantity(self, quantity: float, step_size: float):
        """Miktarı Binance'in stepSize'ına göre formatlar"""
        step_size_str = f"{step_size:f}"
        if '.' in step_size_str:
            precision = len(step_size_str.split('.')[1].rstrip('0'))
        else:
            precision = 0
        
        # Miktarı stepSize'ın katına yuvarla
        formatted_quantity = math.floor(quantity / step_size) * step_size
        return round(formatted_quantity, precision)

    async def start(self):
        """Bot'u başlatır"""
        if self.status["is_running"]:
            print(f"{self.user_id}: Bot zaten çalışıyor.")
            return

        self._stop_requested = False
        self.status.update({
            "is_running": True,
            "status_message": f"{self.settings['symbol']} için başlatılıyor..."
        })
        
        print(f"{self.user_id}: Bot başlatılıyor - {self.settings['symbol']}")

        try:
            # 1. Abonelik kontrolü
            if not firebase_manager.is_subscription_active(self.user_id):
                self.status["status_message"] = "Aboneliğiniz aktif değil veya süresi dolmuş."
                print(f"{self.user_id}: Abonelik aktif olmadığı için bot başlatılamadı.")
                await self.stop()
                return

            # 2. Binance bağlantısı
            if not await self.binance_client.initialize():
                self.status["status_message"] = "Binance bağlantısı kurulamadı. API anahtarlarınızı kontrol edin."
                await self.stop()
                return

            # 3. Sembol bilgilerini al
            symbol_info = await self.binance_client.get_symbol_info(self.settings['symbol'])
            if not symbol_info:
                self.status["status_message"] = f"{self.settings['symbol']} sembolü bulunamadı. Geçerli bir futures sembolü seçin."
                print(f"{self.user_id}: Sembol bulunamadı - {self.settings['symbol']}")
                await self.stop()
                return

            # 4. Precision değerlerini hesapla
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            price_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)

            if not lot_size_filter or not price_filter:
                self.status["status_message"] = f"{self.settings['symbol']} için gerekli filtre bilgileri bulunamadı."
                await self.stop()
                return

            self.quantity_precision = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
            self.price_precision = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')
            self.step_size = float(lot_size_filter['stepSize'])

            print(f"{self.user_id}: {self.settings['symbol']} - Miktar hassasiyeti: {self.quantity_precision}, Fiyat hassasiyeti: {self.price_precision}")

            # 5. Kaldıraç ayarla (isteğe bağlı)
            try:
                await self.binance_client.set_leverage(self.settings['symbol'], self.settings.get('leverage', 10))
            except Exception as e:
                print(f"{self.user_id}: Kaldıraç ayarlanamadı (muhtemelen zaten doğru): {e}")

            # 6. Geçmiş veri çek
            self.klines = await self.binance_client.get_historical_klines(
                self.settings['symbol'], 
                self.settings.get('timeframe', '15m'), 
                limit=50
            )
            
            if not self.klines:
                self.status["status_message"] = "Geçmiş mum verisi alınamadı."
                await self.stop()
                return

            # 7. WebSocket dinleyicisini başlat
            self.status["status_message"] = f"{self.settings['symbol']} ({self.settings.get('timeframe', '15m')}) için sinyal bekleniyor..."
            timeframe = self.settings.get('timeframe', '15m')
            ws_url = f"wss://fstream.binance.com/ws/{self.settings['symbol'].lower()}@kline_{timeframe}"
            
            self.websocket_task = asyncio.create_task(self._websocket_listener(ws_url))
            print(f"{self.user_id}: Bot başarıyla başlatıldı - {self.settings['symbol']}")

        except Exception as e:
            error_msg = f"Bot başlatılırken hata oluştu: {str(e)}"
            print(f"{self.user_id}: {error_msg}")
            self.status["status_message"] = error_msg
            await self.stop()

    async def _websocket_listener(self, ws_url: str):
        """WebSocket dinleyicisi"""
        print(f"{self.user_id}: WebSocket bağlantısı kuruluyor - {ws_url}")
        last_subscription_check = datetime.now(timezone.utc)

        while not self._stop_requested:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    print(f"{self.user_id}: WebSocket bağlantısı başarılı")
                    
                    while not self._stop_requested:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                            await self._handle_websocket_message(message)

                            # Periyodik abonelik kontrolü
                            current_time = datetime.now(timezone.utc)
                            if (current_time - last_subscription_check).total_seconds() >= self.subscription_check_interval:
                                if not firebase_manager.is_subscription_active(self.user_id):
                                    self.status["status_message"] = "Aboneliğiniz sona erdi, bot durduruluyor."
                                    print(f"{self.user_id}: Abonelik sona erdi, bot durduruluyor")
                                    await self.stop()
                                    return
                                last_subscription_check = current_time
                                self.status["last_check_time"] = current_time.isoformat()

                        except asyncio.TimeoutError:
                            await ws.ping()
                        except websockets.exceptions.ConnectionClosed:
                            print(f"{self.user_id}: WebSocket bağlantısı kapandı, yeniden bağlanılıyor...")
                            await asyncio.sleep(5)
                            break
                        except Exception as e:
                            print(f"{self.user_id}: WebSocket mesaj işleme hatası: {e}")
                            await asyncio.sleep(1)

            except Exception as e:
                print(f"{self.user_id}: WebSocket bağlantı hatası: {e}. 5 saniye sonra tekrar denenecek.")
                await asyncio.sleep(5)
                
        print(f"{self.user_id}: WebSocket dinleyicisi durduruldu")

    async def stop(self):
        """Bot'u durdurur"""
        if not self._stop_requested:
            self._stop_requested = True
            
            # Açık pozisyonları kapat (opsiyonel)
            try:
                open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
                if open_positions:
                    print(f"{self.user_id}: Bot durdurulurken açık pozisyonlar tespit edildi")
                    # Not: Pozisyonları otomatik kapatmak riskli olabilir
                    # Kullanıcı tercihine bağlı olarak bu özellik eklenebilir
            except Exception as e:
                print(f"{self.user_id}: Pozisyon kontrolü hatası: {e}")

            # WebSocket görevini iptal et
            if self.websocket_task and not self.websocket_task.done():
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"{self.user_id}: WebSocket görevi iptal edilirken hata: {e}")

            if self.status["is_running"]:
                self.status.update({
                    "is_running": False,
                    "status_message": "Bot durduruldu.",
                    "position_side": None
                })
                print(f"{self.user_id}: Bot durduruldu - {self.settings['symbol']}")
                await self.binance_client.close()

    async def _handle_websocket_message(self, message: str):
        """WebSocket mesajlarını işler"""
        try:
            data = json.loads(message)
            kline_data = data.get('k', {})
            
            # Güncel fiyatı güncelle
            if 'c' in kline_data:
                self.status["current_price"] = float(kline_data['c'])
            
            # Sadece kapanan mumları işle
            if not kline_data.get('x', False):
                return
                
            print(f"{self.user_id}: Yeni mum kapandı - {self.settings['symbol']} - Kapanış: {kline_data['c']}")
            
            # Klines listesini güncelle
            self.klines.pop(0)
            self.klines.append([
                kline_data['t'], kline_data['o'], kline_data['h'], 
                kline_data['l'], kline_data['c'], kline_data['v'], 
                kline_data['T'], kline_data['q'], kline_data['n'], 
                kline_data['V'], kline_data['Q'], kline_data['B']
            ])

            # Pozisyon kontrolü
            await self._check_position_status()
            
            # Sinyal analizi
            signal = trading_strategy.analyze_klines(self.klines)
            print(f"{self.user_id}: Strateji analizi - {self.settings['symbol']}: {signal}")

            # Pozisyon yönetimi
            if signal != "HOLD" and signal != self.status.get("position_side"):
                await self._handle_signal(signal)
                
        except Exception as e:
            print(f"{self.user_id}: WebSocket mesaj işleme hatası: {e}")

    async def _check_position_status(self):
        """Pozisyon durumunu kontrol eder"""
        try:
            open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
            
            if self.status["position_side"] is not None and not open_positions:
                # Pozisyon SL/TP ile kapandı
                print(f"{self.user_id}: Pozisyon SL/TP ile kapandı - {self.settings['symbol']}")
                pnl = await self.binance_client.get_last_trade_pnl(self.settings["symbol"])
                
                firebase_manager.log_trade(self.user_id, {
                    "symbol": self.settings["symbol"],
                    "pnl": pnl,
                    "status": "CLOSED_BY_SL_TP",
                    "timestamp": datetime.now(timezone.utc),
                    "strategy": "EMA_CROSSOVER"
                })
                
                self.status["position_side"] = None
                self.status["entry_price"] = 0.0
                self.status["position_pnl"] = 0.0
                
            elif open_positions:
                # Açık pozisyon var, PnL'i güncelle
                position = open_positions[0]
                self.status["position_pnl"] = float(position.get('unRealizedProfit', 0))
                if not self.status["entry_price"]:
                    self.status["entry_price"] = float(position.get('entryPrice', 0))
                    
        except Exception as e:
            print(f"{self.user_id}: Pozisyon kontrolü hatası: {e}")

    async def _handle_signal(self, new_signal: str):
        """Yeni sinyal geldiğinde pozisyon açar/kapatır"""
        symbol = self.settings["symbol"]
        
        # Abonelik kontrolü
        if not firebase_manager.is_subscription_active(self.user_id):
            self.status["status_message"] = "Abonelik süresi doldu, yeni pozisyon açılamıyor."
            await self.stop()
            return

        try:
            # Mevcut pozisyonu kapat
            open_positions = await self.binance_client.get_open_positions(symbol)
            if open_positions:
                print(f"{self.user_id}: Mevcut pozisyon kapatılıyor - {symbol}")
                await self.binance_client.close_open_position_and_orders(symbol)
                
                pnl = await self.binance_client.get_last_trade_pnl(symbol)
                firebase_manager.log_trade(self.user_id, {
                    "symbol": symbol,
                    "pnl": pnl,
                    "status": "CLOSED_BY_SIGNAL",
                    "timestamp": datetime.now(timezone.utc),
                    "strategy": "EMA_CROSSOVER"
                })
                
                await asyncio.sleep(1)  # Pozisyonun tamamen kapanması için bekle

            # Yeni pozisyon aç
            print(f"{self.user_id}: Yeni {new_signal} pozisyonu açılıyor - {symbol}")
            
            side = "BUY" if new_signal == "LONG" else "SELL"
            current_price = await self.binance_client.get_market_price(symbol)
            
            if not current_price:
                print(f"{self.user_id}: Güncel fiyat alınamadı - {symbol}")
                return

            # Miktar hesapla
            order_size = self.settings.get('order_size', 20.0)
            leverage = self.settings.get('leverage', 10)
            quantity = self._format_quantity((order_size * leverage) / current_price, self.step_size)
            
            if quantity <= 0:
                print(f"{self.user_id}: Hesaplanan miktar çok düşük - {quantity}")
                return

            # Stop Loss ve Take Profit yüzdelerini al
            stop_loss_percent = self.settings.get('stop_loss', 2.0)
            take_profit_percent = self.settings.get('take_profit', 4.0)

            # Emir ver
            order = await self.binance_client.create_order_with_tp_sl(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=current_price,
                price_precision=self.price_precision,
                stop_loss_percent=stop_loss_percent,
                take_profit_percent=take_profit_percent
            )

            if order:
                self.status["position_side"] = new_signal
                self.status["entry_price"] = current_price
                self.status["status_message"] = f"{new_signal} pozisyonu {current_price} fiyattan açıldı"
                
                firebase_manager.log_trade(self.user_id, {
                    "symbol": symbol,
                    "side": new_signal,
                    "entry_price": current_price,
                    "quantity": quantity,
                    "status": "OPENED",
                    "timestamp": datetime.now(timezone.utc),
                    "strategy": "EMA_CROSSOVER"
                })
                
                print(f"{self.user_id}: ✅ {new_signal} pozisyonu açıldı - {symbol} @ {current_price}")
            else:
                self.status["status_message"] = "Pozisyon açılamadı"
                print(f"{self.user_id}: ❌ Pozisyon açılamadı - {symbol}")
                
        except Exception as e:
            error_msg = f"Pozisyon işlemi sırasında hata: {str(e)}"
            print(f"{self.user_id}: {error_msg}")
            self.status["status_message"] = error_msg
