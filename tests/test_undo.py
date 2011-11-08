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
from flexmock import flexmock

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
        undo.undoable('desc', do, undo_)

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


class _Action(TestCase):

    def test_state(self):
        'Make sure state is transferred'
        def do(state):
            state['done'] = True
        def undo_(state):
            self.assertTrue(state['done'])
            state['undone'] = True
        action = undo._Action({'do': do, 'undo': undo_},
                        {'args': tuple(), 'kwargs': {}})
        action.do()
        self.assertEqual(action.state, {'args': tuple(), 'kwargs': {},
                                        'done': True})
        action.undo()
        self.assertEqual(action.state, {'args': tuple(), 'kwargs': {},
                                        'done': True, 'undone': True})

    def test_text(self):
        'description gets formatted with state'
        action = undo._Action({'text': 'desc - {foo}'}, {'foo': 'bar'})
        self.assertEqual(action.text(), 'desc - bar')


class Group(TestCase):

    def test_stack(self):
        'Test the relationship with undo.stack()'
        undo.stack().clear()
        _Group = undo._Group('')
        stack = []
        _Group._stack = stack
        flexmock(undo.stack()).should_call('setreceiver').with_args(stack).ordered
        flexmock(undo.stack()).should_call('resetreceiver').with_args().ordered
        flexmock(undo.stack()).should_call('append').with_args(_Group).ordered
        with _Group:
            pass
        self.assertEqual(stack, [])
        self.assertEqual(undo.stack()._undos, deque([_Group]))


class Stack(TestCase):

    def test_singleton(self):
        'undo.stack() always returns the same object'
        self.assertIs(undo.stack(), undo.stack())

    def test_append(self):
        undo.stack().append('one')
        self.assertEqual(undo.stack()._undos, deque(['one']))

    def test_undo_changes_stacks(self):
        undoable = flexmock(undo._Action({}, {})).should_receive('undo').mock
        undo.stack()._undos = deque([1, 2, undoable])
        undo.stack()._redos = deque([4, 5, 6])
        undo.stack().undo()
        self.assertEqual(undo.stack()._undos, deque([1, 2]))
        self.assertEqual(undo.stack()._redos, deque([4, 5, 6, undoable]))

    def test_undo_resets_redos(self):
        undo.stack()._undos = deque([1, 2, 3])
        undo.stack()._redos = deque([4, 5, 6])
        undo.stack()._receiver = undo.stack()._undos
        undo.stack().append(7)
        self.assertEqual(undo.stack()._undos, deque([1, 2, 3, 7]))
        self.assertEqual(undo.stack()._redos, deque([]))

    def test_undotext(self):
        action = flexmock(undo._Action({}, {})).should_receive(
                                              'text').and_return('blah').mock
        undo.stack()._undos = [action]
        self.assertEqual(undo.stack().undotext(), 'Undo blah')

    def test_redotext(self):
        action = flexmock(undo._Action({}, {})).should_receive(
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

    def test_savepoint(self):
        undo.stack()._undos = deque([1, 2])
        self.assertTrue(undo.stack().haschanged())
        undo.stack().savepoint()
        self.assertFalse(undo.stack().haschanged())
        undo.stack()._undos.pop()
        self.assertTrue(undo.stack().haschanged())

    def test_savepoint_clear(self):
        undo.stack()._undos = deque()
        self.assertTrue(undo.stack().haschanged())
        undo.stack().savepoint()
        self.assertFalse(undo.stack().haschanged())
        undo.stack().clear()
        self.assertTrue(undo.stack().haschanged())
        undo.stack().savepoint()
        self.assertFalse(undo.stack().haschanged())
        undo.stack().clear()
        self.assertTrue(undo.stack().haschanged())


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
        'Test _Group behaviour'
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
        with undo._Group('add many'):
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
        with undo._Group('Add many'):
            for item in [4, 6, 8]:
                add(seq, item)
        self.assertEqual(seq, [4, 6, 8])
        self.assertEqual(undo.stack().undocount(), 1)
        undo.stack().undo()
        self.assertEqual(seq, [])

    def testBound(self):
        class Mod:
            def __init__(self):
                self.l = set()

            @undo.undoable('Add {value}')
            def add(self, state, value):
                self.l.add(value)
                state['value'] = value

            @add.undo
            def add(self, state):
                self.l.remove(state['value'])

            @undo.undoable('Delete {value}')
            def delete(self, state, value):
                self.l.remove(value)
                state['value'] = value

            @delete.undo
            def delete(self, state):
                self.l.add(state['value'])

        m = Mod()
        self.assertEqual(m.l, set())
        m.add(3)
        m.add(4)
        self.assertEqual(m.l, set([3, 4]))
        self.assertEqual(undo.stack().undotext(), 'Undo Add 4')
        undo.stack().undo()
        self.assertEqual(m.l, set([3]))
        m.delete(3)
        self.assertEqual(m.l, set())
        undo.stack().undo()
        self.assertEqual(m.l, set([3]))
        self.assertTrue(undo.stack().canundo())
        undo.stack().undo()
        self.assertEqual(m.l, set())
        self.assertFalse(undo.stack().canundo())

class TestExceptions(TestCase):

    def setUp(self):
        def action(state): pass
        self.action = undo.undoable('', action, action)
        self.calls = 0

    def test_redo(self):
        @undo.undoable('desc')
        def add(state):
            if self.calls == 0:
                self.calls = 1
            else:
                raise TypeError

        @add.undo
        def add(state):
            pass

        self.action()
        self.action()
        add()
        self.assertEqual(undo.stack().undocount(), 3)
        undo.stack().undo()
        self.assertEqual(undo.stack().undocount(), 2)
        self.assertRaises(TypeError, undo.stack().redo)
        self.assertEqual(undo.stack().undocount(), 0)
        self.assertEqual(undo.stack().redocount(), 0)

    def test_undo(self):
        @undo.undoable('desc')
        def add(state):
            pass

        @add.undo
        def add(state):
            if self.calls == 0:
                self.calls = 1
            else:
                raise TypeError

        self.action()
        self.action()
        add()
        undo.stack().undo()
        add()
        self.assertEqual(undo.stack().undocount(), 3)
        self.assertRaises(TypeError, undo.stack().undo)
        self.assertEqual(undo.stack().undocount(), 0)
        self.assertEqual(undo.stack().redocount(), 0)

    def test_do(self):
        @undo.undoable('desc')
        def add(state):
            raise TypeError

        @add.undo
        def add(state):
            self.fail('Undo should not be called')

        self.action()
        self.action()
        self.assertEqual(undo.stack().undocount(), 2)
        self.assertRaises(TypeError, add)
        self.assertEqual(undo.stack().undocount(), 2)

