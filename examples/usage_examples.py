"""
Example usage of ZATCA Compliance Monitor.
Demonstrates various use cases and patterns.
"""
from pathlib import Path
from zatca_monitor import InvoiceValidator, load_invoice, BatchProcessor
from zatca_monitor.processing import ConcurrentValidator
from zatca_monitor.core.parsers import invoice_generator


def example_validate_single_file():
    """Example: Validate a single invoice file"""
    print("Example 1: Single File Validation")
    print("-" * 50)
    
    # Load invoice
    invoice = load_invoice('sample_invoices/invoice_001.xml')
    
    # Create validator
    validator = InvoiceValidator()
    
    # Validate
    result = validator.validate(invoice)
    
    # Check result
    if result.is_compliant:
        print(f"✓ Invoice {result.invoice_number} is compliant")
    else:
        print(f"✗ Invoice {result.invoice_number} has {len(result.violations)} violations:")
        for violation in result.violations:
            print(f"  - [{violation.code}] {violation.message}")
    
    print()


def example_process_directory_sequential():
    """Example: Process directory sequentially using generators"""
    print("Example 2: Sequential Directory Processing")
    print("-" * 50)
    
    processor = BatchProcessor()
    result = processor.process_directory(
        directory=Path('sample_invoices/'),
        pattern='*.xml',
        output_dir=Path('reports/')
    )
    
    print(f"Processed: {result.total} invoices")
    print(f"Compliant: {result.compliant_count}")
    print(f"Failed: {result.failed_count}")
    print(f"Time: {result.processing_time_seconds:.2f}s")
    print()


def example_process_directory_concurrent():
    """Example: Process directory with multithreading"""
    print("Example 3: Concurrent Directory Processing")
    print("-" * 50)
    
    validator = ConcurrentValidator(max_workers=4)
    result = validator.validate_directory(
        directory=Path('sample_invoices/'),
        pattern='*.xml'
    )
    
    print(f"Processed: {result.total} invoices")
    print(f"Compliant: {result.compliant_count}")
    print(f"Failed: {result.failed_count}")
    print(f"Time: {result.processing_time_seconds:.2f}s")
    print(f"Throughput: {result.total/result.processing_time_seconds:.1f} invoices/sec")
    print()


def example_stream_processing():
    """Example: Stream invoices with generator (memory efficient)"""
    print("Example 4: Stream Processing with Generator")
    print("-" * 50)
    
    validator = InvoiceValidator()
    
    # Process invoices one by one without loading all into memory
    compliant_count = 0
    total_count = 0
    
    for invoice in invoice_generator('sample_invoices/', '*.xml'):
        result = validator.validate(invoice)
        total_count += 1
        
        if result.is_compliant:
            compliant_count += 1
        else:
            print(f"Non-compliant: {invoice.invoice_number}")
    
    print(f"\nProcessed {total_count} invoices, {compliant_count} compliant")
    print()


def example_with_callback():
    """Example: Process with custom callback for real-time monitoring"""
    print("Example 5: Processing with Callback")
    print("-" * 50)
    
    def my_callback(result):
        """Called after each invoice validation"""
        if not result.is_compliant:
            print(f"⚠️  Alert: {result.invoice_number} is non-compliant")
    
    validator = ConcurrentValidator(max_workers=4)
    result = validator.validate_directory(
        directory=Path('sample_invoices/'),
        callback=my_callback
    )
    
    print(f"\nFinal result: {result.compliant_count}/{result.total} compliant")
    print()


def example_filter_by_violations():
    """Example: Find invoices with specific violation types"""
    print("Example 6: Filter by Violation Type")
    print("-" * 50)
    
    processor = BatchProcessor()
    result = processor.process_directory(Path('sample_invoices/'))
    
    # Find all invoices with VAT violations
    vat_violations = [
        r for r in result.results
        if any(v.code.startswith('VAT_') for v in r.violations)
    ]
    
    print(f"Found {len(vat_violations)} invoices with VAT violations:")
    for r in vat_violations[:5]:  # Show first 5
        print(f"  - {r.invoice_number}")
    
    print()


def example_performance_metrics():
    """Example: Collect and display performance metrics"""
    print("Example 7: Performance Metrics")
    print("-" * 50)
    
    from zatca_monitor.utils.decorators import metrics
    
    validator = ConcurrentValidator(max_workers=8)
    validator.validate_directory(Path('sample_invoices/'))
    
    # Get metrics
    stats = metrics.get_stats('invoice_validation_time')
    
    if stats:
        print(f"Validation Stats:")
        print(f"  Count: {stats['count']}")
        print(f"  Avg: {stats['avg']:.2f}ms")
        print(f"  Min: {stats['min']:.2f}ms")
        print(f"  Max: {stats['max']:.2f}ms")
    
    print()


if __name__ == '__main__':
    print("ZATCA Compliance Monitor - Usage Examples")
    print("=" * 50)
    print()
    
    # Run examples (comment out as needed)
    # example_validate_single_file()
    # example_process_directory_sequential()
    # example_process_directory_concurrent()
    # example_stream_processing()
    # example_with_callback()
    # example_filter_by_violations()
    # example_performance_metrics()
    
    print("Note: Create sample_invoices/ directory with test files to run examples")
