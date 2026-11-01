from pack_fixture_case import PackFixtureCase
"""Real FFmpeg technical gates using synthetic color/silence, NOT a branded HF export."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from storymotion.engine import Engine,ROOT,checked_process,probe
from storymotion.security import WorkflowError
from storymotion.runtime import media_binary


@unittest.skipUnless(all(Path(media_binary(n)).is_file() or shutil.which(media_binary(n)) for n in ['ffmpeg','ffprobe']),'Local FFmpeg setup required')
class MediaTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.e=Engine(Path(self.tmp.name)/'work')
        self.job=self.e.create(ROOT/'tests/fixtures/examples/sample-mechanism.json')['job'];self.e.run(self.job,'prepare')
        self.out=self.e.directory(self.job);self.payload=self.e.payload(self.job)
    def tearDown(self):self.tmp.cleanup()
    def encode(self,audio=False):
        args=['ffmpeg','-v','error','-y','-f','lavfi','-i','nullsrc=s=1080x1920:r=30:d=4']
        if audio:args+=['-f','lavfi','-i','anullsrc=r=24000:cl=mono']
        args+=['-t','4','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p']
        if audio:args+=['-c:a','aac']
        checked_process(args+[self.out/'render-1080.mp4'])
    def test_real_mobile_encode_decode_and_qa(self):
        self.encode();self.e.perform('mobile',self.payload,self.out)
        self.e.perform('qa',self.payload,self.out)
        report=json.loads((self.out/'qa.json').read_text())
        self.assertEqual(report['technical'],'pass');self.assertEqual(report['media']['render-mobile.mp4']['full_decode'],'pass')
        self.assertEqual(report['human_review']['final_watch'],'pending')
    def test_unexpected_audio_cannot_pass_silent_job(self):
        self.encode(audio=True);self.e.perform('mobile',self.payload,self.out)
        with self.assertRaisesRegex(WorkflowError,'audio'):self.e.perform('qa',self.payload,self.out)


if __name__=='__main__':unittest.main()
