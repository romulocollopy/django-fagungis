#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import os

CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Framework :: Django',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'Operating System :: MacOS :: MacOS X',
    'Operating System :: Unix',
    'Operating System :: POSIX',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2.5',
    'Programming Language :: Python :: 2.6',
    'Topic :: Software Development',
    'Topic :: Software Development :: Build Tools',
    'Topic :: Software Development :: Libraries',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: System :: Clustering',
    'Topic :: System :: Software Distribution',
    'Topic :: System :: Systems Administration',
]

setup(
    name="znc_django_deploy",
    version=__import__('tasks_manager').get_version(),
    url='https://bitbucket.org/znc/znc-django-deploy',
    download_url='https://bitbucket.org/znc/znc-django-deploy/downloads',
    license='BSD License',
    description="DJANGO + Fabric + Gunicorn + Nginx + Supervisor deployment",
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.md')).read(),
    author='ZNC Sistemas',
    author_email='contato@znc.com.br',
    keywords='django fabric gunicorn nginx supervisor',
    packages=find_packages(),
    namespace_packages=['tasks_manager'],
    include_package_data=True,
    zip_safe=False,
    classifiers=CLASSIFIERS,
    install_requires=[
        'Fabric>=1.3',
    ],
)
