"""Static Windows host-scheduler contract; NOT a native Windows qualification."""
import pathlib,re,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]

class HostContract(unittest.TestCase):
    def test_no_unattended_cost_or_repeated_scheduled_instance(self):
        x=(ROOT/'hosts'/'install_windows_task_v2_4.ps1').read_text()
        for term in ('-Daily -At \'22:00\'','-AtLogOn','-MultipleInstances IgnoreNew',
                     '-ExecutionTimeLimit','-StartWhenAvailable','-LogonType Interactive',
                     '-ReplacePreviouslyFrozenTask','Register-ScheduledTask','Get-FileHash'):
            self.assertIn(term,x)
        self.assertNotIn('github-actions',x.lower())
    def test_frozen_queue_and_live_pointer_both_required_at_launch(self):
        x=(ROOT/'hosts'/'run_windows_task_v2_4.ps1').read_text()
        for term in ('Get-FileHash','--expected-queue-sha256','--expected-live-pointer-sha1',
                     '--git-dir','--pointer-path','--wall-seconds','QROS_V24_SCHEDULED_LOGS'):
            self.assertIn(term,x)
    def test_manual_workflow_does_not_consume_automatic_private_action_minutes(self):
        x=(ROOT.parent/'.github'/'workflows'/'qros-nonstall-v24-manual-qualification.yml').read_text()
        self.assertIn('workflow_dispatch:',x)
        self.assertNotRegex(x,r'(?m)^\s+pull_request:')
        self.assertNotRegex(x,r'(?m)^\s+schedule:')

if __name__=='__main__':unittest.main()
