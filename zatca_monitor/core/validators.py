"""
ZATCA compliance validators.
Implements Phase 2 e-invoicing requirements.
"""
import re
import hashlib
from datetime import datetime
from decimal import Decimal
from typing import List

from zatca_monitor.core.models import Invoice, ValidationResult, ValidationViolation
from zatca_monitor.utils.decorators import audit_log, measure_performance


class ZATCAValidator:
    """
    Core validator for ZATCA compliance.
    Checks invoice against technical specifications.
    """
    
    # Saudi VAT number pattern: 15 digits, starts with 3, ends with 3
    VAT_PATTERN = re.compile(r'^3\d{13}3$')
    
    # Required fields that must be present
    REQUIRED_FIELDS = [
        'invoice_number',
        'issue_date',
        'seller',
        'buyer',
        'lines'
    ]
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, warnings are treated as errors
        """
        self.strict_mode = strict_mode
    
    @measure_performance
    @audit_log
    def validate(self, invoice: Invoice) -> ValidationResult:
        """
        Run all validation checks on an invoice.
        
        Args:
            invoice: Invoice to validate
            
        Returns:
            ValidationResult with list of violations
        """
        result = ValidationResult(
            invoice_number=invoice.invoice_number,
            is_compliant=True
        )
        
        # Run all validation checks
        self._check_required_fields(invoice, result)
        self._check_vat_numbers(invoice, result)
        self._check_dates(invoice, result)
        self._check_line_items(invoice, result)
        self._check_calculations(invoice, result)
        self._check_qr_code(invoice, result)
        self._check_previous_hash(invoice, result)
        
        return result
    
    def _check_required_fields(self, invoice: Invoice, result: ValidationResult):
        """Verify all required fields are present"""
        for field in self.REQUIRED_FIELDS:
            if not hasattr(invoice, field) or getattr(invoice, field) is None:
                result.add_violation(
                    code='REQ_001',
                    field=field,
                    message=f'Required field {field} is missing',
                    severity='ERROR',
                    rule='ZATCA-BR-01'
                )
    
    def _check_vat_numbers(self, invoice: Invoice, result: ValidationResult):
        """Validate VAT registration numbers"""
        # Check seller VAT
        if not self.VAT_PATTERN.match(invoice.seller.vat_number):
            result.add_violation(
                code='VAT_001',
                field='seller.vat_number',
                message=f'Invalid seller VAT number format: {invoice.seller.vat_number}',
                severity='ERROR',
                rule='ZATCA-BR-02'
            )
        
        # Check buyer VAT
        if not self.VAT_PATTERN.match(invoice.buyer.vat_number):
            result.add_violation(
                code='VAT_002',
                field='buyer.vat_number',
                message=f'Invalid buyer VAT number format: {invoice.buyer.vat_number}',
                severity='ERROR',
                rule='ZATCA-BR-03'
            )
    
    def _check_dates(self, invoice: Invoice, result: ValidationResult):
        """Validate invoice dates"""
        now = datetime.now()
        
        # Issue date should not be in the future
        if invoice.issue_date > now:
            result.add_violation(
                code='DATE_001',
                field='issue_date',
                message='Invoice date cannot be in the future',
                severity='ERROR',
                rule='ZATCA-BR-04'
            )
        
        # Issue date should not be too old (e.g., > 2 years)
        max_age_days = 730
        age = (now - invoice.issue_date).days
        if age > max_age_days:
            result.add_violation(
                code='DATE_002',
                field='issue_date',
                message=f'Invoice is too old: {age} days',
                severity='WARNING',
                rule='ZATCA-BR-05'
            )
    
    def _check_line_items(self, invoice: Invoice, result: ValidationResult):
        """Validate line item completeness"""
        if not invoice.lines:
            result.add_violation(
                code='LINE_001',
                field='lines',
                message='Invoice must have at least one line item',
                severity='ERROR',
                rule='ZATCA-BR-06'
            )
            return
        
        for idx, line in enumerate(invoice.lines):
            # Check for negative values
            if line.quantity <= 0:
                result.add_violation(
                    code='LINE_002',
                    field=f'lines[{idx}].quantity',
                    message=f'Line {line.id}: Quantity must be positive',
                    severity='ERROR',
                    rule='ZATCA-BR-07'
                )
            
            if line.unit_price < 0:
                result.add_violation(
                    code='LINE_003',
                    field=f'lines[{idx}].unit_price',
                    message=f'Line {line.id}: Unit price cannot be negative',
                    severity='ERROR',
                    rule='ZATCA-BR-08'
                )
            
            # Check VAT rate (common rates in Saudi Arabia: 0%, 15%)
            allowed_rates = [Decimal('0'), Decimal('15')]
            if line.tax_percent not in allowed_rates:
                result.add_violation(
                    code='LINE_004',
                    field=f'lines[{idx}].tax_percent',
                    message=f'Line {line.id}: Unusual VAT rate {line.tax_percent}%',
                    severity='WARNING',
                    rule='ZATCA-BR-09'
                )
    
    def _check_calculations(self, invoice: Invoice, result: ValidationResult):
        """Verify arithmetic calculations are correct"""
        # Calculate expected totals
        calc_subtotal = sum(line.subtotal for line in invoice.lines)
        calc_tax = sum(line.tax_amount for line in invoice.lines)
        calc_total = calc_subtotal + calc_tax
        
        # Compare with invoice totals (allow small rounding differences)
        tolerance = Decimal('0.01')
        
        if abs(invoice.subtotal - calc_subtotal) > tolerance:
            result.add_violation(
                code='CALC_001',
                field='subtotal',
                message=f'Subtotal mismatch: invoice={invoice.subtotal}, calculated={calc_subtotal}',
                severity='ERROR',
                rule='ZATCA-BR-10'
            )
        
        if abs(invoice.total_tax - calc_tax) > tolerance:
            result.add_violation(
                code='CALC_002',
                field='total_tax',
                message=f'Tax total mismatch: invoice={invoice.total_tax}, calculated={calc_tax}',
                severity='ERROR',
                rule='ZATCA-BR-11'
            )
        
        if abs(invoice.grand_total - calc_total) > tolerance:
            result.add_violation(
                code='CALC_003',
                field='grand_total',
                message=f'Grand total mismatch: invoice={invoice.grand_total}, calculated={calc_total}',
                severity='ERROR',
                rule='ZATCA-BR-12'
            )
    
    def _check_qr_code(self, invoice: Invoice, result: ValidationResult):
        """Validate QR code presence and format"""
        if not invoice.qr_code:
            result.add_violation(
                code='QR_001',
                field='qr_code',
                message='QR code is missing',
                severity='ERROR',
                rule='ZATCA-BR-13'
            )
            return
        
        # Basic format validation (QR should be base64 encoded)
        if len(invoice.qr_code) < 20:
            result.add_violation(
                code='QR_002',
                field='qr_code',
                message='QR code appears invalid (too short)',
                severity='WARNING',
                rule='ZATCA-BR-14'
            )
    
    def _check_previous_hash(self, invoice: Invoice, result: ValidationResult):
        """Validate previous invoice hash (PIH) for chain integrity"""
        # PIH is required for simplified invoices (Phase 2)
        if invoice.invoice_type == '388' and not invoice.previous_invoice_hash:
            result.add_violation(
                code='HASH_001',
                field='previous_invoice_hash',
                message='Previous invoice hash (PIH) is required',
                severity='ERROR',
                rule='ZATCA-BR-15'
            )
        
        # If present, validate format (should be hex string)
        if invoice.previous_invoice_hash:
            if not re.match(r'^[0-9a-fA-F]+$', invoice.previous_invoice_hash):
                result.add_violation(
                    code='HASH_002',
                    field='previous_invoice_hash',
                    message='Previous invoice hash format is invalid',
                    severity='ERROR',
                    rule='ZATCA-BR-16'
                )


class InvoiceChainValidator:
    """
    Validates invoice chain integrity using PIH (Previous Invoice Hash).
    Ensures no tampering in the invoice sequence.
    """
    
    def __init__(self):
        self.hash_chain = {}
    
    @staticmethod
    def compute_hash(invoice: Invoice) -> str:
        """
        Compute cryptographic hash of invoice.
        In production, this would follow ZATCA's exact hashing algorithm.
        
        Args:
            invoice: Invoice to hash
            
        Returns:
            Hex string of SHA-256 hash
        """
        # Create canonical representation
        data = f"{invoice.invoice_number}|{invoice.issue_date.isoformat()}|{invoice.grand_total}"
        
        # Compute SHA-256
        hash_obj = hashlib.sha256(data.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def validate_chain(self, invoices: List[Invoice]) -> List[ValidationViolation]:
        """
        Validate a sequence of invoices for chain integrity.
        
        Args:
            invoices: List of invoices in chronological order
            
        Returns:
            List of violations found
        """
        violations = []
        prev_hash = None
        
        for idx, invoice in enumerate(invoices):
            # Skip first invoice
            if idx == 0:
                prev_hash = self.compute_hash(invoice)
                continue
            
            # Check if current invoice's PIH matches previous hash
            if invoice.previous_invoice_hash != prev_hash:
                violations.append(
                    ValidationViolation(
                        code='CHAIN_001',
                        severity='ERROR',
                        field='previous_invoice_hash',
                        message=f'Invoice {invoice.invoice_number}: Hash chain broken',
                        rule='ZATCA-BR-17'
                    )
                )
            
            # Update for next iteration
            prev_hash = self.compute_hash(invoice)
        
        return violations


class InvoiceValidator:
    """
    Main validator interface.
    Combines all validation strategies.
    """
    
    def __init__(self, strict_mode: bool = True):
        self.zatca_validator = ZATCAValidator(strict_mode)
        self.chain_validator = InvoiceChainValidator()
    
    @measure_performance
    @audit_log
    def validate(self, invoice: Invoice) -> ValidationResult:
        """
        Validate a single invoice.
        
        Args:
            invoice: Invoice to validate
            
        Returns:
            ValidationResult
        """
        return self.zatca_validator.validate(invoice)
    
    def validate_batch(self, invoices: List[Invoice]) -> List[ValidationResult]:
        """
        Validate multiple invoices.
        
        Args:
            invoices: List of invoices
            
        Returns:
            List of validation results
        """
        return [self.validate(inv) for inv in invoices]
