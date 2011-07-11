#!/usr/bin/env python3
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
undo.py - Undo/Redo command based framework.

This is an undo/redo framework which uses a command stack to track 
actions.  Commands are defined using decorators on functions and methods, 
and a new instance is added to the stack when the function is called.  

The following example is used to explain basic usage.

>>> @command('Add {pos}')
... def add(state, seq, item):
...     seq.append(item)
...     state['seq'] = seq
...     state['pos'] = len(seq) - 1
>>> @add.undo
... def add(state):
...     seq, pos = state
...     del seq[pos]
>>> sequence = [1, 2, 3, 4]
>>> add(sequence, 5)
>>> sequence
[1, 2, 3, 4, 5]
>>> stack().undotext()
'Undo Add 5'
>>> stack().undo()
>>> sequence
[1, 2, 3, 4]
>>> stack().redo()
>>> sequence
[1, 2, 3, 4, 5]

As can be seen from this, a command is defined using the @command 
decorator, which takes a single string argument representing the undo 
description.  To clarify, a command is the do and undo functions, and an 
action is the result of calling a do function.

Data required for undoing an action is tranferred through a dict, usually 
named state, and is the first argument (after self) of the do and
undo functions.  This dict is also used to format the command 
description using string formatting.

The stack supports a locking mechanism, whereby any actions pushed
while another actions is in process are ignored. This allows, 
for example, the undo function of an "add" command to call a "delete"
command safely.

>>> @command('Add'):
... def add(state, seq, item):
...     seq.append(item)
...     state['seq'] = seq
...
>>> @add.undo
... def add(state):
...     delete(state['seq'])
...
>>> @command('Delete')
... def delete(seq, state):
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

A series of commands may be grouped within a function using the
group() context manager.

>>> @command('Add 1 item'):
... def add(state, seq, item):
...     seq.append(item)
...     state['seq'] = seq
>>> @add.undo
... def add(state):
...     state['seq'].pop()
...
>>> def addmany(seq, items, state):
...     with group('Add many'):
...         for item in items:
...         seq.append(item)
>>> seq = []
>>> addmany(seq, [4, 6, 8])
>>> len(stack())
1
>>> seq
[4, 6, 8]
>>> stack().undo()
>>> seq
[]
'''

import logging
import inspect

from dtlibs.decorators import deco_with_args, singleton
from collections import deque

class Action:
    ''' An Action represents the result of a command call.
    
    It is initialised with the call arguments and the instance of the 
    owning class (which may be None), and should be able to do and undo 
    itself in isolation.  Data related to the action is stored in an 
    internal variable 'state' which is passed to the do and undo functions
    as the first argument, after instance. state is a dict, but has two 
    pre-defined values: __args__ and __kwargs__ which represent the
    initial call arguments. state is expected to be modified by do, but 
    not undo.
    '''

    # This is the unformatted text description of the command
    _desc = None
    
    # The do and undo functions. These should be functions, not methods.
    # They are stored in a dict to avoid binding them to this class.
    functions = {'do': None, 'undo': None}

    def __init__(self, instance, args, kwargs):
        ''' Create the new command instance, storing the args and kwargs
        in state for future use in redo() and undo(). instance is the 
        instance of the parent class, if available.
        '''
        super().__init__()
        self.instance = instance
        self.state = {'__args__': args, '__kwargs__':kwargs}

    def do(self):
        ''' Call the _do command. '''
        assert inspect.isfunction(self.functions['do'])
        args = (self.state,) + self.state['__args__'] 
        if self.instance is not None:
            args = (self.instance,) + args
        return self.functions['do'](*args, **self.state['__kwargs__'])

    def undo(self):
        ''' Call the _undo command. '''
        assert inspect.isfunction(self.functions['undo'])
        if self.instance is None:
            self.functions['undo'](self.state)
        else:
            self.functions['undo'](self.instance, self.state)

    def text(self):
        return self._desc.format(**self.state)


@deco_with_args
class command:
    ''' Factory to create new Action objects. '''

    def __init__(self, desc, do):
        class CmdCls(Action): pass
        self.cmdcls = CmdCls
        self.cmdcls._desc = desc
        if inspect.ismethod(do):
            do = do.__func__
        self.cmdcls.functions['do'] = do
        self._instance = None

    def __call__(self, *args, **kwargs):
        ''' Call the command, thereby creating a new instance and pushing
        it onto the undo stack.
        '''
        if None in self.cmdcls.functions.values():
            raise TypeError('undo and do must both be defined.')
        cmd = self.cmdcls(self._instance, args, kwargs)
        result = cmd.do()
        stack().append(cmd)
        return result

    def __get__(self, instance, owner):
        ''' Store the instance of owning class when this is called. '''
        self._instance = instance
        return self

    def undo(self, func):
        ''' Set the undo action of the command to be created. '''
        if inspect.ismethod(func):
            func = func.__func__
        self.cmdcls.functions['undo'] = func
        return self


class group:
    ''' A command group context manager. '''

    def __init__(self, desc):
        self._desc = desc
        self._stack = []

    def __enter__(self):
        stack().set_receiver(self._stack)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            stack().reset_receiver()
            stack().append(self)
        return False

    def undo(self):
        for command in reversed(self._stack):
            command.undo()

    def do(self):
        for command in self._stack:
            command.do()

    def text(self):
        return self._desc.format(count=len(self._stack))


@singleton
class stack:
    ''' The main undo stack. 
    
    The two key features are the redo() and undo() methods. If an 
    exception occurs during doing or undoing a command, the command
    aborts and the stack is cleared to avoid any further data corruption.  
    '''

    def __init__(self):
        self._undos = deque()
        self._redos = deque()
        self._receiver = self._undos

    def can_undo(self):
        return len(self._undos) > 0
    
    def can_redo(self):
        return len(self._redos) > 0
    
    def redo(self):
        if self.can_redo():
            command = self._redos.pop()
            try:
                command.do()
            except:
                self.clear()
                raise
            else:
                self._undos.append(command)


    def undo(self):
        if self.can_undo():
            command = self._undos.pop()
            try:
                command.undo()
            except:
                self.clear()
                raise
            else:
                self._redos.append(command)

    def clear(self):
        ''' Clear the undo list. '''
        self._undos.clear()
        self._redos.clear()

    def undo_count(self):
        return len(self._undos)

    def redo_count(self):
        return len(self._undos)

    def undo_text(self):
        if self.can_undo():
            return ('Undo ' + self._undos[-1].text()).strip()
    
    def redo_text(self):
        if self.can_redo():
            return ('Redo ' + self._redos[-1].text()).strip()
    
    def __len__(self):
        return self.undo_count()

    def set_receiver(self, receiver=None):
        ''' Set and object to receiver commands pushed onto the stack.
        
        By default it is the internal stack, but it can be set (usually
        internally) to any object with and append() method.
        '''
        assert hasattr(receiver, 'append')
        self._receiver = receiver

    def reset_receiver(self):
        ''' Reset the receiver to the internal stack.'''
        self._receiver = self._undos

    def append(self, command):
        ''' Add a command to the stack, using receiver.append(). '''
        if self._receiver is not None:
            self._receiver.append(command)

