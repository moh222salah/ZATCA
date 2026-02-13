"""
Invoice parsers for XML and JSON formats.
Uses generators for memory-efficient batch processing.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Generator, Union
import xmltodict

from zatca_monitor.core.models import Invoice, Party, Address, InvoiceLine
from zatca_monitor.utils.decorators import audit_log, measure_performance


class ParserError(Exception):
    """Raised when invoice parsing fails"""
    pass


class XMLInvoiceParser:
    """
    Parser for UBL 2.1 XML invoices.
    Follows ZATCA technical specifications.
    """
    
    # UBL namespace (common in e-invoicing)
    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
    }
    
    @staticmethod
    def _get_text(element, xpath: str, default: str = "") -> str:
        """Safely extract text from XML element"""
        found = element.find(xpath, XMLInvoiceParser.NAMESPACES)
        return found.text if found is not None else default
    
    @staticmethod
    def _parse_party(party_element) -> Party:
        """Extract party (seller/buyer) information"""
        vat = XMLInvoiceParser._get_text(
            party_element, 
            './/cbc:CompanyID'
        )
        name = XMLInvoiceParser._get_text(
            party_element,
            './/cbc:RegistrationName'
        )
        
        # Parse address
        addr_elem = party_element.find('.//cac:PostalAddress', 
                                       XMLInvoiceParser.NAMESPACES)
        address = Address(
            street=XMLInvoiceParser._get_text(addr_elem, './/cbc:StreetName'),
            building_number=XMLInvoiceParser._get_text(addr_elem, './/cbc:BuildingNumber'),
            city=XMLInvoiceParser._get_text(addr_elem, './/cbc:CityName'),
            postal_code=XMLInvoiceParser._get_text(addr_elem, './/cbc:PostalZone'),
            country_code=XMLInvoiceParser._get_text(addr_elem, './/cbc:Country/cbc:IdentificationCode', 'SA')
        )
        
        return Party(vat_number=vat, name=name, address=address)
    
    @measure_performance
    @audit_log
    def parse(self, file_path: Union[str, Path]) -> Invoice:
        """
        Parse single XML invoice file.
        
        Args:
            file_path: Path to XML file
            
        Returns:
            Invoice object
            
        Raises:
            ParserError: If parsing fails
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Extract basic invoice info
            invoice_number = self._get_text(root, './/cbc:ID')
            issue_date_str = self._get_text(root, './/cbc:IssueDate')
            invoice_type = self._get_text(root, './/cbc:InvoiceTypeCode', '388')
            
            # Parse date
            from dateutil.parser import parse as parse_date
            issue_date = parse_date(issue_date_str)
            
            # Extract parties
            seller_elem = root.find('.//cac:AccountingSupplierParty/cac:Party', 
                                   self.NAMESPACES)
            buyer_elem = root.find('.//cac:AccountingCustomerParty/cac:Party',
                                  self.NAMESPACES)
            
            seller = self._parse_party(seller_elem)
            buyer = self._parse_party(buyer_elem)
            
            # Extract line items
            lines = []
            for line_elem in root.findall('.//cac:InvoiceLine', self.NAMESPACES):
                line = InvoiceLine(
                    id=self._get_text(line_elem, './/cbc:ID'),
                    description=self._get_text(line_elem, './/cbc:Name'),
                    quantity=self._get_text(line_elem, './/cbc:InvoicedQuantity', '0'),
                    unit_price=self._get_text(line_elem, './/cbc:Price/cbc:PriceAmount', '0'),
                    tax_percent=self._get_text(line_elem, './/cac:TaxTotal/cac:TaxSubtotal/cbc:Percent', '15')
                )
                lines.append(line)
            
            # ZATCA specific fields
            prev_hash = self._get_text(root, './/cbc:UUID')
            qr_code = self._get_text(root, './/cbc:EmbeddedDocumentBinaryObject')
            
            return Invoice(
                invoice_number=invoice_number,
                issue_date=issue_date,
                invoice_type=invoice_type,
                seller=seller,
                buyer=buyer,
                lines=lines,
                previous_invoice_hash=prev_hash or None,
                qr_code=qr_code or None
            )
            
        except Exception as e:
            raise ParserError(f"Failed to parse XML invoice: {str(e)}") from e


class JSONInvoiceParser:
    """Parser for JSON-formatted invoices"""
    
    @measure_performance
    @audit_log
    def parse(self, file_path: Union[str, Path]) -> Invoice:
        """
        Parse single JSON invoice file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Invoice object
            
        Raises:
            ParserError: If parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Direct mapping from JSON to model
            return Invoice(**data)
            
        except Exception as e:
            raise ParserError(f"Failed to parse JSON invoice: {str(e)}") from e


def parse_invoice_file(file_path: Union[str, Path]) -> Invoice:
    """
    Auto-detect format and parse invoice file.
    
    Args:
        file_path: Path to invoice file (XML or JSON)
        
    Returns:
        Parsed Invoice object
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Invoice file not found: {file_path}")
    
    suffix = path.suffix.lower()
    
    if suffix == '.xml':
        parser = XMLInvoiceParser()
    elif suffix == '.json':
        parser = JSONInvoiceParser()
    else:
        raise ParserError(f"Unsupported file format: {suffix}")
    
    return parser.parse(file_path)


def invoice_generator(directory: Union[str, Path], 
                     pattern: str = "*") -> Generator[Invoice, None, None]:
    """
    Generator that yields parsed invoices from a directory.
    Memory-efficient for processing thousands of files.
    
    Args:
        directory: Directory containing invoice files
        pattern: Glob pattern for file matching (e.g., "*.xml")
        
    Yields:
        Parsed Invoice objects
        
    Example:
        for invoice in invoice_generator('invoices/', '*.xml'):
            validate(invoice)
    """
    dir_path = Path(directory)
    
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    # Find all matching files
    for file_path in dir_path.glob(pattern):
        if file_path.is_file():
            try:
                yield parse_invoice_file(file_path)
            except ParserError as e:
                # Log error but continue processing other files
                import logging
                logging.error(f"Failed to parse {file_path}: {e}")
                continue


def batch_invoice_generator(directory: Union[str, Path],
                            batch_size: int = 100,
                            pattern: str = "*") -> Generator[list, None, None]:
    """
    Generator that yields batches of invoices.
    Useful for bulk processing with threading pools.
    
    Args:
        directory: Directory containing invoice files
        batch_size: Number of invoices per batch
        pattern: Glob pattern for file matching
        
    Yields:
        Lists of Invoice objects (batches)
        
    Example:
        for batch in batch_invoice_generator('invoices/', batch_size=50):
            process_batch(batch)  # Process 50 invoices at once
    """
    batch = []
    
    for invoice in invoice_generator(directory, pattern):
        batch.append(invoice)
        
        if len(batch) >= batch_size:
            yield batch
            batch = []
    
    # Yield remaining invoices
    if batch:
        yield batch


def load_invoice(file_path: Union[str, Path]) -> Invoice:
    """
    Convenience function to load a single invoice.
    Alias for parse_invoice_file.
    """
    return parse_invoice_file(file_path)
