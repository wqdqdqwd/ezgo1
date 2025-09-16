# app/position_manager.py

import asyncio
import math
from typing import Dict, List, Optional
from datetime import datetime, timezone

from .binance_client import binance_client
from .firebase_manager import firebase_manager
from .config import settings
from .trading_strategy import trading_strategy
from binance.exceptions import BinanceAPIException, BinanceRequestException
import logging

logger = logging.getLogger(__name__)

class PositionManager:
    """
    Botun pozisyonlarını yönetir, TP/SL (Take Profit/Stop Loss) seviyelerini belirler
    ve pozisyonları aktif olarak izler.
    """
    def __init__(self):
        self.is_running = False
        self._monitor_task = None
        self.active_positions = {}  # Symbol'e göre aktif pozisyonları saklar
        self._last_scan_time = {}  # Her sembol için son tarama zamanı

    def get_status(self) -> dict:
        """Pozisyon yöneticisinin durumunu döndürür."""
        return {
            "is_running": self.is_running,
            "monitored_symbols": list(self.active_positions.keys()),
            "last_scan": {s: t.isoformat() for s, t in self._last_scan_time.items()},
            "details": self.active_positions
        }

    async def get_account_info(self):
        """Hesap bilgilerini Binance'tan çeker ve günceller."""
        try:
            account_info = await binance_client.get_account_balance()
            return account_info
        except Exception as e:
            logger.error(f"Hesap bilgileri alınırken hata oluştu: {e}")
            return {}

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Optional[dict]:
        """Piyasa emri verir ve pozisyonu günceller."""
        try:
            order = await binance_client.create_market_order(symbol, side, quantity)
            logger.info(f"✅ PİYASA EMRİ GÖNDERİLDİ: {order}")
            await self._update_positions()  # Pozisyonları hemen güncelle
            return order
        except Exception as e:
            logger.error(f"❌ PİYASA EMİR HATASI: {e}")
            return None

    async def _update_positions(self):
        """Pozisyonları Binance API'sinden günceller."""
        self.active_positions = await binance_client.get_current_positions()
        
    async def _add_stop_loss_and_take_profit(self, position: dict):
        """Bir pozisyona TP/SL ekler."""
        symbol = position['symbol']
        entry_price = float(position['entryPrice'])
        position_side = "BUY" if float(position['positionAmt']) > 0 else "SELL"
        is_long = position_side == "BUY"

        # TP ve SL fiyatlarını hesapla
        tp_price = entry_price * (1 + settings.TAKE_PROFIT_PERCENT) if is_long else entry_price * (1 - settings.TAKE_PROFIT_PERCENT)
        sl_price = entry_price * (1 - settings.STOP_LOSS_PERCENT) if is_long else entry_price * (1 + settings.STOP_LOSS_PERCENT)

        quantity = abs(float(position['positionAmt']))

        # Emirleri göndermeden önce mevcut TP/SL emirlerini iptal et
        await binance_client.cancel_all_open_orders(symbol)
        
        try:
            # TP (Take Profit) emri
            tp_side = "SELL" if is_long else "BUY"
            await binance_client.create_stop_and_limit_order(
                symbol, tp_side, quantity, stop_price=tp_price, limit_price=tp_price
            )
            logger.info(f"✅ {symbol} için TP emri eklendi: {tp_price}")

            # SL (Stop Loss) emri
            sl_side = "SELL" if is_long else "BUY"
            await binance_client.create_stop_and_limit_order(
                symbol, sl_side, quantity, stop_price=sl_price, limit_price=sl_price
            )
            logger.info(f"✅ {symbol} için SL emri eklendi: {sl_price}")
        
        except Exception as e:
            logger.error(f"❌ TP/SL eklenirken hata: {e}")

    async def _scan_and_protect_positions(self, specific_symbol: Optional[str] = None):
        """
        Açık pozisyonları tarar ve TP/SL emri ekler.
        _monitor_loop ve manuel tarama için kullanılır.
        """
        print("🔍 Pozisyonlar taranıyor...")
        await self._update_positions()
        
        if not self.active_positions:
            print("✔ Açık pozisyon yok.")
            return

        symbols_to_scan = [specific_symbol] if specific_symbol else list(self.active_positions.keys())
        
        for symbol in symbols_to_scan:
            if symbol in self.active_positions:
                position = self.active_positions[symbol]
                
                # Sadece pozisyon açıldığında TP/SL ekle
                if not await binance_client.has_open_orders(symbol):
                    print(f"🎯 {symbol} için pozisyon bulundu. TP/SL ekleniyor...")
                    await self._add_stop_loss_and_take_profit(position)
                    
                self._last_scan_time[symbol] = datetime.now(timezone.utc)
        print("✔ Tarama tamamlandı.")
        
    async def manual_scan_symbol(self, symbol: str) -> bool:
        """
        Belirli bir coin için manuel TP/SL kontrolü. bot_core.py'den çağrılır.
        """
        try:
            await self._scan_and_protect_positions(specific_symbol=symbol)
            return True
        except Exception as e:
            logger.error(f"Manuel tarama hatası: {e}")
            return False

    async def _monitor_loop(self):
        """Arka plan TP/SL izleme döngüsü."""
        while self.is_running:
            try:
                await self._scan_and_protect_positions()
                await asyncio.sleep(settings.CACHE_DURATION_POSITION)  # Ayarlar dosyasındaki süreyi kullan
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor döngüsünde hata: {e}")
                await asyncio.sleep(5)  # Hata durumunda kısa bir süre bekle

    async def start_monitoring(self):
        """Arka plan monitor döngüsünü başlatır."""
        if not self.is_running:
            self.is_running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("Pozisyon monitor döngüsü başlatıldı.")
            
    async def stop_monitoring(self):
        """Arka plan monitor döngüsünü durdurur."""
        if self.is_running and self._monitor_task:
            self.is_running = False
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                logger.info("Pozisyon monitor döngüsü başarıyla durduruldu.")
            finally:
                self._monitor_task = None
        else:
            logger.info("Pozisyon monitor zaten durdurulmuş.")

# Botun geri kalanı tarafından kullanılacak global nesne
position_manager = PositionManager()
