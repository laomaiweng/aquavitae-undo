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


# Implementation Notes
# ^^^^^^^^^^^^^^^^^^^^

# The roles of an _Action are normally set using the :func:`undoable` 
# function as a decorator on the *do* function. This returns an
# :class:`_ActionFactory` instance. :func:`_ActionFactory.undo` can
# also be used as a decorator on the *undo* function.

import functools
import contextlib

from dtlibs import core
from collections import deque

class _Action:
    ''' This represents an action which can be done and undone.
    
    It is the result of a call on an undoable function and has
    three methods: ``do()``, ``undo()`` and ``text()``.  The first value
    returned by the internal call in ``do()`` is the value which will subsequenty be returned
    by ``text``.  Any remaining values are returned by ``do()``.
    '''
    def __init__(self, vars, args, kwargs):
        self.vars = vars
        self.args = args
        self.kwargs = kwargs
        self._text = ''

    def do(self):
        'Do or redo the action'
        rets = self.vars['do'](*self.args, **self.kwargs)
        if isinstance(rets, tuple):
            self._text = rets[0]
            return rets[1:]
        elif rets is None:
            self._text = ''
            return None
        else:
            self._text = rets
            return None

    def undo(self):
        'Undo the action'
        if hasattr(self, 'state'):
            self.vars['undo'](self.state)
        else:
            self.vars['undo']()

    def text(self):
        'Return the descriptive text of the action'
        return self._text


@core.deprecated('0.4.2', 'Old syntax will be removed in 0.5')
class _ActionFactory:
    ''' Used by the ``undoable`` function to create Actions.
    
    ``undoable`` returns an instance of an `ActionFactory`, which is used 
    in code to set up the do and undo functions.  When called, it
    creates a new instance of an _Action, runs it and pushes it onto 
    the stack.
    
    `ActionFactory` is really object which is bound to the name of the
    function it wraps around. `Action` is an instance of a specific call
    to that function. 
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

    def calldo(self, *args, **kwargs):
        if self._instance is None:
            ret = self._do(*args, **kwargs)
        else:
            ret = self._do(self._instance, *args, **kwargs)
        if ret is None:
            ret = tuple()
        return (self._desc.format(**args[0]),) + ret

    def callundo(self, state):
        if self._instance is None:
            return self._undo(state)
        else:
            return self._undo(self._instance, state)

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
            args = (state,) + tuple(args)
            vars = {'do': self.calldo, 'undo': self.callundo}
            action = _Action(vars, args, kwargs)
            action.state = state
            ret = action.do()
            stack().append(action)
            return ret


class _GeneratorActionFactory:
    '''A generator-style action factory. 
    
    *desc* is not set until the method is called, which is fine since it 
    is not needed until that point.
    '''
    def __init__(self, generator):
        self._generator = generator
        self._instance = None

    def __get__(self, instance, owner):
        'Store instance for bound methods.'
        self._instance = instance
        return self

    def _do(self, *args, **kwargs):
        ''' Create an instance of the generator and call it.'''
        if self._instance is not None:
            args = (self._instance,) + args
        self._runner = self._generator(*args, **kwargs)
        return next(self._runner)

    def _undo(self, *args):
        ''' call the next iteration of the generator.'''
        try:
            next(self._runner)
        except StopIteration:
            pass

    def __call__(self, *args, **kwargs):
        ''' Create the action.
         
        This will create an _Action, run it, set *desc*, and push the 
        action onto the stack.
        '''
        vars = {'do': self._do, 'undo': self._undo}
        action = _Action(vars, args, kwargs)
        ret = action.do()
        stack().append(action)
        return ret


def undoable(arg, do=None, undo=None):
    ''' Decorator which creates a new undoable action type. 
    
    Normal usage is as a decorator with no arguments.  However, an
    alternative, deprecated, usage is also allowed as described above.
    '''
    if core.iscallable(arg):
        factory = _GeneratorActionFactory(arg)
    else:
        factory = _ActionFactory(arg, do, undo)
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

class stack(metaclass=core.singleton()):
    ''' The main undo stack. 
    
    This is a singleton, so the smae object is always returned by ``stack()``.
    
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
    >>> @undoable
    ... def action():
    ...     yield 'An action'
    >>> action()
    Can now undo: Undo An action
    >>> stack().undo()
    Can now redo: Redo An action
    >>> stack().redo()
    Can now undo: Undo An action
    
    Setting them back to `dtlibs.core.none` will stop any 
    further actions.
    
    >>> stack().docallback = stack().undocallback = core.none
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
        self.undocallback = core.none
        self.docallback = core.none

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
            with self._pausereceiver():
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
            with self._pausereceiver():
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
        self._receiver = self._undos

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

    @contextlib.contextmanager
    def _pausereceiver(self):
        ''' Return a contect manager which temporarily pauses the receiver. '''
        self.setreceiver([])
        yield
        self.resetreceiver()

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
