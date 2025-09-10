import asyncio
import websockets
import json
import math
from datetime import datetime, timezone
from typing import Optional, Dict, List
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
import logging
from dataclasses import dataclass

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TradingSettings:
    symbol: str
    timeframe: str
    leverage: int
    order_size_usdt: float
    stop_loss_percent: float
    take_profit_percent: float
    margin_type: str
    api_key: str
    api_secret: str

@dataclass
class Position:
    symbol: str
    side: str
    size: float
    entry_price: float
    unrealized_pnl: float
    percentage: float

class TechnicalAnalysis:
    """Teknik analiz için basit EMA stratejisi"""
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> List[float]:
        """EMA hesaplar"""
        if len(prices) < period:
            return []
        
        emas = []
        multiplier = 2 / (period + 1)
        
        # İlk EMA = SMA
        sma = sum(prices[:period]) / period
        emas.append(sma)
        
        # Sonraki EMA'lar
        for i in range(period, len(prices)):
            ema = (prices[i] * multiplier) + (emas[-1] * (1 - multiplier))
            emas.append(ema)
        
        return emas
    
    @staticmethod
    def analyze_trend(klines: List) -> str:
        """Trend analizini yapar"""
        if len(klines) < 50:
            return "HOLD"
        
        # Kapanış fiyatlarını al
        closes = [float(kline[4]) for kline in klines]
        
        # EMA9 ve EMA21 hesapla
        ema9 = TechnicalAnalysis.calculate_ema(closes, 9)
        ema21 = TechnicalAnalysis.calculate_ema(closes, 21)
        
        if len(ema9) < 2 or len(ema21) < 2:
            return "HOLD"
        
        # Crossover kontrolü
        prev_ema9, curr_ema9 = ema9[-2], ema9[-1]
        prev_ema21, curr_ema21 = ema21[-2], ema21[-1]
        
        # Bullish crossover: EMA9 crosses above EMA21
        if prev_ema9 <= prev_ema21 and curr_ema9 > curr_ema21:
            return "LONG"
        
        # Bearish crossover: EMA9 crosses below EMA21
        if prev_ema9 >= prev_ema21 and curr_ema9 < curr_ema21:
            return "SHORT"
        
        return "HOLD"

