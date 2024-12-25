# FlexElog #

FlexElog is a fast, configurable electronic logbook program patterned after [PSI's elog](https://elog.psi.ch/elog/),
but with a fast database backend, a new editor with support for Markdown, inline images, charts and (in progress) laTeX capabilities.  You can migrate an existing PSI elog setup to flexelog, or you can start with a new elog configuration and create a new set of logbooks.

Flexelog is written in pure Python for easy portability while maintaining great speed, as the work done in Python (as opposed to libraries) is not the time-sensitive parts.  It's built on the mature Django web platform to help ensure security and flexibility.  It also makes admin management of elogs and users/groups easier.

Compared with PSI elog, flexelog keeps:
- very similar (elogd.cfg style) configuration 'lamguage'
- the same look and url patterns for common features
- web pages look almost identical, including...
- same CSS styles
- same language translations

What it changes:
- previous PSI elog entries are migrated to an SQL database (much faster searches, much less code to maintain)
- code is pure Python
- Markdown is the default entry type.  Legacy plain, html and ELCode can be viewed.  Viewing of ELCode entries as Markdown is planned.

Of course not all features of PSI's elog are available initially for this project.  The features were tailored for my own use cases.

See below for more information about planned and supported features.


## Installing

See  Quickstart

## Migrating an existing set of PSI logbooks:

See Quickstart

## Supported features in first release

* Migration of existing PSI elog logbooks
* creation of new logbooks
* Web-based serving of elog pages
* Most common features of elogd.cfg supported
* Ability to view, add, edit, reply to, and delete elog entries
* elog summary listing with sorting and filtering (search) of results
* initial support for conditional Attributes
* some Preset support

## Planned Features

Planned features in the short term include:
* Quick filter for column info, date range
* Cleaner display of ELCode from PSI elogs

## Current major differences from PSI elog

General differences not yet available:
* no 'Top Groups'
* no threaded views
* no email capabilities
* multi-editing through Select command


## Development

To install the development version of flexelog (in a virtual env if desired):

    git clone github.com/darcymason/flexelog
    cd flexelog
    pip install -e .
