import unittest
from unittest import mock
import sys
from snare.cloner import BaseCloner
import shutil
from yarl import URL
import asyncio
import aiohttp
from snare.utils.asyncmock import AsyncMock


class TestBaseClonerGetRootHost(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    def test_moved_root(self):
        self.root = "http://example.com"
        self.max_depth = sys.maxsize
        self.css_validate = False
        self.handler = BaseCloner(self.root, self.max_depth, self.css_validate)
        self.expected_moved_root = URL("http://www.example.com")

        async def test():
            if not self.handler:
                raise Exception("Error initializing Cloner!")
            await self.handler.get_root_host()

        self.loop.run_until_complete(test())

        if not self.handler:
            raise Exception("Error initializing Cloner!")

        self.assertEqual(self.handler.moved_root, self.expected_moved_root)

    @mock.patch("aiohttp.ClientSession")
    def test_clienterror(self, session):
        self.root = "http://example.com"
        self.max_depth = sys.maxsize
        self.css_validate = False
        self.handler = BaseCloner(self.root, self.max_depth, self.css_validate)

        aiohttp.ClientSession = mock.Mock(side_effect=aiohttp.ClientError)

        async def test():
            if not self.handler:
                raise Exception("Error initializing Cloner!")
            await self.handler.get_root_host()

        with self.assertRaises(SystemExit):
            self.loop.run_until_complete(test())
