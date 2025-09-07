import pytest
from pydantic import ValidationError
from app.utils.validation import (
    TradingSymbolValidator, 
    TradingParametersValidator,
    EnhancedStartRequest,
    EnhancedApiKeysRequest,
    sanitize_string
)

class TestTradingSymbolValidator:
    
    def test_valid_symbols(self):
        """Geçerli sembol testi"""
        assert TradingSymbolValidator.validate_symbol("BTCUSDT") == True
        assert TradingSymbolValidator.validate_symbol("ETHUSDT") == True
        assert TradingSymbolValidator.validate_symbol("btcusdt") == True  # Case insensitive
    
    def test_invalid_symbols(self):
        """Geçersiz sembol testi"""
        assert TradingSymbolValidator.validate_symbol("INVALID") == False
        assert TradingSymbolValidator.validate_symbol("BTC") == False
        assert TradingSymbolValidator.validate_symbol("") == False
        assert TradingSymbolValidator.validate_symbol(None) == False

class TestTradingParametersValidator:
    
    def test_leverage_validation(self):
        """Kaldıraç validasyon testi"""
        assert TradingParametersValidator.validate_leverage(10) == True
        assert TradingParametersValidator.validate_leverage(1) == True
        assert TradingParametersValidator.validate_leverage(125) == True
        assert TradingParametersValidator.validate_leverage(0) == False
        assert TradingParametersValidator.validate_leverage(126) == False
        assert TradingParametersValidator.validate_leverage("10") == False
    
    def test_order_size_validation(self):
        """Emir büyüklüğü validasyon testi"""
        assert TradingParametersValidator.validate_order_size(100.0) == True
        assert TradingParametersValidator.validate_order_size(10) == True
        assert TradingParametersValidator.validate_order_size(9.99) == False
        assert TradingParametersValidator.validate_order_size(10001) == False
    
    def test_percentage_validation(self):
        """Yüzde validasyon testi"""
        assert TradingParametersValidator.validate_percentage(2.5) == True
        assert TradingParametersValidator.validate_percentage(0.1) == True
        assert TradingParametersValidator.validate_percentage(50.0) == True
        assert TradingParametersValidator.validate_percentage(0.05) == False
        assert TradingParametersValidator.validate_percentage(51.0) == False
    
    def test_timeframe_validation(self):
        """Zaman dilimi validasyon testi"""
        assert TradingParametersValidator.validate_timeframe("15m") == True
        assert TradingParametersValidator.validate_timeframe("1h") == True
        assert TradingParametersValidator.validate_timeframe("1d") == True
        assert TradingParametersValidator.validate_timeframe("2m") == False
        assert TradingParametersValidator.validate_timeframe("invalid") == False

class TestEnhancedStartRequest:
    
    def test_valid_request(self):
        """Geçerli start request testi"""
        request = EnhancedStartRequest(
            symbol="BTCUSDT",
            timeframe="15m",
            leverage=10,
            order_size=100.0,
            stop_loss=2.0,
            take_profit=4.0
        )
        assert request.symbol == "BTCUSDT"
        assert request.take_profit > request.stop_loss
    
    def test_invalid_symbol(self):
        """Geçersiz sembol testi"""
        with pytest.raises(ValidationError):
            EnhancedStartRequest(
                symbol="INVALID",
                timeframe="15m",
                leverage=10,
                order_size=100.0,
                stop_loss=2.0,
                take_profit=4.0
            )
    
    def test_tp_less_than_sl(self):
        """TP < SL durumu testi"""
        with pytest.raises(ValidationError):
            EnhancedStartRequest(
                symbol="BTCUSDT",
                timeframe="15m",
                leverage=10,
                order_size=100.0,
                stop_loss=4.0,
                take_profit=2.0  # TP < SL
            )

class TestSanitization:
    
    def test_sanitize_string(self):
        """String sanitization testi"""
        assert sanitize_string("normal_text") == "normal_text"
        assert sanitize_string("text<script>") == "textscript"
        assert sanitize_string('text"with"quotes') == "textwithquotes"
        assert sanitize_string("a" * 200, max_length=50) == "a" * 50
        assert sanitize_string("  spaced  ") == "spaced"