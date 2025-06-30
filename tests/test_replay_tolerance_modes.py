import unittest
import sys
import os
from datetime import datetime
import uuid

# Ensure root directory is in sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import your verifier class
from verifier.enhanced_snapshot_verifier import EnhancedSnapshotVerifier


class TestReplayToleranceModes(unittest.TestCase):

    def test_timestamp_drift_passes_in_tolerant_mode(self):
        """✅ TC1: Tolerant mode allows timestamp drift (4s)"""
        verifier = EnhancedSnapshotVerifier()
        verifier.setStrict(False)

        recorded = {"created_at": "2024-06-10T12:00:00Z"}
        expected = {"created_at": "2024-06-10T12:00:04Z"}

        self.assertTrue(verifier.verify(recorded, expected))

    def test_uuid_fails_in_strict_mode(self):
        """✅ TC2: Strict mode fails on different UUIDs"""
        verifier = EnhancedSnapshotVerifier()
        verifier.setStrict(True)

        recorded = {"orderId": "123e4567-e89b-12d3-a456-426614174000"}
        expected = {"orderId": "999e4567-e89b-12d3-a456-426614174000"}

        self.assertFalse(verifier.verify(recorded, expected))

    def test_uuid_passes_in_tolerant_mode(self):
        """✅ TC3: Tolerant mode ignores UUID differences"""
        verifier = EnhancedSnapshotVerifier()
        verifier.setStrict(False)

        recorded = {"orderId": "123e4567-e89b-12d3-a456-426614174000"}
        expected = {"orderId": "999e4567-e89b-12d3-a456-426614174000"}

        self.assertTrue(verifier.verify(recorded, expected))


if __name__ == "__main__":
    unittest.main(verbosity=2)
