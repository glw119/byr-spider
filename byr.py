#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2018 Yongwen Zhuang <zeoman@163.com>
# Copyright © 2019 Liangwu <glw119@gmail.com>
#
# Distributed under terms of the MIT license.

"""
Byr
自动从bt.byr.cn上下载第一页种子文件
"""

import os
from PIL import Image
from io import BytesIO
import logging
import pickle
try:
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
from userpass import User
from decaptcha.decaptcha import DeCaptcha


class Byr(object):

    """login/logout/getpage"""

    def __init__(self):
        """Byr Init """
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)10s [%(filename)s %(levelname)6s:%(lineno)4s - %(funcName)10s ] %(message)s'
        )
        console.setFormatter(formatter)

        self.logger = logging.getLogger("byr")
        self.logger.addHandler(console)
        self.logger.setLevel(logging.DEBUG)

        self._session = requests.session()

        self._session.proxies = {
            'http': 'socks5://127.0.0.1:1080',
            'https': 'socks5://127.0.0.1:1080',
        }

        self._session.headers = {
            'User-Agent': 'Magic Browser'
        }
        self._root = 'https://bt.byr.cn/'
        self._user = User('.byr')
        self.list = []
        if os.path.exists('list.csv'):
            self.logger.debug('Read list.csv')
            with open('list.csv', 'r') as f:
                for line in f.readlines():
                    self.list.append(line.split(',')[0])

    def login(self):
        """Login to bt.bry.cn"""
        login_page = self.get_url('login.php')
        image_url = login_page.find('img', alt='CAPTCHA')['src']
        image_hash = login_page.find(
            'input', attrs={'name': 'imagehash'})['value']
        self.logger.debug('Image url: ' + image_url)
        self.logger.debug('Image hash: ' + image_hash)
        req = self._session.get(self._root + image_url)
        image_file = Image.open(BytesIO(req.content))
        decaptcha = DeCaptcha()
        decaptcha.load_model('./decaptcha/captcha_classifier.pkl')
        captcha_text = decaptcha.decode(image_file)
        self.logger.debug('Captcha text: ' + captcha_text)

        login_data = {
            'username': self._user.username,
            'password': self._user.password,
            'imagestring': captcha_text,
            'imagehash': image_hash
        }
        main_page = self._session.post(
            self._root + 'takelogin.php', login_data)
        if main_page.url != self._root + 'index.php':
            self.logger.error('Login error')
            return
        self._save()

    def _save(self):
        """Save cookies to file"""
        self.logger.debug('Save cookies')
        with open('cookie', 'wb') as f:
            pickle.dump(self._session.cookies, f)

    def _load(self):
        """Load cookies from file"""
        if os.path.exists('cookie'):
            with open('cookie', 'rb') as f:
                self.logger.debug('Load cookies from file.')
                self._session.cookies = pickle.load(f)
        else:
            self.logger.debug('Load cookies by login')
            self.login()
            self._save()

    @property
    def pages(self):
        """Return pages in torrents.php
        :returns: yield ByrPage pages
        """
        # free url
        self.logger.debug('Get pages')
        page = self.get_url('torrents.php?page=1')
        n = 0
        for line in page.find('table', class_='torrents').form.findChildren('tr', recursive=False)[2:]:
            if n == 0:
                yield(ByrPage(line))
                n = 1
            else:
                n -= 1

    def get_url(self, url):
        """Return BeautifulSoup Pages
        :url: page url
        :returns: BeautifulSoups
        """
        self.logger.debug('Get url: ' + url)
        req = self._session.get(self._root + url)
        return BeautifulSoup(req.text, 'lxml')

    def start(self):
        """Start spider"""
        self.logger.info('Start Spider')
        self._load()
        with open('list.csv', 'a') as f:
            for page in self.pages:
                self.logger.debug(page.id + ',' + page.name + ',' + page.type + ',' + str(page.size) + 'GB,' + str(page.seeders) + ',' + str(page.snatched))
                self.logger.debug('Check ' + page.name)
                if page.id not in self.list and page.ok:
                    self.logger.info('Download ' + page.name)
                    self.download(page.id)
                    f.write(page.id + ',' + page.name + ',' + str(page.size) + 'GB,' + str(page.seeders) + '\n')

    def download(self, id_):
        """Download torrent in url
        :url: url
        :filename: torrent filename
        """
        url = self._root + 'download.php?id=' + id_
        req = self._session.get(url)
        with open('./tmp/' + id_ + '.torrent', 'wb') as f:
            f.write(req.content)


class ByrPage(object):

    """Torrent Page Info"""

    def __init__(self, soup):
        """Init variables
        :soup: Soup
        """

        url = soup.find(class_='torrentname').a['href']
        self.name = soup.find(class_='torrentname').b.text
        self.type = soup.img['title']
        self.size = self.tosize(soup.find_all('td')[-5].text)
        self.seeders = int(soup.find_all('td')[-4].text.replace(',', ''))
        self.snatched = int(soup.find_all('td')[-2].text.replace(',', ''))
        self.id = parse_qs(urlparse(url).query)['id'][0]

    @property
    def ok(self):
        """Check torrent info
        :returns: If a torrent are ok to be downloaded
        """
        return self.seeders > 0

    def tosize(self, text):
        """Convert text 'xxxGB' to int size
        :text: 123GB or 123MB
        :returns: 123(GB) or 0.123(GB)
        """
        if text.endswith('MB'):
            size = float(text[:-2].replace(',', '')) / 1024
        else:
            size = float(text[:-2].replace(',', ''))
        return size


def main():
    b = Byr()
    b.start()


if __name__ == "__main__":
    main()
