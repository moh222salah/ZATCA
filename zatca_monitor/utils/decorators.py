"""
Decorators for audit logging, performance monitoring, and error handling.
Production-grade implementation with proper context management.
"""
import functools
import logging
import time
from datetime import datetime
from typing import Any, Callable
from contextlib import contextmanager

# Configure audit logger separately from main app logger
audit_logger = logging.getLogger('zatca.audit')
perf_logger = logging.getLogger('zatca.performance')


def audit_log(func: Callable) -> Callable:
    """
    Decorator that logs all function calls with parameters and results.
    Critical for compliance auditing and debugging.
    
    Usage:
        @audit_log
        def validate_invoice(invoice):
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__qualname__
        
        # Extract invoice info if available
        invoice_id = "N/A"
        if args and hasattr(args[0], 'invoice_number'):
            invoice_id = args[0].invoice_number
        elif 'invoice' in kwargs and hasattr(kwargs['invoice'], 'invoice_number'):
            invoice_id = kwargs['invoice'].invoice_number
        
        # Log entry
        audit_logger.info(
            f"CALL | {func_name} | Invoice: {invoice_id} | "
            f"Timestamp: {datetime.now().isoformat()}"
        )
        
        try:
            result = func(*args, **kwargs)
            
            # Log successful exit
            status = "COMPLIANT" if (hasattr(result, 'is_compliant') 
                                     and result.is_compliant) else "PROCESSED"
            audit_logger.info(
                f"SUCCESS | {func_name} | Invoice: {invoice_id} | "
                f"Status: {status}"
            )
            
            return result
            
        except Exception as e:
            # Log failure
            audit_logger.error(
                f"FAILURE | {func_name} | Invoice: {invoice_id} | "
                f"Error: {str(e)}"
            )
            raise
    
    return wrapper


def measure_performance(func: Callable) -> Callable:
    """
    Decorator to measure and log function execution time.
    Useful for identifying bottlenecks in validation pipeline.
    
    Usage:
        @measure_performance
        def process_batch(invoices):
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        
        try:
            result = func(*args, **kwargs)
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            # Attach timing to result if possible
            if hasattr(result, 'processing_time_ms'):
                result.processing_time_ms = elapsed_ms
            
            perf_logger.debug(
                f"{func.__qualname__} completed in {elapsed_ms:.2f}ms"
            )
            
            return result
            
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            perf_logger.warning(
                f"{func.__qualname__} failed after {elapsed_ms:.2f}ms: {str(e)}"
            )
            raise
    
    return wrapper


def retry_on_failure(max_attempts: int = 3, delay_seconds: float = 1.0):
    """
    Decorator for retrying operations that may fail transiently.
    Useful for network operations or external API calls.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay_seconds: Delay between retries
    
    Usage:
        @retry_on_failure(max_attempts=3, delay_seconds=2.0)
        def verify_signature(invoice):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    logging.warning(
                        f"{func.__qualname__} attempt {attempt}/{max_attempts} "
                        f"failed: {str(e)}"
                    )
                    
                    if attempt < max_attempts:
                        time.sleep(delay_seconds)
            
            # All attempts exhausted
            logging.error(
                f"{func.__qualname__} failed after {max_attempts} attempts"
            )
            raise last_exception
        
        return wrapper
    
    return decorator


def validate_input(validator_func: Callable) -> Callable:
    """
    Decorator to validate function inputs before execution.
    
    Args:
        validator_func: Function that validates inputs, raises ValueError if invalid
    
    Usage:
        def check_not_none(invoice):
            if invoice is None:
                raise ValueError("Invoice cannot be None")
        
        @validate_input(check_not_none)
        def process(invoice):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Run validation
            validator_func(*args, **kwargs)
            
            # Proceed if validation passes
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


@contextmanager
def performance_context(operation_name: str):
    """
    Context manager for measuring code block performance.
    
    Usage:
        with performance_context("QR validation"):
            verify_qr_code(invoice)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        perf_logger.debug(f"{operation_name}: {elapsed:.2f}ms")


class MetricsCollector:
    """
    Simple metrics collector for aggregating performance data.
    In production, this would integrate with Prometheus/Grafana.
    """
    def __init__(self):
        self.metrics = {}
    
    def record(self, metric_name: str, value: float):
        """Record a metric value"""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        self.metrics[metric_name].append(value)
    
    def get_stats(self, metric_name: str) -> dict:
        """Get statistics for a metric"""
        if metric_name not in self.metrics:
            return {}
        
        values = self.metrics[metric_name]
        return {
            'count': len(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values)
        }


# Global metrics instance
metrics = MetricsCollector()


def collect_metric(metric_name: str):
    """
    Decorator to automatically collect execution time metrics.
    
    Usage:
        @collect_metric('invoice_validation_time')
        def validate(invoice):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                metrics.record(metric_name, elapsed)
        
        return wrapper
    
    return decorator
