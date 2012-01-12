#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 David Townshend
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 675 Mass Ave, Cambridge, MA 02139, USA.

'''
This is an undo/redo framework which uses a undoable stack to track 
actions.  Commands are defined using decorators on functions and methods, 
and a new instance is added to the stack when the function is called.  

Usage
-------

Basic operation
^^^^^^^^^^^^^^^

Undo commands are defined using :func:`undoable` as a decorator. The
returned object has an *undo()* method, which should then be used
to define the undo operation. 

>>> @undoable('Add {pos}')
... def add(state, seq, item):
...     seq.append(item)
...     state['seq'] = seq
...     state['pos'] = len(seq) - 1
... 
>>> @add.undo
... def add(state):
...     seq, pos = state['seq'], state['pos']
...     del seq[pos]

As can be seen from this, a common argument, *state*, is used to transfer 
data between the functions. The exposed signature of *add*, however is
``add(seq, item)``. *state* is a dict in which data may be stored as 
required to undo the operation. It is also used to format the description of
the operation as returned by :func:`stack.undotext` and 
:func:`stack.redotext`.

*add* now acts as a normal function.

>>> sequence = [1, 2, 3, 4]
>>> add(sequence, 5)
>>> sequence
[1, 2, 3, 4, 5]

However, in the background, when it is called, an instance of the action is
stored in `stack` and its description can be queried using 
:func:`stack.undotext`.

>>> stack().undotext()
'Undo Add 4'

The action can be undone using :func:`stack.undo`.

>>> stack().undo()
>>> sequence
[1, 2, 3, 4]

It can then be redone with :func:`stack.redo`.

>>> stack().redo()
>>> sequence
[1, 2, 3, 4, 5]

Return values and exceptions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The action may have a return value, but this will only be returned when
it is first explicitly called. Subsequent redo or undo calls will ingore 
this.

>>> @undoable('Process')
... def process(state, obj):
...     obj[0] += 1
...     state['obj'] = obj
...     return obj
...
>>> @process.undo
... def process(state):
...     state['obj'][0] -=1
...
>>> obj = [1, 2]
>>> process(obj)
[2, 2]
>>> print(obj)
[2, 2]
>>> stack().undo()
>>> print(obj)
[1, 2]

If an exception is raised during the action, it is not added to the 
stack and the exception is propagated. If an exception is raised 
during a redo or undo operation, the exception is propagated and the
stack is cleared.  
     
Nested actions
^^^^^^^^^^^^^^

Consider a slightly more complex example which also allows deletions.

>>> @undoable('Add')
... def add(state, seq, item):
...     seq.append(item)
...     state['seq'] = seq
...
>>> @add.undo
... def add(state):
...     delete(state['seq'])
...
>>> @undoable('Delete')
... def delete(state, seq):
...     state['value'] = seq.pop()
...     state['seq'] = seq
...
>>> @delete.undo
... def delete(state):
...     add(state['seq'], state['value'])

This example illustrates that undoable actions can call each other safely 
(*delete.undo()* calls *add()* and *add.undo()* calls *delete()*).

>>> seq = [3, 6]
>>> add(seq, 4)
>>> seq
[3, 6, 4]
>>> stack().undo()
>>> seq
[3, 6]
>>> delete(seq)
>>> seq
[3]
>>> stack().undo()
>>> seq
[3, 6]

Clearing the stack
^^^^^^^^^^^^^^^^^^

The stack may be cleared if, for example, the document is saved.

>>> stack().canundo()
True
>>> stack().clear()
>>> stack().canundo()
False

Groups
^^^^^^

A series of commands may be grouped within a function using the
:func:`group` context manager.

>>> seq = []
>>> with _Group('Add many'):
...     for item in [4, 6, 8]:
...         add(seq, item)
>>> seq
[4, 6, 8]
>>> stack().undocount()
1
>>> stack().undo()
>>> seq
[]

Members
-------
'''

# Implementation Notes
# ^^^^^^^^^^^^^^^^^^^^

# The roles of an _Action are normally set using the :func:`undoable` 
# function as a decorator on the *do* function. This returns an
# :class:`_ActionFactory` instance. :func:`_ActionFactory.undo` can
# also be used as a decorator on the *undo* function.

import functools

from dtlibs.core import singleton, none
from collections import deque

