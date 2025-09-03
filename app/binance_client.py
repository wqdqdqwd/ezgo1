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

    # get_symbol_info, get_open_positions, get_last_trade_pnl, close,
    # get_historical_klines, set_leverage, get_market_price metodları aynı kalır...
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
    async def create_order_with_tp_sl(self, symbol: str, side: str, quantity: float, entry_price: float, price_precision: int, quantity_precision: int, stop_loss_percent: float, take_profit_percent: float):
        
        def format_value(value, precision):
            return f"{value:.{precision}f}"
        
        try:
            # Gerekli hassasiyetlere göre miktarları ve fiyatları yuvarla
            formatted_quantity = format_value(quantity, quantity_precision)
            
            # 1. Ana piyasa emrini oluştur
            main_order = await self.client.futures_create_order(
                symbol=symbol, 
                side=side, 
                type='MARKET', 
                quantity=formatted_quantity
            )
            print(f"Başarılı: {symbol} {side} {formatted_quantity} PİYASA EMRİ oluşturuldu.")
            await asyncio.sleep(0.5)

            # 2. TP ve SL fiyatlarını hesapla
            sl_price = entry_price * (1 - stop_loss_percent / 100) if side == 'BUY' else entry_price * (1 + stop_loss_percent / 100)
            tp_price = entry_price * (1 + take_profit_percent / 100) if side == 'BUY' else entry_price * (1 - take_profit_percent / 100)
            
            formatted_sl_price = format_value(sl_price, price_precision)
            formatted_tp_price = format_value(tp_price, price_precision)

            # 3. TP ve SL emirlerini oluştur
            opposite_side = 'SELL' if side == 'BUY' else 'BUY'
            await self.client.futures_create_order(
                symbol=symbol, side=opposite_side, type='STOP_MARKET', 
                stopPrice=formatted_sl_price, closePosition=True
            )
            await self.client.futures_create_order(
                symbol=opposite_side, side=opposite_side, type='TAKE_PROFIT_MARKET', 
                stopPrice=formatted_tp_price, closePosition=True
            )
            print(f"Başarılı: {symbol} için SL({formatted_sl_price}) ve TP({formatted_tp_price}) emirleri kuruldu.")
            return main_order
        except BinanceAPIException as e:
            print(f"Hata: TP/SL ile emir oluşturulurken sorun oluştu: {e}")
            await self.close_open_position_and_orders(symbol)
            return None

    # (YENİ) Açık pozisyonu ve ilişkili emirleri kapatan yardımcı fonksiyon
    async def close_open_position_and_orders(self, symbol: str):
        try:
            # Önce açıkta kalan SL/TP gibi emirleri iptal et
            await self.client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"{symbol} için açık emirler iptal edildi.")
            await asyncio.sleep(0.1)
            
            # Sonra pozisyonu kapat
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
