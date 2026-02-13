"""
Batch processing utilities using generators for memory efficiency.
Processes large volumes of invoices without loading all into memory.
"""
import logging
from pathlib import Path
from typing import Generator, Optional, Callable
from datetime import datetime

from zatca_monitor.core.models import ValidationResult, BatchResult
from zatca_monitor.core.parsers import invoice_generator
from zatca_monitor.core.validators import InvoiceValidator
from zatca_monitor.utils.decorators import measure_performance


logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Sequential batch processor using generators.
    Memory-efficient but single-threaded.
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize batch processor.
        
        Args:
            strict_mode: Whether to use strict validation rules
        """
        self.validator = InvoiceValidator(strict_mode)
        self.strict_mode = strict_mode
    
    @measure_performance
    def process_generator(self,
                         invoice_gen: Generator,
                         callback: Optional[Callable] = None) -> BatchResult:
        """
        Process invoices from a generator.
        Most memory-efficient approach.
        
        Args:
            invoice_gen: Generator yielding Invoice objects
            callback: Optional function called after each validation
                     Signature: callback(result: ValidationResult) -> None
            
        Returns:
            BatchResult with statistics
        """
        import time
        start_time = time.time()
        
        batch_result = BatchResult()
        
        # Process invoices one by one
        for invoice in invoice_gen:
            try:
                result = self.validator.validate(invoice)
                batch_result.add_result(result)
                
                if callback:
                    callback(result)
                
                # Log progress every 100 invoices
                if batch_result.total % 100 == 0:
                    logger.info(
                        f"Processed {batch_result.total} invoices "
                        f"({batch_result.compliant_count} compliant)"
                    )
                    
            except Exception as e:
                logger.error(f"Error processing invoice: {e}")
                # Create error result
                error_result = ValidationResult(
                    invoice_number='UNKNOWN',
                    is_compliant=False
                )
                error_result.add_violation(
                    code='SYS_002',
                    field='system',
                    message=f'Processing error: {str(e)}'
                )
                batch_result.add_result(error_result)
        
        batch_result.processing_time_seconds = time.time() - start_time
        
        logger.info(
            f"Batch complete: {batch_result.total} invoices in "
            f"{batch_result.processing_time_seconds:.2f}s"
        )
        
        return batch_result
    
    @measure_performance
    def process_directory(self,
                         directory: Path,
                         pattern: str = "*.xml",
                         output_dir: Optional[Path] = None,
                         save_reports: bool = True) -> BatchResult:
        """
        Process all invoices in a directory.
        
        Args:
            directory: Directory containing invoices
            pattern: File pattern to match
            output_dir: Directory to save reports (optional)
            save_reports: Whether to save individual reports
            
        Returns:
            BatchResult
        """
        logger.info(f"Starting batch processing: {directory}")
        
        # Create output directory if needed
        if output_dir and save_reports:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # Define callback for saving reports
        def save_result(result: ValidationResult):
            if output_dir and save_reports:
                report_file = output_dir / f"{result.invoice_number}.json"
                with open(report_file, 'w') as f:
                    f.write(result.json(indent=2))
        
        # Use generator for memory efficiency
        gen = invoice_generator(directory, pattern)
        
        return self.process_generator(gen, callback=save_result if save_reports else None)


class ProgressTracker:
    """
    Tracks and reports processing progress.
    Useful for long-running batch operations.
    """
    
    def __init__(self, total_expected: Optional[int] = None):
        """
        Initialize progress tracker.
        
        Args:
            total_expected: Expected total number of items (if known)
        """
        self.total_expected = total_expected
        self.processed = 0
        self.compliant = 0
        self.failed = 0
        self.start_time = datetime.now()
    
    def update(self, result: ValidationResult):
        """Update progress with new result"""
        self.processed += 1
        if result.is_compliant:
            self.compliant += 1
        else:
            self.failed += 1
    
    def get_summary(self) -> str:
        """Get current progress summary"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.processed / elapsed if elapsed > 0 else 0
        
        summary = f"Processed: {self.processed}"
        if self.total_expected:
            pct = (self.processed / self.total_expected) * 100
            summary += f"/{self.total_expected} ({pct:.1f}%)"
        
        summary += f" | Compliant: {self.compliant} | Failed: {self.failed}"
        summary += f" | Rate: {rate:.1f}/s"
        
        return summary
    
    def should_log(self, interval: int = 100) -> bool:
        """Check if progress should be logged"""
        return self.processed % interval == 0


