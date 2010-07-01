# -*- coding: utf-8 -*-

"""
    ebuild.py
    ~~~~~~~~~
    
    This module implements a Python class responsible to create the ebuilds
    for the octave-forge packages and track the dependencies correctly.
    
    :copyright: (c) 2009-2010 by Rafael Goncalves Martins
    :license: GPL-2, see LICENSE for more details.
"""

__all__ = [
    'Ebuild',
    're_keywords',
]

from config import Config
from description import *
from description_tree import *
from exception import EbuildException

has_svn = True
try:
    from svn.description import SvnDescription
except:
    has_svn = False

from portage.versions import vercmp

import os
import portage
import re
import shutil
import subprocess

out = portage.output.EOutput()

# validating keywords (based on the keywords from the sci-mathematics/octave package)
re_keywords = re.compile(r'(~)?(alpha|amd64|hppa|ppc64|ppc|sparc|x86)')

class Ebuild:
    
    def __init__(self, pkg_atom, force=False, conf=None):
        
        self.__force = force
        
        if conf is None:
            conf = Config()
        
        self._config = conf
        
        self.__dbtree = DescriptionTree(conf = self._config)
        self.svn_version = False
        
        atom = re_pkg_atom.match(pkg_atom)
        if atom == None:
            self.pkgname = pkg_atom
            self.version = self.__dbtree.latest_version(self.pkgname)
        else:
            self.pkgname = atom.group(1)
            self.version = atom.group(2)
            if has_svn and self.version == '9999':
                self.svn_version = True
        
        if self.svn_version:
            category = self.__dbtree.categories.get(self.pkgname, None)
            if category is not None:
                self.__desc = SvnDescription(category, self.pkgname)
            else:
                raise EbuildException('Failed to find the octave-forge category of this package.')
        else:
            self.__desc = self.__dbtree['%s-%s' % (self.pkgname, self.version)]
        
        if self.__desc == None:
            raise EbuildException('Package not found: %s' % pkg_atom)
        

    def description(self):
        
        return self.__desc


    def create(self, display_info=True, accept_keywords=None, manifest=True, nodeps=False):
        
        my_ebuild = os.path.join(
            self._config.overlay,
            'g-octave',
            '%s' % self.pkgname,
            '%s-%s.ebuild' % (self.pkgname, self.version)
        )
        
        if not os.path.exists(my_ebuild) or self.__force:
            
            if display_info:
                out.einfo('Creating ebuild: g-octave/%s-%s.ebuild' % (self.pkgname, self.version))
            
            try:
                my_atom = self.__create(accept_keywords, manifest)
            except Exception, error:
                if display_info:
                    out.eerror('Failed to create: g-octave/%s-%s.ebuild' % (self.pkgname, self.version))
                raise EbuildException(error)
            else:
                if not nodeps:
                    self.__resolve_dependencies()
                return my_atom
        
        else:
            return '=g-octave/%s-%s' % (self.pkgname, self.version)


    def __create(self, accept_keywords=None, manifest=True):
        
        ebuild_path = os.path.join(self._config.overlay, 'g-octave', self.pkgname)
        ebuild_file = os.path.join(ebuild_path, '%s-%s.ebuild' % (self.pkgname, self.version))
        
        if not os.path.exists(ebuild_path):
            os.makedirs(ebuild_path, 0755)
        
        ebuild = """\
# Copyright 1999-2010 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# This ebuild was generated by g-octave

EAPI="3"

G_OCTAVE_CAT="%(category)s"

inherit g-octave%(eutils)s

DESCRIPTION="%(description)s"
HOMEPAGE="%(url)s"

LICENSE="|| ( GPL-2 GPL-3 LGPL BSD GFDL )"
SLOT="0"
KEYWORDS="%(keywords)s"
IUSE=""

# it's annoying have to see the download of packages from the official
# mirrors fail with a 404 error.
RESTRICT="mirror"

DEPEND="%(depend)s"
RDEPEND="${DEPEND}
\t%(rdepend)s"
"""
        
        description = len(self.__desc.description) > 70 and \
            self.__desc.description[:70]+'...' or self.__desc.description
        
        if accept_keywords is None:
            accept_keywords = portage.settings['ACCEPT_KEYWORDS']
        
        category = self.__dbtree.categories.get(self.pkgname, '')
        
        vars = {
            'eutils': '',
            'description': description,
            'url': self.__desc.url,
            'keywords': self.__keywords(accept_keywords),
            'category': category,
            'depend': '',
            'rdepend': '',
        }
        
        vars['depend']   = self.__depends(self.__desc.buildrequires)
        
        systemrequirements = self.__depends(self.__desc.systemrequirements)
        if systemrequirements != '':
            vars['depend']  += "\n\t"+systemrequirements
        
        vars['rdepend']  = self.__depends(self.__desc.depends)
        
        patches = self.__search_patches()
        
        if len(patches) > 0:
            
            # WOW, we have patches :(
            
            patchesdir = os.path.join(self._config.db, 'patches')
            filesdir = os.path.join(self._config.overlay, 'g-octave', self.pkgname, 'files')
            if not os.path.exists(filesdir):
                os.makedirs(filesdir, 0755)
            
            patch_string = ''
            for patch in patches:
                patch_string += "\n\tepatch \"${FILESDIR}/%s\"" % patch
                shutil.copy2(os.path.join(patchesdir, patch), filesdir)
            
            ebuild += "\nsrc_prepare() {%s\n}\n" % patch_string
            vars['eutils'] = ' eutils'
            
        fp = open(ebuild_file, 'w', 0644)
        fp.write(ebuild % vars)
        fp.close()
        
        if manifest:
            proc = subprocess.call(['ebuild', ebuild_file, 'manifest'])
            
            if proc != os.EX_OK:
                raise EbuildException('Failed to create Manifest file!')
        
        return '=g-octave/%s-%s' % (self.pkgname, self.version)
        
    
    def __keywords(self, accept_keywords):
        
        keywords = [i.strip() for i in accept_keywords.split(' ')]
        
        stable = []
        unstable = []
        
        for keyword in keywords:
            match = re_keywords.match(keyword)
            if match == None:
                raise EbuildException('Invalid keyword: %s' % keyword)
            if match.group(1) == None:
                stable.append(match.group(2))
            else:
                unstable.append(match.group(2))
        
        final = ['~'+i for i in unstable]
        
        for keyword in stable:
            if keyword not in unstable:
                final.append(keyword)
        
        return ' '.join(final)
    
    
    def __depends(self, mylist):
        
        if mylist != None:
            return "\n\t".join(mylist)
        
        return ''


    def __search_patches(self):
        
        patches_dir = os.path.join(self._config.db, 'patches')
        
        if not os.path.exists(patches_dir):
            return []
        
        tmp = []
        
        for patch in os.listdir(patches_dir):
            if re.match(r'^([0-9]{3})_%s-%s' % (self.pkgname, self.version), patch):
                tmp.append(patch)
        
        tmp.sort()
        
        return tmp


    def __resolve_dependencies(self):
        
        to_install = []
        
        for pkg, comp, version in self.__desc.self_depends:
            
            # no version required, get the latest available
            if version == None:
                to_install.append('%s-%s' % (pkg, self.__dbtree.latest_version(pkg)))
                continue
            
            # here we need to calculate the better version to install
            versions = self.__dbtree.package_versions(pkg)
            
            allowed_versions = []
            
            for _version in versions:
                comparation = vercmp(_version, version)
                if eval('%s %s 0' % (comparation, comp)):
                    allowed_versions.append(_version)
                
            to_install.append('%s-%s' % (pkg, self.__dbtree.version_compare(allowed_versions)))
        
            if len(to_install) == 0:
                raise EbuildException('Can\'t resolve a dependency: %s' % pkg)
        
        # creating the ebuilds for the dependencies, recursivelly
        for ebuild in to_install:
            Ebuild(ebuild).create()
