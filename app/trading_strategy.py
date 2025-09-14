from app.utils.logger import get_logger

logger = get_logger("trading_strategy")

class TradingStrategy:
    """
    Pandas'sız EMA (9, 21) kesişim stratejisi
    Hafif ve hızlı versiyon
    """
    
    def __init__(self, short_ema_period: int = 9, long_ema_period: int = 21):
        self.short_ema_period = short_ema_period
        self.long_ema_period = long_ema_period
        self.alpha_short = 2 / (short_ema_period + 1)
        self.alpha_long = 2 / (long_ema_period + 1)
        logger.info(f"Trading Strategy başlatıldı: EMA({self.short_ema_period}, {self.long_ema_period})")

    def calculate_ema(self, prices: list, period: int) -> list:
        """EMA hesaplama - pandas'sız"""
        if len(prices) < period:
            return []
        
        alpha = 2 / (period + 1)
        ema_values = []
        
        # İlk değer basit ortalama
        sma = sum(prices[:period]) / period
        ema_values.append(sma)
        
        # Sonraki değerler EMA formülü ile
        for i in range(period, len(prices)):
            ema = (prices[i] * alpha) + (ema_values[-1] * (1 - alpha))
            ema_values.append(ema)
            
        return ema_values

    def analyze_klines(self, klines: list) -> str:
        """Kline verilerini analiz eder ve sinyal döndürür"""
        try:
            # Yeterli veri kontrolü
            if len(klines) < self.long_ema_period:
                return "HOLD"

            # Close fiyatlarını çıkar
            close_prices = []
            for kline in klines:
                try:
                    close_price = float(kline[4])  # Close price index 4
                    close_prices.append(close_price)
                except (IndexError, ValueError, TypeError):
                    logger.error("Kline veri formatı hatası")
                    return "HOLD"

            # EMA hesapla
            short_ema = self.calculate_ema(close_prices, self.short_ema_period)
            long_ema = self.calculate_ema(close_prices, self.long_ema_period)
            
            # Yeterli EMA verisi var mı kontrol et
            if len(short_ema) < 2 or len(long_ema) < 2:
                return "HOLD"

            # Son iki değeri al
            current_short = short_ema[-1]
            current_long = long_ema[-1]
            prev_short = short_ema[-2]
            prev_long = long_ema[-2]

            # Crossover kontrolü
            signal = "HOLD"
            
            # Golden Cross (EMA9 > EMA21 kesişimi) = LONG
            if prev_short <= prev_long and current_short > current_long:
                signal = "LONG"
                logger.info(f"LONG sinyali tespit edildi (Golden Cross) - EMA9: {current_short:.6f}, EMA21: {current_long:.6f}")
                
            # Death Cross (EMA9 < EMA21 kesişimi) = SHORT  
            elif prev_short >= prev_long and current_short < current_long:
                signal = "SHORT"
                logger.info(f"SHORT sinyali tespit edildi (Death Cross) - EMA9: {current_short:.6f}, EMA21: {current_long:.6f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Strateji analiz hatası: {e}")
            return "HOLD"

# Global strategy instance
trading_strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)