def process_with_progress(directory: Path,
                         pattern: str = "*.xml",
                         log_interval: int = 100) -> BatchResult:
    """
    Process directory with progress logging.
    
    Args:
        directory: Directory with invoices
        pattern: File pattern
        log_interval: Log progress every N invoices
        
    Returns:
        BatchResult
    """
    processor = BatchProcessor()
    tracker = ProgressTracker()
    
    def progress_callback(result: ValidationResult):
        tracker.update(result)
        if tracker.should_log(log_interval):
            logger.info(tracker.get_summary())
    
    gen = invoice_generator(directory, pattern)
    return processor.process_generator(gen, callback=progress_callback)


def filter_results_generator(results: Generator[ValidationResult, None, None],
                             compliant_only: bool = False,
                             failed_only: bool = False) -> Generator[ValidationResult, None, None]:
    """
    Filter validation results using generator pattern.
    
    Args:
        results: Generator of validation results
        compliant_only: Only yield compliant invoices
        failed_only: Only yield failed invoices
        
    Yields:
        Filtered ValidationResult objects
    """
    for result in results:
        if compliant_only and result.is_compliant:
            yield result
        elif failed_only and not result.is_compliant:
            yield result
        elif not compliant_only and not failed_only:
            yield result


def group_by_violation(results: Generator[ValidationResult, None, None]) -> dict:
    """
    Group results by violation type.
    Useful for identifying common compliance issues.
    
    Args:
        results: Generator of validation results
        
    Returns:
        Dictionary mapping violation codes to lists of invoice numbers
    """
    violations_map = {}
    
    for result in results:
        if not result.is_compliant:
            for violation in result.violations:
                code = violation.code
                if code not in violations_map:
                    violations_map[code] = []
                violations_map[code].append(result.invoice_number)
    
    return violations_map


class ChunkedProcessor:
    """
    Processes invoices in fixed-size chunks.
    Balance between memory usage and processing efficiency.
    """
    
    def __init__(self, chunk_size: int = 50, strict_mode: bool = True):
        """
        Initialize chunked processor.
        
        Args:
            chunk_size: Number of invoices per chunk
            strict_mode: Strict validation mode
        """
        self.chunk_size = chunk_size
        self.validator = InvoiceValidator(strict_mode)
    
    @measure_performance
    def process_chunks(self, directory: Path, pattern: str = "*.xml") -> BatchResult:
        """
        Process directory in chunks.
        
        Args:
            directory: Invoice directory
            pattern: File pattern
            
        Returns:
            BatchResult
        """
        from zatca_monitor.core.parsers import batch_invoice_generator
        import time
        
        start_time = time.time()
        batch_result = BatchResult()
        
        # Process each chunk
        for chunk_num, chunk in enumerate(batch_invoice_generator(
            directory, self.chunk_size, pattern
        ), start=1):
            logger.info(f"Processing chunk {chunk_num} ({len(chunk)} invoices)")
            
            # Validate all in chunk
            for invoice in chunk:
                try:
                    result = self.validator.validate(invoice)
                    batch_result.add_result(result)
                except Exception as e:
                    logger.error(f"Error in chunk {chunk_num}: {e}")
            
            logger.info(
                f"Chunk {chunk_num} complete: "
                f"{batch_result.compliant_count}/{batch_result.total} compliant"
            )
        
        batch_result.processing_time_seconds = time.time() - start_time
        return batch_result
