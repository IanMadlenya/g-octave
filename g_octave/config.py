# -*- coding: utf-8 -*-

"""
    config.py
    ~~~~~~~~~
    
    This module implements a Python object to handle the configuration
    of g-octave.
    
    :copyright: (c) 2009-2010 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

from __future__ import absolute_import

__all__ = ['Config']

import json
import os

from .compat import py3k, open
from .exception import ConfigException

if py3k:
    import configparser
else:
    import ConfigParser as configparser

class Config(object):
    
    _defaults = {
        'db': '/var/cache/g-octave',
        'overlay': '/var/lib/g-octave',
        'categories': 'main,extra,language',
        'db_mirror': 'github://rafaelmartins/g-octave-db-test',
        'trac_user': '',
        'trac_passwd': '',
        'log_level': '',
        'log_file': '/var/log/g-octave.log',
        'package_manager': 'portage',
        'use_scm': 'false',
    }

    _section_name = 'main'
    _env_namespace = 'GOCTAVE_'

    def __init__(self, fetch_phase=False, config_file=None, create_dirs=True):
        
        # Config Parser
        self._config = configparser.ConfigParser(self._defaults)
        
        self._fetch_phase = fetch_phase
        
        my_config = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'etc', 'g-octave.cfg.devel'
        )
        if config_file is not None:
            self._config_file = config_file
        elif os.path.exists(my_config):
            self._config_file = my_config
        else:
            self._config_file = '/etc/g-octave.cfg'
        
        self._config.read(self._config_file)
        
        _db = self._getattr('db')
        _overlay = self._getattr('overlay')
        
        for dir in [_db, _overlay]:
            if not os.path.exists(dir) and create_dirs:
                os.makedirs(dir, 0o755)
        
        self._cache = {}
        self._info = {}
        
        if not fetch_phase:
            
            # JSON
            json_file = os.path.join(_db, 'info.json')
            with open(json_file) as fp:
                self._info = json.load(fp)
        

    def __getattr__(self, attr):
        
        if attr in self._defaults:
            return self._getattr(attr)
        elif attr in self._info:
            return self._info[attr]
        else:
            raise ConfigException('Invalid option: %s' % attr)
    
    
    def _getattr(self, attr):
        from_env = os.environ.get(self._env_namespace + attr.upper(), None)
        if from_env is None:
            return self._config.get(self._section_name, attr)
        return from_env
    
