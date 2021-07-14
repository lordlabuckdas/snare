from aiohttp import web
import os
import unittest

from snare.middlewares import SnareMiddleware


class TestMiddleware(unittest.TestCase):
    def setUp(self):
        with open("error_404.html", "w") as err_404_file:
            err_404_file.write("Error 404 - Page not found")
        with open("error_500.html", "w") as err_500_file:
            err_500_file.write("Error 500 - Page not found")
        self.middleware = SnareMiddleware(
            "error_404.html",
            headers=[{"Content-Type": "text/html; charset=UTF-8"}],
            server_header="nginx",
        )

    def test_initialization(self):
        self.assertIsInstance(self.middleware, SnareMiddleware)

    def test_handle_404(self):
        pass

    def test_handle_500(self):
        pass

    def test_middleware_setup(self):
        self.app = web.Application()
        self.middleware.setup_middlewares(self.app)        

    def tearDown(self):
        os.remove("error_404.html")
        os.remove("error_500.html")
