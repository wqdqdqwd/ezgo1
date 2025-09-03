# binance_client.py

import asyncio
import math
from binance import AsyncClient
from binance.exceptions import BinanceAPIException

class BinanceClient:
    def __init__(self, api_key: str, api_secret: str):
        if not api_key or not api_secret:
            raise ValueError("API anahtarı ve sırrı boş olamaz.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.client: AsyncClient | None = None
        self.exchange_info = None

    async def initialize(self) -> bool:
        if self.client is None:
            try:
                self.client = await AsyncClient.create(self.api_key, self.api_secret)
                self.exchange_info = await self.client.get_exchange_info()
                print(f"Kullanıcı için Binance AsyncClient başarıyla başlatıldı.")
                return True
            except BinanceAPIException as e:
                print(f"Binance istemcisi başlatılamadı. API Anahtarlarını kontrol edin. Hata: {e}")
                return False
        return True

    # Yeni yardımcı fonksiyon: Sembolün hassasiyetini alır
    async def get_precision(self, symbol: str):
        if not self.exchange_info:
            return None, None
        
        symbol_info = next((s for s in self.exchange_info['symbols'] if s['symbol'] == symbol), None)
        if not symbol_info:
            return None, None
        
        price_precision = 0
        quantity_precision = 0
        for f in symbol_info['filters']:
            if f['filterType'] == 'PRICE_FILTER':
                price_precision = int(round(-math.log10(float(f['tickSize']))))
            elif f['filterType'] == 'LOT_SIZE':
                quantity_precision = int(round(-math.log10(float(f['stepSize']))))
        return price_precision, quantity_precision

    # Geri kalan tüm metotlar aynı kalır...
    async def get_symbol_info(self, symbol: str):
        if not self.exchange_info: return None
        for s in self.exchange_info['symbols']:
            if s['symbol'] == symbol: return s
        return None
    async def get_open_positions(self, symbol: str):
        try:
            positions = await self.client.futures_position_information(symbol=symbol)
            return [p for p in positions if float(p['positionAmt']) != 0]
        except BinanceAPIException as e: print(f"Hata: Pozisyon bilgileri alınamadı: {e}"); return []
    async def get_last_trade_pnl(self, symbol: str):
        try:
            trades = await self.client.futures_account_trades(symbol=symbol, limit=10)
            if not trades: return 0.0
            last_order_id = trades[-1]['orderId']
            pnl = 0.0
            for trade in reversed(trades):
                if trade['orderId'] == last_order_id:
                    pnl += float(trade['realizedPnl'])
                else: break
            return pnl
        except BinanceAPIException as e: print(f"Hata: Son işlem PNL'i alınamadı: {e}"); return 0.0
    async def close(self):
        if self.client: await self.client.close_connection(); self.client = None
    async def get_historical_klines(self, symbol: str, interval: str, limit: int = 100):
        try:
            return await self.client.get_historical_klines(symbol, interval, limit=limit)
        except BinanceAPIException as e: print(f"Hata: Geçmiş mum verileri çekilemedi: {e}"); return []
    async def set_leverage(self, symbol: str, leverage: int):
        try:
            await self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"Başarılı: {symbol} kaldıracı {leverage}x olarak ayarlandı.")
            return True
        except BinanceAPIException as e: print(f"Hata: Kaldıraç ayarlanamadı: {e}"); return False
    async def get_market_price(self, symbol: str):
        try:
            ticker = await self.client.futures_symbol_ticker(symbol=symbol); return float(ticker['price'])
        except BinanceAPIException as e: print(f"Hata: {symbol} fiyatı alınamadı: {e}"); return None

    # (GÜNCELLENDİ) TP ve SL ile birlikte emir oluşturma
    async def create_order_with_tp_sl(self, symbol: str, side: str, order_size_usdt: float, leverage: int, tp_pnl_percent: float, sl_pnl_percent: float):
        try:
            # 1. Sembolün hassasiyetini al
            price_precision, quantity_precision = await self.get_precision(symbol)
            if price_precision is None or quantity_precision is None:
                print(f"Hata: {symbol} için hassasiyet bilgileri alınamadı.")
                return None
            
            # 2. Güncel piyasa fiyatını al
            entry_price = await self.get_market_price(symbol)
            if entry_price is None: return None

            # 3. USDT miktarını, kripto miktarına dönüştür ve yuvarla
            quantity_usdt = order_size_usdt
            quantity = quantity_usdt / entry_price
            rounded_quantity = round(quantity, quantity_precision)
            
            # 4. PnL yüzdelerini kaldıraç oranına bölerek gerçek fiyat değişim yüzdelerini bul
            sl_price_change_percent = sl_pnl_percent / leverage
            tp_price_change_percent = tp_pnl_percent / leverage
            
            # 5. TP ve SL fiyatlarını hesapla ve hassasiyete göre yuvarla
            sl_price = entry_price * (1 - sl_price_change_percent / 100) if side == 'BUY' else entry_price * (1 + sl_price_change_percent / 100)
            tp_price = entry_price * (1 + tp_price_change_percent / 100) if side == 'BUY' else entry_price * (1 - tp_price_change_percent / 100)
            
            formatted_sl_price = f"{sl_price:.{price_precision}f}"
            formatted_tp_price = f"{tp_price:.{price_precision}f}"

            # 6. Ana piyasa emrini oluştur
            main_order = await self.client.futures_create_order(
                symbol=symbol, side=side, type='MARKET', quantity=rounded_quantity
            )
            print(f"Başarılı: {symbol} {side} {rounded_quantity} PİYASA EMRİ oluşturuldu.")
            await asyncio.sleep(0.5)

            # 7. TP ve SL emirlerini oluştur
            opposite_side = 'SELL' if side == 'BUY' else 'BUY'
            
            # STOP_MARKET (SL) emri
            await self.client.futures_create_order(
                symbol=symbol, side=opposite_side, type='STOP_MARKET', 
                stopPrice=formatted_sl_price, closePosition=True
            )
            # TAKE_PROFIT_MARKET (TP) emri
            await self.client.futures_create_order(
                symbol=symbol, side=opposite_side, type='TAKE_PROFIT_MARKET', 
                stopPrice=formatted_tp_price, closePosition=True
            )
            print(f"Başarılı: {symbol} için SL({formatted_sl_price}) ve TP({formatted_tp_price}) emirleri kuruldu.")
            return main_order
        except BinanceAPIException as e:
            print(f"Hata: TP/SL ile emir oluşturulurken sorun oluştu: {e}")
            await self.close_open_position_and_orders(symbol)
            return None

    # Açık pozisyonu ve ilişkili emirleri kapatan yardımcı fonksiyon
    async def close_open_position_and_orders(self, symbol: str):
        try:
            await self.client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"{symbol} için açık emirler iptal edildi.")
            await asyncio.sleep(0.1)
            
            positions = await self.get_open_positions(symbol)
            if positions:
                position = positions[0]
                position_amt = float(position['positionAmt'])
                side_to_close = 'SELL' if position_amt > 0 else 'BUY'
                await self.client.futures_create_order(
                    symbol=symbol, side=side_to_close, type='MARKET', 
                    quantity=abs(position_amt), reduceOnly=True
                )
                print(f"--> POZİSYON KAPATILDI: {symbol}")
            return True
        except BinanceAPIException as e:
            print(f"Hata: Pozisyon ve emirler kapatılırken sorun oluştu: {e}")
            return False

# Strateji sınıfı aynı kalacak, onda bir değişiklik yapmanıza gerek yok.
# trading_strategy.py
