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

class TestBasic(TestCase):

    def test(self):
        @undo.command('Add pos {pos}')
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
        self.assertEqual(undo.stack().undo_text(), 'Undo Add pos 4')
        undo.stack().undo()
        self.assertEqual(sequence, [1, 2, 3, 4])
        undo.stack().redo()
        self.assertEqual(sequence, [1, 2, 3, 4, 5])

class TestCommand(unittest.TestCase):

    def setUp(self):
        flexmock(undo).should_receive('stack.append')

    def tearDown(self):
        reload(undo)

    def testUnbound(self):
        @undo.command('desc')
        def do(state, arg):
            _ = arg
        do = do.undo(do)
        # Calling this should not result in any errors
        do(4)

    def testBound(self):
        def cmdcls(i, a):
            assert(isinstance(i, T))
            assert(a == 4)
            return flexmock()
        class T:
            def __init__(self):
                self.var = 0
            @undo.command('desc')
            def do(self, state, arg):
                state['arg'] = arg
            do = do.undo(do)
        # Calling this should not result in any errors
        T().do(4) 


class TestFunction(unittest.TestCase):
    ''' Test for normal functions.'''

    def tearDown(self):
        reload(undo)
        try:
            del self.var
            del self.oldvar
        except AttributeError:
            pass

    def testBasic(self):
        self.var = 0
        @undo.command('test')
        def func1(state):
            self.var = 1
        @func1.undo
        def func1(state):
            self.var = 0
        func1()
        self.assertEqual(self.var, 1)
        undo.stack().undo()
        self.assertEqual(self.var, 0)

    def testState(self):
        @undo.command('test')
        def func(state):
            state['state'] = 1
        @func.undo
        def func(state):
            self.assertEqual(state['state'], 1)
        func()
        undo.stack().undo()


class TestBound(unittest.TestCase):
    ''' Test for action on bound functions.'''

    def tearDown(self):
        reload(undo)

    def testBasic(self):

        # According to the docs, this should work
        class List:
            def __init__(self):
                self._l = []

            @undo.command('Add an item')
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


class Action(TestCase):
    
    def test__init__(self):
        'Make sure values are stored correctly.'
        a = undo.Action('instance', 'args', 'kwargs')
        self.assertEqual(a.instance, 'instance')
        self.assertEqual(a.state, {'__args__': 'args', '__kwargs__': 'kwargs'})
        
    def test_do_bound(self):
        state = {'__args__': ('args',), '__kwargs__': {'key': 'value'}}
        def do(*args, **kwargs):
            self.assertEqual(args, ('instance', state, 'args'))
            self.assertEqual(kwargs, {'key': 'value'})
            return 'return'
        a = undo.Action('instance', ('args',), {'key': 'value'})
        a.state = state
        a.functions['do'] = do 
        self.assertEqual(a.do(), 'return')
        
    def test_do_unbound(self):
        state = {'__args__': ('args',), '__kwargs__': {'key': 'value'}}
        def do(*args, **kwargs):
            self.assertEqual(args, (state, 'args'))
            self.assertEqual(kwargs, {'key': 'value'})
            return 'return'
        a = undo.Action(None, ('args',), {'key': 'value'})
        a.state = state
        a.functions['do'] = do 
        self.assertEqual(a.do(), 'return')
        
    def test_undo(self):
        def f_undo(*args):
            self.assertEqual(args, ('instance', 'state',))
        a = undo.Action('instance', None, None)
        a.state = 'state'
        a.functions['undo'] = f_undo 
        a.undo()

    def test_text(self):
        a = undo.Action(None, None, None)
        a._desc = '{p1}, {p2}'
        a.state = {'p1': 42, 'p2': 'a string'}
        self.assertEqual(a.text(), '42, a string')
        
class Stack(TestCase):
    
    def test_API(self):
        ' stack() should support all these functions. '
        s = undo.stack()
        s.undo()
        s.redo()
        s.undo_text()
        s.redo_text()
        s.undo_count()
        s.redo_count()
        s.can_undo()
        s.can_redo()
        s.append('item')
           
    def test_undo(self):
        s = undo.stack()
        act1 = flexmock().should_receive('undo').mock
        act2 = flexmock().should_receive('undo').mock
        act3 = flexmock().should_receive('undo').mock
        s._undos = deque([act1, act2, act3])
        s.undo()
        self.assertEqual(s._undos, deque([act1, act2]))
        self.assertEqual(s._redos, deque([act3]))
        
    def test_redo(self):
        s = undo.stack()
        act1 = flexmock().should_receive('do').mock
        act2 = flexmock().should_receive('do').mock
        act3 = flexmock().should_receive('do').mock
        s._redos = deque([act1, act2, act3])
        s.redo()
        self.assertEqual(s._redos, deque([act1, act2]))
        self.assertEqual(s._undos, deque([act3]))
        
    def test_undo_text(self):
        act = flexmock().should_receive('text').and_return('some text').mock
        undo.stack()._undos = deque([act])
        self.assertEqual(undo.stack().undo_text(), 'Undo some text')
    
    def test_undo_text_blank(self):
        act = flexmock().should_receive('text').and_return('').mock
        undo.stack()._undos = [act]
        self.assertEqual(undo.stack().undo_text(), 'Undo')
        