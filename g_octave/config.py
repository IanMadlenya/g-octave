# -*- coding: utf-8 -*-

"""
    config.py
    ~~~~~~~~~
    
    This module implements a Python object to handle the configuration
    of g-octave.
    
    :copyright: (c) 2009-2010 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

__all__ = ['Config']

import ConfigParser
import json
import os

from exception import ConfigException

class Config(object):
    
    _defaults = {
        'db': '/var/cache/g-octave',
        'overlay': '/usr/local/portage/g-octave',
        'categories': 'main,extra,language',
        'db_mirror': 'http://soc.dev.gentoo.org/~rafaelmartins/g-octave/db/',
        'trac_user': '',
        'trac_passwd': '',
        'pkg_cache': '',
        'log_level': '',
        'log_file': '/var/log/g-octave.log',
    }

    _section_name = 'main'


    def __init__(self, fetch_phase=False, config_file=None, create_dirs=True):
        
        # Config Parser
        self._config = ConfigParser.ConfigParser(self._defaults)
        
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
        
        _db = self._config.get(self._section_name, 'db')
        _overlay = self._config.get(self._section_name, 'overlay')
        
        for dir in [_db, _overlay]:
            if not os.path.exists(dir) and create_dirs:
                os.makedirs(dir, 0755)
        
        self._cache = {}
        self._info = {}
        
        if not fetch_phase:
            
            # Cache (JSON)
            cache_file = os.path.join(_db, 'cache.json')
            with open(cache_file) as fp:
                self._cache = json.load(fp)
            
            # JSON
            json_file = os.path.join(_db, self._cache['files']['info.json'])
            with open(json_file) as fp:
                self._info = json.load(fp)
        

    def __getattr__(self, attr):
        
        if attr in self._defaults:
            return self._config.get(self._section_name, attr)
        elif attr in self._info:
            return self._info[attr]
        elif attr == 'cache' and 'files' in self._cache:
            return self._cache['files']
        else:
            raise ConfigException('Invalid option: %s' % attr)
