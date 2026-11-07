"""Exercise interrupted installation, local verification and same-size corruption."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import model_setup as models

class InstallTest(unittest.TestCase):
    def test_resume_verify_and_reject_corruption(self):
        root = Path(tempfile.mkdtemp(prefix='recast-model-test-'))
        entries = [dict(name=name, repo='test', revision='pinned', sub='image',
                        size=len(name), sha256=hashlib.sha256(name.encode()).hexdigest())
                   for name in ('first','second')]
        received = []
        def fetch(entry, folder, progress):
            received.append(entry['name'])
            if len(received) == 2:
                raise ConnectionError('interrupted')
            (folder / entry['name']).write_bytes(entry['name'].encode())
            progress(entry['size'])
        def no_fetch(*args):
            self.fail('verification accessed the network')
        update = lambda *args: None
        with (patch.object(models,'MANIFEST',entries),
              patch.object(models,'REPORT',root/'report.json'),
              patch.object(models,'settings',return_value={'image_models':str(root)})):
            with self.assertRaises(ConnectionError):
                models.run(True, update, fetch)
            self.assertFalse(models.ready())
            self.assertIn('1 file(s) missing',models.run(False,update,no_fetch))
            models.run(True,update,fetch)
            self.assertEqual(received,['first','second','second'])
            self.assertTrue(models.ready())
            models.run(False,update,no_fetch)
            (root/'second').write_bytes(b'broken')
            with self.assertRaisesRegex(RuntimeError,'SHA-256 mismatch'):
                models.run(False,update,no_fetch)
            self.assertFalse(models.ready())
            self.assertEqual((root/'second').read_bytes(),b'broken')