class TradingBot:
    """Ana trading bot sınıfı"""
    
    def __init__(self, user_id: str, settings: TradingSettings, websocket_callback=None):
        self.user_id = user_id
        self.settings = settings
        self.websocket_callback = websocket_callback
        self.client: Optional[AsyncClient] = None
        self.is_running = False
        self.current_position: Optional[Position] = None
        self.klines_data = []
        self.websocket_task = None
        self.monitor_task = None
        
    async def start(self):
        """Botu başlatır"""
        if self.is_running:
            return {"success": False, "message": "Bot already running"}
        
        try:
            # Binance client başlat
            self.client = await AsyncClient.create(
                self.settings.api_key,
                self.settings.api_secret
            )
            
            # Hesap bilgilerini kontrol et
            account_info = await self.client.futures_account()
            if not account_info:
                raise Exception("Could not fetch account information")
            
            # Leverage ayarla
            await self.client.futures_change_leverage(
                symbol=self.settings.symbol,
                leverage=self.settings.leverage
            )
            
            # Margin type ayarla
            margin_type = "ISOLATED" if self.settings.margin_type == "isolated" else "CROSSED"
            await self.client.futures_change_margin_type(
                symbol=self.settings.symbol,
                marginType=margin_type
            )
            
            # Geçmiş verileri al
            klines = await self.client.futures_historical_klines(
                self.settings.symbol,
                self.settings.timeframe,
                limit=100
            )
            self.klines_data = klines
            
            # WebSocket ve monitoring başlat
            self.is_running = True
            self.websocket_task = asyncio.create_task(self._start_websocket())
            self.monitor_task = asyncio.create_task(self._monitor_positions())
            
            await self._send_update({
                "type": "bot_status",
                "status": "running",
                "message": f"Bot started successfully for {self.settings.symbol}",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Bot started for user {self.user_id} on {self.settings.symbol}")
            return {"success": True, "message": "Bot started successfully"}
            
        except Exception as e:
            logger.error(f"Failed to start bot for user {self.user_id}: {e}")
            await self.stop()
            return {"success": False, "message": f"Failed to start bot: {str(e)}"}
    
    async def stop(self):
        """Botu durdurur"""
        if not self.is_running:
            return {"success": False, "message": "Bot is not running"}
        
        try:
            self.is_running = False
            
            # WebSocket bağlantısını kapat
            if self.websocket_task and not self.websocket_task.done():
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
            
            # Monitoring görevini durdur
            if self.monitor_task and not self.monitor_task.done():
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
            
            # Açık pozisyonu kapat (opsiyonel)
            if self.current_position:
                await self._close_position("Bot stopped")
            
            # Client bağlantısını kapat
            if self.client:
                await self.client.close_connection()
                self.client = None
            
            await self._send_update({
                "type": "bot_status",
                "status": "stopped",
                "message": "Bot stopped successfully",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Bot stopped for user {self.user_id}")
            return {"success": True, "message": "Bot stopped successfully"}
            
        except Exception as e:
            logger.error(f"Error stopping bot for user {self.user_id}: {e}")
            return {"success": False, "message": f"Error stopping bot: {str(e)}"}
    
    async def _start_websocket(self):
        """WebSocket veri akışını başlatır"""
        stream_name = f"{self.settings.symbol.lower()}@kline_{self.settings.timeframe}"
        uri = f"wss://fstream.binance.com/ws/{stream_name}"
        
        while self.is_running:
            try:
                async with websockets.connect(uri) as websocket:
                    logger.info(f"WebSocket connected for {self.settings.symbol}")
                    
                    while self.is_running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                            data = json.loads(message)
                            
                            if 'k' in data and data['k']['x']:  # Kline tamamlandı
                                await self._process_kline(data['k'])
                                
                        except asyncio.TimeoutError:
                            # Ping gönder
                            await websocket.ping()
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"WebSocket connection closed for {self.settings.symbol}")
                            break
                            
            except Exception as e:
                logger.error(f"WebSocket error for {self.settings.symbol}: {e}")
                if self.is_running:
                    await asyncio.sleep(5)  # Yeniden bağlanmadan önce bekle
    
    async def _process_kline(self, kline_data):
        """Yeni kline verisini işler"""
        try:
            # Yeni kline'ı listeye ekle
            new_kline = [
                int(kline_data['t']),  # Open time
                kline_data['o'],       # Open price
                kline_data['h'],       # High price
                kline_data['l'],       # Low price
                kline_data['c'],       # Close price
                kline_data['v'],       # Volume
            ]
            
            # Eski veriyi güncelle
            self.klines_data.append(new_kline)
            if len(self.klines_data) > 100:
                self.klines_data.pop(0)
            
            # Teknik analiz yap
            signal = TechnicalAnalysis.analyze_trend(self.klines_data)
            
            # Price update gönder
            await self._send_update({
                "type": "price_update",
                "symbol": self.settings.symbol,
                "price": float(kline_data['c']),
                "change_24h": 0,  # Bu bilgiyi ayrı bir API'dan almak gerekir
                "signal": signal,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Trading sinyali kontrolü
            if signal in ["LONG", "SHORT"]:
                await self._execute_trade(signal, float(kline_data['c']))
                
        except Exception as e:
            logger.error(f"Error processing kline for {self.settings.symbol}: {e}")
    
    async def _execute_trade(self, signal: str, current_price: float):
        """Trading emrini gerçekleştirir"""
        try:
            # Eğer zıt pozisyon varsa önce kapat
            if self.current_position and self.current_position.side != signal:
                await self._close_position("Signal change")
                await asyncio.sleep(1)  # Kısa bekleme
            
            # Yeni pozisyon aç
            if not self.current_position:
                await self._open_position(signal, current_price)
                
        except Exception as e:
            logger.error(f"Error executing trade for {self.settings.symbol}: {e}")
            await self._send_update({
                "type": "error",
                "message": f"Trade execution failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def _open_position(self, side: str, entry_price: float):
        """Yeni pozisyon açar"""
        try:
            # Miktar hesapla
            quantity = self.settings.order_size_usdt / entry_price
            
            # Symbol info al
            exchange_info = await self.client.futures_exchange_info()
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == self.settings.symbol:
                    symbol_info = s
                    break
            
            if not symbol_info:
                raise Exception(f"Symbol {self.settings.symbol} not found")
            
            # Quantity'yi uygun formata getir
            quantity_precision = 0
            for f in symbol_info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    quantity_precision = len(str(step_size).split('.')[-1]) if '.' in str(step_size) else 0
                    quantity = round(quantity / step_size) * step_size
                    break
            
            # Market order aç
            order_side = "BUY" if side == "LONG" else "SELL"
            order = await self.client.futures_create_order(
                symbol=self.settings.symbol,
                side=order_side,
                type="MARKET",
                quantity=round(quantity, quantity_precision)
            )
            
            # Position bilgilerini kaydet
            self.current_position = Position(
                symbol=self.settings.symbol,
                side=side,
                size=quantity,
                entry_price=entry_price,
                unrealized_pnl=0.0,
                percentage=0.0
            )
            
            # Stop Loss ve Take Profit emirlerini yerleştir
            await self._set_stop_loss_take_profit(entry_price, side)
            
            # WebSocket üzerinden bildirim gönder
            await self._send_update({
                "type": "position_opened",
                "symbol": self.settings.symbol,
                "side": side,
                "size": quantity,
                "entry_price": entry_price,
                "order_id": order['orderId'],
                "timestamp": datetime.utcnow().isoformat()
            })
            
            logger.info(f"Position opened for {self.user_id}: {side} {quantity} {self.settings.symbol} at {entry_price}")
            
        except Exception as e:
            logger.error(f"Error opening position for {self.settings.symbol}: {e}")
            raise
    
    async def _set_stop_loss_take_profit(self, entry_price: float, side: str):
        """Stop Loss ve Take Profit emirlerini yerleştirir"""
        try:
            # Price precision hesapla
            exchange_info = await self.client.futures_exchange_info()
            price_precision = 2  # Varsayılan
            
            for s in exchange_info['symbols']:
                if s['symbol'] == self.settings.symbol:
                    for f in s['filters']:
                        if f['filterType'] == 'PRICE_FILTER':
                            tick_size = float(f['tickSize'])
                            price_precision = len(str(tick_size).split('.')[-1]) if '.' in str(tick_size) else 0
                            break
                    break
            
            if side == "LONG":
                # Long pozisyon için
                stop_loss_price = entry_price * (1 - self.settings.stop_loss_percent / 100)
                take_profit_price = entry_price * (1 + self.settings.take_profit_percent / 100)
                sl_side = "SELL"
                tp_side = "SELL"
            else:
                # Short pozisyon için
                stop_loss_price = entry_price * (1 + self.settings.stop_loss_percent / 100)
                take_profit_price = entry_price * (1 - self.settings.take_profit_percent / 100)
                sl_side = "BUY"
                tp_side = "BUY"
            
            # Fiyatları formatla
            stop_loss_price = round(stop_loss_price, price_precision)
            take_profit_price = round(take_profit_price, price_precision)
            
            # Stop Loss emri
            await self.client.futures_create_order(
                symbol=self.settings.symbol,
                side=sl_side,
                type="STOP_MARKET",
                stopPrice=stop_loss_price,
                closePosition=True
            )
            
            # Take Profit emri
            await self.client.futures_create_order(
                symbol=self.settings.symbol,
                side=tp_side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=take_profit_price,
                closePosition=True
            )
            
            logger.info(f"SL/TP set for {self.settings.symbol}: SL={stop_loss_price}, TP={take_profit_price}")
            
        except Exception as e:
            logger.error(f"Error setting SL/TP for {self.settings.symbol}: {e}")
    
    async def _close_position(self, reason: str):
        """Mevcut pozisyonu kapatır"""
        try:
            if not self.current_position:
                return
            
            # Açık emirleri iptal et
            open_orders = await self.client.futures_get_open_orders(symbol=self.settings.symbol)
            for order in open_orders:
                await self.client.futures_cancel_order(
                    symbol=self.settings.symbol,
                    orderId=order['orderId']
                )
            
            # Pozisyon bilgilerini al
            positions = await self.client.futures_position_information(symbol=self.settings.symbol)
            position_amt = 0
            
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    position_amt = float(pos['positionAmt'])
                    break
            
            if position_amt != 0:
                # Market order ile pozisyonu kapat
                side = "SELL" if position_amt > 0 else "BUY"
                await self.client.futures_create_order(
                    symbol=self.settings.symbol,
                    side=side,
                    type="MARKET",
                    quantity=abs(position_amt),
                    reduceOnly=True
                )
            
            # WebSocket üzerinden bildirim gönder
            await self._send_update({
                "type": "position_closed",
                "symbol": self.settings.symbol,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            self.current_position = None
            logger.info(f"Position closed for {self.user_id}: {reason}")
            
        except Exception as e:
            logger.error(f"Error closing position for {self.settings.symbol}: {e}")
    
    async def _monitor_positions(self):
        """Pozisyonları izler ve güncel P&L bilgilerini gönderir"""
        while self.is_running:
            try:
                if self.current_position:
                    # Güncel pozisyon bilgilerini al
                    positions = await self.client.futures_position_information(symbol=self.settings.symbol)
                    
                    for pos in positions:
                        if float(pos['positionAmt']) != 0:
                            unrealized_pnl = float(pos['unRealizedProfit'])
                            percentage = float(pos['percentage'])
                            
                            # Position nesnesini güncelle
                            self.current_position.unrealized_pnl = unrealized_pnl
                            self.current_position.percentage = percentage
                            
                            # WebSocket üzerinden güncelleme gönder
                            await self._send_update({
                                "type": "position_update",
                                "symbol": self.settings.symbol,
                                "side": self.current_position.side,
                                "size": self.current_position.size,
                                "entry_price": self.current_position.entry_price,
                                "unrealized_pnl": unrealized_pnl,
                                "percentage": percentage,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            break
                    else:
                        # Pozisyon bulunamadı, bot position tracking'ini sıfırla
                        if self.current_position:
                            await self._send_update({
                                "type": "position_closed",
                                "symbol": self.settings.symbol,
                                "reason": "Position closed externally",
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            self.current_position = None
                
                await asyncio.sleep(5)  # 5 saniyede bir kontrol et
                
            except Exception as e:
                logger.error(f"Error monitoring positions for {self.settings.symbol}: {e}")
                await asyncio.sleep(10)  # Hata durumunda daha uzun bekle
    
    async def _send_update(self, message: dict):
        """WebSocket üzerinden güncelleme gönderir"""
        if self.websocket_callback:
            try:
                await self.websocket_callback(self.user_id, message)
            except Exception as e:
                logger.error(f"Error sending WebSocket update: {e}")
    
    def get_status(self) -> dict:
        """Bot durumunu döndürür"""
        return {
            "is_running": self.is_running,
            "symbol": self.settings.symbol,
            "timeframe": self.settings.timeframe,
            "leverage": self.settings.leverage,
            "margin_type": self.settings.margin_type,
            "current_position": {
                "symbol": self.current_position.symbol,
                "side": self.current_position.side,
                "size": self.current_position.size,
                "entry_price": self.current_position.entry_price,
                "unrealized_pnl": self.current_position.unrealized_pnl,
                "percentage": self.current_position.percentage
            } if self.current_position else None,
            "last_update": datetime.utcnow().isoformat()
        }

class BotManager:
    """Bot yönetici sınıfı"""
    
    def __init__(self):
        self.active_bots: Dict[str, TradingBot] = {}
    
    async def start_bot(self, user_id: str, settings: TradingSettings, websocket_callback=None) -> dict:
        """Kullanıcı için bot başlatır"""
        try:
            # Eğer bot zaten çalışıyorsa durdur
            if user_id in self.active_bots:
                await self.stop_bot(user_id)
            
            # Yeni bot oluştur ve başlat
            bot = TradingBot(user_id, settings, websocket_callback)
            result = await bot.start()
            
            if result["success"]:
                self.active_bots[user_id] = bot
            
            return result
            
        except Exception as e:
            logger.error(f"Error starting bot for user {user_id}: {e}")
            return {"success": False, "message": f"Failed to start bot: {str(e)}"}
    
    async def stop_bot(self, user_id: str) -> dict:
        """Kullanıcının botunu durdurur"""
        try:
            if user_id not in self.active_bots:
                return {"success": False, "message": "No active bot found"}
            
            bot = self.active_bots[user_id]
            result = await bot.stop()
            
            if result["success"]:
                del self.active_bots[user_id]
            
            return result
            
        except Exception as e:
            logger.error(f"Error stopping bot for user {user_id}: {e}")
            return {"success": False, "message": f"Failed to stop bot: {str(e)}"}
    
    def get_bot_status(self, user_id: str) -> dict:
        """Kullanıcının bot durumunu döndürür"""
        if user_id in self.active_bots:
            return self.active_bots[user_id].get_status()
        else:
            return {
                "is_running": False,
                "symbol": None,
                "current_position": None,
                "last_update": datetime.utcnow().isoformat()
            }
    
    async def stop_all_bots(self):
        """Tüm botları durdurur"""
        for user_id in list(self.active_bots.keys()):
            await self.stop_bot(user_id)
        
        logger.info("All bots stopped")

# Global bot manager instance
bot_manager = BotManager()
