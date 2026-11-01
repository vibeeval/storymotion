from pack_fixture_case import PackFixtureCase
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from storymotion.engine import checked_process,process_cancellation
from storymotion.security import WorkflowError


class OwnedProcessTests(PackFixtureCase):
    def test_timeout_stops_child_after_group_leader_exits(self):
        with tempfile.TemporaryDirectory() as td:
            marker=Path(td)/'late-marker'
            child='import time,pathlib;time.sleep(.6);pathlib.Path('+repr(str(marker))+').write_text("late");time.sleep(5)'
            parent='import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(child)+'])'
            with self.assertRaisesRegex(WorkflowError,'owned process group stopped'):
                checked_process([sys.executable,'-c',parent],timeout=.2)
            threading.Event().wait(.7)
            self.assertFalse(marker.exists())
    def test_cancel_stops_only_spawned_group_and_returns(self):
        event=threading.Event();timer=threading.Timer(.1,event.set);timer.start()
        try:
            with process_cancellation(event),self.assertRaisesRegex(WorkflowError,'cancelled'):
                checked_process([sys.executable,'-c','import time;time.sleep(5)'],timeout=10)
        finally:timer.cancel()
