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

''' Test suite for undo '''

import unittest
from imp import reload
from flexmock import flexmock_pytest as flexmock

from collections import deque

from dtlibs import undo

class TestCase(unittest.TestCase):

    def tearDown(self):
        reload(undo)

class Undoable(TestCase):
    ''' Test the undoable function. '''

    def setUp(self):
        'Mock undo.stack() and store as self.stack'
        self.stack = []
        mock_stack = lambda: self.stack
        flexmock(undo).should_receive('stack').replace_with(mock_stack)

    def test_function(self):
        'Function should run with basic arguments'
        do = lambda state: None
        undo_ = lambda state: None
        undo.undoable('desc', do, undo)

    def test_decorator(self):
        'Function can be used as a decorator'
        @undo.undoable('desc')
        def do(state):
            pass
        @do.undo
        def do_undo(state):
            pass
        self.assertIs(do, do_undo)

    def test_do(self):
        'undoable.do() runs'
        self.do_called = False
        def do(state):
            self.do_called = True
        def undo_(state):
            self.fail('Undo should not be called')
        undoable = undo.undoable('desc', do, undo_)
        undoable()
        self.assertTrue(self.do_called)

    def test_undo(self):
        'undoable.undo() runs'
        self.undo_called = False
        def do(state):
            pass
        def undo_(state):
            self.undo_called = True
        undoable = undo.undoable('desc', do, undo_)
        undoable()
        self.stack[0].undo()
        self.assertTrue(self.undo_called)


class Action(TestCase):

    def test_state(self):
        'Make sure state is transferred'
        def do(state):
            state['done'] = True
        def undo_(state):
            self.assertTrue(state['done'])
            state['undone'] = True
        action = undo.Action({'do': do, 'undo': undo_},
                        {'args': tuple(), 'kwargs': {}})
        action.do()
        self.assertEqual(action.state, {'args': tuple(), 'kwargs': {},
                                        'done': True})
        action.undo()
        self.assertEqual(action.state, {'args': tuple(), 'kwargs': {},
                                        'done': True, 'undone': True})

    def test_text(self):
        'description gets formatted with state'
        action = undo.Action({'text': 'desc - {foo}'}, {'foo': 'bar'})
        self.assertEqual(action.text(), 'desc - bar')


class Group(TestCase):

    def test_stack(self):
        'Test the relationship with undo.stack()'
        group = undo.group('')
        stack = []
        group._stack = stack
        flexmock(undo.stack()).should_call('setreceiver').with_args(stack).ordered
        flexmock(undo.stack()).should_call('resetreceiver').with_args().ordered
        flexmock(undo.stack()).should_call('append').with_args(group).ordered
        with group:
            pass
        self.assertEqual(stack, [])
        self.assertEqual(undo.stack()._undos, deque([group]))


class Stack(TestCase):

    def test_singleton(self):
        'undo.stack() always returns the same object'
        self.assertIs(undo.stack(), undo.stack())

    def test_append(self):
        undo.stack().append('one')
        self.assertEqual(undo.stack()._undos, deque(['one']))

    def test_undotext(self):
        action = flexmock(undo.Action({}, {})).should_receive(
                                              'text').and_return('blah').mock
        undo.stack()._undos = [action]
        self.assertEqual(undo.stack().undotext(), 'Undo blah')

    def test_redotext(self):
        action = flexmock(undo.Action({}, {})).should_receive(
                                              'text').and_return('blah').mock
        undo.stack()._redos = [action]
        self.assertEqual(undo.stack().redotext(), 'Redo blah')

    def test_receiver(self):
        stack = []
        undo.stack()._undos = []
        undo.stack().setreceiver(stack)
        undo.stack().append('item')
        self.assertEqual(stack, ['item'])
        self.assertEqual(undo.stack()._undos, [])
        undo.stack().resetreceiver()
        undo.stack().append('next item')
        self.assertEqual(stack, ['item'])
        self.assertEqual(undo.stack()._undos, ['next item'])

class TestSystem(TestCase):
    'A series of system tests'

    def test1(self):
        @undo.undoable('add @{pos} to {seq}')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq
            state['pos'] = len(seq) - 1
        @add.undo
        def add(state):
            seq, pos = state['seq'], state['pos']
            del seq[pos]
        sequence = [1, 2, 3, 4]
        add(sequence, 5)
        self.assertEqual(sequence, [1, 2, 3, 4, 5])
        self.assertEqual(undo.stack().undotext(), 'Undo add @4 to [1, 2, 3, 4, 5]')
        undo.stack().undo()
        self.assertEqual(sequence, [1, 2, 3, 4])
        undo.stack().redo()
        self.assertEqual(sequence, [1, 2, 3, 4, 5])

    def test2(self):
        'Bound functions'
        class List:
            def __init__(self):
                self._l = []

            @undo.undoable('Add an item')
            def add(self, state, item):
                self._l.append(item)

            @add.undo
            def add(self, state):
                self._l.pop()

        l = List()
        l.add(5)
        self.assertEqual(l._l, [5])
        l.add(3)
        self.assertEqual(l._l, [5, 3])
        l.add(5)
        self.assertEqual(l._l, [5, 3, 5])
        undo.stack().undo()
        self.assertEqual(l._l, [5, 3])
        undo.stack().undo()
        self.assertEqual(l._l, [5])
        undo.stack().undo()
        self.assertEqual(l._l, [])

    def testGroups1(self):
        'Test group behaviour'
        @undo.undoable('add @{pos} to {seq}')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq
            state['pos'] = len(seq) - 1
        @add.undo
        def add(state):
            seq, pos = state['seq'], state['pos']
            del seq[pos]
        sequence = [1, 2]
        with undo.group('add many'):
            for i in range(5, 8):
                add(sequence, i)
        self.assertEqual(sequence, [1, 2, 5, 6, 7])
        self.assertEqual(undo.stack().undotext(), 'Undo add many')
        undo.stack().undo()
        self.assertEqual(sequence, [1, 2])
        self.assertEqual(undo.stack().redotext(), 'Redo add many')
        undo.stack().redo()
        self.assertEqual(sequence, [1, 2, 5, 6, 7])
        self.assertEqual(undo.stack().undotext(), 'Undo add many')

    def test_groups2(self):
        @undo.undoable('Add 1 item')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq
        @add.undo
        def add(state):
            state['seq'].pop()
        seq = []
        with undo.group('Add many'):
            for item in [4, 6, 8]:
                add(seq, item)
        self.assertEqual(seq, [4, 6, 8])
        self.assertEqual(undo.stack().undocount(), 1)
        undo.stack().undo()
        self.assertEqual(seq, [])

