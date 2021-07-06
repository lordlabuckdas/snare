import unittest
import sys
from snare.cloner import CloneRunner
import shutil


class TestCloneRunnerInitialization(unittest.TestCase):
    def setUp(self):
        self.root = "http://example.com"
        self.max_depth = sys.maxsize
        self.css_validate = False
        self.handler = CloneRunner(self.root, self.max_depth, self.css_validate, default_path="/tmp")

    def test_cloner_init(self):
        self.assertIsInstance(self.handler, CloneRunner)

    def tearDown(self):
        if self.handler.runner:
            shutil.rmtree(self.handler.runner.target_path)
        else:
            raise Exception("Error initializing Cloner")
