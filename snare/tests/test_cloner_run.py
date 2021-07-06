import asyncio
import os
import shutil
from snare.cloner import CloneRunner
import sys
import unittest

from snare.utils.page_path_generator import generate_unique_path


class TestCloneRunnerRun(unittest.TestCase):
    def setUp(self):
        self.main_page_path = generate_unique_path()
        os.makedirs(self.main_page_path)
        self.root = "http://example.com"
        self.max_depth = sys.maxsize
        self.css_validate = False
        self.handler = CloneRunner(self.root, self.max_depth, self.css_validate, default_path="/tmp")
        self.loop = asyncio.new_event_loop()

    def test_run(self):
        self.loop.run_until_complete(self.handler.run())

    def tearDown(self):
        shutil.rmtree(self.main_page_path)
