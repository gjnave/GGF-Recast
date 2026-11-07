import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
import media,projects,prompts

class MediaTests(unittest.TestCase):
    def test_windows_cover_source_exactly(self):
        for count in (1,89,90,124,125,248,299,1000):
            windows=media.plan_windows(count,124)
            self.assertEqual(sum(x['count'] for x in windows),count)
            self.assertEqual([x['start'] for x in windows],list(range(0,count,124)))
            for x in windows:
                self.assertGreaterEqual(x['render_frames'],x['count'])
                self.assertEqual((x['render_frames']-5)%17,0)
                self.assertGreaterEqual(x['render_frames'],90)
    def test_roundtrip_and_padding(self):
        # Keep test artifacts; no file/folder deletion in this suite.
        root=Path(projects.settings()['projects'])/'test-artifacts'
        root.mkdir(parents=True,exist_ok=True)
        import uuid
        path=root/(uuid.uuid4().hex+'.mp4')
        frames=np.zeros((24,64,96,3),np.uint8)
        for i in range(24):frames[i,:,:,0]=i*8
        media.write_video(frames,path)
        self.assertEqual(media.frame_count(path),24)
        result=media.read_frames(path,.5,1,96,64)
        self.assertEqual(result.shape,(24,64,96,3))
        self.assertGreater(result[0,:,:,0].mean(),80)
        self.assertTrue(np.array_equal(result[-1],result[-2]))
        self.assertFalse(media.probe(path)['audio'])
        self.assertEqual(float(media.audio_samples(path,0,1).sum()),0)
        with self.assertRaises(FileExistsError):media.write_video(frames,path)
    def test_prompt_binds_two_people(self):
        cast=[{'source':'person on left','description':'gold robot'}, {'source':'person on right','description':'astronaut'}]
        text=prompts.image_prompt(cast)
        self.assertIn('image 2',text);self.assertIn('image 3',text)
        video=prompts.video_prompt(cast,'Keep the stage.')
        self.assertIn('<Subject 2>',video);self.assertIn('astronaut',video)

if __name__=='__main__':unittest.main()