#class Testundoable(unittest.TestCase):
#
#    def setUp(self):
#        flexmock(undo).should_receive('stack.append')
#
#    def tearDown(self):
#        reload(undo)
#
#    def testUnbound(self):
#        @undo.undoable('desc')
#        def do(state, arg):
#            _ = arg
#        do = do.undo(do)
#        # Calling this should not result in any errors
#        do(4)
#
#    def testBound(self):
#        def cmdcls(i, a):
#            assert(isinstance(i, T))
#            assert(a == 4)
#            return flexmock()
#        class T:
#            def __init__(self):
#                self.var = 0
#            @undo.undoable('desc')
#            def do(self, state, arg):
#                state['arg'] = arg
#            do = do.undo(do)
#        # Calling this should not result in any errors
#        T().do(4)
#
#
#class TestFunction(unittest.TestCase):
#    ''' Test for normal functions.'''
#
#    def tearDown(self):
#        reload(undo)
#        try:
#            del self.var
#            del self.oldvar
#        except AttributeError:
#            pass
#
#    def testBasic(self):
#        self.var = 0
#        @undo.undoable('test')
#        def func1(state):
#            self.var = 1
#        @func1.undo
#        def func1(state):
#            self.var = 0
#        func1()
#        self.assertEqual(self.var, 1)
#        undo.stack().undo()
#        self.assertEqual(self.var, 0)
#
#
#
#class TestBound(unittest.TestCase):
#    ''' Test for action on bound functions.'''
#
#    def tearDown(self):
#        reload(undo)
#
#    def test_undo(self):
#        s = undo.stack()
#        act1 = flexmock().should_receive('undo').mock
#        act2 = flexmock().should_receive('undo').mock
#        act3 = flexmock().should_receive('undo').mock
#        s._undos = deque([act1, act2, act3])
#        s.undo()
#        self.assertEqual(s._undos, deque([act1, act2]))
#        self.assertEqual(s._redos, deque([act3]))
#
#    def test_redo(self):
#        s = undo.stack()
#        act1 = flexmock().should_receive('do').mock
#        act2 = flexmock().should_receive('do').mock
#        act3 = flexmock().should_receive('do').mock
#        s._redos = deque([act1, act2, act3])
#        s.redo()
#        self.assertEqual(s._redos, deque([act1, act2]))
#        self.assertEqual(s._undos, deque([act3]))
#
#    def test_undo_text(self):
#        act = flexmock().should_receive('text').and_return('some text').mock
#        undo.stack()._undos = deque([act])
#        self.assertEqual(undo.stack().undo_text(), 'Undo some text')
#
#    def test_undo_text_blank(self):
#        act = flexmock().should_receive('text').and_return('').mock
#        undo.stack()._undos = [act]
#        self.assertEqual(undo.stack().undo_text(), 'Undo')
#
#class Group(TestCase):
#
#    def test_context(self):
#        'Make sure group works correctly as a context manager'
#        stack = []
#        flexmock(undo.stack()).should_receive('set_receiver').with_args(stack).ordered
#        flexmock(undo.stack()).should_receive('reset_receiver').ordered
#        g = undo.group('')
#        with g:
#            pass
#        self.assertEqual(undo.stack()._undos, deque([g]))
#
#    def test_stack(self):
#        'Test that commands are passed to the group and not the main stack.'
#        g = undo.group('')
#        with g:
#            undo.stack().append('command1')
#            self.assertEqual(undo.stack()._undos, deque())
#            self.assertEqual(g._stack, ['command1'])
#        self.assertEqual(undo.stack()._undos, deque([g]))
#
#    def setup_actions(self):
#        self.calls = []
#        self.g = undo.group('')
#        com1 = flexmock()
#        com2 = flexmock()
#        com3 = flexmock()
#        com1.should_receive('undo').replace_with(lambda: self.calls.append('com1')).mock
#        com2.should_receive('undo').replace_with(lambda: self.calls.append('com2')).mock
#        com3.should_receive('undo').replace_with(lambda: self.calls.append('com3')).mock
#        com1.should_receive('do').replace_with(lambda: self.calls.append('com1')).mock
#        com2.should_receive('do').replace_with(lambda: self.calls.append('com2')).mock
#        com3.should_receive('do').replace_with(lambda: self.calls.append('com3')).mock
#        self.g._stack.append(com1)
#        self.g._stack.append(com2)
#        self.g._stack.append(com3)
#
#    def test_do(self):
#        'Test that undone actions can be redone in order'
#        self.setup_actions()
#        self.g.do()
#        self.assertEqual(self.calls, ['com1', 'com2', 'com3'])
#
#    def test_undo(self):
#        'Test that undone actions can be redone in order'
#        self.setup_actions()
#        self.g.undo()
#        self.assertEqual(self.calls, ['com3', 'com2', 'com1'])