class _Action:
    ''' This represents an action which can be done and undone.
    
    It is basically the result of a call on an undoable function and has
    three methods: ``do()``, ``undo()`` and ``text()``. This class
    should always be instantiated by an _ActionFactory.
    '''
    def __init__(self, vars, state):
        self.vars = vars
        self.state = state

    def do(self):
        'Redo the action'
        if 'instance' in self.vars and self.vars['instance'] is not None:
            args = (self.vars['instance'], self.state) + self.state['args']
        else:
            args = (self.state,) + self.state['args']
        kwargs = self.state['kwargs']
        return self.vars['do'](*args, **kwargs)

    def undo(self):
        'Undo the action'
        if 'instance' in self.vars and self.vars['instance'] is not None:
            args = (self.vars['instance'], self.state)
        else:
            args = (self.state,)
        self.vars['undo'](*args)

    def text(self):
        'Return the descriptive text of the action'
        return self.vars['text'].format(**self.state)


class _ActionFactory:
    ''' Used by the ``undoable`` function to create Actions.
    
    ``undoable`` returns an instance of an _ActionFactory, which is used 
    in code to set up the do and undo functions.  When called, it
    creates a new instance of an _Action, runs it and pushes it onto the stack.
    '''
    def __init__(self, desc, do, undo):
        self._desc = desc
        self._do = do
        self._undo = undo
        self._instance = None

    def __get__(self, instance, owner):
        'Store instance for bound methods.'
        self._instance = instance
        return self

    def do(self, func):
        ' Set the do function'
        self._do = func
        return self

    def undo(self, func):
        ' Set the undo function'
        self._undo = func
        return self

    def __call__(self, *args, **kwargs):
        ''' Either set ``do`` or create the action.
         
        If do has been set, this will create an _Action, run it and 
        push it onto the stack. If not, it will set the do function.
        This allows the following two ways of using it:
        >>> factory = _ActionFactory('desc', None, None)
        >>> @factory
        ... def do_something(self):
        ...     pass
        >>> do_something is factory
        True
        '''
        if self._do is None:
            self.do(args[0])
            return self
        else:
            assert None not in [self._do, self._undo]
            state = {'args': args, 'kwargs': kwargs}
            vars = {'text': self._desc, 'instance': self._instance,
                    'do': self._do, 'undo': self._undo}
            action = _Action(vars, state)
            ret = action.do()
            stack().append(action)
            return ret


def undoable(desc, do=None, undo=None):
    ''' Factory to create a new undoable action type. 
    
    This function creates a new undoable command given a description
    and do function. An undo function must also be specified before
    it is used, but is optional to allow :func:`undoable` to be used as a
    decorator. The command object returned has an *undo* method 
    which can be used as a decorator to set the undo function.
    
    >>> def do_something(state):
    ...     pass
    >>> def undo_something(state):
    ...     pass
    >>> command = undoable('Do something', do_something, undo_something)
    
    Or as a decorator:
    
    >>> @undoable('Do something')
    ... def do_something(state):
    ...     pass
    >>> @do_something.undo
    ... def do_something(state):
    ...     pass
    
    Both the do and undo functions should accept a *state* variable, 
    which is passed as the first argument (after *self*) to the *do*
    function and as the only argument (other than *self*) to the *undo*
    function. *state* is a dict of values which are used to transfer 
    data between *do* and *undo*, and initially contains keys 'args' and 
    'kwargs' which correspond to the arguments passed to the *do* function.
    
    The description string can include formatting commands (see 
    :ref:`Python's String Formatting <python:string-formatting>`), which 
    are formatted using the state variable. This can be retrieved using 
    ``stack().undotext()``
    
    >>> @undoable('description of {foo}')
    ... def do_foo(state):
    ...     state['foo'] = 'bar'
    >>> @do_foo.undo
    ... def do_foo(state):
    ...     pass
    >>> do_foo()
    >>> stack().undotext()
    'Undo description of bar'
    '''
    factory = _ActionFactory(desc, do, undo)
    functools.update_wrapper(factory, do)
    return factory


class _Group:
    ''' A undoable group context manager. '''

    def __init__(self, desc):
        self._desc = desc
        self._stack = []

    def __enter__(self):
        stack().setreceiver(self._stack)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            stack().resetreceiver()
            stack().append(self)
        return False

    def undo(self):
        for undoable in reversed(self._stack):
            undoable.undo()

    def do(self):
        for undoable in self._stack:
            undoable.do()

    def text(self):
        return self._desc.format(count=len(self._stack))


