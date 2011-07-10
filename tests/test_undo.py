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

from dtlibs import undo

class TestCase(unittest.TestCase):

    def tearDown(self):
        reload(undo)

class TestBasic:

    def test(self):
        @undo.command('Add {pos}')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq
            state['pos'] = len(seq) - 1
        @add.undo
        def add(state):
            seq, pos = state
            del seq[pos]
        sequence = [1, 2, 3, 4]
        add(sequence, 5)
        self.assertEqual(sequence, [1, 2, 3, 4, 5])
        self.assertEqual(undo.stack().undotext(), 'Undo Add 5')
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
