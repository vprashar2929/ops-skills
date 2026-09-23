"""Keep shared operational guidance consistent without evaluation tooling."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OperationalContractTests(unittest.TestCase):
    def test_shared_operational_guidance_stays_consistent(self):
        contracts = sorted((ROOT / "skills").glob("*/references/operations.md"))
        self.assertEqual(len(contracts), 8)
        for contract in contracts[1:]:
            self.assertEqual(contract.read_bytes(), contracts[0].read_bytes(), str(contract))


if __name__ == "__main__":
    unittest.main()
