from typing import List, Dict

class TradingStrategy:
    """
    EMA (9, 21) kesişimine dayalı alım-satım sinyalleri üreten sınıf.
    Pandas kullanmadan manuel EMA hesaplama ile çalışır.
    """
    def __init__(self, short_ema_period: int = 9, long_ema_period: int = 21):
        """
        Stratejiyi EMA periyotları ile başlatır.
        """
        self.short_ema_period = short_ema_period
        self.long_ema_period = long_ema_period
        print(f"Trading Strategy başlatıldı: EMA({self.short_ema_period}, {self.long_ema_period})")

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

        # Kapanış fiyatlarını al
        closes = [float(kline[4]) for kline in klines]
        
        # EMA'ları hesapla
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
        """
        Exponential Moving Average hesaplama
        
        Args:
            prices (list): Fiyat listesi
            period (int): EMA periyodu
            
        Returns:
            list: EMA değerleri listesi
        """
        if len(prices) < period:
            return []
        
        multiplier = 2 / (period + 1)
        emas = []
        
        # İlk EMA = SMA (Simple Moving Average)
        sma = sum(prices[:period]) / period
        emas.append(sma)
        
        # Sonraki EMA'lar
        for i in range(period, len(prices)):
            ema = (prices[i] * multiplier) + (emas[-1] * (1 - multiplier))
            emas.append(ema)
        
        return emas

    def get_strategy_info(self) -> Dict:
        """
        Strateji bilgilerini döndürür
        """
        return {
            "name": "EMA Crossover Strategy",
            "short_period": self.short_ema_period,
            "long_period": self.long_ema_period,
            "description": f"EMA({self.short_ema_period}) ve EMA({self.long_ema_period}) kesişim stratejisi"
        }

# Stratejiyi projenin her yerinden kullanmak için bir nesne oluştur
trading_strategy = TradingStrategy(short_ema_period=9, long_ema_period=21)
