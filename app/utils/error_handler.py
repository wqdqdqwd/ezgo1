from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from binance.exceptions import BinanceAPIException
from app.utils.logger import get_logger
import asyncio
from typing import Callable, Any
from functools import wraps

logger = get_logger("error_handler")

class CircuitBreakerError(Exception):
    """Circuit breaker açık olduğunda fırlatılan hata"""
    pass

class CircuitBreaker:
    """
    Circuit breaker pattern implementasyonu
    """
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func: Callable, *args, **kwargs):
        """
        Circuit breaker ile fonksiyon çağrısı
        """
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerError("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """
        Circuit breaker'ı reset etmeyi deneyip denemeyeceğini kontrol eder
        """
        import time
        return (
            self.last_failure_time and 
            time.time() - self.last_failure_time >= self.timeout
        )

    def _on_success(self):
        """Başarılı çağrı sonrası state güncelleme"""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Başarısız çağrı sonrası state güncelleme"""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                "Circuit breaker opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )

# Global circuit breaker instances
binance_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)
firebase_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

def robust_binance_call(max_attempts: int = 3):
    """
    Binance API çağrıları için robust decorator
    """
    def decorator(func):
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((BinanceAPIException, ConnectionError, TimeoutError)),
            reraise=True
        )
        async def wrapper(*args, **kwargs):
            try:
                return await binance_circuit_breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                logger.error("Binance circuit breaker is open, skipping call")
                raise BinanceAPIException("Service temporarily unavailable")
            except Exception as e:
                logger.error(
                    "Binance API call failed",
                    function=func.__name__,
                    error=str(e),
                    args=str(args)[:100]  # Limit log size
                )
                raise
        return wrapper
    return decorator

def robust_firebase_call(max_attempts: int = 2):
    """
    Firebase çağrıları için robust decorator
    """
    def decorator(func):
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=5),
            reraise=True
        )
        async def wrapper(*args, **kwargs):
            try:
                return await firebase_circuit_breaker.call(func, *args, **kwargs)
            except CircuitBreakerError:
                logger.error("Firebase circuit breaker is open")
                raise Exception("Database temporarily unavailable")
            except Exception as e:
                logger.error(
                    "Firebase call failed",
                    function=func.__name__,
                    error=str(e)
                )
                raise
        return wrapper
    return decorator

async def safe_async_call(func: Callable, *args, default_return=None, **kwargs):
    """
    Güvenli async fonksiyon çağrısı
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(
            "Safe async call failed",
            function=func.__name__,
            error=str(e)
        )
        return default_return