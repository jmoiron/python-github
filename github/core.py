#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Github wrapper which mimics my python-bitbucket wrapper, ironically
originally intended to mimic py-github.  But I don't like the way py-github
and python-github2 wrap all of the API results."""

from urllib2 import Request, urlopen
from urllib import urlencode
from functools import wraps
import re
import datetime
import time

try:
    import json
except ImportError:
    import simplejson as json

__all__ = ['AccessRestricted', 'AuthenticationRequired', 'to_datetime', 'Github']

api_base = 'https://github.com/api/v2/json/'
gist_base = 'https://gist.github.com/api/v1/json/'

github_timezone = '-0700'
github_date_format = '%Y/%m/%d %H:%M:%S'
commit_date_format = '%Y-%m-%dT%H:%M:%S'

class AuthenticationRequired(Exception):
    pass

class AccessRestricted(Exception):
    pass

def authenticated_user_only(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.gh.username != self.username:
            raise AccessRestricted("%s is only callable for the authenticated user" % method.__name__)
        return method(self, *args, **kwargs)
    return requires_authentication(wrapper)

def requires_authentication(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        is_authenticated = self.gh.is_authenticated if hasattr(self, 'gh') else self.is_authenticated
        if not is_authenticated:
            raise AuthenticationRequired("%s requires authentication" % method.__name__)
        return method(self, *args, **kwargs)
    return wrapper

def handle_pagination_all(method):
    """Handles the "all" keyword argument, looping over the method page by
    page until the page is empty and then returning a list of items."""
    @wraps(method)
    def wrapper(self, **kwargs):
        kwargs = dict(kwargs)
        all = kwargs.pop('all', None)
        if all:
            kwargs['page'] = 1
            items = []
            result = method(self, **kwargs)
            while result:
                items += result
                kwargs['page'] += 1
                try:
                    result = method(self, **kwargs)
                except:
                    break
            return items
        return method(self, **kwargs)
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
    import pytz
    mountain = re.search('-07:?00', timestring)
    stripped = re.sub('-0\d:?00', '', timestring).strip()
    try:
        dt = datetime.datetime(*time.strptime(stripped, github_date_format)[:6])
    except ValueError:
        try:
            dt = datetime.datetime(*time.strptime(stripped, commit_date_format)[:6])
        except ValueError:
            raise Exception("Unrecognized timestamp format for string \"%s\"" % timestring)
    if mountain:
        timezone = pytz.timezone('US/Mountain')
    else:
        timezone = pytz.timezone('US/Pacific')
    local = timezone.normalize(timezone.localize(dt))
    return local.astimezone(pytz.utc)

class Github(object):
    """Main github class.  Use an instantiated version of this class
    to make calls against the REST API."""
    def __init__(self, username='', password='', token='', throttle=True):
        self.username = username
        self.password = password
        self.token = token
        self.throttle = throttle
        self.throttle_list = []
        # extended API support

    def _is_authenticated(self):
        return self.username and any([self.password, self.token])
    is_authenticated = property(_is_authenticated)

    def wait(self):
        """Handle request throttling.  Keeps a list of request timestamps and
        will wait ultil oldest+60 if there are 60 timestamps in the queue."""
        if not self.throttle:
            return
        now = time.time()
        a_minute_ago = now - 60
        self.throttle_list = [t for t in self.throttle_list if t > a_minute_ago]
        if len(self.throttle_list) < 60:
            self.throttle_list.append(now)
            return
        oldest = self.throttle_list[0]
        if len(self.throttle_list) >= 60:
            time.sleep((oldest + 60) - now)

    def build_request(self, url, data=None):
        if not self.is_authenticated:
            return Request(url)
        if self.password:
            auth = '%s:%s' % (self.username, self.password)
        else:
            auth = '%s/token:%s' % (self.username, self.token)
        auth = {'Authorization': 'Basic %s' % (auth.encode('base64').strip())}
        return Request(url, data, auth)

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

    def post_url(self, url, data={}, quiet=False):
        data = dict(data)
        self.wait()
        request = self.build_request(url, urlencode(data))
        try:
            result = urlopen(request).read()
        except:
            if not quiet:
                import traceback
                traceback.print_exc()
                print "url was: %s" % url
            result = False
        return result

    def user_search(self, term):
        pass

    def repository_search(self, term):
        pass

    def user(self, username):
        return User(self, username)

    def repository(self, username, name):
        return Repository(self, username, name)

    def gist(self, id):
        return Gist(self, id)

    @requires_authentication
    def organizations(self):
        url = api_base + 'organizations'
        return json.loads(self.load_url(url))

    def __repr__(self):
        extra = ''
        if self.is_authenticated:
            extra = ' (auth: %s)' % self.username
        return '<Github API%s>' % extra

class User(object):
    """API encapsulation for user related bitbucket queries."""
    def __init__(self, gh, username):
        self.gh = gh
        self.username = username

    def repository(self, name):
        return Repository(self.gh, self.username, name)

    @handle_pagination_all
    def repositories(self, page=None, all=False):
        """Show a user's repositories.  If 'all' is True, load all pages."""
        query = smart_encode(page=page)
        url = api_base + 'repos/show/%s' % self.username
        if query:
            url += '?%s' % query
        return json.loads(self.gh.load_url(url))['repositories']

    def watched_repositories(self):
        """Show repositories a user is following.  I am not sure if this is
        paged or not."""
        url = api_base + 'repos/watched/%s' % self.username
        return json.loads(self.gh.load_url(url))['repositories']

    @authenticated_user_only
    def follow(self, username):
        """Follow user with currently authenticated user."""
        url = api_base + 'user/follow/%s' % username
        return bool(self.gh.post_url(url))

    @authenticated_user_only
    def unfollow(self, username):
        """Unfollow a user with currently authenticated user."""
        url = api_base + 'user/unfollow/%s' % username
        return bool(self.gh.post_url(url))

    def following(self):
        url = api_base + 'user/show/%s/following' % self.username
        return json.loads(self.gh.load_url(url))

    def followers(self):
        url = api_base + 'user/show/%s/followers' % self.username
        return json.loads(self.gh.load_url(url))

    @authenticated_user_only
    def emails(self):
        url = api_base + 'user/emails'
        return json.loads(self.gh.load_url(url))

    # XXX: the API docs aren't finished for these two
    @authenticated_user_only
    def add_email(self):
        raise NotImplementedError

    @authenticated_user_only
    def remove_email(self):
        raise NotImplementedError

    @authenticated_user_only
    def keys(self):
        url = api_base + 'user/keys'
        return json.loads(self.gh.load_url(url))

    @authenticated_user_only
    def add_key(self, title, key):
        url = api_base + 'user/key/add'
        return self.gh.post_url(url, dict(title=title, key=key))

    @authenticated_user_only
    def remove_key(self, id):
        url = api_base + 'user/key/remove'
        return self.gh.post_url(url, dict(id=id))

    def gists(self, private=False):
        if private:
            raise NotImplementedError #XXX: no API docs yet
        url = gist_base + 'gists/%s' % self.username
        return json.loads(self.gh.load_url(url))

    def gist(self, id):
        # XXX: Gists don't actually "belong" to a user under the GIST API,
        # but it makes sense to be able to fetch them from the user as well
        return Gist(self.gh, id)

    @authenticated_user_only
    def create_gist(self, *args, **kwargs):
        raise NotImplementedError

    def get(self):
        url = api_base + 'user/show/%s' % self.username
        return json.loads(self.gh.load_url(url)).get('user', {})

    def __repr__(self):
        return '<User: %s>' % self.username

