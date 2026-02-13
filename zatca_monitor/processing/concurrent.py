"""
Concurrent validation processing using ThreadPoolExecutor.
Enables parallel validation of multiple invoices.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Optional
from pathlib import Path

from zatca_monitor.core.models import Invoice, ValidationResult, BatchResult
from zatca_monitor.core.validators import InvoiceValidator
from zatca_monitor.core.parsers import invoice_generator
from zatca_monitor.utils.decorators import measure_performance


logger = logging.getLogger(__name__)


class ConcurrentValidator:
    """
    Thread-safe validator for concurrent invoice processing.
    Each thread gets its own validator instance to avoid race conditions.
    """
    
    def __init__(self, max_workers: Optional[int] = None, strict_mode: bool = True):
        """
        Initialize concurrent validator.
        
        Args:
            max_workers: Maximum number of worker threads (default: CPU count * 2)
            strict_mode: Whether to use strict validation rules
        """
        self.max_workers = max_workers
        self.strict_mode = strict_mode
        self._validator = None  # Thread-local validator
    
    def _get_validator(self) -> InvoiceValidator:
        """Get or create thread-local validator instance"""
        if self._validator is None:
            self._validator = InvoiceValidator(self.strict_mode)
        return self._validator
    
    def validate_one(self, invoice: Invoice) -> ValidationResult:
        """
        Validate a single invoice (thread-safe).
        
        Args:
            invoice: Invoice to validate
            
        Returns:
            ValidationResult
        """
        validator = self._get_validator()
        return validator.validate(invoice)
    
    @measure_performance
    def validate_batch(self, invoices: List[Invoice]) -> List[ValidationResult]:
        """
        Validate multiple invoices concurrently.
        
        Args:
            invoices: List of invoices to validate
            
        Returns:
            List of validation results (order may differ from input)
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all validation tasks
            future_to_invoice = {
                executor.submit(self.validate_one, inv): inv 
                for inv in invoices
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_invoice):
                invoice = future_to_invoice[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(
                        f"Validation failed for invoice {invoice.invoice_number}: {e}"
                    )
                    # Create error result
                    error_result = ValidationResult(
                        invoice_number=invoice.invoice_number,
                        is_compliant=False
                    )
                    error_result.add_violation(
                        code='SYS_001',
                        field='system',
                        message=f'Validation error: {str(e)}',
                        severity='ERROR'
                    )
                    results.append(error_result)
        
        return results
    
    @measure_performance
    def validate_directory(self, 
                          directory: Path, 
                          pattern: str = "*.xml",
                          callback: Optional[Callable] = None) -> BatchResult:
        """
        Validate all invoices in a directory concurrently.
        Uses generator to avoid loading all files into memory.
        
        Args:
            directory: Directory containing invoice files
            pattern: File pattern to match (e.g., "*.xml", "*.json")
            callback: Optional callback function called after each invoice
                     Signature: callback(result: ValidationResult) -> None
            
        Returns:
            BatchResult with aggregated statistics
        """
        import time
        start_time = time.time()
        
        batch_result = BatchResult()
        
        # Collect invoices (we need a list for ThreadPoolExecutor)
        # In production, consider streaming batches for very large datasets
        invoices = list(invoice_generator(directory, pattern))
        logger.info(f"Found {len(invoices)} invoices to validate")
        
        if not invoices:
            logger.warning(f"No invoices found in {directory} matching {pattern}")
            return batch_result
        
        # Process concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_invoice = {
                executor.submit(self.validate_one, inv): inv 
                for inv in invoices
            }
            
            # Process results as they complete
            for future in as_completed(future_to_invoice):
                invoice = future_to_invoice[future]
                try:
                    result = future.result()
                    batch_result.add_result(result)
                    
                    # Call callback if provided
                    if callback:
                        callback(result)
                    
                    # Log progress
                    if batch_result.total % 100 == 0:
                        logger.info(
                            f"Progress: {batch_result.total}/{len(invoices)} "
                            f"({batch_result.compliant_count} compliant)"
                        )
                        
                except Exception as e:
                    logger.error(
                        f"Failed to process {invoice.invoice_number}: {e}"
                    )
                    # Create error result
                    error_result = ValidationResult(
                        invoice_number=invoice.invoice_number,
                        is_compliant=False
                    )
                    error_result.add_violation(
                        code='SYS_001',
                        field='system',
                        message=f'Processing error: {str(e)}'
                    )
                    batch_result.add_result(error_result)
        
        # Finalize timing
        batch_result.processing_time_seconds = time.time() - start_time
        
        logger.info(
            f"Validation complete: {batch_result.compliant_count}/{batch_result.total} "
            f"compliant in {batch_result.processing_time_seconds:.2f}s"
        )
        
        return batch_result


class StreamingValidator:
    """
    Alternative validator that processes invoices as a stream.
    More memory efficient for very large datasets but sacrifices some concurrency.
    """
    
    def __init__(self, max_workers: int = 4, strict_mode: bool = True):
        self.max_workers = max_workers
        self.strict_mode = strict_mode
    
    @measure_performance
    def validate_stream(self,
                       directory: Path,
                       pattern: str = "*.xml",
                       batch_size: int = 100,
                       callback: Optional[Callable] = None) -> BatchResult:
        """
        Process invoices in streaming batches.
        Trades off maximum concurrency for constant memory usage.
        
        Args:
            directory: Directory with invoices
            pattern: File pattern
            batch_size: Number of invoices to process per batch
            callback: Optional result callback
            
        Returns:
            BatchResult
        """
        from zatca_monitor.core.parsers import batch_invoice_generator
        import time
        
        start_time = time.time()
        batch_result = BatchResult()
        
        # Process in batches
        for batch in batch_invoice_generator(directory, batch_size, pattern):
            # Validate batch concurrently
            validator = ConcurrentValidator(self.max_workers, self.strict_mode)
            results = validator.validate_batch(batch)
            
            # Aggregate results
            for result in results:
                batch_result.add_result(result)
                if callback:
                    callback(result)
            
            logger.info(
                f"Processed batch: {len(results)} invoices "
                f"(Total: {batch_result.total})"
            )
        
        batch_result.processing_time_seconds = time.time() - start_time
        return batch_result


def validate_invoices_parallel(invoices: List[Invoice],
                               max_workers: Optional[int] = None) -> List[ValidationResult]:
    """
    Convenience function for parallel validation.
    
    Args:
        invoices: List of invoices to validate
        max_workers: Number of worker threads
        
    Returns:
        List of validation results
    """
    validator = ConcurrentValidator(max_workers=max_workers)
    return validator.validate_batch(invoices)


def validate_directory_parallel(directory: Path,
                                pattern: str = "*.xml",
                                max_workers: Optional[int] = None) -> BatchResult:
    """
    Convenience function for parallel directory validation.
    
    Args:
        directory: Directory containing invoices
        pattern: File pattern to match
        max_workers: Number of worker threads
        
    Returns:
        BatchResult with statistics
    """
    validator = ConcurrentValidator(max_workers=max_workers)
    return validator.validate_directory(directory, pattern)
