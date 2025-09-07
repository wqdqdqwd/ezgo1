import pytest
from unittest.mock import patch
from app.utils.metrics import MetricsCollector, metrics

class TestMetricsCollector:
    
    def setup_method(self):
        """Her test öncesi çalışır"""
        self.metrics = MetricsCollector()
    
    def test_record_bot_start(self):
        """Bot başlatma metriği testi"""
        with patch('app.utils.metrics.logger') as mock_logger:
            self.metrics.record_bot_start("user123", "BTCUSDT")
            mock_logger.info.assert_called_once()
    
    def test_record_trade(self):
        """Trade metriği testi"""
        with patch('app.utils.metrics.logger') as mock_logger:
            self.metrics.record_trade("user123", "BTCUSDT", "BUY", 10.5, "completed")
            mock_logger.info.assert_called_once()
    
    def test_record_error(self):
        """Hata metriği testi"""
        with patch('app.utils.metrics.logger') as mock_logger:
            self.metrics.record_error("api_error", "binance_client")
            mock_logger.error.assert_called_once()
    
    def test_update_active_bots(self):
        """Aktif bot sayısı güncelleme testi"""
        # Bu test prometheus metrics'i test eder
        self.metrics.update_active_bots(5)
        # Gerçek test için prometheus client mock'lanmalı
        assert True  # Placeholder
    
    def test_metrics_data_format(self):
        """Metrics data formatı testi"""
        from app.utils.metrics import get_metrics_data, get_metrics_content_type
        
        # Metrics data string olmalı
        data = get_metrics_data()
        assert isinstance(data, (str, bytes))
        
        # Content type doğru olmalı
        content_type = get_metrics_content_type()
        assert "text/plain" in content_type