"""Regeneration must never mutate task assets that an active Harbor run may read later."""
import tempfile
import unittest
from pathlib import Path
from opsdesk.make_harbor import build

class TaskGenerationTests(unittest.TestCase):
    def test_existing_task_aborts_before_any_output_is_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            old = out/'ops-desk-standard-seed1'
            old.mkdir()
            marker = old/'instruction.md'
            marker.write_text('Frozen task used by an active run.\n')
            with self.assertRaises(FileExistsError):
                build([2,1], 'standard', out, 10800)
            self.assertEqual(marker.read_text(), 'Frozen task used by an active run.\n')
            self.assertFalse((out/'ops-desk-standard-seed2').exists())

if __name__ == '__main__':
    unittest.main()
