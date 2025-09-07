try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    # Fallback implementation without pandas
    import json
    from typing import List, Dict

class TradingStrategy:
    """
    EMA (9, 21) kesişimine dayalı alım-satım sinyalleri üreten sınıf.
    """
    def __init__(self, short_ema_period: int = 9, long_ema_period: int = 21):
        """
        Stratejiyi EMA periyotları ile başlatır.
        """
        self.short_ema_period = short_ema_period
        self.long_ema_period = long_ema_period
        print(f"Reversal Stratejisi başlatıldı: EMA({self.short_ema_period}, {self.long_ema_period})")

    def analyze_klines(self, klines: list) -> str:
        """
        Verilen mum (kline) verilerini analiz ederek 'LONG', 'SHORT' veya 'HOLD' sinyali üretir.
        
        Args:
            klines (list): Binance'ten alınan mum verileri listesi.
        
        Returns:
            str: Üretilen sinyal ('LONG', 'SHORT', 'HOLD').
        """
        # Yeterli veri yoksa analiz yapma
        if len(klines) < self.long_ema_period:
            return "HOLD"

        if PANDAS_AVAILABLE:
            return self._analyze_with_pandas(klines)
        else:
            return self._analyze_without_pandas(klines)
    
    def _analyze_with_pandas(self, klines: list) -> str:
        """Pandas ile analiz"""
        # Gelen listeyi bir pandas DataFrame'e dönüştür
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Veri tiplerini doğru formata çevir
        df['close'] = pd.to_numeric(df['close'])
        
        # Kısa ve uzun periyotlu EMA'ları hesapla
        df['short_ema'] = df['close'].ewm(span=self.short_ema_period, adjust=False).mean()
        df['long_ema'] = df['close'].ewm(span=self.long_ema_period, adjust=False).mean()

        # Son iki mumu al (mevcut ve bir önceki)
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        signal = "HOLD"

        # Alım Sinyali: Kısa EMA, uzun EMA'yı aşağıdan yukarıya keserse
        if prev_row['short_ema'] < prev_row['long_ema'] and last_row['short_ema'] > last_row['long_ema']:
            signal = "LONG"
        # Satım Sinyali: Kısa EMA, uzun EMA'yı yukarıdan aşağıya keserse
        elif prev_row['short_ema'] > prev_row['long_ema'] and last_row['short_ema'] < last_row['long_ema']:
            signal = "SHORT"
        
        return signal
    
    def _analyze_without_pandas(self, klines: list) -> str:
        """Pandas olmadan basit analiz"""
        # Kapanış fiyatlarını al
        closes = [float(kline[4]) for kline in klines]
        
        # Basit EMA hesaplama
        short_emas = self._calculate_ema(closes, self.short_ema_period)
        long_emas = self._calculate_ema(closes, self.long_ema_period)
        
        if len(short_emas) < 2 or len(long_emas) < 2:
            return "HOLD"
        
        # Son iki değeri karşılaştır
        prev_short, curr_short = short_emas[-2], short_emas[-1]
        prev_long, curr_long = long_emas[-2], long_emas[-1]
        
        # Crossover kontrolü
        if prev_short < prev_long and curr_short > curr_long:
            return "LONG"
        elif prev_short > prev_long and curr_short < curr_long:
            return "SHORT"
        
        return "HOLD"
    
    def _calculate_ema(self, prices: list, period: int) -> list:
        """Basit EMA hesaplama"""
        if len(prices) < period:
            return []
        
        multiplier = 2 / (period + 1)
        emas = []
        
        # İlk EMA = SMA
        sma = sum(prices[:period]) / period
        emas.append(sma)
        
        # Sonraki EMA'lar
        for i in range(period, len(prices)):
            ema = (prices[i] * multiplier) + (emas[-1] * (1 - multiplier))
            emas.append(ema)
        
        return emas

# Stratejiyi projenin her yerinden kullanmak için bir nesne oluştur
trading_strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)
