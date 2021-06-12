import unittest
import sys
from snare.cloner import Cloner
import shutil
import asyncio
import yarl
import os
from snare.utils.page_path_generator import generate_unique_path
from unittest import mock
import selenium


class TestClonerRun(unittest.TestCase):
    def setUp(self):
        self.main_page_path = generate_unique_path()
        os.makedirs(self.main_page_path)
        self.root = "http://example.com"
        self.target_path = "/opt/snare/pages/{}".format(yarl.URL(self.root).host)
        self.max_depth = sys.maxsize
        self.css_validate = False
        self.headless = True
        self.handler = Cloner(self.root, self.max_depth, self.css_validate, self.headless, default_path="/tmp")
        self.loop = asyncio.new_event_loop()

    def test_headless_run(self):
        self.loop.run_until_complete(self.handler.run())

    def test_keyboard_interrupt(self):
        self.handler.new_urls.put = mock.Mock(side_effect=KeyboardInterrupt)
        self.assertRaises(KeyboardInterrupt, self.loop.run_until_complete(self.handler.run()))

    @mock.patch("selenium.webdriver.firefox.options")
    def test_no_geckodriver(self, mock_options):
        selenium.webdriver.firefox.options = mock.Mock(side_effect=Exception)

        async def test():
            await self.handler.run()

        self.assertRaises(Exception, self.loop.run_until_complete(test()))

    def tearDown(self):
        shutil.rmtree(self.main_page_path)
