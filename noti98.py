from PyQt4.QtGui import (
    QApplication,
    QSystemTrayIcon,
    QIcon,
    QMenu,
    QDesktopServices,
    QWidget
)
from PyQt4.QtCore import (
    QTimer,
    QUrl
)
from urlparse import urljoin
from urllib import urlencode
import re
import bs4
import urllib2
from cookielib import CookieJar
import sys


base_url = 'http://www.cc98.org'
login_url = 'http://www.cc98.org/login.asp'
posts_url = 'http://www.cc98.org/queryresult.asp?stype=3'


def ispost(t):
    return (
        t.name == 'a'
        and len(t.contents) == 1
        and type(t.contents[0]) is bs4.NavigableString
        and t.has_attr('href')
        and re.match(r'dispbbs.*', t['href'])
    )


class Tray(QSystemTrayIcon):

    def __init__(self, icon, parent=None):
        super(Tray, self).__init__(icon, parent)
        menu = QMenu(parent)
        exit = menu.addAction('&Exit')
        exit.triggered.connect(QApplication.instance().quit)
        self.setContextMenu(menu)
        self.cached_post = None
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(CookieJar()))
        self.messageClicked.connect(self.openurl)
        self.login()

    def last_post(self):
        data = self.opener.open(posts_url).read()
        soup = bs4.BeautifulSoup(data)
        post = soup.find_all(ispost)[0]
        title = post.string.strip()
        url = urljoin(base_url, post['href'])
        return title, url

    def login(self):
        self.opener.open(login_url, urlencode(dict(
            username='answeror',
            password='42',
            action='chk'
        )))

    def openurl(self):
        QDesktopServices.openUrl(QUrl(self.url))

    def check(self):
        post = self.last_post()
        if post != self.cached_post:
            title, url = post
            self.url = url
            self.showMessage('', title)
            self.cached_post = post


app = QApplication(sys.argv)
w = QWidget()
tray = Tray(QIcon('smile.png'), w)
tray.show()
timer = QTimer()
timer.timeout.connect(tray.check)
timer.start(5000)
app.exec_()
