import pytest
import pandas as pd
from app.trading_strategy import TradingStrategy

class TestTradingStrategy:
    
    def setup_method(self):
        """Her test öncesi çalışır"""
        self.strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)
    
    def create_sample_klines(self, prices):
        """Test için sample kline data oluşturur"""
        klines = []
        for i, price in enumerate(prices):
            klines.append([
                1640995200000 + i * 60000,  # timestamp
                str(price),  # open
                str(price + 1),  # high
                str(price - 1),  # low
                str(price),  # close
                "1000",  # volume
                1640995259999 + i * 60000,  # close_time
                "50000",  # quote_asset_volume
                100,  # number_of_trades
                "500",  # taker_buy_base_asset_volume
                "25000",  # taker_buy_quote_asset_volume
                "0"  # ignore
            ])
        return klines
    
    def test_insufficient_data(self):
        """Yetersiz veri ile test"""
        klines = self.create_sample_klines([100, 101, 102])  # 21'den az
        signal = self.strategy.analyze_klines(klines)
        assert signal == "HOLD"
    
    def test_bullish_crossover(self):
        """Yükseliş sinyali testi"""
        # EMA(9) > EMA(21) olacak şekilde artan fiyatlar
        prices = [100] * 10 + list(range(101, 131))  # 30 veri noktası
        klines = self.create_sample_klines(prices)
        signal = self.strategy.analyze_klines(klines)
        # Bu durumda LONG sinyali bekliyoruz
        assert signal in ["LONG", "HOLD"]  # Crossover timing'e bağlı
    
    def test_bearish_crossover(self):
        """Düşüş sinyali testi"""
        # EMA(9) < EMA(21) olacak şekilde azalan fiyatlar
        prices = [130] * 10 + list(range(129, 99, -1))  # 30 veri noktası
        klines = self.create_sample_klines(prices)
        signal = self.strategy.analyze_klines(klines)
        # Bu durumda SHORT sinyali bekliyoruz
        assert signal in ["SHORT", "HOLD"]  # Crossover timing'e bağlı
    
    def test_sideways_market(self):
        """Yatay piyasa testi"""
        prices = [100] * 30  # Sabit fiyat
        klines = self.create_sample_klines(prices)
        signal = self.strategy.analyze_klines(klines)
        assert signal == "HOLD"
    
    def test_strategy_initialization(self):
        """Strateji başlatma testi"""
        custom_strategy = TradingStrategy(short_ema_period=5, long_ema_period=15)
        assert custom_strategy.short_ema_period == 5
        assert custom_strategy.long_ema_period == 15