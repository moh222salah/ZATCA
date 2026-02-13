"""
Report generation utilities.
Creates human-readable compliance reports.
"""
from datetime import datetime
from collections import Counter
from typing import List

from zatca_monitor.core.models import BatchResult, ValidationResult


def generate_summary_report(batch_result: BatchResult) -> str:
    """
    Generate text summary report from batch results.
    
    Args:
        batch_result: Batch processing results
        
    Returns:
        Formatted text report
    """
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("ZATCA COMPLIANCE VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Summary statistics
    lines.append("SUMMARY STATISTICS")
    lines.append("-" * 70)
    lines.append(f"Total Invoices Processed:  {batch_result.total}")
    lines.append(f"Compliant:                 {batch_result.compliant_count} "
                f"({batch_result.compliant_count/batch_result.total*100:.1f}%)")
    lines.append(f"Non-Compliant:             {batch_result.failed_count} "
                f"({batch_result.failed_count/batch_result.total*100:.1f}%)")
    lines.append(f"Processing Time:           {batch_result.processing_time_seconds:.2f} seconds")
    lines.append(f"Throughput:                {batch_result.total/batch_result.processing_time_seconds:.1f} invoices/sec")
    lines.append("")
    
    # Violation analysis
    if batch_result.failed_count > 0:
        lines.append("COMMON VIOLATIONS")
        lines.append("-" * 70)
        
        # Count violations by code
        violation_counts = Counter()
        for result in batch_result.results:
            if not result.is_compliant:
                for violation in result.violations:
                    violation_counts[violation.code] += 1
        
        # Sort by frequency
        for code, count in violation_counts.most_common(10):
            # Find example message
            example_msg = ""
            for result in batch_result.results:
                for v in result.violations:
                    if v.code == code:
                        example_msg = v.message
                        break
                if example_msg:
                    break
            
            lines.append(f"[{code}] {example_msg}")
            lines.append(f"  Occurrences: {count}")
            lines.append("")
    
    # Non-compliant invoices
    if batch_result.failed_count > 0:
        lines.append("NON-COMPLIANT INVOICES")
        lines.append("-" * 70)
        
        failed_results = [r for r in batch_result.results if not r.is_compliant]
        for result in failed_results[:20]:  # Show first 20
            lines.append(f"Invoice: {result.invoice_number}")
            lines.append(f"  Violations: {len(result.violations)}")
            for violation in result.violations:
                lines.append(f"    - [{violation.code}] {violation.message}")
            lines.append("")
        
        if len(failed_results) > 20:
            lines.append(f"... and {len(failed_results) - 20} more non-compliant invoices")
            lines.append("")
    
    # Footer
    lines.append("=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def generate_csv_report(results: List[ValidationResult], output_path: str):
    """
    Generate CSV report of validation results.
    
    Args:
        results: List of validation results
        output_path: Path to output CSV file
    """
    import csv
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'Invoice Number',
            'Compliant',
            'Violation Count',
            'Violation Codes',
            'Processing Time (ms)'
        ])
        
        # Data rows
        for result in results:
            codes = ','.join(v.code for v in result.violations)
            writer.writerow([
                result.invoice_number,
                'Yes' if result.is_compliant else 'No',
                len(result.violations),
                codes,
                result.processing_time_ms or ''
            ])


def generate_json_report(batch_result: BatchResult, output_path: str):
    """
    Generate JSON report.
    
    Args:
        batch_result: Batch results
        output_path: Output file path
    """
    import json
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(batch_result.dict(), f, indent=2, default=str)
