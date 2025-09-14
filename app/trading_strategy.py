import pandas as pd
from app.utils.logger import get_logger

logger = get_logger("trading_strategy")

class TradingStrategy:
    """
    EMA (9, 21) kesişim stratejisi
    """
    
    def __init__(self, short_ema_period: int = 9, long_ema_period: int = 21):
        self.short_ema_period = short_ema_period
        self.long_ema_period = long_ema_period
        logger.info(f"Trading Strategy başlatıldı: EMA({self.short_ema_period}, {self.long_ema_period})")

    def analyze_klines(self, klines: list) -> str:
        """Kline verilerini analiz eder ve sinyal döndürür"""
        try:
            # Yeterli veri kontrolü
            if len(klines) < self.long_ema_period:
                return "HOLD"

            # DataFrame oluştur
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
                'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
                'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Close fiyatlarını numeric'e çevir
            df['close'] = pd.to_numeric(df['close'])
            
            # EMA'ları hesapla
            df['short_ema'] = df['close'].ewm(span=self.short_ema_period, adjust=False).mean()
            df['long_ema'] = df['close'].ewm(span=self.long_ema_period, adjust=False).mean()

            # Son iki mumun verilerini al
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            
            # Crossover kontrolü
            signal = "HOLD"
            
            # Golden Cross (EMA9 > EMA21 kesişimi) = LONG
            if (prev_row['short_ema'] <= prev_row['long_ema'] and 
                last_row['short_ema'] > last_row['long_ema']):
                signal = "LONG"
                logger.info("LONG sinyali tespit edildi (Golden Cross)")
                
            # Death Cross (EMA9 < EMA21 kesişimi) = SHORT  
            elif (prev_row['short_ema'] >= prev_row['long_ema'] and 
                  last_row['short_ema'] < last_row['long_ema']):
                signal = "SHORT"
                logger.info("SHORT sinyali tespit edildi (Death Cross)")
            
            return signal
            
        except Exception as e:
            logger.error(f"Strateji analiz hatası: {e}")
            return "HOLD"

# Global strategy instance
trading_strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)
