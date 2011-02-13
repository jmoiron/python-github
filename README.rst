python-github
-----------

A simple python library to access the GitHub API.

usage
=====

API Usage all stems from the ``Github`` object.  You can instantiate one
easily::
    
    >>> import github
    >>> gh = github.Github()
    >>> gh
    <Github API>

Github's API also has a lot of write access, and some private data for a user
is only accessible when authenticated as that user.  Github's auth is HTTP 
Basic over https, and you can authenticate with either a username/password
pair or a username/token pair.  Your token can be found in the _`Account Admin`
section of your github account preferences.  You can auth either of these two
ways:

.. _admin: https://github.com/account#admin_bucket

    >>> gh = github.Github('jmoiron', 'mypassword')
    >>> gh
    <Github API (auth: jmoiron)>
    >>> gh = github.Github('jmoiron', token='mytokenwhichisquiteabitlonger')
    >>> gh
    <Github API (auth: jmoiron)>

If at any time you set the ``username`` and one of the ``password`` or 
``token`` attributes on the Github object, authentication becomes active on
your subsequent requests.

getting data
============

``Github`` provides an objected oriented querying hierarchy that is based on
ownership relationships between data on Github more than it is on the structure
of the REST API itself::

    >>> import pprint
    >>> jmoiron = gh.user("jmoiron")
    >>> jmoiron
    <User: jmoiron>
    >>> pprint.pprint(jmoiron.repositories())
    [{u'created_at': u'2010/10/26 20:28:08 -0700',
      u'description': u'python command-line photo management thing',
      u'fork': False,
      u'forks': 1,
      u'name': u'iris',
      ...
    ]
    >>> iris = jmoiron.repository('iris')
    >>> iris
    <Repository: jmoiron's iris>
    >>> pprint.pprint(iris.commits()[0])
    {u'author': {u'email': u'jmoiron@jmoiron.net',
                 u'login': u'jmoiron',
                 u'name': u'Jason Moiron'},
     u'authored_date': u'2010-11-10T21:19:10-08:00',
     u'committed_date': u'2010-11-10T21:19:10-08:00',
     u'committer': {u'email': u'jmoiron@jmoiron.net',
                    u'login': u'jmoiron',
                    u'name': u'Jason Moiron'},
     u'id': u'9cf5068398cfd1b2dbbaf86a33583a2ed395d259',
     u'message': u'a little work on the shell side of parsing the queries',
     u'parents': [{u'id': u'3291c3c8e891d0d00ca832450998446472bd902e'}],
     u'tree': u'd61d15176f0a865365bb9cfaacad7286470626b4',
     u'url': u'/jmoiron/iris/commit/9cf5068398cfd1b2dbbaf86a33583a2ed395d259'}

``github`` mostly returns results that are unmodified from what the Github 
REST API itself returns.  The result formats can thus be mostly determined
from _`github's developer API documents`.

.. _github's developer API documents: http://develop.github.com/

