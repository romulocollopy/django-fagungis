===========================================================================
django-fagungis: DJANGO + FAbric + GUnicorn + NGInx + Supervisor deployment
===========================================================================

Introduction
============

django-fagungis allow you to easy setup and deploy your django project on
your linux server.
django-fagungis will install and configure for you:

* nginx

* gunicorn

* supervisor

* virtualenv

Patches are welcome! Feel free to fork and contribute to this project on:

**bitbucket**: `bitbucket.org/DNX/django-fagungis <https://bitbucket.org/DNX/django-fagungis/>`_


**github**: `github.com/DNX/django-fagungis <https://github.com/DNX/django-fagungis>`_


Installation
============

There are a few different ways to install Fagungis:

Using pip
---------
If you have pip install available on your system, just type::

    pip install git+https://github.com/cadu-leite/django-fagungis.git

If you've already got an old version of Fagungis, and want to upgrade, use::

    pip install -U git+https://github.com/cadu-leite/django-fagungis.git

Installing from a directory
---------------------------
If you've obtained a copy of Fagungis using either Git or a downloadable
archive, you'll need to install the copy you have system-wide. Try running::

    python setup.py develop

If that fails, you don't have ``setuptools`` or an equivalent installed;
either install them, or run::

    python setup.py install


How to use fagungis?
====================

If you have already installed Fagungis, you must proceed with the
configuration of your project.

Configuration
-------------

First of all you must configure your project task settings. To do this we
have prepared for you an example file in **path/to/fagungis/example_fabfile.py**
so you can create a copy of this file and modify it according to your
needs.

You can find also an online version of **example_fabfile.py** here: https://raw.github.com/damianmoore/django-fagungis/master/fagungis/example_fabfile.py

Please pay attention to not have any tasks in your fabfile.py called:
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

* setup

* deploy

* test_configuration

* hg_pull

* git_pull

* remove

because these names are reserved by Fagungis.

Test your configuration first!
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fagungis come with its own automatic configuration tests. Each time you run
**setup** or **deploy** task, configuration tests are called.
Anyway, you can manually run these tests for your project configuration::

    fab project_name test_configuration

If you run **test_configuration** manually, you'll observe some output about all your project settings.

Do you need an example?
~~~~~~~~~~~~~~~~~~~~~~~

OK, let's assume you want to configure your django project called "simpleproject".
So, what do we know about it?
We know:

* the project is called **simpleproject**

* the git repository is **https://github.com/damianmoore/django-simple-project.git**

* the IP of the server where you want to host it is: **88.88.88.88**

* you want to use the domain **simpleproject.org** which points to 88.88.88.88


OK, it's enough to configure and deploy your project, let's do it!
Clone example_fabfile.py::

    cp path/to/fagungis/example_fabfile.py path/to/projectus/fabfile.py

or::

    wget -O fabfile.py https://raw.github.com/cadu-leite/django-fagungis/master/fagungis/example_fabfile.py


Now apply some changes to earlier cloned fabfile.py file in your project root:

* change task name::

    # from:
    @task
    def example():
    # to:
    @task
    def simpleproject():

* change project name::

    # from:
    env.project = 'example_production'
    # to:
    env.project = 'simpleproject'

* change repository::

    # from:
    env.repository = 'https://bitbucket.org/DNX/example'
    # to:
    env.repository = 'https://github.com/damianmoore/django-simple-project.git'

* change repository type::

    # from:
    env.repository_type = 'hg'
    # to:
    env.repository_type = 'git'

* change server IP::

    # from:
    env.hosts = ['root@192.168.1.1', ]
    # to: (or whatever the address of your server is)
    env.hosts = ['root@88.88.88.88', ]

* change nginx server name::

    # from:
    env.nginx_server_name = 'example.com'
    # to:
    env.nginx_server_name = 'simpleproject.org'

not, let's test our configuration::

    fab simpleproject test_configuration

you must see a message::

    Configuration tests passed!


Setup your project
------------------

Assuming you've configured your project now you are ready to launch the setup::

    fab simpleproject setup

during this process you can see all the output of the commands launched on
the server. At some point you may be asked for some information as django
user password(if django user did not exist before) or repository password to
clone your project.
At the end of this task you must view a message saying that the setup
successful ended.
Now you can go on with the deployment of the project.
**Please** test manualy the setup at least at the first time following
this guide:: https://bitbucket.org/DNX/django-fagungis/wiki/Setup_test

Deploy the project
------------------

After you've run the setup you're ready to deploy your project. This is as
simple as typing::

    fab simpleproject deploy

As for setup you may be asked for some info during the deployment.
At the end you must view a message saying that the deployment successful
ended.
Set the IP address of your server to simpleproject.org in your /etc/hosts file.
Now navigate to **http://simpleproject.org** in your browser and assure that
everything is OK.


How to test fagungis?
=====================

**Please** test all operations manualy, at least at the first time, following
this guide:

https://bitbucket.org/DNX/django-fagungis/wiki/Setup_test

This will increase your confidence in using **fagungis**.
