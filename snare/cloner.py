import os
import sys
import logging
import asyncio
from asyncio import Queue
import hashlib
import json
import re
from collections import defaultdict
import aiohttp
import cssutils
import yarl
from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import InvalidArgumentException, TimeoutException
import time
from snare.utils.snare_helpers import print_color

animation = "|/-\\"


class Cloner(object):
    def __init__(self, root, max_depth, css_validate=False, headless=False, default_path="/opt/snare"):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.visited_urls = []
        self.root, self.error_page = self.add_scheme(root)
        self.max_depth = max_depth
        self.moved_root = None
        self.default_path = default_path
        self.headless = headless
        if (self.root.host is None) or (len(self.root.host) < 4):
            sys.exit("invalid target {}".format(self.root.host))
        self.target_path = "{}/pages/{}".format(self.default_path, self.root.host)

        if not os.path.exists(self.target_path):
            os.makedirs(self.target_path)
        # NOTE: cssutils log level affects cloner's log level as well
        # if not css_validate:
        #     cssutils.log.setLevel("CRITICAL")
        self.css_validate = css_validate
        cssutils.log.setLog(self.logger)

        self.new_urls = Queue()
        self.meta = defaultdict(dict)
        self.counter = 0
        self.itr = 0

    @staticmethod
    def add_scheme(url):
        new_url = yarl.URL(url)
        if not new_url.scheme:
            new_url = yarl.URL("http://" + url)
        err_url = new_url.with_path("/status_404").with_query(None).with_fragment(None)
        return new_url, err_url

    @staticmethod
    def get_headers(response_headers):
        ignored_headers_lowercase = [
            "age",
            "cache-control",
            "connection",
            "content-encoding",
            "content-length",
            "date",
            "etag",
            "expires",
            "x-cache",
        ]

        headers = []
        for key, value in response_headers.items():
            if key.lower() not in ignored_headers_lowercase:
                headers.append({key: value})
        return headers

    async def process_link(self, url, level, check_host=False):
        try:
            url = yarl.URL(url)
        except UnicodeError:
            return None
        if url.scheme in ["data", "javascript", "file"]:
            return url.human_repr()
        if not url.is_absolute():
            if self.moved_root is None:
                url = self.root.join(url)
            else:
                url = self.moved_root.join(url)

        host = url.host

        if check_host and (
            (host != self.root.host and self.moved_root is None)
            or url.fragment
            or (self.moved_root is not None and host != self.moved_root.host)
        ):
            return None
        if url.human_repr() not in self.visited_urls and (level + 1) <= self.max_depth:
            await self.new_urls.put((url, level + 1))

        # res = None
        # try:
        res = url.relative().human_repr()
        # except ValueError:
        #     self.logger.error("ValueError while processing the %s link", url)
        return res

    async def replace_links(self, data, level):
        soup = BeautifulSoup(data, "html.parser")

        # find all relative links
        for link in soup.findAll(href=True):
            res = await self.process_link(link["href"], level, check_host=True)
            if res is not None:
                link["href"] = res

        # find all images and scripts
        for elem in soup.findAll(src=True):
            res = await self.process_link(elem["src"], level)
            if res is not None:
                elem["src"] = res

        # find all action elements
        for act_link in soup.findAll(action=True):
            res = await self.process_link(act_link["action"], level)
            if res is not None:
                act_link["action"] = res

        # prevent redirects
        for redir in soup.findAll(True, attrs={"name": re.compile("redirect.*")}):
            if redir["value"] != "":
                redir["value"] = yarl.URL(redir["value"]).relative().human_repr()

        return soup

    def _make_filename(self, url):
        host = url.host
        if url.is_absolute():
            file_name = url.relative().human_repr()
        else:
            file_name = url.human_repr()
        if not file_name.startswith("/"):
            file_name = "/" + file_name

        if file_name == "/" or file_name == "":
            if host == self.root.host or self.moved_root is not None and self.moved_root.host == host:
                file_name = "/index.html"
            else:
                file_name = host
        m = hashlib.md5()
        m.update(file_name.encode("utf-8"))
        hash_name = m.hexdigest()
        return file_name, hash_name

    async def get_site(self, session, current_url):
        """
        Fetch the given URL with aiohttp
        """
        data = None
        headers = []
        content_type = None
        try:
            response = await session.get(
                current_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
                    "Accept": "text/html",
                },
                timeout=10.0,
            )
            headers = self.get_headers(response.headers)
            content_type = response.content_type
            data = await response.read()
            data = data.decode()
        except (aiohttp.ClientError, asyncio.TimeoutError) as client_error:
            self.logger.error(client_error)
        else:
            await response.release()
        return [data, headers, content_type]

    async def get_site_headless(self, driver, session, current_url):
        """
        Fetch the given URL with selenium (headless cloning)
        """
        data = None
        headers = []
        content_type = None
        try:
            driver.get(str(current_url))
        except TimeoutException:
            self.logger.error("Request timed out:" + str(current_url))
        except InvalidArgumentException:
            self.logger.error("Malformed URL:" + str(current_url))
        except Exception as err:
            self.logger.error(err)
        time.sleep(1)
        data = driver.page_source
        for request in driver.requests:
            if request.response and request.response.headers and str(current_url) in request.url:
                headers = self.get_headers(request.response.headers)
                # content-type from seleniumwire is stored as "text/html; charset=utf-8"
                for header in headers:
                    for key, val in header.items():
                        if key.lower() == "content-type":
                            content_type = val
                            break
                break
        if content_type and "text/html" not in content_type:
            data, _, _ = await self.get_site(session, current_url)
        return [data, headers, content_type]

    async def get_body(self, session, driver=None):
        while not self.new_urls.empty():
            print(animation[self.itr % len(animation)], end="\r")
            self.itr = self.itr + 1
            current_url, level = await self.new_urls.get()
            if current_url.human_repr() in self.visited_urls:
                continue
            self.visited_urls.append(current_url.human_repr())
            file_name, hash_name = self._make_filename(current_url)
            self.logger.debug("Cloned file: %s", file_name)

            data = None
            headers = []
            content_type = None

            if driver and session:
                data, headers, content_type = await self.get_site_headless(driver, session, current_url)
            elif session:
                data, headers, content_type = await self.get_site(session, current_url)
            else:
                self.logger.error("Neither aiohttp.Session nor selenium.driver provided")
                raise Exception("Session and Driver both missing")

            if data:
                self.meta[file_name]["hash"] = hash_name
                self.meta[file_name]["headers"] = headers
                self.counter = self.counter + 1

                if content_type:
                    if "text/html" in content_type:
                        soup = await self.replace_links(str(data), level)
                        data = str(soup).encode()
                    elif "text/css" in content_type:
                        css = cssutils.parseString(data, validate=self.css_validate)
                        for carved_url in cssutils.getUrls(css):
                            if carved_url.startswith("data"):
                                continue
                            carved_url = yarl.URL(carved_url)
                            if not carved_url.is_absolute():
                                carved_url = self.root.join(carved_url)
                            if carved_url.human_repr() not in self.visited_urls:
                                await self.new_urls.put((carved_url, level + 1))

                try:
                    with open(os.path.join(self.target_path, hash_name), "wb") as index_fh:
                        index_fh.write(data)
                except TypeError:
                    await self.new_urls.put((current_url, level))

            else:
                await self.new_urls.put((current_url, level))

    async def get_root_host(self):
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(self.root)
                if resp.host != self.root.host:
                    self.moved_root = resp.url
                resp.close()
        except aiohttp.ClientError as err:
            self.logger.error("Can't connect to target host: %s", err)
            exit(-1)

    async def run(self):
        driver = None
        session = None
        if self.headless:
            try:
                firefox_options = Options()
                firefox_options.headless = True  # for headless cloning
                driver = webdriver.Firefox(
                    service_log_path="/dev/null", options=firefox_options
                )  # write geckodriver's log to /dev/null
                driver.set_page_load_timeout(2)  # wait for a maximum of 2s before proceeding to the next URL
            except Exception as err:
                print_color(
                    "Error setting up headless cloning!\n"
                    + "Make sure Firefox and Geckodriver are installed and in $PATH",
                    "ERROR",
                )
                self.logger.error(err)
        try:
            await self.new_urls.put((self.root, 0))
            await self.new_urls.put((self.error_page, 0))
            session = aiohttp.ClientSession()
            await self.get_body(session, driver)
        except KeyboardInterrupt:
            print_color("KeyboardInterrupt received, exiting...", "ERROR")
        except Exception as err:
            print_color(str(err), "ERROR")
        finally:
            with open(os.path.join(self.target_path, "meta.json"), "w") as mj:
                json.dump(self.meta, mj)
            if session:
                await session.close()
            if driver:
                driver.close()
