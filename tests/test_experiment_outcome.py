"""A process exit0 alone must not pass a partial or infrastructure-failed experiment."""
import unittest
from opsdesk.experiment import harbor_outcome

class ExperimentOutcomeTests(unittest.TestCase):
    def test_only_complete_healthy_trials_pass(self):
        summary, rc = harbor_outcome({'n_completed_trials':3}, 0, 0, 3)
        self.assertEqual(rc, 0)
        self.assertEqual(summary['expected_trials'], 3)
        for bad in [
            {'n_completed_trials':1,'n_cancelled_trials':2},
            {'n_completed_trials':1},
            {'n_completed_trials':3,'n_errored_trials':1},
            {'n_completed_trials':1,'n_running_trials':2},
            {'n_completed_trials':1,'n_pending_trials':2},
        ]:
            with self.subTest(bad=bad):
                self.assertNotEqual(harbor_outcome(bad,0,0,3)[1],0)
    def test_verifier_and_process_errors_propagate(self):
        self.assertNotEqual(harbor_outcome({'n_completed_trials':3},1,0,3)[1],0)
        self.assertEqual(harbor_outcome({'n_completed_trials':3},0,2,3)[1],2)

if __name__ == '__main__':
    unittest.main()
