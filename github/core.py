#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Github wrapper which mimics my python-bitbucket wrapper, ironically
originally intended to mimic py-github.  But I don't like the way py-github
and python-github2 wrap all of the API results."""

from urllib2 import Request, urlopen
from urllib import urlencode
from functools import wraps
import datetime
import time

try:
    import json
except ImportError:
    import simplejson as json

__all__ = ['AuthenticationRequired', 'to_datetime', 'Github']

api_base = 'https://github.com/api/v2/json/'

github_timezone = '-0700'
github_date_format = '%Y/%m/%d %H:%M:%S'
commit_date_format = '%Y-%m-%dT%H:%M:%S'

class AuthenticationRequired(Exception):
    pass

def requires_authentication(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        is_authenticated = self.gh.is_authenticated if hasattr(self, 'gh') else self.is_authenticated
        if not is_authenticated:
            raise AuthenticationRequired("%s requires authentication" % method.__name__)
        return method(self, *args, **kwargs)
    return wrapper

def smart_encode(**kwargs):
    """Urlencode's provided keyword arguments.  If any kwargs are None, it does
    not include those."""
    args = dict(kwargs)
    for k,v in args.items():
        if v is None:
            del args[k]
    if not args:
        return ''
    return urlencode(args)

def to_datetime(timestring):
    """Convert one of the bitbucket API's timestamps to a datetime object."""
    format = '%Y-%m-%d %H:%M:%S'
    return datetime.datetime(*time.strptime(timestring, format)[:7])

class Github(object):
    """Main github class.  Use an instantiated version of this class
    to make calls against the REST API."""
    def __init__(self, username='', password='', token='', throttle=True):
        self.username = username
        self.password = password
        self.token = token
        self.is_authenticated = self.username and any([self.password, self.token])
        self.throttle = throttle
        self.throttle_list = []
        # extended API support

    def wait(self):
        """Handle request throttling.  Keeps a list of request timestamps and
        will wait ultil oldest+60 if there are 60 timestamps in the queue."""
        if not self.throttle:
            return
        now = time.time()
        a_minute_ago = now - 60
        self.throttle_list = [t for t in self.throttle_list if t > a_minute_ago]
        oldest = self.throttle_list[0]
        if len(self.throttle_list) >= 60:
            time.sleep((oldest + 60) - now)
        self.throttle_list.append(oldest+60)

    def build_request(self, url):
        if not self.is_authenticated:
            return Request(url)
        if self.password:
            auth = '%s:%s' % (self.username, self.password)
        else:
            auth = '%s/token:%s' % (self.username, self.token)
        auth = {'Authorization': 'Basic %s' % (auth.encode('base64').strip())}
        return Request(url, None, auth)

    def load_url(self, url, quiet=False):
        self.wait()
        request = self.build_request(url)
        try:
            result = urlopen(request).read()
        except:
            if not quiet:
                import traceback
                traceback.print_exc()
                print "url was: %s" % url
            result = "[]"
        return result

    def user(self, username):
        return User(self, username)

    def repository(self, username, name):
        return Repository(self, username, name)

    @requires_authentication
    def organizations(self):
        url = api_base + 'organizations'
        return json.loads(self.load_url(url))

    def __repr__(self):
        extra = ''
        if all((self.username, self.password)):
            extra = ' (auth: %s)' % self.username
        return '<Github API%s>' % extra

class User(object):
    """API encapsulation for user related bitbucket queries."""
    def __init__(self, gh, username):
        self.gh = gh
        self.username = username

    def repository(self, name):
        return Repository(self.gh, self.username, name)

    def repositories(self, page=None, all=False):
        """Show a user's repositories.  If 'all' is True, load all of the
        pages."""
        if all:
            repos = []
            page = 1
            result = self.repositories(page=page)
            while result:
                repos += result
                page += 1
                result = self.repositories(page=page)
            return repos
        query = smart_encode(page=page)
        url = api_base + 'repos/show/%s' % self.username
        if query:
            url += '?%s' % query
        return json.loads(self.gh.load_url(url))['repositories']

    def events(self, start=None, limit=None):
        query = smart_encode(start=start, limit=limit)
        url = api_base + 'users/%s/events/' % self.username
        if query:
            url += '?%s' % query
        return json.loads(self.gh.load_url(url))

    def get(self):
        url = api_base + 'users/%s/' % self.username
        return json.loads(self.gh.load_url(url))

    def __repr__(self):
        return '<User: %s>' % self.username

class Repository(object):
    def __init__(self, gh, username, slug):
        self.gh = gh
        self.username = username
        self.slug = slug
        self.base_url = api_base + 'repositories/%s/%s/' % (self.username, self.slug)

    def get(self):
        return json.loads(self.gh.load_url(self.base_url))

    def changeset(self, revision):
        """Get one changeset from a repos."""
        url = self.base_url + 'changesets/%s/' % (revision)
        return json.loads(self.gh.load_url(url))

    def changesets(self, limit=None):
        """Get information about changesets on a repository."""
        url = self.base_url + 'changesets/'
        query = smart_encode(limit=limit)
        if query: url += '?%s' % query
        return json.loads(self.gh.load_url(url, quiet=True))

    def tags(self):
        """Get a list of tags for a repository."""
        url = self.base_url + 'tags/'
        return json.loads(self.gh.load_url(url))

    def branches(self):
        """Get a list of branches for a repository."""
        url = self.base_url + 'branches/'
        return json.loads(self.gh.load_url(url))

    def issue(self, number):
        return Issue(self.gh, self.username, self.slug, number)

    def issues(self, start=None, limit=None):
        url = self.base_url + 'issues/'
        query = smart_encode(start=start, limit=limit)
        if query: url += '?%s' % query
        return json.loads(self.gh.load_url(url))

    def events(self):
        url = self.base_url + 'events/'
        return json.loads(self.gh.load_url(url))

    def followers(self):
        url = self.base_url + 'followers/'
        return json.loads(self.gh.load_url(url))

    def __repr__(self):
        return '<Repository: %s\'s %s>' % (self.username, self.slug)

class Issue(object):
    def __init__(self, gh, username, slug, number):
        self.gh = gh
        self.username = username
        self.slug = slug
        self.number = number
        self.base_url = api_base + 'repositories/%s/%s/issues/%s/' % (username, slug, number)

    def get(self):
        return json.loads(self.gh.load_url(self.base_url))

    def followers(self):
        url = self.base_url + 'followers/'
        return json.loads(self.gh.load_url(url))

    def __repr__(self):
        return '<Issue #%s on %s\'s %s>' % (self.number, self.username, self.slug)