def group(desc):
    ''' Return a context manager for grouping undoable actions. '''
    return _Group(desc)

class stack(metaclass=singleton()):
    ''' The main undo stack. 
    
    This is a singleton, so it can always be called as ``stack()``.
    
    >>> stk = stack()
    >>> stk is stack()
    True
    >>> stack() is stack()
    True
    
    The two key features are the :func:`redo` and :func:`undo` methods. If an 
    exception occurs during doing or undoing a undoable, the undoable
    aborts and the stack is cleared to avoid any further data corruption. 
    
    The stack provides two properties for tracking actions: *docallback* 
    and *undocallback*. Each of these allow a callback function to be set
    which is called when an action is done or undone repectively. By default, 
    they do nothing.
    
    >>> def done():
    ...     print('Can now undo: {}'.format(stack().undotext()))
    >>> def undone():
    ...     print('Can now redo: {}'.format(stack().redotext()))
    >>> stack().docallback = done
    >>> stack().undocallback = undone
    >>> def action(state): pass
    >>> action = undoable('An action', action, action)
    >>> action()
    Can now undo: Undo An action
    >>> stack().undo()
    Can now redo: Redo An action
    >>> stack().redo()
    Can now undo: Undo An action
    
    Setting them back to :func:`dtlibs.core.none` will stop any 
    further actions.
    
    >>> stack().docallback = stack().undocallback = none
    >>> action()
    >>> stack().undo()
    
    It is possible to mark a point in the undo history when the document
    handled is saved. This allows the undo system to report whether a 
    document has changed. The point is marked using :func:`savepoint` and
    :func:`haschanged` returns whether or not the state has changed (either
    by doing or undoing an action). Only one savepoint can be tracked,
    marking a new one removes the old one.
    
    >>> stack().savepoint()
    >>> stack().haschanged()
    False
    >>> action()
    >>> stack().haschanged()
    True
    '''

    def __init__(self):
        self._undos = deque()
        self._redos = deque()
        self._receiver = self._undos
        self._savepoint = None
        self.undocallback = none
        self.docallback = none

    def canundo(self):
        ''' Return *True* if undos are available '''
        return len(self._undos) > 0

    def canredo(self):
        ''' Return *True* if redos are available '''
        return len(self._redos) > 0

    def redo(self):
        ''' Redo the last undone action. 
        
        This is only possible if no other actions have occurred since the 
        last undo call.
        '''
        if self.canredo():
            undoable = self._redos.pop()
            try:
                undoable.do()
            except:
                self.clear()
                raise
            else:
                self._undos.append(undoable)
            self.docallback()

    def undo(self):
        ''' Undo the last action. '''
        if self.canundo():
            undoable = self._undos.pop()
            try:
                undoable.undo()
            except:
                self.clear()
                raise
            else:
                self._redos.append(undoable)
            self.undocallback()

    def clear(self):
        ''' Clear the undo list. '''
        self._undos.clear()
        self._redos.clear()
        self._savepoint = None

    def undocount(self):
        ''' Return the number of undos available. '''
        return len(self._undos)

    def redocount(self):
        ''' Return the number of redos available. '''
        return len(self._undos)

    def undotext(self):
        ''' Return a description of the next available undo. '''
        if self.canundo():
            return ('Undo ' + self._undos[-1].text()).strip()

    def redotext(self):
        ''' Return a description of the next available redo. '''
        if self.canredo():
            return ('Redo ' + self._redos[-1].text()).strip()

    def setreceiver(self, receiver=None):
        ''' Set an object to receiver commands pushed onto the stack.
        
        By default it is the internal stack, but it can be set (usually
        internally) to any object with an *append()* method.
        '''
        assert hasattr(receiver, 'append')
        self._receiver = receiver

    def resetreceiver(self):
        ''' Reset the receiver to the internal stack.'''
        self._receiver = self._undos

    def append(self, action):
        ''' Add a undoable to the stack, using ``receiver.append()``. '''
        if self._receiver is not None:
            self._receiver.append(action)
        if self._receiver is self._undos:
            self._redos.clear()
            self.docallback()

    def savepoint(self):
        ''' Set the savepoint. '''
        self._savepoint = self.undocount()

    def haschanged(self):
        ''' Return *True* if the state has changed since the savepoint. 
        
        This will always return *True* if the savepoint has not been set.
        '''
        return self._savepoint is None or self._savepoint != self.undocount()
