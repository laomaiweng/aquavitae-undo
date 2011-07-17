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
Undo/Redo undoable based framework.

This is an undo/redo framework which uses a undoable stack to track 
actions.  Commands are defined using decorators on functions and methods, 
and a new instance is added to the stack when the function is called.  

The following example is used to explain basic usage.

>>> @undoable('Add {pos}')
... def add(state, seq, item):
...     seq.append(item)
...     state['seq'] = seq
...     state['pos'] = len(seq) - 1
>>> @add.undo
... def add(state):
...     seq, pos = state['seq'], state['pos']
...     del seq[pos]
>>> sequence = [1, 2, 3, 4]
>>> add(sequence, 5)
>>> sequence
[1, 2, 3, 4, 5]
>>> stack().undotext()
'Undo Add 4'
>>> stack().undo()
>>> sequence
[1, 2, 3, 4]
>>> stack().redo()
>>> sequence
[1, 2, 3, 4, 5]

As can be seen from this, a undoable is defined using the @undoable 
decorator, which takes a single string argument representing the undo 
description.  To clarify, a undoable is the do and undo functions, and an 
action is the result of calling a do function.

Data required for undoing an action is tranferred through a dict, usually 
named state, and is the first argument (after self) of the do and
undo functions.  This dict is also used to format the undoable 
description using string formatting.

The stack supports a locking mechanism, whereby any actions pushed
while another actions is in process are ignored. This allows, 
for example, the undo function of an "add" undoable to call a "delete"
undoable safely.

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
...
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

The stack may be cleared if, for example, the document is saved.

>>> stack().canundo()
True
>>> stack().clear()
>>> stack().canundo()
False

A series of commands may be grouped within a function using the
group() context manager.

>>> @undoable('Add 1 item')
... def add(state, seq, item):
...     seq.append(item)
...     state['seq'] = seq
>>> @add.undo
... def add(state):
...     state['seq'].pop()
>>> seq = []
>>> with group('Add many'):
...     for item in [4, 6, 8]:
...         add(seq, item)
>>> seq
[4, 6, 8]
>>> stack().undocount()
1
>>> stack().undo()
>>> seq
[]
'''

import functools

from dtlibs.functions import singleton
from collections import deque

class Action:
    ''' This represents an action which can be done and undone.
    
    It is basically the result of a call on an undoable function and has
    three methods: ``do()``, ``undo()`` and ``text()``. This class
    should always be instantiated by an ActionFactory.
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


class ActionFactory:
    ''' Used by the ``undoable`` function to create Actions.
    
    ``undoable`` returns an instance of an ActionFactory, which is used 
    in code to set up the do and undo functions.  When called, it
    creates a new instance of an Action, runs it and pushes it onto the stack.
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
         
        If do has been set, this will create an Action, run it and 
        push it onto the stack. If not, it will set the do function.
        This allows the following two ways of using it:
        >>> factory = ActionFactory('desc', None, None)
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
            action = Action(vars, state)
            ret = action.do()
            stack().append(action)
            return ret


def undoable(desc, do=None, undo=None):
    ''' Factory to create a new undoable action type. 
    
    This function creates a new undoable command given a description
    and do function. An undo function must also be specified before
    it is used, but is optional to allow ``undoable`` to be used as a
    decorator. The command object returned has an ``undo`` method 
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
    
    Both the do and undo functions should accept a ``state`` variable, 
    which is passed as the first argument (after ``self``) to ``do``
    and as the only argument (other than ``self``) to ``undo``.   
    ``state`` is a dict of values which are used to transfer data between
    do and undo, and initially contains keys 'args' and 'kwargs' which
    correspond to the arguments passed to the do function.
    
    The description string can include formatting commands (see python string 
    formatting), which are formatted using the state variable. This can be
    retrieved using ``stack().undotext()``
    
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
    factory = ActionFactory(desc, do, undo)
    functools.update_wrapper(factory, do)
    return factory


class group:
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


@singleton
class stack:
    ''' The main undo stack. 
    
    The two key features are the redo() and undo() methods. If an 
    exception occurs during doing or undoing a undoable, the undoable
    aborts and the stack is cleared to avoid any further data corruption.  
    '''

    def __init__(self):
        self._undos = deque()
        self._redos = deque()
        self._receiver = self._undos

    def canundo(self):
        return len(self._undos) > 0

    def canredo(self):
        return len(self._redos) > 0

    def redo(self):
        if self.canredo():
            undoable = self._redos.pop()
            try:
                undoable.do()
            except:
                self.clear()
                raise
            else:
                self._undos.append(undoable)


    def undo(self):
        if self.canundo():
            undoable = self._undos.pop()
            try:
                undoable.undo()
            except:
                self.clear()
                raise
            else:
                self._redos.append(undoable)

    def clear(self):
        ''' Clear the undo list. '''
        self._undos.clear()
        self._redos.clear()

    def undocount(self):
        return len(self._undos)

    def redocount(self):
        return len(self._undos)

    def undotext(self):
        if self.canundo():
            return ('Undo ' + self._undos[-1].text()).strip()

    def redotext(self):
        if self.canredo():
            return ('Redo ' + self._redos[-1].text()).strip()

    def setreceiver(self, receiver=None):
        ''' Set an object to receiver commands pushed onto the stack.
        
        By default it is the internal stack, but it can be set (usually
        internally) to any object with and append() method.
        '''
        assert hasattr(receiver, 'append')
        self._receiver = receiver

    def resetreceiver(self):
        ''' Reset the receiver to the internal stack.'''
        self._receiver = self._undos

    def append(self, action):
        ''' Add a undoable to the stack, using receiver.append(). '''
        if self._receiver is not None:
            self._receiver.append(action)

