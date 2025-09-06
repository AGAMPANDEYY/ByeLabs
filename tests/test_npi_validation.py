"""
Unit tests for NPI validation and Luhn algorithm.
"""

import unittest
import sys
import os

# Add the api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from app.agents.normalizer import _normalize_npi, _is_valid_npi_checksum


class TestNPIValidation(unittest.TestCase):
    """Test NPI validation and Luhn algorithm."""
    
    def test_valid_npi_format(self):
        """Test valid NPI format detection."""
        # Valid 10-digit NPI
        self.assertTrue(_is_valid_npi_format("1234567890"))
        self.assertTrue(_is_valid_npi_format("9876543210"))
        
        # Invalid formats
        self.assertFalse(_is_valid_npi_format("123456789"))  # Too short
        self.assertFalse(_is_valid_npi_format("12345678901"))  # Too long
        self.assertFalse(_is_valid_npi_format("123456789a"))  # Contains letter
        self.assertFalse(_is_valid_npi_format("123-456-7890"))  # Contains dash
        self.assertFalse(_is_valid_npi_format(""))  # Empty
    
    def test_npi_luhn_algorithm(self):
        """Test NPI Luhn checksum validation."""
        # Valid NPIs (these should pass Luhn check)
        valid_npis = [
            "1234567893",  # Valid Luhn
            "9876543210",  # Valid Luhn
            "1234567890",  # Valid Luhn
        ]
        
        for npi in valid_npis:
            with self.subTest(npi=npi):
                result = _is_valid_npi_checksum(npi)
                self.assertTrue(result, f"NPI {npi} should be valid")
        
        # Invalid NPIs (these should fail Luhn check)
        invalid_npis = [
            "1234567891",  # Invalid Luhn
            "9876543211",  # Invalid Luhn
            "0000000000",  # Invalid Luhn
        ]
        
        for npi in invalid_npis:
            with self.subTest(npi=npi):
                result = _is_valid_npi_checksum(npi)
                self.assertFalse(result, f"NPI {npi} should be invalid")
    
    def test_npi_normalization(self):
        """Test NPI normalization with various inputs."""
        test_cases = [
            # (input, expected_normalized, expected_valid)
            ("1234567893", "1234567893", True),
            ("123-456-7893", "1234567893", True),
            ("123 456 7893", "1234567893", True),
            ("(123) 456-7893", "1234567893", True),
            ("1234567891", "1234567891", False),  # Invalid Luhn
            ("123456789", "123456789", False),    # Too short
            ("abc123def", "123", False),          # Contains letters
            ("", "", False),                      # Empty
        ]
        
        for input_npi, expected_norm, expected_valid in test_cases:
            with self.subTest(input=input_npi):
                normalized, delta = _normalize_npi(input_npi)
                
                self.assertEqual(normalized, expected_norm)
                self.assertEqual(delta["is_valid"], expected_valid)
                self.assertEqual(delta["original_value"], input_npi)
                self.assertEqual(delta["normalized_value"], expected_norm)
    
    def test_npi_with_80840_prefix(self):
        """Test NPI normalization with 80840 prefix logic."""
        # Test cases with 80840 prefix
        test_cases = [
            ("8084012345", "8084012345", True),   # Valid with prefix
            ("8084012346", "8084012346", False),  # Invalid with prefix
        ]
        
        for input_npi, expected_norm, expected_valid in test_cases:
            with self.subTest(input=input_npi):
                normalized, delta = _normalize_npi(input_npi)
                
                self.assertEqual(normalized, expected_norm)
                self.assertEqual(delta["is_valid"], expected_valid)
                self.assertTrue(delta["has_80840_prefix"])


def _is_valid_npi_format(npi: str) -> bool:
    """Helper function to validate NPI format."""
    if not npi or len(npi) != 10:
        return False
    return npi.isdigit()


if __name__ == "__main__":
    unittest.main()
