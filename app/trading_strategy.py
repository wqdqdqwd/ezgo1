import pandas as pd

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

# Stratejiyi projenin her yerinden kullanmak için bir nesne oluştur
trading_strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)
