import unittest
import aiohttp
import asyncio
import sys
from unittest import mock
import shutil
from snare.cloner import Cloner
from seleniumwire import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import TimeoutException, InvalidArgumentException


class TestGetSiteHeadless(unittest.TestCase):
    def setUp(self):
        self.root = "http://example.com"
        self.level = 0
        self.max_depth = sys.maxsize
        self.loop = asyncio.new_event_loop()
        self.css_validate = False
        self.handler = Cloner(self.root, self.max_depth, self.css_validate)
        self.expected_content = None
        self.return_content = None
        self.return_url = None
        self.return_level = None
        self.qsize = None
        self.session = aiohttp.ClientSession()
        try:
            firefox_options = Options()
            firefox_options.headless = True
            self.driver = webdriver.Firefox(service_log_path="/dev/null", options=firefox_options)
        except Exception as err:
            raise Exception(
                "Error setting up headless cloning! Make sure Firefox and Geckodriver are installed and in $PATH\n"
                + str(err)
            )

    def test_timeout(self):
        self.driver.get = mock.Mock(side_effect=TimeoutException)

        async def test():
            _, _, _ = await self.handler.get_site_headless(self.driver, self.session, self.root)

        with self.assertLogs(level="ERROR") as log:
            self.loop.run_until_complete(test())
            self.assertIn("Request timed out:", "".join(log.output))

    def test_invalid_argument(self):
        self.driver.get = mock.Mock(side_effect=InvalidArgumentException)

        async def test():
            _, _, _ = await self.handler.get_site_headless(self.driver, self.session, self.root)

        with self.assertLogs(level="ERROR") as log:
            self.loop.run_until_complete(test())
            self.assertIn("Malformed URL:", "".join(log.output))

    def test_general_exception(self):
        self.driver.get = mock.Mock(side_effect=Exception("Error in fetching URL"))

        async def test():
            _, _, _ = await self.handler.get_site_headless(self.driver, self.session, self.root)

        with self.assertLogs(level="ERROR") as log:
            self.loop.run_until_complete(test())
            self.assertIn("Error in fetching URL", "".join(log.output))

    def tearDown(self):
        if self.driver:
            self.driver.close()
        self.loop.run_until_complete(self.session.close())
        shutil.rmtree("/opt/snare/pages")
