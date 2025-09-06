"""
Unit tests for phone and date normalization.
"""

import unittest
import sys
import os
from datetime import datetime

# Add the api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from app.agents.normalizer import _normalize_phone, _normalize_date


class TestPhoneNormalization(unittest.TestCase):
    """Test phone number normalization."""
    
    def test_phone_normalization(self):
        """Test phone number normalization with various formats."""
        test_cases = [
            # (input, expected_normalized, expected_e164)
            ("(555) 123-4567", "(555) 123-4567", "+15551234567"),
            ("555-123-4567", "(555) 123-4567", "+15551234567"),
            ("555.123.4567", "(555) 123-4567", "+15551234567"),
            ("5551234567", "(555) 123-4567", "+15551234567"),
            ("+1 555 123 4567", "(555) 123-4567", "+15551234567"),
            ("1-555-123-4567", "(555) 123-4567", "+15551234567"),
            ("", "", ""),  # Empty
            ("invalid", "invalid", ""),  # Invalid
        ]
        
        for input_phone, expected_norm, expected_e164 in test_cases:
            with self.subTest(input=input_phone):
                normalized, delta = _normalize_phone(input_phone)
                
                self.assertEqual(normalized, expected_norm)
                self.assertEqual(delta["e164_reference"], expected_e164)
                self.assertEqual(delta["original_value"], input_phone)
                self.assertEqual(delta["normalized_value"], expected_norm)
    
    def test_international_phone(self):
        """Test international phone number handling."""
        test_cases = [
            ("+44 20 7946 0958", "+44 20 7946 0958", "+442079460958"),  # UK
            ("+33 1 42 86 83 26", "+33 1 42 86 83 26", "+33142868326"),  # France
        ]
        
        for input_phone, expected_norm, expected_e164 in test_cases:
            with self.subTest(input=input_phone):
                normalized, delta = _normalize_phone(input_phone)
                
                # International numbers should be preserved as-is
                self.assertEqual(normalized, expected_norm)
                self.assertEqual(delta["e164_reference"], expected_e164)


class TestDateNormalization(unittest.TestCase):
    """Test date normalization."""
    
    def test_date_normalization(self):
        """Test date normalization with various formats."""
        test_cases = [
            # (input, expected_normalized)
            ("01/15/2023", "01/15/2023"),
            ("1/15/2023", "01/15/2023"),
            ("01-15-2023", "01/15/2023"),
            ("2023-01-15", "01/15/2023"),
            ("January 15, 2023", "01/15/2023"),
            ("Jan 15, 2023", "01/15/2023"),
            ("15 Jan 2023", "01/15/2023"),
            ("2023/01/15", "01/15/2023"),
            ("", ""),  # Empty
            ("invalid", "invalid"),  # Invalid
        ]
        
        for input_date, expected_norm in test_cases:
            with self.subTest(input=input_date):
                normalized, delta = _normalize_date(input_date)
                
                self.assertEqual(normalized, expected_norm)
                self.assertEqual(delta["original_value"], input_date)
                self.assertEqual(delta["normalized_value"], expected_norm)
    
    def test_date_edge_cases(self):
        """Test date normalization edge cases."""
        test_cases = [
            ("12/31/2023", "12/31/2023"),  # End of year
            ("01/01/2023", "01/01/2023"),  # Start of year
            ("02/29/2024", "02/29/2024"),  # Leap year
            ("13/01/2023", "13/01/2023"),  # Invalid month (should preserve)
        ]
        
        for input_date, expected_norm in test_cases:
            with self.subTest(input=input_date):
                normalized, delta = _normalize_date(input_date)
                
                self.assertEqual(normalized, expected_norm)
                self.assertEqual(delta["original_value"], input_date)
                self.assertEqual(delta["normalized_value"], expected_norm)


if __name__ == "__main__":
    unittest.main()
