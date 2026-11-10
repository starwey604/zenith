import importlib.machinery
import pathlib
import unittest
import tempfile

module = importlib.machinery.SourceFileLoader(
    'amp_report', str(pathlib.Path(__file__).resolve().parents[4] / 'tools/amp-shm-report')).load_module()


class TraceReportTest(unittest.TestCase):
    def test_nested_and_threaded_irq(self):
        lines = [
            'x-1 [000] d... 1.000000: irq_handler_entry: irq=3 name=outer',
            'x-1 [000] d... 1.000001: irq_handler_entry: irq=4 name=inner',
            'x-1 [000] d... 1.000002: irq_handler_exit: irq=4 ret=handled',
            'x-1 [000] d... 1.000004: irq_handler_exit: irq=3 ret=handled',
            'x-1 [000] .... 1.000005: sched_switch: prev_comm=x prev_pid=1 prev_prio=120 prev_state=R ==> next_comm=irq/3-test next_pid=22 next_prio=50',
            'x-1 [000] .... 1.000015: sched_switch: prev_comm=irq/3-test prev_pid=22 prev_prio=50 prev_state=S ==> next_comm=x next_pid=1 next_prio=120',
        ]
        result = module.parse_trace(lines)
        self.assertEqual(result['intervals']['hardirq_interval/3']['sum_ns'], 4000)
        self.assertEqual(result['intervals']['hardirq_interval/4']['sum_ns'], 1000)
        self.assertEqual(result['by_cpu']['0']['hardirq_interval/3']['sum_ns'], 4000)
        self.assertEqual(result['timestamp_print_resolution_ns'], 1000)
        self.assertEqual(result['intervals']['thread_scheduled/irq/3-test/22']['sum_ns'], 10000)
        self.assertEqual(result['boundary_or_unmatched_events']['open_irq_intervals'], 0)

    def test_boundary_and_proc(self):
        result = module.parse_trace(['x-1 [001] d... 2.000000: softirq_exit: vec=1 [action=TIMER]'])
        self.assertEqual(result['boundary_or_unmatched_events']['softirq_interval_exit'], 1)
        self.assertEqual(module.proc_delta('ctxt 12\ncpu 1 2 3\n', 'ctxt 15\ncpu 1 4 6\n'),
                         {'ctxt': [3], 'cpu': [0, 2, 3]})

    def test_capture_loss_and_plain_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory)
            (path / 'trace.txt').write_text('')
            (path / 'buffer-stats.txt').write_text('overrun: 3\ncommit overrun: 2\ndropped events: 1\n')
            (path / 'bench.json').write_text('{"correctness_errors":0}')
            (path / 'exit-status.txt').write_text('0')
            (path / 'stat.before').write_text('cpu4 1 2 3\n')
            (path / 'stat.after').write_text('cpu4 2 3 4\n')
            result = module.report(path)
            self.assertEqual(result['trace_lost_events'], 6)
            self.assertFalse(result['valid_complete_capture'])
            self.assertEqual(result['proc_stat_delta']['cpu4'], [1, 1, 1])
            (path / 'capture-mode.txt').write_text('plain')
            (path / 'exit-status.txt').write_text('2')
            result = module.report(path)
            self.assertEqual(result['capture_mode'], 'plain')
            self.assertFalse(result['correctness_passed'])


if __name__ == '__main__':
    unittest.main()
