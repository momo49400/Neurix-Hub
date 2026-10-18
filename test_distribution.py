import json
import unittest
from distribution_engine import parse_catalog, validate_release, DistributionError

class TestDistribution(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(parse_catalog(b'{"schema_version":1,"applications":[{"id":"neurix-ai","name":"Neurix AI","releases":[]}]}'),[])
    def test_reject_wrong_domain(self):
        entry=dict(version='1.0.3',channel='beta',platform='windows-x64',filename='NeurixAI-Beta-1.0.3-Setup.exe',download_url='https://evil.example/bad.exe',sha256='a'*64,size_bytes=27969746,released_at='2026-10-18',notes='test')
        with self.assertRaises(DistributionError): validate_release(entry)
    def test_reject_wrong_size(self):
        with self.assertRaises(DistributionError):parse_catalog(b'{"schema_version":2,"applications":[]}')
    def test_reject_path(self):
        entry=dict(version='1.0.3',channel='beta',platform='windows-x64',filename='../escape.exe',download_url='https://github.com/momo49400/Neurix-Group-Releases/releases/download/tag/escape.exe',sha256='a'*64,size_bytes=5,released_at='2026-10-18',notes='test')
        with self.assertRaises(DistributionError):validate_release(entry)
if __name__=='__main__':unittest.main()
