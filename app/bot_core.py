import asyncio
import json
import websockets
from .config import settings
from .binance_client import binance_client
from .trading_strategy import trading_strategy
from .firebase_manager import firebase_manager
from .position_manager import position_manager
from datetime import datetime, timezone
import math
import time
import traceback

class BotCore:
    def __init__(self):
        self.status = {
            "is_running": False, 
            "symbols": [],  # ÇOK ÖNEMLİ: Tek symbol yerine symbols listesi
            "active_symbol": None,  # Şu anda pozisyonu olan symbol
            "position_side": None, 
            "status_message": "Bot başlatılmadı.",
            "account_balance": 0.0,
            "position_pnl": 0.0,
            "order_size": 0.0,
            "dynamic_sizing": True,
            "position_monitor_active": False,
            "last_signals": {}  # Her coin için son sinyal
        }
        self.multi_klines = {}  # Her symbol için ayrı kline data
        self._stop_requested = False
        self.quantity_precision = {}  # Her symbol için precision
        self.price_precision = {}
        self._last_status_update = 0
        self._websocket_connections = {}  # Her symbol için WebSocket bağlantısı
        self._websocket_tasks = []  # WebSocket task'ları
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

    async def start(self, symbols: list):
        """ÇOK ÖNEMLİ: Artık symbols listesi alıyor"""
        if self.status["is_running"]:
            print("Bot zaten çalışıyor.")
            return
            
        if not symbols or len(symbols) == 0:
            print("❌ Hiç symbol verilmedi!")
            return
            
        self._stop_requested = False
        self.status.update({
            "is_running": True, 
            "symbols": symbols,  # Symbol listesi
            "active_symbol": None,  # Şu anda pozisyonu olan symbol
            "position_side": None, 
            "status_message": f"{len(symbols)} coin için başlatılıyor...",
            "dynamic_sizing": True,
            "position_monitor_active": False,
            "last_signals": {symbol: "HOLD" for symbol in symbols}
        })
        print(f"🚀 Multi-coin bot başlatılıyor: {', '.join(symbols)}")
        
        try:
            # 1. Binance bağlantısı
            print("1. Binance bağlantısı kuruluyor...")
            try:
                await binance_client.initialize()
                print("✅ Binance bağlantısı başarılı")
            except Exception as binance_error:
                print(f"❌ Binance bağlantı hatası: {binance_error}")
                raise binance_error
            
            # 2. Tüm symboller için yetim emir temizliği
            print("2. 🧹 Tüm symboller için yetim emir temizliği yapılıyor...")
            for symbol in symbols:
                try:
                    cleanup_result = await binance_client.cancel_all_orders_safe(symbol)
                    if cleanup_result:
                        print(f"✅ {symbol} yetim emir temizliği başarılı")
                    else:
                        print(f"⚠️ {symbol} yetim emir temizliği eksik - devam ediliyor")
                    await asyncio.sleep(0.2)
                except Exception as cleanup_error:
                    print(f"⚠️ {symbol} temizlik hatası: {cleanup_error} - devam ediliyor")
            
            # 3. Hesap bakiyesi kontrolü
            print("3. Hesap bakiyesi kontrol ediliyor...")
            try:
                self.status["account_balance"] = await binance_client.get_account_balance(use_cache=False)
                initial_order_size = await self._calculate_dynamic_order_size()
                print(f"✅ Hesap bakiyesi: {self.status['account_balance']} USDT")
                print(f"✅ İlk pozisyon boyutu: {initial_order_size} USDT")
            except Exception as balance_error:
                print(f"❌ Bakiye kontrol hatası: {balance_error}")
                raise balance_error
            
            # 4. Tüm symboller için bilgi alma ve hazırlık
            print(f"4. {len(symbols)} symbol için bilgiler alınıyor...")
            for symbol in symbols:
                try:
                    symbol_info = await binance_client.get_symbol_info(symbol)
                    if not symbol_info:
                        print(f"❌ {symbol} için borsa bilgileri alınamadı. Atlanıyor...")
                        continue
                    
                    # Precision hesaplama
                    self.quantity_precision[symbol] = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
                    self.price_precision[symbol] = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')
                    print(f"✅ {symbol} bilgileri alındı (Q:{self.quantity_precision[symbol]}, P:{self.price_precision[symbol]})")
                    
                    # Geçmiş veri çekme
                    klines = await binance_client.get_historical_klines(symbol, settings.TIMEFRAME, limit=50)
                    if klines:
                        self.multi_klines[symbol] = klines
                        print(f"✅ {symbol} için {len(klines)} geçmiş mum verisi alındı")
                    else:
                        print(f"❌ {symbol} için geçmiş veri alınamadı. Atlanıyor...")
                        continue
                        
                    await asyncio.sleep(0.2)  # Rate limit koruması
                    
                except Exception as symbol_error:
                    print(f"❌ {symbol} hazırlık hatası: {symbol_error} - Atlanıyor...")
                    continue
            
            # 5. Mevcut açık pozisyon kontrolü
            print("5. Mevcut açık pozisyonlar kontrol ediliyor...")
            try:
                await binance_client._rate_limit_delay()
                all_positions = await binance_client.client.futures_position_information()
                open_positions = [p for p in all_positions if float(p['positionAmt']) != 0]
                
                if open_positions:
                    # İlk bulunan açık pozisyonu aktif yap
                    active_position = open_positions[0]
                    active_symbol = active_position['symbol']
                    position_amt = float(active_position['positionAmt'])
                    
                    if position_amt > 0:
                        self.status["position_side"] = "LONG"
                    elif position_amt < 0:
                        self.status["position_side"] = "SHORT"
                        
                    self.status["active_symbol"] = active_symbol
                    print(f"⚠️ Mevcut {self.status['position_side']} pozisyonu tespit edildi: {active_symbol}")
                    print("Mevcut kaldıraçla devam ediliyor...")
                    
                    # Mevcut pozisyon için yetim emirleri temizle
                    print(f"🧹 {active_symbol} mevcut pozisyon için ekstra yetim emir temizliği...")
                    await binance_client.cancel_all_orders_safe(active_symbol)
                    
                    # Mevcut pozisyon için TP/SL kontrol et
                    print(f"🛡️ {active_symbol} mevcut pozisyon için TP/SL kontrolü yapılıyor...")
                    await position_manager.manual_scan_symbol(active_symbol)
                else:
                    print("✅ Açık pozisyon bulunamadı")
                    # Tüm symboller için kaldıraç ayarlama
                    print("6. Tüm symboller için kaldıraç ayarlanıyor...")
                    for symbol in symbols:
                        if symbol in self.multi_klines:  # Sadece başarılı symboller için
                            if await binance_client.set_leverage(symbol, settings.LEVERAGE):
                                print(f"✅ {symbol} kaldıracı {settings.LEVERAGE}x olarak ayarlandı")
                            else:
                                print(f"⚠️ {symbol} kaldıracı ayarlanamadı, mevcut kaldıraçla devam ediliyor")
                            await asyncio.sleep(0.3)
                            
            except Exception as position_error:
                print(f"❌ Pozisyon kontrolü hatası: {position_error}")
                raise position_error
                
            # 7. Pozisyon Monitoring Başlat
            print("7. 🛡️ Otomatik TP/SL monitoring başlatılıyor...")
            try:
                asyncio.create_task(position_manager.start_monitoring())
                self.status["position_monitor_active"] = True
                print("✅ Otomatik TP/SL koruması aktif")
            except Exception as monitor_error:
                print(f"⚠️ Position monitoring başlatılamadı: {monitor_error}")
                
            # 8. Multi-WebSocket bağlantıları başlat
            print("8. 🌐 Multi-coin WebSocket bağlantıları kuruluyor...")
            valid_symbols = [s for s in symbols if s in self.multi_klines]
            self.status["symbols"] = valid_symbols  # Sadece geçerli symboller
            
            if not valid_symbols:
                raise Exception("Hiç geçerli symbol bulunamadı!")
                
            self.status["status_message"] = f"{len(valid_symbols)} coin izleniyor ({settings.TIMEFRAME}) [DİNAMİK SİZING + YETİM EMİR KORUMASII + OTOMATIK TP/SL AKTİF]"
            print(f"✅ {self.status['status_message']}")
            
            await self._start_multi_websocket_loop(valid_symbols)
                        
        except Exception as e:
            error_msg = f"❌ Bot başlatılırken beklenmeyen hata: {e}"
            print(error_msg)
            print(f"❌ Full traceback: {traceback.format_exc()}")
            self.status["status_message"] = error_msg
        
        print("Bot durduruluyor...")
        await self.stop()

    async def _start_multi_websocket_loop(self, symbols: list):
        """Multi-coin WebSocket bağlantı döngüsü"""
        print(f"🌐 {len(symbols)} symbol için WebSocket bağlantıları başlatılıyor...")
        
        # Her symbol için ayrı WebSocket task oluştur
        self._websocket_tasks = []
        for symbol in symbols:
            task = asyncio.create_task(self._single_websocket_loop(symbol))
            self._websocket_tasks.append(task)
        
        # Tüm WebSocket task'larını bekle
        try:
            await asyncio.gather(*self._websocket_tasks)
        except Exception as e:
            print(f"❌ Multi-WebSocket hatası: {e}")

    async def _single_websocket_loop(self, symbol: str):
        """Tek symbol için WebSocket döngüsü"""
        ws_url = f"{settings.WEBSOCKET_URL}/ws/{symbol.lower()}@kline_{settings.TIMEFRAME}"
        reconnect_attempts = 0
        
        print(f"🔗 {symbol} WebSocket bağlantısı başlatılıyor...")
        
        while not self._stop_requested and reconnect_attempts < self._max_reconnect_attempts:
            try:
                async with websockets.connect(
                    ws_url, 
                    ping_interval=30, 
                    ping_timeout=15,
                    close_timeout=10
                ) as ws:
                    print(f"✅ {symbol} WebSocket bağlantısı kuruldu")
                    reconnect_attempts = 0
                    self._websocket_connections[symbol] = ws
                    
                    while not self._stop_requested:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=65.0)
                            await self._handle_single_websocket_message(symbol, message)
                        except asyncio.TimeoutError:
                            print(f"⏰ {symbol} WebSocket timeout - ping gönderiliyor...")
                            try:
                                await ws.ping()
                                await asyncio.sleep(1)
                            except:
                                print(f"❌ {symbol} WebSocket ping başarısız - yeniden bağlanılıyor...")
                                break
                        except websockets.exceptions.ConnectionClosed:
                            print(f"🔌 {symbol} WebSocket bağlantısı koptu...")
                            break
                        except Exception as e:
                            print(f"❌ {symbol} WebSocket mesaj işleme hatası: {e}")
                            await asyncio.sleep(1)
                            
            except Exception as e:
                if not self._stop_requested:
                    reconnect_attempts += 1
                    backoff_time = min(5 * reconnect_attempts, 30)
                    print(f"❌ {symbol} WebSocket bağlantı hatası (Deneme {reconnect_attempts}/{self._max_reconnect_attempts}): {e}")
                    if reconnect_attempts < self._max_reconnect_attempts:
                        print(f"⏳ {symbol} için {backoff_time} saniye sonra yeniden deneniyor...")
                        await asyncio.sleep(backoff_time)
            finally:
                if symbol in self._websocket_connections:
                    del self._websocket_connections[symbol]
        
        if reconnect_attempts >= self._max_reconnect_attempts:
            print(f"❌ {symbol} WebSocket maksimum yeniden bağlanma denemesi aşıldı")

    async def stop(self):
        """Bot durdurma - tüm WebSocket bağlantılarını kapat"""
        self._stop_requested = True
        if self.status["is_running"]:
            print("🛑 Multi-coin bot durduruluyor...")
            
            # WebSocket task'larını iptal et
            for task in self._websocket_tasks:
                if not task.done():
                    task.cancel()
            
            # WebSocket bağlantılarını kapat
            for symbol, ws in self._websocket_connections.items():
                try:
                    await ws.close()
                except:
                    pass
            self._websocket_connections.clear()
            
            # Position monitoring'i durdur
            if self.status.get("position_monitor_active"):
                print("🛡️ Otomatik TP/SL monitoring durduruluyor...")
                await position_manager.stop_monitoring()
                self.status["position_monitor_active"] = False
            
            # Bot durdururken son temizlik
            if self.status.get("symbols"):
                print(f"🧹 Bot durduruluyor - tüm symboller için son yetim emir temizliği...")
                for symbol in self.status["symbols"]:
                    try:
                        await binance_client.cancel_all_orders_safe(symbol)
                        await asyncio.sleep(0.1)
                    except Exception as final_cleanup_error:
                        print(f"⚠️ {symbol} son temizlik hatası: {final_cleanup_error}")
            
            self.status.update({
                "is_running": False, 
                "symbols": [],
                "active_symbol": None,
                "status_message": "Bot durduruldu.",
                "account_balance": 0.0,
                "position_pnl": 0.0,
                "order_size": 0.0,
                "position_monitor_active": False,
                "last_signals": {}
            })
            print(self.status["status_message"])
            await binance_client.close()

    async def _handle_single_websocket_message(self, symbol: str, message: str):
        """Tek symbol için WebSocket mesaj işleme"""
        try:
            data = json.loads(message)
            kline_data = data.get('k', {})
            
            # Durum bilgilerini güncelle (tüm symboller için ortak)
            current_time = time.time()
            if current_time - self._last_status_update > 10:
                await self._update_status_info()
                self._last_status_update = current_time
            
            # Sadece kapanan mumları işle
            if not kline_data.get('x', False):
                return
                
            print(f"📊 {symbol} yeni mum kapandı ({settings.TIMEFRAME}) - Kapanış: {kline_data['c']}")
            
            # Bu symbol için kline data güncelle
            if symbol not in self.multi_klines:
                self.multi_klines[symbol] = []
            
            self.multi_klines[symbol].pop(0) if len(self.multi_klines[symbol]) >= 50 else None
            self.multi_klines[symbol].append([
                kline_data[key] for key in ['t','o','h','l','c','v','T','q','n','V','Q']
            ] + ['0'])
            
            # Sinyal analizi
            signal = trading_strategy.analyze_klines(self.multi_klines[symbol])
            self.status["last_signals"][symbol] = signal
            print(f"🔍 {symbol} strateji analizi: {signal}")

            # ÇOK ÖNEMLİ: Pozisyon yönetimi - Multi-coin mantığı
            await self._handle_multi_coin_position_logic(symbol, signal)
                
        except Exception as e:
            print(f"❌ {symbol} WebSocket mesaj işlenirken hata: {e}")

    async def _handle_multi_coin_position_logic(self, signal_symbol: str, signal: str):
        """Multi-coin pozisyon yönetim mantığı"""
        try:
            # Mevcut durum kontrolü
            current_active_symbol = self.status.get("active_symbol")
            current_position_side = self.status.get("position_side")
            
            # DURUM 1: Hiç pozisyon yok, yeni sinyal geldi
            if not current_active_symbol and not current_position_side and signal != "HOLD":
                print(f"🚀 Yeni pozisyon fırsatı: {signal_symbol} -> {signal}")
                await self._open_new_position(signal_symbol, signal)
                return
            
            # DURUM 2: Mevcut pozisyon var, aynı symbol'den ters sinyal geldi
            if (current_active_symbol == signal_symbol and 
                current_position_side and 
                signal != "HOLD" and 
                signal != current_position_side):
                print(f"🔄 {signal_symbol} ters sinyal geldi: {current_position_side} -> {signal}")
                await self._flip_position(signal_symbol, signal)
                return
            
            # DURUM 3: Mevcut pozisyon var, başka symbol'den sinyal geldi
            if (current_active_symbol and 
                current_active_symbol != signal_symbol and 
                current_position_side and 
                signal != "HOLD"):
                print(f"💡 Yeni coin fırsatı: {signal_symbol} -> {signal} (Mevcut: {current_active_symbol})")
                await self._switch_to_new_coin(current_active_symbol, signal_symbol, signal)
                return
            
            # DURUM 4: Pozisyon kapanmış mı kontrol et (SL/TP)
            if current_active_symbol and current_position_side:
                open_positions = await binance_client.get_open_positions(current_active_symbol, use_cache=True)
                if not open_positions:
                    print(f"✅ {current_active_symbol} pozisyonu SL/TP ile kapandı")
                    pnl = await binance_client.get_last_trade_pnl(current_active_symbol)
                    firebase_manager.log_trade({
                        "symbol": current_active_symbol, 
                        "pnl": pnl, 
                        "status": "CLOSED_BY_SL_TP", 
                        "timestamp": datetime.now(timezone.utc)
                    })
                    
                    # Pozisyon kapandı, durumu temizle
                    self.status["active_symbol"] = None
                    self.status["position_side"] = None
                    
                    # Pozisyon kapandıktan sonra yetim emir temizliği
                    print(f"🧹 {current_active_symbol} pozisyon kapandı - yetim emir temizliği yapılıyor...")
                    await binance_client.cancel_all_orders_safe(current_active_symbol)
                    
                    # Pozisyon kapandıktan sonra yeni bakiye ile order size güncelle
                    await self._calculate_dynamic_order_size()
                    
                    # Eğer bu mesajı gönderen symbol'de aktif sinyal varsa hemen pozisyon aç
                    if signal != "HOLD":
                        print(f"🚀 Pozisyon kapandıktan sonra hemen yeni fırsat: {signal_symbol} -> {signal}")
                        await self._open_new_position(signal_symbol, signal)
                        
        except Exception as e:
            print(f"❌ Multi-coin pozisyon mantığı hatası: {e}")

    async def _open_new_position(self, symbol: str, signal: str):
        """Yeni pozisyon açma"""
        try:
            print(f"🎯 {symbol} için yeni {signal} pozisyonu açılıyor...")
            
            # Yetim emir temizliği
            print(f"🧹 {symbol} pozisyon öncesi yetim emir temizliği...")
            await binance_client.cancel_all_orders_safe(symbol)
            await asyncio.sleep(0.3)
            
            # Dinamik order size hesapla
            dynamic_order_size = await self._calculate_dynamic_order_size()
            
            # Pozisyon aç
            side = "BUY" if signal == "LONG" else "SELL"
            price = await binance_client.get_market_price(symbol)
            if not price:
                print(f"❌ {symbol} için fiyat alınamadı.")
                return False
                
            quantity = self._format_quantity(symbol, (dynamic_order_size * settings.LEVERAGE) / price)
            if quantity <= 0:
                print(f"❌ {symbol} için hesaplanan miktar çok düşük.")
                return False

            # YETİM EMİR KORUMASLI pozisyon açma
            order = await binance_client.create_market_order_with_sl_tp(
                symbol, side, quantity, price, self.price_precision.get(symbol, 2)
            )
            
            if order:
                self.status["active_symbol"] = symbol
                self.status["position_side"] = signal
                self.status["status_message"] = f"YENİ {signal} POZİSYONU: {symbol} @ {price} (Tutar: {dynamic_order_size:.2f} USDT) [OTOMATIK TP/SL KORUMASII AKTİF]"
                print(f"✅ {self.status['status_message']}")
                
                # Cache temizle
                try:
                    if hasattr(binance_client, '_cached_positions'):
                        binance_client._cached_positions.clear()
                    if hasattr(binance_client, '_last_position_check'):
                        binance_client._last_position_check.clear()
                except Exception as cache_error:
                    print(f"Cache temizleme hatası: {cache_error}")
                    
                # Yeni pozisyon için position manager'a bildir
                await asyncio.sleep(2)
                print(f"🛡️ {symbol} yeni pozisyon otomatik TP/SL sisteme bildiriliyor...")
                await position_manager.manual_scan_symbol(symbol)
                return True
            else:
                print(f"❌ {symbol} pozisyonu açılamadı.")
                await binance_client.force_cleanup_orders(symbol)
                return False
                
        except Exception as e:
            print(f"❌ {symbol} yeni pozisyon açma hatası: {e}")
            await binance_client.force_cleanup_orders(symbol)
            return False

    async def _flip_position(self, symbol: str, new_signal: str):
        """Aynı coin'de pozisyon çevirme (mevcut sistem - KORUNDU)"""
        try:
            # Pozisyon değişiminden önce yetim emir kontrolü
            print(f"🧹 {symbol} pozisyon değişimi öncesi yetim emir temizliği...")
            await binance_client.cancel_all_orders_safe(symbol)
            await asyncio.sleep(0.2)
            
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
                close_result = await binance_client.close_position(symbol, position_amt, side_to_close)
                if not close_result:
                    print("❌ Pozisyon kapatma başarısız - yeni pozisyon açılmayacak")
                    return
                    
                await asyncio.sleep(1)

            # Yeni pozisyon aç
            success = await self._open_new_position(symbol, new_signal)
            if not success:
                self.status["active_symbol"] = None
                self.status["position_side"] = None
                
        except Exception as e:
            print(f"❌ {symbol} pozisyon değiştirme hatası: {e}")
            try:
                await binance_client.force_cleanup_orders(symbol)
            except Exception as cleanup_error:
                print(f"⚠️ Acil temizlik de başarısız: {cleanup_error}")
            self.status["active_symbol"] = None
            self.status["position_side"] = None

    async def _switch_to_new_coin(self, current_symbol: str, new_symbol: str, new_signal: str):
        """Farklı coin'e geçiş yapma"""
        try:
            print(f"🔄 Coin değişimi: {current_symbol} -> {new_symbol} ({new_signal})")
            
            # Mevcut pozisyonu kapat
            open_positions = await binance_client.get_open_positions(current_symbol, use_cache=False)
            if open_positions:
                position = open_positions[0]
                position_amt = float(position['positionAmt'])
                side_to_close = 'SELL' if position_amt > 0 else 'BUY'
                
                print(f"📉 {current_symbol} pozisyonu kapatılıyor (coin değişimi)...")
                
                pnl = await binance_client.get_last_trade_pnl(current_symbol)
                firebase_manager.log_trade({
                    "symbol": current_symbol, 
                    "pnl": pnl, 
                    "status": "CLOSED_FOR_COIN_SWITCH", 
                    "timestamp": datetime.now(timezone.utc)
                })

                # Mevcut pozisyonu kapat
                close_result = await binance_client.close_position(current_symbol, position_amt, side_to_close)
                if not close_result:
                    print(f"❌ {current_symbol} pozisyon kapatma başarısız - coin değişimi iptal")
                    return
                    
                await asyncio.sleep(1)

            # Yeni coin'de pozisyon aç
            success = await self._open_new_position(new_symbol, new_signal)
            if not success:
                print(f"❌ {new_symbol} yeni pozisyon açılamadı")
                self.status["active_symbol"] = None
                self.status["position_side"] = None
                
        except Exception as e:
            print(f"❌ Coin değişimi hatası: {e}")
            try:
                await binance_client.force_cleanup_orders(current_symbol)
                await binance_client.force_cleanup_orders(new_symbol)
            except Exception as cleanup_error:
                print(f"⚠️ Coin değişimi acil temizlik hatası: {cleanup_error}")
            self.status["active_symbol"] = None
            self.status["position_side"] = None

    async def _update_status_info(self):
        """Durum bilgilerini günceller - rate limit korumalı"""
        try:
            if self.status["is_running"]:
                # Cache kullanarak sorgu sayısını azalt
                self.status["account_balance"] = await binance_client.get_account_balance(use_cache=True)
                if self.status["active_symbol"] and self.status["position_side"]:
                    self.status["position_pnl"] = await binance_client.get_position_pnl(
                        self.status["active_symbol"], use_cache=True
                    )
                else:
                    self.status["position_pnl"] = 0.0
                # Order size'ı dinamik tut
                await self._calculate_dynamic_order_size()
                
                # Position monitor durumunu güncelle
                monitor_status = position_manager.get_status()
                self.status["position_monitor_active"] = monitor_status["is_running"]
                
        except Exception as e:
            print(f"Durum güncelleme hatası: {e}")

    def _format_quantity(self, symbol: str, quantity: float):
        precision = self.quantity_precision.get(symbol, 0)
        if precision == 0:
            return math.floor(quantity)
        factor = 10 ** precision
        return math.floor(quantity * factor) / factor

    # YENİ METODLAR - MULTI-COIN YÖNETİMİ
    async def add_symbol(self, symbol: str):
        """Çalışan bot'a yeni symbol ekle"""
        if not self.status["is_running"]:
            return {"success": False, "message": "Bot çalışmıyor"}
            
        if symbol in self.status["symbols"]:
            return {"success": False, "message": f"{symbol} zaten izleniyor"}
            
        try:
            # Symbol bilgilerini al ve hazırla
            symbol_info = await binance_client.get_symbol_info(symbol)
            if not symbol_info:
                return {"success": False, "message": f"{symbol} için borsa bilgileri alınamadı"}
            
            # Precision hesaplama
            self.quantity_precision[symbol] = self._get_precision_from_filter(symbol_info, 'LOT_SIZE', 'stepSize')
            self.price_precision[symbol] = self._get_precision_from_filter(symbol_info, 'PRICE_FILTER', 'tickSize')
            
            # Geçmiş veri çekme
            klines = await binance_client.get_historical_klines(symbol, settings.TIMEFRAME, limit=50)
            if not klines:
                return {"success": False, "message": f"{symbol} için geçmiş veri alınamadı"}
            
            self.multi_klines[symbol] = klines
            
            # Kaldıraç ayarla
            await binance_client.set_leverage(symbol, settings.LEVERAGE)
            
            # Symbol listesine ekle
            self.status["symbols"].append(symbol)
            self.status["last_signals"][symbol] = "HOLD"
            
            # Yeni WebSocket bağlantısı başlat
            task = asyncio.create_task(self._single_websocket_loop(symbol))
            self._websocket_tasks.append(task)
            
            print(f"✅ {symbol} bot'a eklendi")
            return {"success": True, "message": f"{symbol} başarıyla eklendi"}
            
        except Exception as e:
            return {"success": False, "message": f"{symbol} eklenirken hata: {e}"}

    async def remove_symbol(self, symbol: str):
        """Çalışan bot'tan symbol çıkar"""
        if not self.status["is_running"]:
            return {"success": False, "message": "Bot çalışmıyor"}
            
        if symbol not in self.status["symbols"]:
            return {"success": False, "message": f"{symbol} zaten izlenmiyor"}
            
        if self.status["active_symbol"] == symbol:
            return {"success": False, "message": f"{symbol} şu anda aktif pozisyonda - önce pozisyonu kapatın"}
            
        try:
            # Symbol'ü listeden çıkar
            self.status["symbols"].remove(symbol)
            if symbol in self.status["last_signals"]:
                del self.status["last_signals"][symbol]
            if symbol in self.multi_klines:
                del self.multi_klines[symbol]
            if symbol in self.quantity_precision:
                del self.quantity_precision[symbol]
            if symbol in self.price_precision:
                del self.price_precision[symbol]
            
            # WebSocket bağlantısını kapat (task kendini kapatacak)
            if symbol in self._websocket_connections:
                try:
                    await self._websocket_connections[symbol].close()
                except:
                    pass
                del self._websocket_connections[symbol]
            
            print(f"✅ {symbol} bot'tan çıkarıldı")
            return {"success": True, "message": f"{symbol} başarıyla çıkarıldı"}
            
        except Exception as e:
            return {"success": False, "message": f"{symbol} çıkarılırken hata: {e}"}

    def get_multi_status(self):
        """Multi-coin bot durumunu döndür"""
        return {
            "is_running": self.status["is_running"],
            "symbols": self.status["symbols"],
            "active_symbol": self.status["active_symbol"],
            "position_side": self.status["position_side"],
            "status_message": self.status["status_message"],
            "account_balance": self.status["account_balance"],
            "position_pnl": self.status["position_pnl"],
            "order_size": self.status["order_size"],
            "last_signals": self.status["last_signals"],
            "position_monitor_active": self.status["position_monitor_active"],
            "websocket_connections": len(self._websocket_connections),
            "position_manager": position_manager.get_status()
        }

    # MEVCUT METODLAR - GERİYE UYUMLULUK İÇİN KORUNDU
    async def scan_all_positions(self):
        """Tüm açık pozisyonları manuel tarayıp TP/SL ekle"""
        if not self.status["is_running"]:
            return {"success": False, "message": "Bot çalışmıyor"}
            
        try:
            print("🔍 Manuel pozisyon taraması başlatılıyor...")
            
            # Position manager ile tam tarama yap
            await position_manager._scan_and_protect_positions()
            
            return {
                "success": True, 
                "message": "Tüm pozisyonlar tarandı ve gerekli TP/SL eklendi",
                "monitor_status": position_manager.get_status()
            }
        except Exception as e:
            return {"success": False, "message": f"Tarama hatası: {e}"}
    
    async def scan_specific_symbol(self, symbol: str):
        """Belirli bir coin için manuel TP/SL kontrolü"""
        try:
            print(f"🎯 {symbol} için manuel TP/SL kontrolü...")
            success = await position_manager.manual_scan_symbol(symbol)
            
            return {
                "success": success,
                "symbol": symbol,
                "message": f"{symbol} için TP/SL kontrolü tamamlandı"
            }
        except Exception as e:
            return {"success": False, "message": f"{symbol} kontrolü hatası: {e}"}

bot_core = BotCore()
