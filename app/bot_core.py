import asyncio
import json
import websockets
from .config import settings
from .binance_client import binance_client
from .trading_strategy import trading_strategy
from .firebase_manager import firebase_manager
from datetime import datetime, timezone
import math
import time
import traceback

class BotCore:
    def __init__(self):
        self.status = {
            "is_running": False, 
            "symbol": None, 
            "position_side": None, 
            "status_message": "Bot başlatılmadı.",
            "account_balance": 0.0,
            "position_pnl": 0.0,
            "order_size": 0.0,
            "dynamic_sizing": True
        }
        self.klines = []
        self._stop_requested = False
        self.quantity_precision = 0
        self.price_precision = 0
        self._last_status_update = 0
        self._websocket_reconnect_attempts = 0
        self._max_reconnect_attempts = 10

    def _get_precision_from_filter(self, symbol_info, filter_type, key):
        for f in symbol_info['filters']:
            if f['filterType'] == filter_type:
                size_str = f[key]
                if '.' in size_str:
                    return len(size_str.split('.')[1].rstrip('0'))
                return 0
        return 0

    async def _calculate_dynamic_order_size(self):
        """Dinamik pozisyon boyutu hesapla - bakiyenin %90'ı"""
        try:
            current_balance = await binance_client.get_account_balance(use_cache=False)
            dynamic_size = current_balance * 0.9
            
            min_size = 5.0
            max_size = 1000.0
            
            final_size = max(min(dynamic_size, max_size), min_size)
            
            print(f"💰 Dinamik pozisyon hesaplama:")
            print(f"   Mevcut bakiye: {current_balance:.2f} USDT")
            print(f"   %90'ı: {dynamic_size:.2f} USDT")
            print(f"   Kullanılacak tutar: {final_size:.2f} USDT")
            
            self.status["order_size"] = final_size
            return final_size
            
        except Exception as e:
            print(f"Dinamik pozisyon hesaplama hatası: {e}")
            fallback_size = 35.0
            self.status["order_size"] = fallback_size
            return fallback_size

    async def start(self, symbol: str):
        if self.status["is_running"]:
            print("Bot zaten çalışıyor.")
            return
            
        self._stop_requested = False
        self._websocket_reconnect_attempts = 0
        self.status.update({
            "is_running": True, 
            "symbol": symbol, 
            "position_side": None, 
            "status_message": f"{symbol} için başlatılıyor...",
            "dynamic_sizing": True
        })
        print(self.status["status_message"])
        
        try:
            # 1. Binance bağlantısı
            print("1. Binance bağlantısı kuruluyor...")
            try:
                await binance_client.initialize()
                print("✅ Binance bağlantısı başarılı")
            except Exception as binance_error:
                print(f"❌ Binance bağlantı hatası: {binance_error}")
                raise binance_error
            
            # 2. Hesap bakiyesi kontrolü
            print("2. Hesap bakiyesi kontrol ediliyor...")
            try:
                self.status["account_balance"] = await binance_client.get_account_balance(use_cache=False)
                initial_order_size = await self._calculate_dynamic_order_size()
                print(f"✅ Hesap bakiyesi: {self.status['account_balance']} USDT")
                print(f"✅ İlk pozisyon boyutu: {initial_order_size} USDT")
            except Exception as balance_error:
                print(f"❌ Bakiye kontrol hatası: {balance_error}")
                raise balance_error
            
            # 3. Symbol bilgileri
            print(f"3. {symbol} sembol bilgileri alınıyor...")
            try:
                symbol_info = await binance_client.get_symbol_info(symbol)
                if not symbol_info:
                    error_msg = f"❌ {symbol} için borsa bilgileri alınamadı. Sembol doğru mu?"
                    print(error_msg)
                    self.status["status_message"] = error_msg
                    await self.stop()
                    return
                print(f"✅ {symbol} sembol bilgileri alındı")
            except Exception as symbol_error:
                print(f"❌ Symbol bilgisi hatası: {symbol_error}")
                raise symbol_error
                
            # 4. Precision hesaplama
            print("4. Hassasiyet bilgileri hesaplanıyor...")
            try:
                self.quantity_precision = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
                self.price_precision = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')
                print(f"✅ Miktar Hassasiyeti: {self.quantity_precision}, Fiyat Hassasiyeti: {self.price_precision}")
            except Exception as precision_error:
                print(f"❌ Precision hesaplama hatası: {precision_error}")
                raise precision_error
            
            # 5. Açık pozisyon kontrolü
            print("5. Açık pozisyonlar kontrol ediliyor...")
            try:
                open_positions = await binance_client.get_open_positions(symbol, use_cache=False)
                if open_positions:
                    position = open_positions[0]
                    position_amt = float(position['positionAmt'])
                    if position_amt > 0:
                        self.status["position_side"] = "LONG"
                    elif position_amt < 0:
                        self.status["position_side"] = "SHORT"
                    print(f"⚠️ {symbol} için açık pozisyon tespit edildi: {self.status['position_side']}")
                    print("Mevcut kaldıraçla devam ediliyor...")
                else:
                    print(f"✅ {symbol} için açık pozisyon yok")
                    # Kaldıraç ayarlama
                    print("6. Kaldıraç ayarlanıyor...")
                    if await binance_client.set_leverage(symbol, settings.LEVERAGE):
                        print(f"✅ Kaldıraç {settings.LEVERAGE}x olarak ayarlandı")
                    else:
                        print("⚠️ Kaldıraç ayarlanamadı, mevcut kaldıraçla devam ediliyor")
            except Exception as position_error:
                print(f"❌ Pozisyon kontrolü hatası: {position_error}")
                raise position_error
                
            # 6. Geçmiş veri çekme
            print("7. Geçmiş mum verileri çekiliyor...")
            try:
                self.klines = await binance_client.get_historical_klines(symbol, settings.TIMEFRAME, limit=50)
                if not self.klines:
                    error_msg = f"❌ {symbol} için geçmiş veri alınamadı"
                    print(error_msg)
                    self.status["status_message"] = error_msg
                    await self.stop()
                    return
                print(f"✅ {len(self.klines)} adet geçmiş mum verisi alındı")
            except Exception as klines_error:
                print(f"❌ Geçmiş veri çekme hatası: {klines_error}")
                raise klines_error
                
            # 7. WebSocket bağlantısı
            print("8. WebSocket bağlantısı kuruluyor...")
            self.status["status_message"] = f"{symbol} ({settings.TIMEFRAME}) için sinyal bekleniyor... [DİNAMİK SİZING AKTİF]"
            print(f"✅ {self.status['status_message']}")
            
            await self._start_websocket_loop()
                        
        except Exception as e:
            error_msg = f"❌ Bot başlatılırken beklenmeyen hata: {e}"
            print(error_msg)
            print(f"❌ Full traceback: {traceback.format_exc()}")
            self.status["status_message"] = error_msg
        
        print("Bot durduruluyor...")
        await self.stop()

    async def _start_websocket_loop(self):
        """WebSocket bağlantı döngüsü - otomatik yeniden bağlanma ile"""
        ws_url = f"{settings.WEBSOCKET_URL}/ws/{self.status['symbol'].lower()}@kline_{settings.TIMEFRAME}"
        print(f"WebSocket URL: {ws_url}")
        
        while not self._stop_requested and self._websocket_reconnect_attempts < self._max_reconnect_attempts:
            try:
                async with websockets.connect(
                    ws_url, 
                    ping_interval=30, 
                    ping_timeout=15,
                    close_timeout=10
                ) as ws:
                    print(f"✅ WebSocket bağlantısı kuruldu (Deneme: {self._websocket_reconnect_attempts + 1})")
                    self._websocket_reconnect_attempts = 0
                    
                    while not self._stop_requested:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=65.0)
                            await self._handle_websocket_message(message)
                        except asyncio.TimeoutError:
                            print("WebSocket timeout - bağlantı kontrol ediliyor...")
                            try:
                                await ws.ping()
                                await asyncio.sleep(1)
                            except:
                                print("WebSocket ping başarısız - yeniden bağlanılıyor...")
                                break
                        except websockets.exceptions.ConnectionClosed:
                            print("WebSocket bağlantısı koptu...")
                            break
                        except Exception as e:
                            print(f"WebSocket mesaj işleme hatası: {e}")
                            await asyncio.sleep(1)
                            
            except Exception as e:
                if not self._stop_requested:
                    self._websocket_reconnect_attempts += 1
                    backoff_time = min(5 * self._websocket_reconnect_attempts, 30)
                    print(f"WebSocket bağlantı hatası (Deneme {self._websocket_reconnect_attempts}/{self._max_reconnect_attempts}): {e}")
                    print(f"{backoff_time} saniye sonra yeniden deneniyor...")
                    await asyncio.sleep(backoff_time)
        
        if self._websocket_reconnect_attempts >= self._max_reconnect_attempts:
            print(f"❌ WebSocket maksimum yeniden bağlanma denemesi ({self._max_reconnect_attempts}) aşıldı")
            self.status["status_message"] = "WebSocket bağlantısı kurulamadı - Bot durduruluyor"

    async def stop(self):
        self._stop_requested = True
        if self.status["is_running"]:
            self.status.update({
                "is_running": False, 
                "status_message": "Bot durduruldu.",
                "account_balance": 0.0,
                "position_pnl": 0.0,
                "order_size": 0.0
            })
            print(self.status["status_message"])
            await binance_client.close()

    async def _handle_websocket_message(self, message: str):
        try:
            data = json.loads(message)
            kline_data = data.get('k', {})
            
            # Durum bilgilerini güncelle
            current_time = time.time()
            if current_time - self._last_status_update > 10:
                await self._update_status_info()
                self._last_status_update = current_time
            
            # Sadece kapanan mumları işle
            if not kline_data.get('x', False):
                return
                
            print(f"Yeni mum kapandı: {self.status['symbol']} ({settings.TIMEFRAME}) - Kapanış: {kline_data['c']}")
            self.klines.pop(0)
            self.klines.append([
                kline_data[key] for key in ['t','o','h','l','c','v','T','q','n','V','Q']
            ] + ['0'])
            
            # Pozisyon kontrolü
            open_positions = await binance_client.get_open_positions(self.status["symbol"], use_cache=True)
            if self.status["position_side"] is not None and not open_positions:
                print(f"--> Pozisyon SL/TP ile kapandı. Yeni sinyal bekleniyor.")
                pnl = await binance_client.get_last_trade_pnl(self.status["symbol"])
                firebase_manager.log_trade({
                    "symbol": self.status["symbol"], 
                    "pnl": pnl, 
                    "status": "CLOSED_BY_SL_TP", 
                    "timestamp": datetime.now(timezone.utc)
                })
                
                self.status["position_side"] = None
                
                # Pozisyon kapandıktan sonra yeni bakiye ile order size güncelle
                await self._calculate_dynamic_order_size()

            # Sinyal analizi
            signal = trading_strategy.analyze_klines(self.klines)
            print(f"Strateji analizi sonucu: {signal}")

            # Pozisyon yönetimi
            if signal != "HOLD" and signal != self.status.get("position_side"):
                await self._flip_position(signal)
                
        except Exception as e:
            print(f"WebSocket mesaj işlenirken hata: {e}")

    async def _update_status_info(self):
        """Durum bilgilerini günceller - rate limit korumalı"""
        try:
            if self.status["is_running"]:
                # Cache kullanarak sorgu sayısını azalt
                self.status["account_balance"] = await binance_client.get_account_balance(use_cache=True)
                if self.status["position_side"]:
                    self.status["position_pnl"] = await binance_client.get_position_pnl(
                        self.status["symbol"], use_cache=True
                    )
                else:
                    self.status["position_pnl"] = 0.0
                # Order size'ı dinamik tut
                await self._calculate_dynamic_order_size()
                
        except Exception as e:
            print(f"Durum güncelleme hatası: {e}")

    def _format_quantity(self, quantity: float):
        if self.quantity_precision == 0:
            return math.floor(quantity)
        factor = 10 ** self.quantity_precision
        return math.floor(quantity * factor) / factor

    async def _flip_position(self, new_signal: str):
        symbol = self.status["symbol"]
        
        try:
            # Mevcut pozisyonu kapat
            open_positions = await binance_client.get_open_positions(symbol, use_cache=False)
            if open_positions:
                position = open_positions[0]
                position_amt = float(position['positionAmt'])
                side_to_close = 'SELL' if position_amt > 0 else 'BUY'
                print(f"--> Ters sinyal geldi. Mevcut {self.status['position_side']} pozisyonu kapatılıyor...")
                
                pnl = await binance_client.get_last_trade_pnl(symbol)
                firebase_manager.log_trade({
                    "symbol": symbol, 
                    "pnl": pnl, 
                    "status": "CLOSED_BY_FLIP", 
                    "timestamp": datetime.now(timezone.utc)
                })

                # Pozisyonu kapat
                close_result = await binance_client.close_open_position_and_orders(symbol)
                if not close_result:
                    print("❌ Pozisyon kapatma başarısız - yeni pozisyon açılmayacak")
                    return
                    
                await asyncio.sleep(1)

            # Dinamik order size hesapla
            print(f"--> Yeni {new_signal} pozisyonu için dinamik boyut hesaplanıyor...")
            dynamic_order_size = await self._calculate_dynamic_order_size()
            
            # Yeni pozisyon aç
            print(f"--> Yeni {new_signal} pozisyonu açılıyor... (Tutar: {dynamic_order_size} USDT)")
            side = "BUY" if new_signal == "LONG" else "SELL"
            price = await binance_client.get_market_price(symbol)
            if not price:
                print("❌ Yeni pozisyon için fiyat alınamadı.")
                return
                
            quantity = self._format_quantity((dynamic_order_size * settings.LEVERAGE) / price)
            if quantity <= 0:
                print("❌ Hesaplanan miktar çok düşük.")
                return

            # Pozisyon açma
            order = await binance_client.create_order_with_tp_sl(
                symbol, side, quantity, price, self.price_precision, 
                settings.STOP_LOSS_PERCENT * 100, settings.TAKE_PROFIT_PERCENT * 100
            )
            
            if order:
                self.status["position_side"] = new_signal
                self.status["status_message"] = f"Yeni {new_signal} pozisyonu {price} fiyattan açıldı. (Tutar: {dynamic_order_size:.2f} USDT)"
                print(f"✅ {self.status['status_message']}")
            else:
                self.status["position_side"] = None
                self.status["status_message"] = "Yeni pozisyon açılamadı."
                print(f"❌ {self.status['status_message']}")
                
        except Exception as e:
            print(f"❌ Pozisyon değiştirme hatası: {e}")
            self.status["position_side"] = None

bot_core = BotCore()
