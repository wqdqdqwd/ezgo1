import asyncio
from binance import AsyncClient
from binance.exceptions import BinanceAPIException
from .config import settings
import time
from typing import Optional, Dict, Any

class BinanceClient:
    def __init__(self):
        self.api_key = settings.API_KEY
        self.api_secret = settings.API_SECRET
        self.is_testnet = settings.ENVIRONMENT == "TEST"
        self.client: AsyncClient | None = None
        self.exchange_info = None
        self._last_balance_check = 0
        self._cached_balance = 0.0
        self._last_position_check = {}
        self._cached_positions = {}
        self._rate_limit_delay_time = 0.1  # Minimum delay between requests (RENAMED)
        print(f"Binance İstemcisi başlatılıyor. Ortam: {settings.ENVIRONMENT}")
        
    async def _rate_limit_delay(self):
        """Rate limit koruması için bekleme"""
        await asyncio.sleep(self._rate_limit_delay_time)  # Use the renamed variable
        
    async def initialize(self):
        if self.client is None:
            self.client = await AsyncClient.create(self.api_key, self.api_secret, testnet=self.is_testnet)
            await self._rate_limit_delay()
            self.exchange_info = await self.client.get_exchange_info()
            print("Binance AsyncClient başarıyla başlatıldı.")
        return self.client
        
    async def get_symbol_info(self, symbol: str):
        if not self.exchange_info:
            return None
        for s in self.exchange_info['symbols']:
            if s['symbol'] == symbol:
                return s
        return None
        
    async def get_open_positions(self, symbol: str, use_cache: bool = True):
        """Açık pozisyonları getirir - cache desteği ile"""
        try:
            current_time = time.time()
            cache_key = symbol
            
            # Cache kontrolü (5 saniye cache)
            if use_cache and cache_key in self._last_position_check:
                if current_time - self._last_position_check[cache_key] < 5:
                    return self._cached_positions.get(cache_key, [])
            
            await self._rate_limit_delay()
            positions = await self.client.futures_position_information(symbol=symbol)
            open_positions = [p for p in positions if float(p['positionAmt']) != 0]
            
            # Cache güncelle
            self._last_position_check[cache_key] = current_time
            self._cached_positions[cache_key] = open_positions
            
            return open_positions
            
        except BinanceAPIException as e:
            if "-1003" in str(e):  # Rate limit hatası
                print(f"Rate limit - pozisyon kontrolü atlanıyor")
                # Cache'den döndür
                return self._cached_positions.get(symbol, [])
            print(f"Hata: Pozisyon bilgileri alınamadı: {e}")
            return []

    async def cancel_all_orders_safe(self, symbol: str):
        """Tüm açık emirleri güvenli şekilde iptal eder"""
        try:
            await self._rate_limit_delay()
            open_orders = await self.client.futures_get_open_orders(symbol=symbol)
            if open_orders:
                print(f"🧹 {len(open_orders)} adet yetim emir temizleniyor...")
                await self._rate_limit_delay()
                await self.client.futures_cancel_all_open_orders(symbol=symbol)
                await asyncio.sleep(0.5)
                print("✅ Tüm yetim emirler temizlendi.")
                return True
            else:
                print("✅ Temizlenecek yetim emir yok.")
                return True
        except BinanceAPIException as e:
            if "-1003" in str(e):
                print("⚠️ Rate limit - emir iptali atlanıyor")
                return False
            print(f"❌ Emirler iptal edilirken hata: {e}")
            return False

    async def create_market_order_with_sl_tp(self, symbol: str, side: str, quantity: float, entry_price: float, price_precision: int):
        """
        Piyasa emri ile birlikte hem Stop Loss hem de Take Profit emri oluşturur
        YETİM EMİR KORUMASLI VERSİYON - TP/SL TAMAMEN DÜZELTİLMİŞ
        """
        def format_price(price):
            return f"{price:.{price_precision}f}"
            
        try:
            # 🧹 ADIM 1: Önce tüm açık emirleri temizle (YETİM EMİR KORUMASII)
            print(f"🧹 {symbol} için yetim emir kontrolü yapılıyor...")
            cleanup_success = await self.cancel_all_orders_safe(symbol)
            if not cleanup_success:
                print("⚠️ Yetim emir temizliği başarısız - devam ediliyor...")
            
            # Kısa bekleme - emirlerin tamamen iptal olması için
            await asyncio.sleep(0.3)
            
            # 📈 ADIM 2: Ana piyasa emrini oluştur
            print(f"📈 {symbol} {side} {quantity} ana piyasa emri oluşturuluyor...")
            await self._rate_limit_delay()
            main_order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            print(f"✅ Ana pozisyon başarılı: {symbol} {side} {quantity}")
            
            # Pozisyon açıldıktan sonra bekleme - SL/TP için hazır olması için
            await asyncio.sleep(1.0)
            
            # 🛡️ ADIM 3: Stop Loss ve Take Profit fiyatlarını hesapla
            if side == 'BUY':  # Long pozisyon
                sl_price = entry_price * (1 - settings.STOP_LOSS_PERCENT)
                tp_price = entry_price * (1 + settings.TAKE_PROFIT_PERCENT)
                opposite_side = 'SELL'
            else:  # Short pozisyon
                sl_price = entry_price * (1 + settings.STOP_LOSS_PERCENT)
                tp_price = entry_price * (1 - settings.TAKE_PROFIT_PERCENT)
                opposite_side = 'BUY'
            
            formatted_sl_price = format_price(sl_price)
            formatted_tp_price = format_price(tp_price)
            
            print(f"💡 Hesaplanan fiyatlar:")
            print(f"   Giriş: {entry_price}")
            print(f"   SL: {formatted_sl_price}")
            print(f"   TP: {formatted_tp_price}")
            
            # 🛑 ADIM 4: Stop Loss emrini oluştur - DÜZELTİLMİŞ FORMAT
            sl_success = False
            tp_success = False
            
            try:
                print(f"🛑 Stop Loss emri oluşturuluyor: {formatted_sl_price}")
                await self._rate_limit_delay()
                sl_order = await self.client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type='STOP_MARKET',
                    quantity=quantity,               # ✅ quantity eklendi
                    stopPrice=formatted_sl_price,
                    timeInForce='GTE_GTC',          # ✅ timeInForce eklendi
                    reduceOnly=True                 # ✅ reduceOnly eklendi
                )
                print(f"✅ STOP LOSS başarılı: {formatted_sl_price}")
                sl_success = True
            except BinanceAPIException as e:
                print(f"❌ Stop Loss emri hatası: {e}")
                print(f"🔍 SL Hata detayı: Code={getattr(e, 'code', 'N/A')}, Message={getattr(e, 'message', str(e))}")
            
            # 🎯 ADIM 5: Take Profit emrini oluştur - DÜZELTİLMİŞ FORMAT
            try:
                print(f"🎯 Take Profit emri oluşturuluyor: {formatted_tp_price}")
                await self._rate_limit_delay()
                tp_order = await self.client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type='TAKE_PROFIT_MARKET',
                    quantity=quantity,               # ✅ quantity eklendi
                    stopPrice=formatted_tp_price,
                    timeInForce='GTE_GTC',          # ✅ timeInForce eklendi
                    reduceOnly=True                 # ✅ reduceOnly eklendi
                )
                print(f"✅ TAKE PROFIT başarılı: {formatted_tp_price}")
                tp_success = True
            except BinanceAPIException as e:
                print(f"❌ Take Profit emri hatası: {e}")
                print(f"🔍 TP Hata detayı: Code={getattr(e, 'code', 'N/A')}, Message={getattr(e, 'message', str(e))}")
            
            # 📊 ADIM 6: Alternatif yaklaşım - Eğer yukarıdaki başarısız olursa
            if not sl_success or not tp_success:
                print("🔄 Alternatif yaklaşım deneniyor...")
                
                # Alternatif SL yaklaşımı
                if not sl_success:
                    try:
                        print("🔄 Alternatif SL yaklaşımı...")
                        await self._rate_limit_delay()
                        alt_sl_order = await self.client.futures_create_order(
                            symbol=symbol,
                            side=opposite_side,
                            type='STOP',
                            quantity=quantity,
                            price=formatted_sl_price,    # limit price olarak
                            stopPrice=formatted_sl_price,
                            timeInForce='GTC',
                            reduceOnly=True
                        )
                        print(f"✅ Alternatif SL başarılı: {formatted_sl_price}")
                        sl_success = True
                    except BinanceAPIException as alt_sl_error:
                        print(f"❌ Alternatif SL de başarısız: {alt_sl_error}")
                
                # Alternatif TP yaklaşımı
                if not tp_success:
                    try:
                        print("🔄 Alternatif TP yaklaşımı...")
                        await self._rate_limit_delay()
                        alt_tp_order = await self.client.futures_create_order(
                            symbol=symbol,
                            side=opposite_side,
                            type='LIMIT',
                            quantity=quantity,
                            price=formatted_tp_price,
                            timeInForce='GTC',
                            reduceOnly=True
                        )
                        print(f"✅ Alternatif TP (Limit) başarılı: {formatted_tp_price}")
                        tp_success = True
                    except BinanceAPIException as alt_tp_error:
                        print(f"❌ Alternatif TP de başarısız: {alt_tp_error}")
            
            # 📊 ADIM 7: Sonuç raporu ve güvenlik kontrolü
            if not sl_success and not tp_success:
                print("⚠️ UYARI: Ne SL ne de TP kurulabildi! Manuel kontrol gerekebilir.")
                print("🚨 Korumasız pozisyon tespit edildi!")
            elif not sl_success:
                print("⚠️ UYARI: Sadece TP kuruldu, SL kurulamadı!")
            elif not tp_success:
                print("⚠️ UYARI: Sadece SL kuruldu, TP kurulamadı!")
            else:
                print("✅ Pozisyon tam korumalı: Hem SL hem TP kuruldu.")
            
            return main_order
            
        except BinanceAPIException as e:
            print(f"❌ KRITIK HATA: Ana pozisyon emri oluşturulamadı: {e}")
            # Ana emir başarısız olursa mutlaka temizlik yap
            print("🧹 Hata sonrası acil temizlik yapılıyor...")
            await self.cancel_all_orders_safe(symbol)
            return None
        except Exception as e:
            print(f"❌ BEKLENMEYEN HATA: {e}")
            # Genel hata durumunda da temizlik yap
            print("🧹 Beklenmeyen hata sonrası temizlik yapılıyor...")
            await self.cancel_all_orders_safe(symbol)
            return None

    async def close_position(self, symbol: str, position_amt: float, side_to_close: str):
        """
        Pozisyon kapatır - YETİM EMİR TEMİZLİĞİ İLE
        """
        try:
            # 🧹 ADIM 1: Pozisyon kapatmadan önce açık emirleri temizle
            print(f"🧹 {symbol} pozisyon kapatma öncesi yetim emir temizliği...")
            await self.cancel_all_orders_safe(symbol)
            await asyncio.sleep(0.2)
            
            # 📉 ADIM 2: Pozisyonu kapat
            print(f"📉 {symbol} pozisyonu kapatılıyor: {abs(position_amt)} miktar")
            await self._rate_limit_delay()
            response = await self.client.futures_create_order(
                symbol=symbol,
                side=side_to_close,
                type='MARKET',
                quantity=abs(position_amt),
                reduceOnly=True
            )
            print(f"✅ POZİSYON KAPATILDI: {symbol}")
            
            # 🧹 ADIM 3: Kapanış sonrası ekstra temizlik (ihtiyaten)
            await asyncio.sleep(0.5)
            await self.cancel_all_orders_safe(symbol)
            
            # 💾 ADIM 4: Cache temizle
            if symbol in self._cached_positions:
                del self._cached_positions[symbol]
            if symbol in self._last_position_check:
                del self._last_position_check[symbol]
            
            return response
            
        except BinanceAPIException as e:
            print(f"❌ Pozisyon kapatma hatası: {e}")
            # Hata durumunda yine de temizlik yap
            print("🧹 Hata sonrası acil yetim emir temizliği...")
            await self.cancel_all_orders_safe(symbol)
            return None

    async def get_last_trade_pnl(self, symbol: str) -> float:
        try:
            await self._rate_limit_delay()
            trades = await self.client.futures_account_trades(symbol=symbol, limit=5)
            if trades:
                last_order_id = trades[-1]['orderId']
                pnl = 0.0
                for trade in reversed(trades):
                    if trade['orderId'] == last_order_id:
                        pnl += float(trade['realizedPnl'])
                    else:
                        break
                return pnl
            return 0.0
        except BinanceAPIException as e:
            if "-1003" in str(e):
                print("Rate limit - PNL sorgusu atlanıyor")
                return 0.0
            print(f"Hata: Son işlem PNL'i alınamadı: {e}")
            return 0.0

    async def close(self):
        if self.client:
            await self.client.close_connection()
            self.client = None
            print("Binance AsyncClient bağlantısı kapatıldı.")

    async def get_historical_klines(self, symbol: str, interval: str, limit: int = 100):
        try:
            print(f"{symbol} için {limit} adet geçmiş mum verisi çekiliyor...")
            await self._rate_limit_delay()
            return await self.client.get_historical_klines(symbol, interval, limit=limit)
        except BinanceAPIException as e:
            print(f"Hata: Geçmiş mum verileri çekilemedi: {e}")
            return []

    async def set_leverage(self, symbol: str, leverage: int):
        """Kaldıraç ayarlama - açık pozisyon kontrolü ile"""
        try:
            # Önce açık pozisyon kontrolü yap
            open_positions = await self.get_open_positions(symbol, use_cache=False)
            if open_positions:
                print(f"Uyarı: {symbol} için açık pozisyon mevcut. Kaldıraç değiştirilemez.")
                return False
            
            # Margin tipini cross olarak ayarla
            try:
                await self._rate_limit_delay()
                await self.client.futures_change_margin_type(symbol=symbol, marginType='CROSSED')
                print(f"{symbol} margin tipi CROSSED olarak ayarlandı.")
            except BinanceAPIException as margin_error:
                if "No need to change margin type" in str(margin_error) or "-4046" in str(margin_error):
                    print(f"{symbol} zaten CROSSED margin modunda.")
                else:
                    print(f"Margin tipi değiştirilemedi: {margin_error}")
            
            # Kaldıracı ayarla
            await self._rate_limit_delay()
            await self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"Başarılı: {symbol} kaldıracı {leverage}x olarak ayarlandı.")
            return True
            
        except BinanceAPIException as e:
            if "-1003" in str(e):
                print("Rate limit - kaldıraç ayarı atlanıyor")
                return False
            print(f"Hata: Kaldıraç ayarlanamadı: {e}")
            return False

    async def get_market_price(self, symbol: str):
        try:
            await self._rate_limit_delay()
            ticker = await self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            if "-1003" in str(e):
                print("Rate limit - fiyat sorgusu atlanıyor")
                return None
            print(f"Hata: {symbol} fiyatı alınamadı: {e}")
            return None

    async def get_account_balance(self, use_cache: bool = True):
        """Hesap bakiyesini getirir - cache desteği ile"""
        try:
            current_time = time.time()
            
            # Cache kontrolü (10 saniye cache)
            if use_cache and current_time - self._last_balance_check < 10:
                return self._cached_balance
            
            await self._rate_limit_delay()
            account = await self.client.futures_account()
            total_balance = 0.0
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    total_balance = float(asset['walletBalance'])
                    break
            
            # Cache güncelle
            self._last_balance_check = current_time
            self._cached_balance = total_balance
            
            return total_balance
            
        except BinanceAPIException as e:
            if "-1003" in str(e):
                # Rate limit durumunda cache'den döndür
                return self._cached_balance
            print(f"Hata: Hesap bakiyesi alınamadı: {e}")
            return self._cached_balance

    async def get_position_pnl(self, symbol: str, use_cache: bool = True):
        """Açık pozisyonun anlık PnL'ini getirir - cache desteği ile"""
        try:
            current_time = time.time()
            cache_key = f"{symbol}_pnl"
            
            # Cache kontrolü (3 saniye cache)
            if use_cache and cache_key in self._last_position_check:
                if current_time - self._last_position_check[cache_key] < 3:
                    return self._cached_positions.get(cache_key, 0.0)
            
            await self._rate_limit_delay()
            positions = await self.client.futures_position_information(symbol=symbol)
            pnl = 0.0
            for position in positions:
                if float(position['positionAmt']) != 0:
                    pnl = float(position['unRealizedProfit'])
                    break
            
            # Cache güncelle
            self._last_position_check[cache_key] = current_time
            self._cached_positions[cache_key] = pnl
            
            return pnl
            
        except BinanceAPIException as e:
            if "-1003" in str(e):
                # Rate limit durumunda cache'den döndür
                return self._cached_positions.get(f"{symbol}_pnl", 0.0)
            print(f"Hata: Pozisyon PnL'i alınamadı: {e}")
            return 0.0

    async def force_cleanup_orders(self, symbol: str):
        """
        ACIL DURUM: Tüm açık emirleri zorla temizler
        """
        try:
            print(f"🚨 {symbol} için ZORLA YETİM EMİR TEMİZLİĞİ başlatılıyor...")
            max_attempts = 3
            
            for attempt in range(max_attempts):
                print(f"🧹 Temizlik denemesi {attempt + 1}/{max_attempts}")
                
                # Açık emirleri kontrol et
                await self._rate_limit_delay()
                open_orders = await self.client.futures_get_open_orders(symbol=symbol)
                
                if not open_orders:
                    print(f"✅ {symbol} için yetim emir kalmadı.")
                    return True
                
                print(f"🎯 {len(open_orders)} adet yetim emir tespit edildi.")
                
                # Tek tek iptal etmeyi dene
                for order in open_orders:
                    try:
                        await self._rate_limit_delay()
                        await self.client.futures_cancel_order(
                            symbol=symbol, 
                            orderId=order['orderId']
                        )
                        print(f"✅ Emir iptal edildi: {order['orderId']}")
                    except Exception as order_error:
                        print(f"⚠️ Emir iptal hatası: {order_error}")
                
                # Toplu iptal dene
                try:
                    await self._rate_limit_delay()
                    await self.client.futures_cancel_all_open_orders(symbol=symbol)
                    print("🧹 Toplu iptal komutu gönderildi")
                except Exception as batch_error:
                    print(f"⚠️ Toplu iptal hatası: {batch_error}")
                
                await asyncio.sleep(1)  # Sonraki deneme için bekle
            
            print(f"⚠️ {max_attempts} deneme sonrası bazı yetim emirler kalabilir.")
            return False
            
        except Exception as e:
            print(f"❌ Zorla temizlik hatası: {e}")
            return False

binance_client = BinanceClient()
