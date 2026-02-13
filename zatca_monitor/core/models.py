"""
Data models for ZATCA invoice representation.
Using Pydantic for validation and type safety.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class Address(BaseModel):
    """Physical address representation"""
    street: str
    building_number: Optional[str] = None
    additional_number: Optional[str] = None
    city: str
    postal_code: str
    country_code: str = "SA"
    
    @validator('country_code')
    def validate_country(cls, v):
        if len(v) != 2:
            raise ValueError('Country code must be 2 characters')
        return v.upper()


class Party(BaseModel):
    """Seller or Buyer party information"""
    vat_number: str = Field(..., min_length=15, max_length=15)
    name: str
    address: Address
    
    @validator('vat_number')
    def validate_vat(cls, v):
        # Saudi VAT numbers are 15 digits
        if not v.isdigit():
            raise ValueError('VAT number must be numeric')
        return v


class InvoiceLine(BaseModel):
    """Single line item in invoice"""
    id: str
    description: str
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    tax_percent: Decimal = Field(..., ge=0, le=100)
    discount: Decimal = Field(default=Decimal('0'), ge=0)
    
    @property
    def subtotal(self) -> Decimal:
        return self.quantity * self.unit_price - self.discount
    
    @property
    def tax_amount(self) -> Decimal:
        return self.subtotal * (self.tax_percent / Decimal('100'))
    
    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax_amount


class Invoice(BaseModel):
    """Complete invoice representation"""
    invoice_number: str
    issue_date: datetime
    invoice_type: str  # 388 (standard), 381 (credit note), 383 (debit note)
    
    seller: Party
    buyer: Party
    
    lines: List[InvoiceLine] = Field(..., min_items=1)
    
    # ZATCA specific fields
    previous_invoice_hash: Optional[str] = None
    qr_code: Optional[str] = None
    cryptographic_stamp: Optional[str] = None
    
    @property
    def subtotal(self) -> Decimal:
        return sum(line.subtotal for line in self.lines)
    
    @property
    def total_tax(self) -> Decimal:
        return sum(line.tax_amount for line in self.lines)
    
    @property
    def grand_total(self) -> Decimal:
        return self.subtotal + self.total_tax
    
    @validator('invoice_type')
    def validate_type(cls, v):
        allowed = ['388', '381', '383']
        if v not in allowed:
            raise ValueError(f'Invoice type must be one of {allowed}')
        return v


class ValidationViolation(BaseModel):
    """Represents a single compliance violation"""
    code: str
    severity: str  # ERROR, WARNING
    field: str
    message: str
    rule: str


class ValidationResult(BaseModel):
    """Result of invoice validation"""
    invoice_number: str
    timestamp: datetime = Field(default_factory=datetime.now)
    is_compliant: bool
    violations: List[ValidationViolation] = []
    processing_time_ms: Optional[float] = None
    
    def add_violation(self, code: str, field: str, message: str, 
                     severity: str = "ERROR", rule: str = ""):
        """Helper to add violation"""
        violation = ValidationViolation(
            code=code,
            severity=severity,
            field=field,
            message=message,
            rule=rule
        )
        self.violations.append(violation)
        if severity == "ERROR":
            self.is_compliant = False


class BatchResult(BaseModel):
    """Result of batch processing"""
    total: int = 0
    compliant_count: int = 0
    failed_count: int = 0
    processing_time_seconds: float = 0.0
    results: List[ValidationResult] = []
    
    def add_result(self, result: ValidationResult):
        self.results.append(result)
        self.total += 1
        if result.is_compliant:
            self.compliant_count += 1
        else:
            self.failed_count += 1
