from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urljoin
import os
from bs4 import BeautifulSoup as BS
import logging
import logging.config
from contextlib import contextmanager
import subprocess as sp
import datetime
import re
from uuid import uuid4
import base64
import shutil
from joblib import Memory


logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'detailed': {
            'class': 'logging.Formatter',
            'format': '%(asctime)s %(levelname)-8s %(message)s'
        },
        'simple': {
            'class': 'logging.Formatter',
            'format': '%(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple'
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'filename': 'archive.log',
            'mode': 'a',
            'formatter': 'detailed'
        }
    },
    'root': {
        'level': 'DEBUG',
        'handlers': ['console', 'file']
    }
})
log = logging.getLogger(__name__)

memo = Memory('cache', verbose=0)

ROOT = os.path.abspath(os.path.dirname(__file__))
OUTPUT = 'archive'


class Bunch(object):

    def __init__(self, **kargs):
        self.__dict__.update(**kargs)


def load():
    buf = []
    with open('archive.txt', 'rb') as f:
        for lineno, line in enumerate(f):
            log.info('parse %dth line' % (lineno + 1))
            line = line.decode('ascii').strip()
            if line and not line.startswith('#'):
                words = line.split()
                if words[0] not in ('homework', 'lecture'):
                    try:
                        art = parse_homework(words)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        log.info('parse failed: {}'.format(words))
                    else:
                        for i in range(len(buf)):
                            if buf[i].name == art.name and buf[i].dirname == art.dirname:
                                log.info('update %s in %s' % (art.name, art.dirname))
                                art.time = buf[i].time
                                buf[i] = art
                                break
                        else:
                            buf.append(art)
                else:
                    buf.append(parse_mine(words))
    return buf


def infopen(url):
    while True:
        try:
            return urlopen(url).read()
        except URLError as e:
            if e.code in (400, 404):
                log.info('open %s return %d, stop' % (url, e.code))
                return None
            else:
                log.info('open %s return %d, reopen' % (url, e.code))
        except Exception as e:
            log.info('open %s failed, reopen' % url)


@memo.cache
def parse_homework(words):
    n, gist, id, time = words
    dirname = os.path.join(OUTPUT, 'homework', n)
    name = id
    url = 'http://nbviewer.ipython.org/%s' % gist
    text = infopen(url)
    if text is None:
        url = 'http://gist.github.com/%s' % gist
        text = infopen(url)
        assert text is not None
        soup = BS(text)
        a = soup.find('a', title='View Raw')
        assert a is not None
        content = infopen(urljoin(url, a['href']))
        assert content is not None
        good = False
    else:
        soup = BS(text)
        a = soup.find('a', text='Download Notebook')
        if a is None:
            content = text
            good = False
        else:
            content = infopen(urljoin(url, a['href']))
            assert content is not None
            good = True
    return Bunch(
        dirname=dirname,
        name=name,
        content=content,
        good=good,
        time=time,
        title='homework %s' % n,
        author=id
    )


def mdate(path):
    t = os.path.getmtime(path)
    t = datetime.datetime.fromtimestamp(t)
    return t.strftime('%Y-%m-%d')


def parse_mine(words):
    typename, n, path = words
    n = int(n)
    dirname = os.path.join(OUTPUT, 'lecture')
    name = '%s.%02d' % (typename, n)
    with open(path, 'rb') as f:
        content = f.read()
    good = True
    time = mdate(path)
    return Bunch(
        dirname=dirname,
        name=name,
        content=content,
        good=good,
        time=time,
        title='%s %d' % (typename, n),
        author='answeror+python-course.2013@gmail.com'
    )


@contextmanager
def pushd(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield old
    finally:
        os.chdir(old)


@contextmanager
def rmtmp(name, exts):
    try:
        yield None
    finally:
        for ext in exts:
            path = name + ext if ext[0] == '.' else ext
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.unlink(path)


def dump(path, data):
    if not os.path.exists('images'):
        os.makedirs('images')
    with open(path, 'wb') as f:
        f.write(data)
    return path.replace('\\', '/')


def compress_html(name):
    with open('%s.html' % name, 'rb') as f:
        soup = BS(f.read())
    for img in soup.find_all('img'):
        if img['src'].startswith('http://'):
            log.info('download img in %s' % name)
            data = infopen(img['src'])
            ext = img['src'].split('.')[-1]
            if ext not in ('jpg', 'png', 'gif'):
                ext = 'jpg'
            iname = uuid4()
            ipath = os.path.join('images', '%s.%s' % (iname, ext))
            img['src'] = dump(ipath, data)
        else:
            m = re.search(r"data:image/png;base64,b'(.*)'", img['src'])
            if m:
                log.info('compress img in %s' % name)
                iname = uuid4()
                ipath = os.path.join('images', '%s.png' % iname)
                # remove '\n'
                s = m.group(1).replace(r'\n', '')
                img['src'] = dump(ipath, base64.b64decode(s.encode('ascii')))
    with open('%s.html' % name, 'wb') as f:
        f.write(soup.encode('utf-8'))


def convert(art):
    log.info("convert %s's %s" % (art.author, art.title))
    if not os.path.exists(art.dirname):
        os.makedirs(art.dirname)
    with pushd(art.dirname):
        if not art.good:
            log.info('not good, save to txt')
            with open('%s.txt' % art.name, 'wb') as f:
                f.write(art.content)
        else:
            log.info('good, convert to pdf')
            with open('%s.ipynb' % art.name, 'wb') as f:
                f.write(art.content)
            with rmtmp(art.name, [
                '.ipynb',
                '.html',
                '.tex',
                '.log',
                '.out',
                '.aux',
                'images'
            ]):
                log.info('ipynb to html')
                with open(os.path.join(ROOT, 'archive.tmp'), 'wb') as tmp:
                    if sp.call([
                        'ipython3',
                        'nbconvert',
                        '--to',
                        'html',
                        '%s.ipynb' % art.name
                    ], stdout=tmp, stderr=tmp):
                        log.info('failed')
                        return
                    compress_html(art.name)
                    log.info('html to tex')
                    if sp.call([
                        'pandoc',
                        '--template',
                        os.path.join(ROOT, 'simple.tex'),
                        '%s.html' % art.name,
                        '-o',
                        '%s.tex' % art.name,
                        '-V',
                        'date:%s' % art.time,
                        '-V',
                        'title:%s' % art.title,
                        '-V',
                        'author:%s' % art.author,
                        '-N'
                    ], stdout=tmp, stderr=tmp):
                        log.info('failed')
                        return
                    log.info('tex to pdf')
                    if sp.call([
                        'xelatex',
                        '-shell-escape',
                        '-interaction=nonstopmode',
                        '%s.tex' % art.name
                    ], stdout=tmp, stderr=tmp):
                        log.info('failed or warning')
                        return


if __name__ == '__main__':
    for art in load():
        convert(art)
