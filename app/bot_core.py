import asyncio
import json
import websockets
import math
from datetime import datetime, timezone
from app.binance_client import BinanceClient
from app.trading_strategy import trading_strategy
from app.firebase_manager import firebase_manager
from app.utils.logger import get_logger
from app.utils.metrics import metrics

logger = get_logger("bot_core")

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
            "last_check_time": datetime.now(timezone.utc).isoformat()
        }
        self.klines = []
        self._stop_requested = False
        self.quantity_precision = 0
        self.price_precision = 0
        self.step_size = 0.0
        self.websocket_task = None
        self.subscription_check_interval = 60
        
        # Metrics tracking
        self.start_time = None
        self.websocket_reconnect_count = 0
        
        logger.info(f"BotCore oluşturuldu - Kullanıcı: {user_id}, Symbol: {settings.get('symbol')}")

    def _get_precision_from_filter(self, symbol_info, filter_type, key):
        """Symbol filtrelerinden precision değerini alır"""
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
            logger.warning(f"Bot zaten çalışıyor - Kullanıcı: {self.user_id}")
            return

        self._stop_requested = False
        self.start_time = datetime.now(timezone.utc)
        self.status.update({
            "is_running": True, 
            "status_message": f"{self.settings['symbol']} için başlatılıyor..."
        })

        logger.info(f"Bot başlatılıyor - Kullanıcı: {self.user_id}, Symbol: {self.settings['symbol']}")

        try:
            # 1. Abonelik kontrolü
            if not firebase_manager.is_subscription_active(self.user_id):
                self.status["status_message"] = "Bot başlatılamadı: Aboneliğiniz aktif değil veya süresi dolmuş."
                logger.warning(f"Abonelik aktif değil - Kullanıcı: {self.user_id}")
                await self.stop()
                return

            # 2. Binance bağlantısını başlat
            if not await self.binance_client.initialize():
                self.status["status_message"] = "Binance bağlantısı kurulamadı. API anahtarlarınızı kontrol edin."
                logger.error(f"Binance bağlantısı başarısız - Kullanıcı: {self.user_id}")
                await self.stop()
                return

            # 3. Symbol bilgilerini al
            symbol_info = await self.binance_client.get_symbol_info(self.settings['symbol'])
            if not symbol_info:
                self.status["status_message"] = f"{self.settings['symbol']} için borsa bilgileri alınamadı."
                logger.error(f"Symbol bilgisi alınamadı - Kullanıcı: {self.user_id}, Symbol: {self.settings['symbol']}")
                await self.stop()
                return

            # 4. Filtre bilgilerini al
            lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
            price_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)

            if not lot_size_filter or not price_filter:
                self.status["status_message"] = f"{self.settings['symbol']} için gerekli filtre bilgileri bulunamadı."
                logger.error(f"Filtre bilgileri eksik - Kullanıcı: {self.user_id}")
                await self.stop()
                return

            # 5. Precision değerlerini ayarla
            self.quantity_precision = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
            self.price_precision = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')
            self.step_size = float(lot_size_filter['stepSize'])

            logger.info(f"Symbol bilgileri alındı - Kullanıcı: {self.user_id}, Qty Precision: {self.quantity_precision}, Price Precision: {self.price_precision}")

            # 6. Kaldıraç ayarla
            leverage_set = await self.binance_client.set_leverage(self.settings['symbol'], self.settings['leverage'])
            if leverage_set:
                logger.info(f"Kaldıraç ayarlandı - Kullanıcı: {self.user_id}, Leverage: {self.settings['leverage']}")
            else:
                logger.warning(f"Kaldıraç ayarlanamadı - Kullanıcı: {self.user_id}")

            # 7. Geçmiş verileri al
            self.klines = await self.binance_client.get_historical_klines(
                self.settings['symbol'], 
                self.settings['timeframe'], 
                limit=50
            )
            
            if not self.klines:
                self.status["status_message"] = "Geçmiş mum verisi alınamadı."
                logger.error(f"Geçmiş veri alınamadı - Kullanıcı: {self.user_id}")
                await self.stop()
                return

            # 8. WebSocket bağlantısını başlat
            self.status["status_message"] = f"{self.settings['symbol']} ({self.settings['timeframe']}) için sinyal bekleniyor..."
            ws_url = f"wss://fstream.binance.com/ws/{self.settings['symbol'].lower()}@kline_{self.settings['timeframe']}"
            
            self.websocket_task = asyncio.create_task(self._websocket_listener(ws_url))
            
            # Metrics güncelle
            metrics.update_websocket_connections(1)
            
            logger.info(f"Bot başarıyla başlatıldı - Kullanıcı: {self.user_id}")

        except Exception as e:
            self.status["status_message"] = f"Bot başlatma hatası: {str(e)}"
            logger.error(f"Bot başlatma hatası - Kullanıcı: {self.user_id}, Hata: {e}")
            await self.stop()

    async def _websocket_listener(self, ws_url: str):
        """WebSocket dinleyicisi"""
        logger.info(f"WebSocket bağlantısı başlatılıyor - Kullanıcı: {self.user_id}")
        last_subscription_check = datetime.now(timezone.utc)

        while not self._stop_requested:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info(f"WebSocket bağlandı - Kullanıcı: {self.user_id}")
                    
                    while not self._stop_requested:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                            await self._handle_websocket_message(message)

                            # Abonelik kontrolü (dakikada bir)
                            current_time = datetime.now(timezone.utc)
                            if (current_time - last_subscription_check).total_seconds() >= self.subscription_check_interval:
                                if not firebase_manager.is_subscription_active(self.user_id):
                                    self.status["status_message"] = "Aboneliğiniz sona erdi, bot durduruluyor."
                                    logger.warning(f"Abonelik süresi doldu - Kullanıcı: {self.user_id}")
                                    await self.stop()
                                    return
                                last_subscription_check = current_time
                                self.status["last_check_time"] = current_time.isoformat()

                        except asyncio.TimeoutError:
                            await ws.ping()
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"WebSocket bağlantısı koptu - Kullanıcı: {self.user_id}")
                            self.websocket_reconnect_count += 1
                            metrics.record_websocket_reconnection(self.user_id)
                            await asyncio.sleep(5)
                            break
                        except Exception as e:
                            logger.error(f"WebSocket mesaj işleme hatası - Kullanıcı: {self.user_id}, Hata: {e}")
                            await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"WebSocket bağlantı hatası - Kullanıcı: {self.user_id}, Hata: {e}")
                self.websocket_reconnect_count += 1
                metrics.record_websocket_reconnection(self.user_id)
                await asyncio.sleep(5)
        
        logger.info(f"WebSocket dinleyicisi durduruldu - Kullanıcı: {self.user_id}")

    async def stop(self):
        """Bot'u durdurur"""
        if not self._stop_requested:
            self._stop_requested = True

            logger.info(f"Bot durduruluyor - Kullanıcı: {self.user_id}")

            # Açık pozisyonları kapat
            try:
                open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
                if open_positions:
                    logger.info(f"Açık pozisyonlar kapatılıyor - Kullanıcı: {self.user_id}")
                    await self.binance_client.close_open_position_and_orders(self.settings["symbol"])
                    pnl = await self.binance_client.get_last_trade_pnl(self.settings["symbol"])
                    firebase_manager.log_trade(self.user_id, {
                        "symbol": self.settings["symbol"], 
                        "pnl": pnl, 
                        "status": "CLOSED_ON_BOT_STOP", 
                        "timestamp": datetime.now(timezone.utc)
                    })
                    metrics.record_trade(self.user_id, self.settings["symbol"], "CLOSE", pnl, "bot_stop")
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Pozisyon kapatma hatası - Kullanıcı: {self.user_id}, Hata: {e}")

            # WebSocket task'ını iptal et
            if self.websocket_task and not self.websocket_task.done():
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    logger.info(f"WebSocket görevi iptal edildi - Kullanıcı: {self.user_id}")
                except Exception as e:
                    logger.error(f"WebSocket görevi iptal hatası - Kullanıcı: {self.user_id}, Hata: {e}")

            # Binance bağlantısını kapat
            if self.status["is_running"]:
                self.status.update({"is_running": False, "status_message": "Bot durduruldu."})
                await self.binance_client.close()
                
                # Uptime hesapla
                if self.start_time:
                    uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
                    logger.info(f"Bot durduruldu - Kullanıcı: {self.user_id}, Uptime: {uptime:.0f}s, Reconnects: {self.websocket_reconnect_count}")
                else:
                    logger.info(f"Bot durduruldu - Kullanıcı: {self.user_id}")

    async def _handle_websocket_message(self, message: str):
        """WebSocket mesajlarını işler"""
        try:
            data = json.loads(message)
            
            # Sadece kapanan mumları işle
            if not data.get('k', {}).get('x', False):
                return

            # Kline verisini güncelle
            kline = data['k']
            self.klines.pop(0)
            self.klines.append([
                kline['t'], kline['o'], kline['h'], kline['l'], kline['c'],
                kline['v'], kline['T'], kline['q'], kline['n'], kline['V'],
                kline['Q'], kline['B']
            ])

            # Pozisyon durumunu kontrol et
            open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
            if self.status["position_side"] is not None and not open_positions:
                logger.info(f"Pozisyon SL/TP ile kapandı - Kullanıcı: {self.user_id}")
                pnl = await self.binance_client.get_last_trade_pnl(self.settings["symbol"])
                firebase_manager.log_trade(self.user_id, {
                    "symbol": self.settings["symbol"], 
                    "pnl": pnl, 
                    "status": "CLOSED_BY_SL_TP_OR_MANUAL", 
                    "timestamp": datetime.now(timezone.utc)
                })
                metrics.record_trade(self.user_id, self.settings["symbol"], "CLOSE", pnl, "sl_tp_manual")
                self.status["position_side"] = None

            # Strateji analizini çalıştır
            signal = trading_strategy.analyze_klines(self.klines)
            if signal != "HOLD":
                logger.info(f"Strateji sinyali - Kullanıcı: {self.user_id}, Sinyal: {signal}")

            # Pozisyon değişikliği gerekiyorsa işle
            if signal != "HOLD" and signal != self.status.get("position_side"):
                await self._flip_position(signal)

        except Exception as e:
            logger.error(f"WebSocket mesaj işleme hatası - Kullanıcı: {self.user_id}, Hata: {e}")

    async def _flip_position(self, new_signal: str):
        """Pozisyon değişikliği yapar"""
        symbol = self.settings["symbol"]

        # Abonelik kontrolü
        if not firebase_manager.is_subscription_active(self.user_id):
            self.status["status_message"] = "Aboneliğiniz sona erdi, yeni pozisyon açılamıyor."
            logger.warning(f"Abonelik süresi doldu, pozisyon açılamıyor - Kullanıcı: {self.user_id}")
            await self.stop()
            return

        try:
            # Mevcut pozisyonu kapat
            open_positions = await self.binance_client.get_open_positions(symbol)
            if open_positions:
                logger.info(f"Mevcut pozisyon kapatılıyor - Kullanıcı: {self.user_id}, Yön: {self.status['position_side']}")
                await self.binance_client.close_open_position_and_orders(symbol)
                pnl = await self.binance_client.get_last_trade_pnl(symbol)
                firebase_manager.log_trade(self.user_id, {
                    "symbol": symbol, 
                    "pnl": pnl, 
                    "status": "CLOSED_BY_FLIP", 
                    "timestamp": datetime.now(timezone.utc)
                })
                metrics.record_trade(self.user_id, symbol, "CLOSE", pnl, "flip")
                await asyncio.sleep(1)

            # Yeni pozisyon aç
            logger.info(f"Yeni pozisyon açılıyor - Kullanıcı: {self.user_id}, Sinyal: {new_signal}")
            side = "BUY" if new_signal == "LONG" else "SELL"
            price = await self.binance_client.get_market_price(symbol)
            
            if not price:
                self.status["status_message"] = "Yeni pozisyon için fiyat alınamadı."
                logger.error(f"Market fiyatı alınamadı - Kullanıcı: {self.user_id}")
                return

            # Miktar hesapla
            quantity = self._format_quantity(self.settings['order_size'] / price, self.step_size)
            
            if quantity <= 0:
                self.status["status_message"] = f"Hesaplanan miktar çok düşük: {quantity}"
                logger.error(f"Miktar çok düşük - Kullanıcı: {self.user_id}, Miktar: {quantity}")
                return

            # TP/SL ile emir oluştur
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
                self.status["status_message"] = f"Yeni {new_signal} pozisyonu {price:.{self.price_precision}f} fiyattan açıldı."
                metrics.record_trade(self.user_id, symbol, side, 0.0, "opened")
                logger.info(f"Pozisyon başarıyla açıldı - Kullanıcı: {self.user_id}, Sinyal: {new_signal}, Fiyat: {price}")
            else:
                self.status["position_side"] = None
                self.status["status_message"] = "Yeni pozisyon açılamadı."
                logger.error(f"Pozisyon açılamadı - Kullanıcı: {self.user_id}")

        except Exception as e:
            logger.error(f"Pozisyon değiştirme hatası - Kullanıcı: {self.user_id}, Hata: {e}")
            self.status["status_message"] = f"Pozisyon değiştirme hatası: {str(e)}"
