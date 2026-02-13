"""
ZATCA Compliance Monitor - Main Entry Point
Command-line interface for invoice validation.
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from zatca_monitor.processing.concurrent import ConcurrentValidator
from zatca_monitor.processing.batch import BatchProcessor
from zatca_monitor.reports.generator import generate_summary_report


# Configure logging
def setup_logging(verbose: bool = False):
    """Configure application logging"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('zatca_monitor.log')
        ]
    )


def validate_directory(args):
    """Handle directory validation command"""
    input_dir = Path(args.input)
    output_dir = Path(args.output) if args.output else None
    
    if not input_dir.exists():
        logging.error(f"Input directory not found: {input_dir}")
        return 1
    
    logging.info(f"Starting validation: {input_dir}")
    logging.info(f"Pattern: {args.pattern}")
    logging.info(f"Workers: {args.workers}")
    logging.info(f"Mode: {'concurrent' if args.concurrent else 'sequential'}")
    
    # Choose processor based on mode
    if args.concurrent:
        processor = ConcurrentValidator(
            max_workers=args.workers,
            strict_mode=args.strict
        )
        result = processor.validate_directory(input_dir, args.pattern)
    else:
        processor = BatchProcessor(strict_mode=args.strict)
        result = processor.process_directory(
            input_dir,
            pattern=args.pattern,
            output_dir=output_dir,
            save_reports=args.save_reports
        )
    
    # Print summary
    print("\n" + "="*60)
    print("ZATCA COMPLIANCE VALIDATION SUMMARY")
    print("="*60)
    print(f"Total Invoices:    {result.total}")
    print(f"Compliant:         {result.compliant_count} ({result.compliant_count/result.total*100:.1f}%)")
    print(f"Non-Compliant:     {result.failed_count} ({result.failed_count/result.total*100:.1f}%)")
    print(f"Processing Time:   {result.processing_time_seconds:.2f}s")
    print(f"Rate:              {result.total/result.processing_time_seconds:.1f} invoices/sec")
    print("="*60)
    
    # Generate detailed report if output specified
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_path, 'w') as f:
            report = generate_summary_report(result)
            f.write(report)
        
        logging.info(f"Summary report saved: {report_path}")
    
    # Return exit code (0 if all compliant, 1 if any failures)
    return 0 if result.failed_count == 0 else 1


def validate_single(args):
    """Handle single file validation command"""
    file_path = Path(args.file)
    
    if not file_path.exists():
        logging.error(f"File not found: {file_path}")
        return 1
    
    from zatca_monitor.core.parsers import load_invoice
    from zatca_monitor.core.validators import InvoiceValidator
    
    logging.info(f"Validating: {file_path}")
    
    # Load and validate
    invoice = load_invoice(file_path)
    validator = InvoiceValidator(strict_mode=args.strict)
    result = validator.validate(invoice)
    
    # Print result
    print("\n" + "="*60)
    print(f"Invoice: {result.invoice_number}")
    print("="*60)
    
    if result.is_compliant:
        print("✓ COMPLIANT")
        print("\nThis invoice meets all ZATCA requirements.")
    else:
        print("✗ NON-COMPLIANT")
        print(f"\nFound {len(result.violations)} violation(s):\n")
        
        for i, violation in enumerate(result.violations, 1):
            print(f"{i}. [{violation.code}] {violation.message}")
            print(f"   Field: {violation.field}")
            print(f"   Rule: {violation.rule}")
            print(f"   Severity: {violation.severity}\n")
    
    print("="*60)
    
    if result.processing_time_ms:
        print(f"Processing time: {result.processing_time_ms:.2f}ms")
    
    return 0 if result.is_compliant else 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='ZATCA Compliance Monitor - Validate e-invoices against Saudi ZATCA requirements'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Directory validation command
    dir_parser = subparsers.add_parser('directory', help='Validate all invoices in a directory')
    dir_parser.add_argument('--input', '-i', required=True, help='Input directory path')
    dir_parser.add_argument('--output', '-o', help='Output directory for reports')
    dir_parser.add_argument('--pattern', '-p', default='*.xml', help='File pattern (default: *.xml)')
    dir_parser.add_argument('--workers', '-w', type=int, default=None, help='Number of worker threads')
    dir_parser.add_argument('--concurrent', '-c', action='store_true', help='Use concurrent processing')
    dir_parser.add_argument('--strict', action='store_true', help='Use strict validation mode')
    dir_parser.add_argument('--save-reports', action='store_true', help='Save individual reports')
    dir_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    # Single file validation command
    file_parser = subparsers.add_parser('file', help='Validate a single invoice file')
    file_parser.add_argument('file', help='Path to invoice file')
    file_parser.add_argument('--strict', action='store_true', help='Use strict validation mode')
    file_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Execute command
    try:
        if args.command == 'directory':
            return validate_directory(args)
        elif args.command == 'file':
            return validate_single(args)
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
