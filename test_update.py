import unittest
from update_engine import release_key, update_summary, newest_remote


def release(ch, v, hashchar='a'):
    return dict(channel=ch,version=v,sha256=hashchar*64)

class TestUpdateEngine(unittest.TestCase):
    def test_version_order(self):
        self.assertGreater(release_key('beta','1.0.10'),release_key('beta','1.0.3'))
        self.assertGreater(release_key('stable','1.0.3'),release_key('beta','1.0.3'))
    def test_empty(self):
        self.assertEqual(update_summary([],[])['state'],'empty')
    def test_available(self):
        self.assertEqual(update_summary([release('beta','1.0.3')],[])['state'],'available')
    def test_cached(self):
        self.assertEqual(update_summary([release('beta','1.0.3')],[dict(family='Beta',version='1.0.3',sha256='a'*64)])['state'],'cached')
    def test_newer(self):
        self.assertEqual(update_summary([release('beta','1.0.3')],[dict(family='Beta',version='1.0.2',sha256='b'*64)])['state'],'newer')
    def test_not_confuse_app_install(self):
        self.assertEqual(update_summary([release('beta','1.0.3')],[])['state'],'available')
    def test_latest(self):
        self.assertEqual(newest_remote([release('beta','1.0.3'),release('beta','1.0.10')])['version'],'1.0.10')

if __name__=='__main__':unittest.main()
