# Undo Framework for Python

**NB 2023/10/03:** this is a fork of the [archived _aquavitae/undo_ project](https://bitbucket-archive.softwareheritage.org/projects/aq/aquavitae/undo.html) by [@aquavitae](https://github.com/aquavitae). The original project was hosted on Bitbucket, and used Mercurial as its CVS.

This is an undo/redo framework based on a functional approach which uses
a undoable stack to track actions.  Actions are the result of a function
call and know how to undo and redo themselves, assuming that any objects
they act on will always be in the same state before and after the action
occurs respectively.  The `Stack` tracks all actions which can be done
or undone.


## Installation

**undo** can be downloaded from [http://bitbucket.org/aquavitae/undo](http://bitbucket.org/aquavitae/undo)
and installed using `python setup.py install`.  It has been tested
with Python 2.7 and Python 3.2, and has no extra dependencies.
