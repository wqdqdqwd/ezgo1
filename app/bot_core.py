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
        self.settings = settings  # Kullanıcıdan gelen tüm ayarlar
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
        self.websocket_task = None
        self.subscription_check_interval = 60

        # Metrics tracking
        self.start_time = None
        self.websocket_reconnect_count = 0

    def _get_precision_from_filter(self, symbol_info, filter_type, key):
        for f in symbol_info['filters']:
            if f['filterType'] == filter_type:
                size_str = f[key]
                if '.' in size_str:
                    return len(size_str.split('.')[1].rstrip('0'))
                return 0
        return 0

    # BURADAKİ METOT YENİDEN GÜNCELLENDİ
    def _format_quantity(self, quantity: float, step_size: float):
        """
        Miktarı Binance'in 'LOT_SIZE' filtresindeki 'stepSize' değerine göre formatlar.
        """
        # StepSize'ın ondalık hassasiyetini bul
        step_size_str = f"{step_size:f}"
        if '.' in step_size_str:
            precision = len(step_size_str.split('.')[1].rstrip('0'))
        else:
            precision = 0
        
        # Miktarı stepSize'ın katına yuvarla
        return math.floor(quantity / step_size) * step_size

    async def start(self):
        if self.status["is_running"]: return

        self._stop_requested = False
        self.start_time = datetime.now(timezone.utc)
        self.status.update({"is_running": True, "status_message": f"{self.settings['symbol']} için başlatılıyor..."})

        logger.info("Bot starting", user_id=self.user_id, symbol=self.settings['symbol'])

        # DÜZELTME: await eklendi
        if not await firebase_manager.is_subscription_active(self.user_id):
            self.status["status_message"] = "Bot başlatılamadı: Aboneliğiniz aktif değil veya süresi dolmuş."
            logger.warning("Bot start failed - inactive subscription", user_id=self.user_id)
            await self.stop(); return

        if not await self.binance_client.initialize():
            self.status["status_message"] = "Binance bağlantısı kurulamadı. API anahtarlarınızı kontrol edin."
            await self.stop(); return

        symbol_info = await self.binance_client.get_symbol_info(self.settings['symbol'])
        if not symbol_info:
            self.status["status_message"] = f"{self.settings['symbol']} için borsa bilgileri alınamadı."
            await self.stop(); return

        # Gerekli filtre değerlerini alalım
        lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
        price_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'), None)

        if not lot_size_filter or not price_filter:
            self.status["status_message"] = f"{self.settings['symbol']} için gerekli filtre bilgileri bulunamadı."
            await self.stop(); return

        self.quantity_precision = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
        self.price_precision = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')
        
        self.step_size = float(lot_size_filter['stepSize']) # Yeni eklenen step_size değeri

        self.klines = await self.binance_client.get_historical_klines(self.settings['symbol'], self.settings['timeframe'], limit=50)
        if not self.klines:
            self.status["status_message"] = "Geçmiş mum verisi alınamadı."
            await self.stop(); return

        self.status["status_message"] = f"{self.settings['symbol']} ({self.settings['timeframe']}) için sinyal bekleniyor..."
        ws_url = f"wss://fstream.binance.com/ws/{self.settings['symbol'].lower()}@kline_{self.settings['timeframe']}"
        self.websocket_task = asyncio.create_task(self._websocket_listener(ws_url))
        
        # Update metrics
        metrics.update_websocket_connections(len(bot_manager.active_bots) if 'bot_manager' in globals() else 1)
        
        logger.info("Bot started successfully", user_id=self.user_id, symbol=self.settings['symbol'])

    async def _websocket_listener(self, ws_url: str):
        logger.info("WebSocket connection starting", user_id=self.user_id, url=ws_url)
        last_subscription_check = datetime.now(timezone.utc)

        while not self._stop_requested:
            try:
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                    logger.info("WebSocket connected", user_id=self.user_id)
                    while not self._stop_requested:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                            await self._handle_websocket_message(message)

                            current_time = datetime.now(timezone.utc)
                            if (current_time - last_subscription_check).total_seconds() >= self.subscription_check_interval:
                                # DÜZELTME: await eklendi
                                if not await firebase_manager.is_subscription_active(self.user_id):
                                    self.status["status_message"] = "Aboneliğiniz sona erdi, bot durduruluyor."
                                    logger.warning("Subscription expired, stopping bot", user_id=self.user_id)
                                    await self.stop()
                                    return
                                last_subscription_check = current_time
                                self.status["last_check_time"] = current_time.isoformat()

                        except asyncio.TimeoutError:
                            await ws.ping()
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("WebSocket connection closed, reconnecting", user_id=self.user_id)
                            self.websocket_reconnect_count += 1
                            metrics.record_websocket_reconnection(self.user_id)
                            await asyncio.sleep(5)
                            break
                        except Exception as e:
                            logger.error("WebSocket message processing error", user_id=self.user_id, error=str(e))
                            await asyncio.sleep(1)

            except Exception as e:
                logger.error("WebSocket connection error", user_id=self.user_id, error=str(e))
                self.websocket_reconnect_count += 1
                metrics.record_websocket_reconnection(self.user_id)
                await asyncio.sleep(5)
        
        logger.info("WebSocket listener stopped", user_id=self.user_id)


    async def stop(self):
        if not self._stop_requested:
            self._stop_requested = True

            open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
            if open_positions:
                logger.info("Closing open positions on bot stop", user_id=self.user_id)
                await self.binance_client.close_open_position_and_orders(self.settings["symbol"])
                pnl = await self.binance_client.get_last_trade_pnl(self.settings["symbol"])
                firebase_manager.log_trade(self.user_id, {"symbol": self.settings["symbol"], "pnl": pnl, "status": "CLOSED_ON_BOT_STOP", "timestamp": datetime.now(timezone.utc)})
                metrics.record_trade(self.user_id, self.settings["symbol"], "CLOSE", pnl, "bot_stop")
                await asyncio.sleep(1)

            if self.websocket_task and not self.websocket_task.done():
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    logger.info("WebSocket task cancelled", user_id=self.user_id)
                except Exception as e:
                    logger.error("Error cancelling WebSocket task", user_id=self.user_id, error=str(e))

            if self.status["is_running"]:
                self.status.update({"is_running": False, "status_message": "Bot durduruldu."})
                logger.info("Bot stopping", user_id=self.user_id)
                await self.binance_client.close()
                
                # Calculate uptime for metrics
                if self.start_time:
                    uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
                    logger.info("Bot stopped", user_id=self.user_id, uptime_seconds=uptime, reconnects=self.websocket_reconnect_count)
                else:
                    logger.info("Bot stopped", user_id=self.user_id)

    async def _handle_websocket_message(self, message: str):
        data = json.loads(message)
        if not data.get('k', {}).get('x', False): return

        self.klines.pop(0)
        self.klines.append([
            data['k']['t'], data['k']['o'], data['k']['h'], data['k']['l'], data['k']['c'],
            data['k']['v'], data['k']['T'], data['k']['q'], data['k']['n'], data['k']['V'],
            data['k']['Q'], data['k']['B']
        ])

        open_positions = await self.binance_client.get_open_positions(self.settings["symbol"])
        if self.status["position_side"] is not None and not open_positions:
            logger.info("Position closed by SL/TP or manual", user_id=self.user_id)
            pnl = await self.binance_client.get_last_trade_pnl(self.settings["symbol"])
            firebase_manager.log_trade(self.user_id, {"symbol": self.settings["symbol"], "pnl": pnl, "status": "CLOSED_BY_SL_TP_OR_MANUAL", "timestamp": datetime.now(timezone.utc)})
            metrics.record_trade(self.user_id, self.settings["symbol"], "CLOSE", pnl, "sl_tp_manual")
            self.status["position_side"] = None

        signal = trading_strategy.analyze_klines(self.klines)
        if signal != "HOLD":
            logger.info("Strategy signal", user_id=self.user_id, signal=signal)

        if signal != "HOLD" and signal != self.status.get("position_side"):
            await self._flip_position(signal)

    async def _flip_position(self, new_signal: str):
        symbol = self.settings["symbol"]

        # DÜZELTME: await eklendi
        if not await firebase_manager.is_subscription_active(self.user_id):
            self.status["status_message"] = "Aboneliğiniz sona erdi, yeni pozisyon açılamıyor."
            logger.warning("Cannot open position - subscription expired", user_id=self.user_id)
            await self.stop()
            return

        open_positions = await self.binance_client.get_open_positions(symbol)
        if open_positions:
            logger.info("Closing existing position for flip", user_id=self.user_id, current_side=self.status['position_side'])
            await self.binance_client.close_open_position_and_orders(symbol)
            pnl = await self.binance_client.get_last_trade_pnl(symbol)
            firebase_manager.log_trade(self.user_id, {"symbol": symbol, "pnl": pnl, "status": "CLOSED_BY_FLIP", "timestamp": datetime.now(timezone.utc)})
            metrics.record_trade(self.user_id, symbol, "CLOSE", pnl, "flip")
            await asyncio.sleep(1)

        logger.info("Opening new position", user_id=self.user_id, signal=new_signal)
        side = "BUY" if new_signal == "LONG" else "SELL"
        price = await self.binance_client.get_market_price(symbol)
        if not price:
            self.status["status_message"] = "Yeni pozisyon için fiyat alınamadı."
            logger.error("Failed to get market price", user_id=self.user_id, symbol=symbol)
            return

        # quantity hesaplamasını güncelledik ve step_size parametresini kullandık
        quantity = self._format_quantity((self.settings['order_size']) / price, self.step_size)
        
        if quantity <= 0:
            self.status["status_message"] = f"Hesaplanan miktar çok düşük: {quantity}"
            logger.error("Calculated quantity too low", user_id=self.user_id, quantity=quantity)
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
            metrics.record_trade(self.user_id, symbol, side, 0.0, "opened")
            logger.info("Position opened successfully", user_id=self.user_id, signal=new_signal, price=price)
        else:
            self.status["position_side"] = None
            self.status["status_message"] = "Yeni pozisyon açılamadı."
            logger.error("Failed to open position", user_id=self.user_id)
