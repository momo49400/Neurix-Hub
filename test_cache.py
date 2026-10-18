import tempfile
import unittest
from pathlib import Path
from cache_engine import CacheEngine, CacheError, identify

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = CacheEngine(self.root / 'appdata')
        self.setup = self.root / 'NeurixAI-Beta-1.0.3-Setup.exe'
        self.setup.write_bytes(b'demo installer bytes')

    def test_import_retains_after_source_deleted(self):
        entry = self.engine.add(self.setup)
        self.setup.unlink()
        self.assertTrue(self.engine.verify(entry).exists())
        self.assertEqual(len(CacheEngine(self.root / 'appdata').entries), 1)

    def test_dedup(self):
        self.engine.add(self.setup)
        self.engine.add(self.setup)
        self.assertEqual(len(self.engine.entries), 1)

    def test_tamper_blocks(self):
        e = self.engine.add(self.setup)
        self.engine.verify(e).write_bytes(b'corrupted')
        with self.assertRaises(CacheError): self.engine.verify(e)
        with self.assertRaises(CacheError): self.engine.remove(e)

    def test_delete_only_cache(self):
        entry = self.engine.add(self.setup)
        self.engine.remove(entry)
        self.assertTrue(self.setup.exists())
        self.assertFalse(self.engine.entries)

    def test_reject_unknown(self):
        with self.assertRaises(CacheError): identify(Path('random.exe'))
        with self.assertRaises(CacheError): identify(Path('NeurixAI-Beta-1.1-Setup.zip'))

    def test_multiple_versions(self):
        self.engine.add(self.setup)
        other = self.root / 'NeurixAI-Alpha-1.5-Setup.exe'
        other.write_bytes(b'older')
        self.engine.add(other)
        self.assertEqual({x['version'] for x in self.engine.entries}, {'1.0.3','1.5'})

if __name__ == '__main__': unittest.main()
