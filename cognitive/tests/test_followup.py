"""F09-F11 exposed DEVELOPMENT regressions; host contracts are synthetic."""
import copy
import unittest
from cognitive import runtime as v
from cognitive.tests import test_runtime as fixtures


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RuntimeTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def tasks(self, status):
        return [dict(item_id='A', prerequisites=[], status='BLOCKED'),
                dict(item_id='B', prerequisites=['A'], status=status),
                dict(item_id='C', prerequisites=['B'], status='READY')]

    def test_f09_impossible_completed_and_in_progress_states_block(self):
        for status in ('COMPLETED', 'IN_PROGRESS'):
            with self.subTest(status=status), self.assertRaisesRegex(v.ContractError, 'IMPOSSIBLE_TASK_STATE'):
                v.next_ready(self.tasks(status))

    def test_f09_consistent_chain_and_external_prerequisites_work(self):
        tasks = self.tasks('COMPLETED')
        tasks[0]['status'] = 'COMPLETED'
        self.assertEqual(v.next_ready(tasks)['item_id'], 'C')
        tasks[0]['prerequisites'] = ['HOST_VERIFIED_CAPABILITY']
        with self.assertRaisesRegex(v.ContractError, 'UNKNOWN_DEPENDENCY'):
            v.next_ready(tasks)
        self.assertEqual(v.next_ready(tasks, frozenset({'HOST_VERIFIED_CAPABILITY'}))['item_id'], 'C')

    def test_f10_large_integer_and_recursive_encoding_are_structured(self):
        with self.assertRaisesRegex(v.ContractError, 'INVALID_JSON'):
            v.parse_json(b'{"n":' + b'1' * 5000 + b'}')
        deep = {}
        for _ in range(2000):
            deep = {'next': deep}
        with self.assertRaisesRegex(v.ContractError, 'INVALID_JSON_VALUE'):
            v.canonical(deep)
        with self.assertRaisesRegex(v.ContractError, 'DUPLICATE_JSON_KEY'):
            v.parse_json(b'{"id":1,"id":2}')

    def test_f10_checkpoint_bad_types_are_structured(self):
        for field in ('execution_state', 'holdout_exposure'):
            for value in ([], {}, None, 1, True):
                cp, kwargs = self.fixture.checkpoint()
                cp[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(v.ContractError):
                    v.verify_checkpoint(self.fixture.snapshot, cp, **kwargs)

    def test_f10_integer_limits_preserve_compression_roundtrip(self):
        for number in (10 ** 1024 - 1, -(10 ** 1024 - 1)):
            state = {'n': number}
            encoded = v.compress_state(state)
            self.assertEqual(v.reconstruct_state(encoded, v.sha256(v.canonical(state))), state)
        for number in (10 ** 1024, -(10 ** 1024)):
            with self.assertRaisesRegex(v.ContractError, 'INVALID_JSON_INTEGER_SIZE'):
                v.compress_state({'n': number})

    def test_f10_explicit_nesting_boundary_and_cycles(self):
        state = {}
        for _ in range(128):
            state = {'next': state}
        self.assertEqual(v.parse_json(v.canonical(state)), state)
        with self.assertRaisesRegex(v.ContractError, 'INVALID_JSON_VALUE'):
            v.canonical({'next': state})
        cycle = {}
        cycle['next'] = cycle
        with self.assertRaisesRegex(v.ContractError, 'INVALID_JSON_VALUE'):
            v.canonical(cycle)

    def test_f10_task_status_bad_types_are_structured(self):
        for value in ([], {}, None, 1, True):
            with self.subTest(value=value), self.assertRaisesRegex(v.ContractError, 'UNKNOWN_TASK_STATUS'):
                v.next_ready([dict(item_id='A', prerequisites=[], status=value)])

    def test_f10_head_scientific_state_bad_types_are_structured(self):
        for value in ([], None, 'READY', False):
            self.fixture.authority()
            h, _ = self.fixture.snapshot.json(v.PATHS['head'])
            h['scientific_state'] = value
            anchor = self.fixture.rebind('head', h)
            obs = v.observe_authority(self.fixture.snapshot, anchor)
            with self.subTest(value=value), self.assertRaisesRegex(v.ContractError, 'INVALID_HEAD_SCIENTIFIC_STATE'):
                v.inspect_active_queue(obs)

    def test_f11_parent_commit_is_externally_bound(self):
        cp, kwargs = self.fixture.checkpoint()
        cp['parent_commit'] = 'c' * 40
        with self.assertRaisesRegex(v.ContractError, 'CHECKPOINT_PARENT_MISMATCH'):
            v.verify_checkpoint(self.fixture.snapshot, cp, **kwargs)

    def test_f11_premature_completion_and_out_of_extent_rejected(self):
        cp, kwargs = self.fixture.checkpoint()
        for total, error in ((4, 'CHECKPOINT_INCOMPLETE_COMPLETION'), (2, 'CHECKPOINT_EXTENT_EXCEEDED')):
            kwargs['expected_total_count'] = total
            with self.subTest(total=total), self.assertRaisesRegex(v.ContractError, error):
                v.verify_checkpoint(self.fixture.snapshot, cp, **kwargs)

    def test_f11_completed_work_cannot_remain_pending(self):
        cp, kwargs = self.fixture.checkpoint()
        cp['execution_state'] = 'PENDING_RESUMABLE'
        with self.assertRaisesRegex(v.ContractError, 'CHECKPOINT_NOTHING_TO_RESUME'):
            v.verify_checkpoint(self.fixture.snapshot, cp, **kwargs)
        kwargs['expected_total_count'] = 4
        r = v.verify_checkpoint(self.fixture.snapshot, cp, **kwargs)
        self.assertEqual((r['completed_count'], r['expected_total_count']), (3, 4))
        self.assertFalse(r['scientific_effect_authorized'])

    def test_f11_total_must_be_nonnegative_exact_integer(self):
        cp, kwargs = self.fixture.checkpoint()
        for value in (-1, True, 3.0, '3', None):
            kwargs['expected_total_count'] = value
            with self.subTest(value=value), self.assertRaisesRegex(v.ContractError, 'INVALID_EXPECTED_TOTAL'):
                v.verify_checkpoint(self.fixture.snapshot, cp, **kwargs)
