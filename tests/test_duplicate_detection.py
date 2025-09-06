"""
Unit tests for duplicate NPI detection.
"""

import unittest
import sys
import os

# Add the api directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from app.agents.validator import _validate_row


class TestDuplicateDetection(unittest.TestCase):
    """Test duplicate NPI detection in validation."""
    
    def test_duplicate_npi_detection(self):
        """Test detection of duplicate NPIs in a dataset."""
        # Create a set to track NPIs (simulating the npi_set parameter)
        npi_set = set()
        
        # First occurrence of NPI should be valid
        row_data_1 = {
            "NPI": "1234567893",
            "Provider Name": "Dr. John Smith",
            "Specialty": "Internal Medicine",
            "Effective Date": "01/01/2023"
        }
        
        issues_1 = _validate_row(row_data_1, 0, npi_set)
        
        # Should have no duplicate issues
        duplicate_issues = [issue for issue in issues_1 if "duplicate" in issue.get("message", "").lower()]
        self.assertEqual(len(duplicate_issues), 0, "First NPI should not be flagged as duplicate")
        
        # Second occurrence of same NPI should be flagged as duplicate
        row_data_2 = {
            "NPI": "1234567893",  # Same NPI
            "Provider Name": "Dr. Jane Doe",
            "Specialty": "Cardiology",
            "Effective Date": "01/01/2023"
        }
        
        issues_2 = _validate_row(row_data_2, 1, npi_set)
        
        # Should have duplicate issue
        duplicate_issues = [issue for issue in issues_2 if "duplicate" in issue.get("message", "").lower()]
        self.assertGreater(len(duplicate_issues), 0, "Duplicate NPI should be flagged")
        
        # Check that the duplicate issue has correct details
        duplicate_issue = duplicate_issues[0]
        self.assertEqual(duplicate_issue["field"], "NPI")
        self.assertEqual(duplicate_issue["level"], "error")
        self.assertIn("duplicate", duplicate_issue["message"].lower())
    
    def test_multiple_duplicates(self):
        """Test detection of multiple duplicate NPIs."""
        npi_set = set()
        
        # Add first NPI
        row_data_1 = {
            "NPI": "1234567893",
            "Provider Name": "Dr. John Smith",
            "Specialty": "Internal Medicine",
            "Effective Date": "01/01/2023"
        }
        _validate_row(row_data_1, 0, npi_set)
        
        # Add second unique NPI
        row_data_2 = {
            "NPI": "9876543210",
            "Provider Name": "Dr. Jane Doe",
            "Specialty": "Cardiology",
            "Effective Date": "01/01/2023"
        }
        _validate_row(row_data_2, 1, npi_set)
        
        # Try to add first NPI again (should be duplicate)
        row_data_3 = {
            "NPI": "1234567893",  # Duplicate of first
            "Provider Name": "Dr. Bob Wilson",
            "Specialty": "Dermatology",
            "Effective Date": "01/01/2023"
        }
        issues_3 = _validate_row(row_data_3, 2, npi_set)
        
        # Try to add second NPI again (should be duplicate)
        row_data_4 = {
            "NPI": "9876543210",  # Duplicate of second
            "Provider Name": "Dr. Alice Brown",
            "Specialty": "Pediatrics",
            "Effective Date": "01/01/2023"
        }
        issues_4 = _validate_row(row_data_4, 3, npi_set)
        
        # Both should have duplicate issues
        duplicate_issues_3 = [issue for issue in issues_3 if "duplicate" in issue.get("message", "").lower()]
        duplicate_issues_4 = [issue for issue in issues_4 if "duplicate" in issue.get("message", "").lower()]
        
        self.assertGreater(len(duplicate_issues_3), 0, "Third row should have duplicate issue")
        self.assertGreater(len(duplicate_issues_4), 0, "Fourth row should have duplicate issue")
    
    def test_case_insensitive_duplicate_detection(self):
        """Test that duplicate detection is case-insensitive for NPIs."""
        npi_set = set()
        
        # Add first NPI
        row_data_1 = {
            "NPI": "1234567893",
            "Provider Name": "Dr. John Smith",
            "Specialty": "Internal Medicine",
            "Effective Date": "01/01/2023"
        }
        _validate_row(row_data_1, 0, npi_set)
        
        # Try to add same NPI with different case (should still be duplicate)
        row_data_2 = {
            "NPI": "1234567893",  # Same NPI, same case
            "Provider Name": "Dr. Jane Doe",
            "Specialty": "Cardiology",
            "Effective Date": "01/01/2023"
        }
        issues_2 = _validate_row(row_data_2, 1, npi_set)
        
        # Should have duplicate issue
        duplicate_issues = [issue for issue in issues_2 if "duplicate" in issue.get("message", "").lower()]
        self.assertGreater(len(duplicate_issues), 0, "Duplicate NPI should be detected regardless of case")
    
    def test_empty_npi_not_duplicate(self):
        """Test that empty NPIs are not considered duplicates."""
        npi_set = set()
        
        # Add row with empty NPI
        row_data_1 = {
            "NPI": "",
            "Provider Name": "Dr. John Smith",
            "Specialty": "Internal Medicine",
            "Effective Date": "01/01/2023"
        }
        issues_1 = _validate_row(row_data_1, 0, npi_set)
        
        # Add another row with empty NPI
        row_data_2 = {
            "NPI": "",
            "Provider Name": "Dr. Jane Doe",
            "Specialty": "Cardiology",
            "Effective Date": "01/01/2023"
        }
        issues_2 = _validate_row(row_data_2, 1, npi_set)
        
        # Neither should have duplicate issues (empty NPIs are handled by required field validation)
        duplicate_issues_1 = [issue for issue in issues_1 if "duplicate" in issue.get("message", "").lower()]
        duplicate_issues_2 = [issue for issue in issues_2 if "duplicate" in issue.get("message", "").lower()]
        
        self.assertEqual(len(duplicate_issues_1), 0, "Empty NPI should not be flagged as duplicate")
        self.assertEqual(len(duplicate_issues_2), 0, "Empty NPI should not be flagged as duplicate")


if __name__ == "__main__":
    unittest.main()
