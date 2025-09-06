"""
Unit tests for Excel export functionality.
"""

import unittest
import sys
import os
import pandas as pd
from io import BytesIO

# Add the api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from app.agents.exporter_excel import EXCEL_SCHEMA, _create_excel_file


class TestExcelExport(unittest.TestCase):
    """Test Excel export functionality."""
    
    def test_excel_schema_order(self):
        """Test that Excel schema has correct column order."""
        expected_schema = [
            "NPI",
            "Provider Name",
            "Specialty",
            "Phone",
            "Email",
            "Address",
            "City",
            "State",
            "ZIP",
            "DOB",
            "Effective Date",
            "Term Date",
            "TIN",
            "Group",
            "Network",
            "Tier",
            "Notes"
        ]
        
        self.assertEqual(EXCEL_SCHEMA, expected_schema, "Excel schema should match expected order")
        self.assertEqual(len(EXCEL_SCHEMA), 17, "Excel schema should have exactly 17 columns")
    
    def test_excel_file_creation(self):
        """Test Excel file creation with proper formatting."""
        # Sample data
        records = [
            {
                "NPI": "1234567893",
                "Provider Name": "Dr. John Smith",
                "Specialty": "Internal Medicine",
                "Phone": "(555) 123-4567",
                "Email": "john.smith@example.com",
                "Address": "123 Main St",
                "City": "Anytown",
                "State": "CA",
                "ZIP": "12345",
                "DOB": "01/15/1980",
                "Effective Date": "01/01/2023",
                "Term Date": "",
                "TIN": "123456789",
                "Group": "Group A",
                "Network": "Network 1",
                "Tier": "Tier 1",
                "Notes": "Test provider"
            },
            {
                "NPI": "9876543210",
                "Provider Name": "Dr. Jane Doe",
                "Specialty": "Cardiology",
                "Phone": "(555) 987-6543",
                "Email": "jane.doe@example.com",
                "Address": "456 Oak Ave",
                "City": "Somewhere",
                "State": "NY",
                "ZIP": "67890",
                "DOB": "03/22/1975",
                "Effective Date": "02/01/2023",
                "Term Date": "",
                "TIN": "987654321",
                "Group": "Group B",
                "Network": "Network 2",
                "Tier": "Tier 2",
                "Notes": "Another test provider"
            }
        ]
        
        # Create Excel file
        excel_bytes = _create_excel_file(records, job_id=1, version_id=1)
        
        # Verify file was created
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 0, "Excel file should not be empty")
        
        # Read the Excel file to verify structure
        df = pd.read_excel(BytesIO(excel_bytes), sheet_name=0)
        
        # Verify column order
        self.assertEqual(list(df.columns), EXCEL_SCHEMA, "Excel columns should match schema order")
        
        # Verify data
        self.assertEqual(len(df), 2, "Should have 2 rows of data")
        self.assertEqual(df.iloc[0]["NPI"], "1234567893")
        self.assertEqual(df.iloc[1]["Provider Name"], "Dr. Jane Doe")
    
    def test_excel_data_types(self):
        """Test that Excel file preserves correct data types."""
        records = [
            {
                "NPI": "1234567893",  # Should be text to preserve leading zeros
                "Provider Name": "Dr. John Smith",
                "Specialty": "Internal Medicine",
                "Phone": "(555) 123-4567",
                "Email": "john.smith@example.com",
                "Address": "123 Main St",
                "City": "Anytown",
                "State": "CA",
                "ZIP": "12345",  # Should be text to preserve leading zeros
                "DOB": "01/15/1980",  # Should be date
                "Effective Date": "01/01/2023",  # Should be date
                "Term Date": "",
                "TIN": "123456789",  # Should be text to preserve leading zeros
                "Group": "Group A",
                "Network": "Network 1",
                "Tier": "Tier 1",
                "Notes": "Test provider"
            }
        ]
        
        # Create Excel file
        excel_bytes = _create_excel_file(records, job_id=1, version_id=1)
        
        # Read the Excel file
        df = pd.read_excel(BytesIO(excel_bytes), sheet_name=0)
        
        # Verify data types are preserved
        self.assertEqual(df.iloc[0]["NPI"], "1234567893")
        self.assertEqual(df.iloc[0]["ZIP"], "12345")
        self.assertEqual(df.iloc[0]["TIN"], "123456789")
        
        # Verify dates are properly formatted
        self.assertEqual(str(df.iloc[0]["DOB"]), "1980-01-15 00:00:00")
        self.assertEqual(str(df.iloc[0]["Effective Date"]), "2023-01-01 00:00:00")
    
    def test_excel_provenance_sheet(self):
        """Test that Excel file includes provenance sheet."""
        records = [
            {
                "NPI": "1234567893",
                "Provider Name": "Dr. John Smith",
                "Specialty": "Internal Medicine",
                "Phone": "(555) 123-4567",
                "Email": "john.smith@example.com",
                "Address": "123 Main St",
                "City": "Anytown",
                "State": "CA",
                "ZIP": "12345",
                "DOB": "01/15/1980",
                "Effective Date": "01/01/2023",
                "Term Date": "",
                "TIN": "123456789",
                "Group": "Group A",
                "Network": "Network 1",
                "Tier": "Tier 1",
                "Notes": "Test provider"
            }
        ]
        
        # Create Excel file
        excel_bytes = _create_excel_file(records, job_id=1, version_id=1)
        
        # Read the Excel file and check for provenance sheet
        with pd.ExcelFile(BytesIO(excel_bytes)) as xls:
            sheet_names = xls.sheet_names
            
            # Should have main sheet and provenance sheet
            self.assertIn("_Provenance", sheet_names, "Excel file should have provenance sheet")
            
            # Read provenance sheet
            provenance_df = pd.read_excel(xls, sheet_name="_Provenance")
            
            # Verify provenance data
            self.assertGreater(len(provenance_df), 0, "Provenance sheet should have data")
            
            # Check for key provenance fields
            provenance_data = provenance_df.to_dict('records')[0]
            self.assertEqual(provenance_data["Job ID"], 1)
            self.assertEqual(provenance_data["Version ID"], 1)
            self.assertEqual(provenance_data["Record Count"], 1)
    
    def test_empty_data_handling(self):
        """Test Excel export with empty data."""
        records = []
        
        # Create Excel file with empty data
        excel_bytes = _create_excel_file(records, job_id=1, version_id=1)
        
        # Verify file was created
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 0, "Excel file should be created even with empty data")
        
        # Read the Excel file
        df = pd.read_excel(BytesIO(excel_bytes), sheet_name=0)
        
        # Verify structure is maintained
        self.assertEqual(list(df.columns), EXCEL_SCHEMA, "Excel columns should match schema even with empty data")
        self.assertEqual(len(df), 0, "Should have 0 rows of data")


if __name__ == "__main__":
    unittest.main()
