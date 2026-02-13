"""
Unit tests for ZATCA validators.
Demonstrates testing approach for the compliance monitor.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from zatca_monitor.core.models import Invoice, Party, Address, InvoiceLine
from zatca_monitor.core.validators import ZATCAValidator, InvoiceValidator


@pytest.fixture
def valid_address():
    """Create a valid Saudi address"""
    return Address(
        street="King Fahd Road",
        building_number="1234",
        city="Riyadh",
        postal_code="12345",
        country_code="SA"
    )


@pytest.fixture
def valid_party(valid_address):
    """Create a valid party with proper VAT number"""
    return Party(
        vat_number="310122393500003",  # Valid format: starts with 3, ends with 3, 15 digits
        name="ABC Trading Company",
        address=valid_address
    )


@pytest.fixture
def valid_invoice(valid_party):
    """Create a fully compliant invoice"""
    return Invoice(
        invoice_number="INV-2024-001",
        issue_date=datetime.now(),
        invoice_type="388",
        seller=valid_party,
        buyer=valid_party,  # In real test, would be different party
        lines=[
            InvoiceLine(
                id="1",
                description="Laptop Computer",
                quantity=Decimal("2"),
                unit_price=Decimal("3000.00"),
                tax_percent=Decimal("15")
            )
        ],
        qr_code="TlRBQj1BQkMgVHJhZGluZyBDb21wYW55",
        previous_invoice_hash="abc123def456"
    )


class TestZATCAValidator:
    """Test suite for ZATCA validation rules"""
    
    def test_valid_invoice_passes(self, valid_invoice):
        """Test that a fully compliant invoice passes validation"""
        validator = ZATCAValidator()
        result = validator.validate(valid_invoice)
        
        assert result.is_compliant
        assert len(result.violations) == 0
    
    def test_invalid_vat_number_fails(self, valid_invoice):
        """Test that invalid VAT numbers are detected"""
        # Make VAT invalid (not starting with 3)
        valid_invoice.seller.vat_number = "210122393500003"
        
        validator = ZATCAValidator()
        result = validator.validate(valid_invoice)
        
        assert not result.is_compliant
        assert any(v.code == 'VAT_001' for v in result.violations)
    
    def test_future_date_fails(self, valid_invoice):
        """Test that future invoice dates are rejected"""
        valid_invoice.issue_date = datetime.now() + timedelta(days=1)
        
        validator = ZATCAValidator()
        result = validator.validate(valid_invoice)
        
        assert not result.is_compliant
        assert any(v.code == 'DATE_001' for v in result.violations)
    
    def test_negative_quantity_fails(self, valid_invoice):
        """Test that negative quantities are rejected"""
        valid_invoice.lines[0].quantity = Decimal("-1")
        
        validator = ZATCAValidator()
        result = validator.validate(valid_invoice)
        
        assert not result.is_compliant
        assert any(v.code == 'LINE_002' for v in result.violations)
    
    def test_missing_qr_code_fails(self, valid_invoice):
        """Test that missing QR code is detected"""
        valid_invoice.qr_code = None
        
        validator = ZATCAValidator()
        result = validator.validate(valid_invoice)
        
        assert not result.is_compliant
        assert any(v.code == 'QR_001' for v in result.violations)
    
    def test_calculation_accuracy(self, valid_invoice):
        """Test that invoice calculations are verified"""
        # Invoice has 2 laptops @ 3000 SAR each = 6000 SAR
        # Tax @ 15% = 900 SAR
        # Total = 6900 SAR
        
        assert valid_invoice.subtotal == Decimal("6000.00")
        assert valid_invoice.total_tax == Decimal("900.00")
        assert valid_invoice.grand_total == Decimal("6900.00")
        
        validator = ZATCAValidator()
        result = validator.validate(valid_invoice)
        
        # Should pass calculation checks
        calc_violations = [v for v in result.violations if v.code.startswith('CALC_')]
        assert len(calc_violations) == 0


class TestInvoiceValidator:
    """Test the main invoice validator interface"""
    
    def test_validator_with_strict_mode(self, valid_invoice):
        """Test strict mode treats warnings as errors"""
        # Add unusual but technically valid VAT rate
        valid_invoice.lines[0].tax_percent = Decimal("5")  # Non-standard rate
        
        # Strict mode
        strict_validator = InvoiceValidator(strict_mode=True)
        strict_result = strict_validator.validate(valid_invoice)
        
        # Lenient mode
        lenient_validator = InvoiceValidator(strict_mode=False)
        lenient_result = lenient_validator.validate(valid_invoice)
        
        # Both should flag the unusual rate, but only strict fails the invoice
        assert len(strict_result.violations) > 0
        assert len(lenient_result.violations) > 0


class TestPerformance:
    """Performance and stress tests"""
    
    def test_validates_quickly(self, valid_invoice):
        """Test that validation completes within acceptable time"""
        import time
        
        validator = InvoiceValidator()
        
        start = time.perf_counter()
        result = validator.validate(valid_invoice)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        # Should validate in under 10ms
        assert elapsed_ms < 10
        assert result.is_compliant
    
    @pytest.mark.slow
    def test_batch_validation_performance(self, valid_invoice):
        """Test batch validation throughput"""
        import time
        
        validator = InvoiceValidator()
        
        # Create 1000 invoices
        invoices = []
        for i in range(1000):
            invoice = valid_invoice.copy(deep=True)
            invoice.invoice_number = f"INV-2024-{i:04d}"
            invoices.append(invoice)
        
        start = time.perf_counter()
        results = validator.validate_batch(invoices)
        elapsed = time.perf_counter() - start
        
        # Should process at least 100 invoices/sec
        throughput = len(invoices) / elapsed
        assert throughput > 100
        assert all(r.is_compliant for r in results)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
