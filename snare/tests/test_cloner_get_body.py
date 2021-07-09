import unittest
import aiohttp
import yarl
import sys
import os
import shutil
import asyncio
from snare.cloner import CloneRunner
from snare.utils.asyncmock import AsyncMock
from snare.utils.page_path_generator import generate_unique_path


class TestGetBody(unittest.TestCase):
    def setUp(self):
        self.main_page_path = generate_unique_path()
        os.makedirs(self.main_page_path)
        self.root = "http://example.com"
        self.level = 0
        self.max_depth = sys.maxsize
        self.loop = asyncio.new_event_loop()
        self.css_validate = False
        self.handler = CloneRunner(self.root, self.max_depth, self.css_validate)
        self.target_path = "/opt/snare/pages/{}".format(yarl.URL(self.root).host)
        self.return_content = None
        self.expected_content = None
        self.filename = None
        self.hashname = None
        self.url = None
        self.content = None
        self.return_url = None
        self.return_level = None
        self.meta = None
        self.q_size = None

        self.session = aiohttp.ClientSession
        self.session.get = AsyncMock(
            return_value=aiohttp.ClientResponse(
                url=yarl.URL("http://www.example.com"),
                method="GET",
                writer=None,
                continue100=1,
                timer=None,
                request_info=None,
                traces=None,
                loop=self.loop,
                session=None,
            )
        )

    def test_get_body(self):
        self.content = b"""<html><body><a href="http://example.com/test"></a></body></html>"""

        aiohttp.ClientResponse._headers = {"Content-Type": "text/html"}
        aiohttp.ClientResponse.read = AsyncMock(return_value=self.content)
        if not self.handler.runner:
            raise Exception("Error initializing Cloner!")
        self.filename, self.hashname = self.handler.runner._make_filename(yarl.URL(self.root))
        self.expected_content = '<html><body><a href="/test"></a></body></html>'

        self.meta = {
            "/index.html": {
                "hash": "d1546d731a9f30cc80127d57142a482b",
                "headers": [{"Content-Type": "text/html"}],
            },
            "/test": {
                "hash": "4539330648b80f94ef3bf911f6d77ac9",
                "headers": [{"Content-Type": "text/html"}],
            },
        }

        async def test():
            if not self.handler.runner:
                raise Exception("Error initializing Cloner!")
            await self.handler.runner.new_urls.put({"url": yarl.URL(self.root), "level": 0, "try_count": 0})
            await self.handler.runner.get_body(self.session)

        with self.assertLogs(level="DEBUG") as log:
            self.loop.run_until_complete(test())
            self.assertIn("DEBUG:snare.cloner:Cloned file: /test", "".join(log.output))

        with open(os.path.join(self.target_path, self.hashname)) as f:
            self.return_content = f.read()

        self.assertEqual(self.return_content, self.expected_content)
        self.assertEqual(
            self.handler.runner.visited_urls[-2:],
            ["http://example.com/", "http://example.com/test"],
        )
        self.assertEqual(self.handler.runner.meta, self.meta)

    def test_get_body_css_validate(self):
        aiohttp.ClientResponse._headers = {"Content-Type": "text/css"}

        self.css_validate = True
        self.handler = CloneRunner(self.root, self.max_depth, self.css_validate)
        self.content = b""".banner { background: url("/example.png") }"""
        aiohttp.ClientResponse.read = AsyncMock(return_value=self.content)
        self.expected_content = "http://example.com/example.png"
        self.return_size = 0
        self.meta = {
            "/example.png": {
                "hash": "5a64beebcd2a6f1cbd00b8370debaa72",
                "headers": [{"Content-Type": "text/css"}],
            },
            "/index.html": {
                "hash": "d1546d731a9f30cc80127d57142a482b",
                "headers": [{"Content-Type": "text/css"}],
            },
        }

        async def test():
            if not self.handler.runner:
                raise Exception("Error initializing Cloner!")
            await self.handler.runner.new_urls.put({"url": yarl.URL(self.root), "level": 0, "try_count": 0})
            await self.handler.runner.get_body(self.session)
            self.q_size = self.handler.runner.new_urls.qsize()

        if not self.handler.runner:
            raise Exception("Error initializing Cloner!")

        self.loop.run_until_complete(test())
        self.assertEqual(self.handler.runner.visited_urls[-1], self.expected_content)
        self.assertEqual(self.q_size, self.return_size)
        self.assertEqual(self.meta, self.handler.runner.meta)

    def test_get_body_css_validate_scheme(self):
        aiohttp.ClientResponse._headers = {"Content-Type": "text/css"}

        self.css_validate = True
        self.return_size = 0
        self.handler = CloneRunner(self.root, self.max_depth, self.css_validate)
        self.content = [
            b""".banner { background: url("data://domain/test.txt") }""",
            b""".banner { background: url("file://domain/test.txt") }""",
        ]
        self.meta = {
            "/index.html": {
                "hash": "d1546d731a9f30cc80127d57142a482b",
                "headers": [{"Content-Type": "text/css"}],
            },
        }

        self.expected_content = "http://example.com/"

        async def test():
            if not self.handler.runner:
                raise Exception("Error initializing Cloner!")
            await self.handler.runner.new_urls.put({"url": yarl.URL(self.root), "level": 0, "try_count": 0})
            await self.handler.runner.get_body(self.session)
            self.q_size = self.handler.runner.new_urls.qsize()

        if not self.handler.runner:
            raise Exception("Error initializing Cloner!")

        for content in self.content:
            aiohttp.ClientResponse.read = AsyncMock(return_value=content)
            self.loop.run_until_complete(test())
            self.assertEqual(self.return_size, self.q_size)
            self.assertEqual(self.handler.runner.meta, self.meta)
            self.assertEqual(self.handler.runner.visited_urls[-1], self.expected_content)

    def test_client_error(self):
        self.session.get = AsyncMock(side_effect=aiohttp.ClientError)

        async def test():
            if not self.handler.runner:
                raise Exception("Error initializing Cloner!")
            await self.handler.runner.new_urls.put({"url": yarl.URL(self.root), "level": 0, "try_count": 0})
            await self.handler.runner.get_body(self.session)

        with self.assertLogs(level="ERROR") as log:
            self.loop.run_until_complete(test())
            self.assertIn("ERROR:snare.cloner:", "".join(log.output))

    def test_try_count(self):
        async def test():
            if not self.handler.runner:
                raise Exception("Error initializing Cloner!")
            await self.handler.runner.new_urls.put({"url": yarl.URL(self.root), "level": 0, "try_count": 3})
            await self.handler.runner.get_body(None)

        if not self.handler.runner:
            raise Exception("Error initializing Cloner!")
        self.loop.run_until_complete(test())
        self.assertFalse(self.root in self.handler.runner.visited_urls)

    def tearDown(self):
        shutil.rmtree(self.main_page_path)