class Repository(object):
    def __init__(self, gh, username, name):
        self.gh = gh
        self.username = username
        self.name = name
        self.project = '%s/%s' % (username, name)

    def get(self):
        url = api_base + 'repos/show/%s/%s' % (self.username, self.name)
        return json.loads(self.gh.load_url(url))

    @requires_authentication
    def watch(self):
        raise NotImplementedError

    @handle_pagination_all
    def commits(self, branch='master', page=None, all=False):
        query = smart_encode(page=page)
        url = api_base + 'commits/list/%s/%s/%s' % (self.username, self.name, branch)
        if query:
            url += '?%s' % query
        return json.loads(self.gh.load_url(url)).get('commits', [])

    def commit(self, sha):
        url = api_base + 'commits/show/%s/%s/%s' % (self.username, self.name, sha)
        return json.loads(self.gh.load_url(url)).get('commit', {})

    def tags(self):
        """Get a list of tags for a repository."""
        url = api_base + 'repos/show/%s/%s/tags' % (self.username, self.name)
        return json.loads(self.gh.load_url(url)).get('tags', [])

    def branches(self):
        """Get a list of branches for a repository."""
        url = api_base + 'repos/show/%s/%s/branches' % (self.username, self.name)
        return json.loads(self.gh.load_url(url)).get('branches', [])

    def issue(self, number):
        return Issue(self.gh, self.username, self.name, number)

    def followers(self):
        url = self.base_url + 'followers/'
        return json.loads(self.gh.load_url(url))

    def __repr__(self):
        return '<Repository: %s\'s %s>' % (self.username, self.name)

class Gist(object):
    def __init__(self, gh, id):
        self.gh = gh
        self.id = id

    def get(self):
        url = gist_base + '%s' % self.id
        return json.loads(self.gh.load_url(url))['gists']

    def get_file(self, filename):
        """Get a raw file from a gist.  Note that this is not in json, but
        in whatever format the file in the gist is in."""
        url = 'http://gist.github.com/raw/%s/%s' % (self.id, filename)
        return self.gh.load_url(url)

    @requires_authentication
    def fork(self, *args, **kwargs):
        raise NotImplementedError

    @requires_authentication
    def delete(self, *args, **kwargs):
        raise NotImplementedError

    @requires_authentication
    def edit(self, *args, **kwargs):
        raise NotImplementedError

    def __repr__(self):
        return '<Gist %s>' % (self.id)

class Issue(object):
    def __init__(self, gh, username, repos, number):
        self.gh = gh
        self.username = username
        self.repos = repos
        self.number = number

    def get(self):
        url = api_base + 'issues/show/%s/%s/%s' % (self.username. self.repos, self.number)
        return json.loads(self.gh.load_url(self.base_url))

    def followers(self):
        url = self.base_url + 'followers/'
        return json.loads(self.gh.load_url(url))

    def __repr__(self):
        return '<Issue #%s on %s\'s %s>' % (self.number, self.username, self.slug)

