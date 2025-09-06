import asyncio
import math
from binance import AsyncClient
from binance.exceptions import BinanceAPIException

class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        if not api_key or not api_secret:
            raise ValueError("API anahtarı ve sırrı boş olamaz.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client: AsyncClient | None = None
        self.exchange_info = None

    async def initialize(self) -> bool:
        """Binance client'ı başlatır"""
        if self.client is None:
            try:
                self.client = await AsyncClient.create(
                    self.api_key, 
                    self.api_secret, 
                    testnet=self.testnet
                )
                self.exchange_info = await self.client.get_exchange_info()
                print(f"Binance AsyncClient başlatıldı (testnet: {self.testnet})")
                return True
            except BinanceAPIException as e:
                print(f"Binance client başlatılamadı: {e}")
                return False
            except Exception as e:
                print(f"Beklenmeyen hata: {e}")
                return False
        return True

    async def get_symbol_info(self, symbol: str):
        """Sembol bilgilerini getirir"""
        if not self.exchange_info:
            await self.initialize()
            
        if not self.exchange_info:
            return None
            
        for s in self.exchange_info['symbols']:
            if s['symbol'] == symbol and s['status'] == 'TRADING':
                return s
        return None

    async def get_available_symbols(self, quote_asset: str = "USDT") -> list:
        """Mevcut futures sembollerini getirir"""
        try:
            if not self.exchange_info:
                await self.initialize()
                
            if not self.exchange_info:
                return []
                
            symbols = []
            for s in self.exchange_info['symbols']:
                if (s['status'] == 'TRADING' and 
                    s['contractType'] == 'PERPETUAL' and 
                    s['quoteAsset'] == quote_asset):
                    symbols.append({
                        'symbol': s['symbol'],
                        'baseAsset': s['baseAsset'],
                        'quoteAsset': s['quoteAsset']
                    })
            
            return sorted(symbols, key=lambda x: x['symbol'])
            
        except Exception as e:
            print(f"Sembol listesi alınamadı: {e}")
            return []

    async def get_open_positions(self, symbol: str):
        """Açık pozisyonları getirir"""
        try:
            positions = await self.client.futures_position_information(symbol=symbol)
            return [p for p in positions if float(p['positionAmt']) != 0]
        except BinanceAPIException as e:
            print(f"Pozisyon bilgileri alınamadı: {e}")
            return []

    async def get_account_balance(self) -> float:
        """USDT bakiyesini getirir"""
        try:
            account = await self.client.futures_account()
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
            return 0.0
        except BinanceAPIException as e:
            print(f"Hesap bakiyesi alınamadı: {e}")
            return 0.0

    async def get_market_price(self, symbol: str) -> float:
        """Güncel piyasa fiyatını getirir"""
        try:
            ticker = await self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            print(f"{symbol} fiyatı alınamadı: {e}")
            return 0.0

    async def get_historical_klines(self, symbol: str, interval: str, limit: int = 100):
        """Geçmiş mum verilerini getirir"""
        try:
            print(f"{symbol} için {limit} adet geçmiş mum verisi çekiliyor...")
            klines = await self.client.get_historical_klines(symbol, interval, limit=limit)
            return klines
        except BinanceAPIException as e:
            print(f"Geçmiş mum verileri çekilemedi: {e}")
            return []

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Kaldıracı ayarlar"""
        try:
            # Önce açık pozisyon kontrolü
            open_positions = await self.get_open_positions(symbol)
            if open_positions:
                print(f"{symbol} için açık pozisyon var, kaldıraç değiştirilemez")
                return True  # Hata vermeyip devam et
            
            # Margin tipini cross'a çevir (isolated'da problem olabilir)
            try:
                await self.client.futures_change_margin_type(symbol=symbol, marginType='CROSSED')
            except BinanceAPIException as e:
                if "No need to change margin type" in str(e):
                    pass  # Zaten cross modunda
                elif "-4046" in str(e):
                    pass  # Margin type zaten doğru
                else:
                    print(f"Margin tipi değiştirilemedi: {e}")
            
            # Kaldıracı ayarla
            await self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            print(f"✅ {symbol} kaldıracı {leverage}x olarak ayarlandı")
            return True
            
        except BinanceAPIException as e:
            if "-4028" in str(e):
                print(f"❌ Geçersiz kaldıraç değeri: {leverage}")
            elif "-4161" in str(e):
                print(f"⚠️ {symbol} için açık pozisyon varken kaldıraç değiştirilemez")
                return True  # Hata vermeyip devam et
            else:
                print(f"❌ Kaldıraç ayarlanamadı: {e}")
            return False

    async def create_order_with_tp_sl(self, symbol: str, side: str, quantity: float, 
                                    entry_price: float, price_precision: int, 
                                    stop_loss_percent: float, take_profit_percent: float):
        """Piyasa emri ile birlikte TP ve SL emirleri oluşturur"""
        
        def format_price(price):
            return f"{price:.{price_precision}f}"
        
        try:
            # 1. Ana piyasa emrini oluştur
            main_order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            print(f"✅ {symbol} {side} {quantity} piyasa emri oluşturuldu")
            
            # Kısa bekleme
            await asyncio.sleep(0.5)
            
            # 2. Stop Loss ve Take Profit fiyatlarını hesapla
            if side == 'BUY':  # Long pozisyon
                sl_price = entry_price * (1 - stop_loss_percent / 100)
                tp_price = entry_price * (1 + take_profit_percent / 100)
                opposite_side = 'SELL'
            else:  # Short pozisyon
                sl_price = entry_price * (1 + stop_loss_percent / 100)
                tp_price = entry_price * (1 - take_profit_percent / 100)
                opposite_side = 'BUY'
            
            formatted_sl_price = format_price(sl_price)
            formatted_tp_price = format_price(tp_price)
            
            # 3. Stop Loss emrini oluştur
            try:
                sl_order = await self.client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type='STOP_MARKET',
                    stopPrice=formatted_sl_price,
                    closePosition=True,
                    timeInForce='GTC'
                )
                print(f"✅ {symbol} Stop Loss emri kuruldu: {formatted_sl_price}")
            except BinanceAPIException as e:
                print(f"❌ Stop Loss emri oluşturulamadı: {e}")
            
            # 4. Take Profit emrini oluştur
            try:
                tp_order = await self.client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type='TAKE_PROFIT_MARKET',
                    stopPrice=formatted_tp_price,
                    closePosition=True,
                    timeInForce='GTC'
                )
                print(f"✅ {symbol} Take Profit emri kuruldu: {formatted_tp_price}")
            except BinanceAPIException as e:
                print(f"❌ Take Profit emri oluşturulamadı: {e}")
            
            return main_order
            
        except BinanceAPIException as e:
            print(f"❌ Emir oluşturulurken hata: {e}")
            # Hata durumunda temizlik yap
            try:
                await self.client.futures_cancel_all_open_orders(symbol=symbol)
            except:
                pass
            return None

    async def close_open_position_and_orders(self, symbol: str) -> bool:
        """Açık pozisyonu ve emirleri kapatır"""
        try:
            # 1. Açık emirleri iptal et
            await self.client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"✅ {symbol} açık emirler iptal edildi")
            await asyncio.sleep(0.1)
            
            # 2. Pozisyonu kapat
            positions = await self.get_open_positions(symbol)
            if positions:
                position = positions[0]
                position_amt = float(position['positionAmt'])
                side_to_close = 'SELL' if position_amt > 0 else 'BUY'
                
                await self.client.futures_create_order(
                    symbol=symbol,
                    side=side_to_close,
                    type='MARKET',
                    quantity=abs(position_amt),
                    reduceOnly=True
                )
                print(f"✅ {symbol} pozisyonu kapatıldı")
            
            return True
            
        except BinanceAPIException as e:
            print(f"❌ Pozisyon kapatılırken hata: {e}")
            return False

    async def get_last_trade_pnl(self, symbol: str) -> float:
        """Son işlemin PnL'ini getirir"""
        try:
            trades = await self.client.futures_account_trades(symbol=symbol, limit=10)
            if not trades:
                return 0.0
                
            last_order_id = trades[-1]['orderId']
            pnl = 0.0
            
            for trade in reversed(trades):
                if trade['orderId'] == last_order_id:
                    pnl += float(trade['realizedPnl'])
                else:
                    break
                    
            return pnl
            
        except BinanceAPIException as e:
            print(f"Son işlem PnL'i alınamadı: {e}")
            return 0.0

    async def get_position_pnl(self, symbol: str) -> float:
        """Açık pozisyonun anlık PnL'ini getirir"""
        try:
            positions = await self.client.futures_position_information(symbol=symbol)
            for position in positions:
                if float(position['positionAmt']) != 0:
                    return float(position['unRealizedProfit'])
            return 0.0
        except BinanceAPIException as e:
            print(f"Pozisyon PnL'i alınamadı: {e}")
            return 0.0

    async def get_24hr_ticker(self, symbol: str) -> dict:
        """24 saatlik ticker bilgilerini getirir"""
        try:
            ticker = await self.client.futures_24hr_ticker(symbol=symbol)
            return {
                'symbol': ticker['symbol'],
                'price': float(ticker['lastPrice']),
                'change': float(ticker['priceChange']),
                'changePercent': float(ticker['priceChangePercent']),
                'high': float(ticker['highPrice']),
                'low': float(ticker['lowPrice']),
                'volume': float(ticker['volume'])
            }
        except BinanceAPIException as e:
            print(f"{symbol} ticker bilgisi alınamadı: {e}")
            return {}

    async def close(self):
        """Client bağlantısını kapatır"""
        if self.client:
            await self.client.close_connection()
            self.client = None
            print("Binance client bağlantısı kapatıldı")
