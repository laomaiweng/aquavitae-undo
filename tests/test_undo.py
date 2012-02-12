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

from collections import deque
from nose.tools import assert_raises

from dtlibs import undo, core
from dtlibs.mock import saver

class TestCase:

    def setup(self):
        pass

    def teardown(self):
        undo.stack().__init__()
        saver.restore()

class TestUndoable(TestCase):
    'Test the undoable function.'

    def setup(self):
        #Mock undo.stack() to return a list, stored as self.stack
        self.stack = []
        saver(undo, 'stack')
        mock_stack = lambda: self.stack
        undo.stack = mock_stack
        super().setup()

    def test_function(self):
        'undoable should run with basic arguments.'
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
        assert do is do_undo

    def test_do(self):
        'Make sure undoable.do() runs'
        self.do_called = False
        def do(state):
            self.do_called = True
        def undo_(state):
            self.fail('Undo should not be called')
        undoable = undo.undoable('desc', do, undo_)
        undoable()
        assert self.do_called

    def test_undo(self):
        'Make sure undoable.undo() runs'
        self.undo_called = False
        def do(state):
            pass
        def undo_(state):
            self.undo_called = True
        undoable = undo.undoable('desc', do, undo_)
        undoable()
        self.stack[0].undo()
        assert self.undo_called


class TestGenerator(TestCase):
    'Test undoble as a generator.'

    def setup(self):
        #Mock undo.stack() to return a list, stored as self.stack
        self.stack = []
        saver(undo, 'stack')
        mock_stack = lambda: self.stack
        undo.stack = mock_stack
        super().setup()

    def test_function(self):
        'undoable should create a generator action with no arguments.'
        @undo.undoable
        def do():
            yield

    def test_do(self):
        'Make sure undoable.do() runs'
        self.do_called = False
        @undo.undoable
        def do():
            self.do_called = True
            yield
            self.fail('Undo should not be called')
        do()
        assert self.do_called

    def test_undo(self):
        'Make sure undoable.undo() runs'
        self.undo_called = False
        @undo.undoable
        def do():
            yield
            self.undo_called = True
        do()
        self.stack[0].undo()
        assert self.undo_called

    def test_text(self):
        'Mare sure the undo text is set.'
        @undo.undoable
        def do():
            yield 'text'
        do()
        assert self.stack[0].text() == 'text'

    def test_method(self):
        'Test that arguments are passed correctly to methods.'
        class A:
            @undo.undoable
            def f(self, arg1, arg2):
                assert isinstance(self, A)
                assert arg1 == 1
                assert arg2 == 2
                yield
        a = A()
        a.f(1, 2)


class TestActionFactory(TestCase):

    def test_state(self):
        'Make sure state is transferred'
        def do(state):
            state['done'] = True
        def undo_(state):
            assert state['done']
        action = undo._ActionFactory('', do, undo_)
        action()
        undo.stack().undo()

    def test_text(self):
        'Test that description gets formatted with state'
        def do(state):
            state['foo'] = 'bar'
        action = undo._ActionFactory('desc - {foo}', do, lambda: None)
        action()
        assert undo.stack().undotext() == 'Undo desc - bar', undo.stack().undotext()


class TestGroup(TestCase):

    def test_stack(self):
        'Test that ``with group()`` diverts undo.stack()'
        undo.stack().clear()
        _Group = undo._Group('')
        stack = []
        _Group._stack = stack
        assert undo.stack()._receiver == undo.stack()._undos
        assert undo.stack().undocount() == 0
        with _Group:
            assert undo.stack()._receiver == stack
        assert undo.stack()._receiver == undo.stack()._undos
        assert undo.stack().undocount() == 1
        assert stack == []
        assert undo.stack()._undos == deque([_Group])

    def test_group(self):
        'Test that ``group()`` returns a context manager.'
        with undo.group('desc'):
            pass

class TestStack(TestCase):

    def setup(self):
        # Create a mock action for use in tests
        self.action = undo._Action('', core.none, core.none)
        self.action.undo = lambda: None
        self.action.text = lambda: 'blah'
        super().setup()

    def test_singleton(self):
        'undo.stack() always returns the same object'
        assert undo.stack() is undo.stack()

    def test_append(self):
        'undo.stack().append adds actions to the undo queue.'
        undo.stack().append('one')
        assert undo.stack()._undos == deque(['one'])

    def test_undo_changes_stacks(self):
        'Calling undo updates both the undos and redos stacks.'
        undo.stack()._undos = deque([1, 2, self.action])
        undo.stack()._redos = deque([4, 5, 6])
        undo.stack().undo()
        assert undo.stack()._undos == deque([1, 2])
        assert undo.stack()._redos == deque([4, 5, 6, self.action])

    def test_undo_resets_redos(self):
        'Calling undo clears any available redos.'
        undo.stack()._undos = deque([1, 2, 3])
        undo.stack()._redos = deque([4, 5, 6])
        undo.stack()._receiver = undo.stack()._undos
        undo.stack().append(7)
        assert undo.stack()._undos == deque([1, 2, 3, 7])
        assert undo.stack()._redos == deque([])

    def test_undotext(self):
        'undo.stack().undotext() returns a description of the undo available.'
        undo.stack()._undos = [self.action]
        assert undo.stack().undotext() == 'Undo blah'

    def test_redotext(self):
        'undo.stack().redotext() returns a description of the redo available.'
        undo.stack()._redos = [self.action]
        assert undo.stack().redotext() == 'Redo blah'

    def test_receiver(self):
        'Test that setreceiver and resetreceiver behave correctly.'
        stack = []
        undo.stack()._undos = []
        undo.stack().setreceiver(stack)
        undo.stack().append('item')
        assert stack == ['item']
        assert undo.stack()._undos == []
        undo.stack().resetreceiver()
        undo.stack().append('next item')
        assert stack == ['item']
        assert undo.stack()._undos == ['next item']

    def test_savepoint(self):
        'Test that savepoint behaves correctly.'
        undo.stack()._undos = deque([1, 2])
        assert undo.stack().haschanged()
        undo.stack().savepoint()
        assert not undo.stack().haschanged()
        undo.stack()._undos.pop()
        assert undo.stack().haschanged()

    def test_savepoint_clear(self):
        'Check that clearing the stack resets the savepoint.'
        undo.stack()._undos = deque()
        assert undo.stack().haschanged()
        undo.stack().savepoint()
        assert not undo.stack().haschanged()
        undo.stack().clear()
        assert undo.stack().haschanged()
        undo.stack().savepoint()
        assert not undo.stack().haschanged()
        undo.stack().clear()
        assert undo.stack().haschanged()


class TestSystem(TestCase):
    'A series of system tests'

    def setup_common(self):
        @undo.undoable('add @{pos} to {seq}')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq
            state['pos'] = len(seq) - 1
        @add.undo
        def add(state):
            seq, pos = state['seq'], state['pos']
            del seq[pos]
        return add

    def test_common(self):
        'Test some common useage.'
        add = self.setup_common()
        sequence = [1, 2, 3, 4]
        add(sequence, 5)
        assert sequence == [1, 2, 3, 4, 5]
        assert undo.stack().undotext() == 'Undo add @4 to [1, 2, 3, 4, 5]'
        undo.stack().undo()
        assert sequence == [1, 2, 3, 4]
        undo.stack().redo()
        assert sequence == [1, 2, 3, 4, 5]

    def setup_bound1(self):
        class List:
            def __init__(self):
                self._l = []

            @undo.undoable('Add an item')
            def add(self, state, item):
                self._l.append(item)

            @add.undo
            def add(self, state):
                self._l.pop()
        return List

    def test_bound1(self):
        'Test bound functions'
        List = self.setup_bound1()
        l = List()
        l.add(5)
        assert l._l == [5]
        l.add(3)
        assert l._l == [5, 3]
        l.add(5)
        assert l._l == [5, 3, 5]
        undo.stack().undo()
        assert l._l == [5, 3]
        undo.stack().undo()
        assert l._l == [5]
        undo.stack().undo()
        assert l._l == []

    def setup_bound2(self):
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

        return Mod

    def test_bound2(self):
        'Test more bound functions'
        Mod = self.setup_bound2()
        m = Mod()
        assert m.l == set()
        m.add(3)
        m.add(4)
        assert m.l == set([3, 4])
        assert undo.stack().undotext() == 'Undo Add 4'
        undo.stack().undo()
        assert m.l == set([3])
        m.delete(3)
        assert m.l == set()
        undo.stack().undo()
        assert m.l == set([3])
        assert undo.stack().canundo()
        undo.stack().undo()
        assert m.l == set()
        assert not undo.stack().canundo()

    def setup_groups1(self):
        @undo.undoable('add @{pos} to {seq}')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq
            state['pos'] = len(seq) - 1
        @add.undo
        def add(state):
            seq, pos = state['seq'], state['pos']
            del seq[pos]
        return add

    def test_groups1(self):
        'Test _Group behaviour'
        add = self.setup_groups1()
        sequence = [1, 2]
        with undo._Group('add many'):
            for i in range(5, 8):
                add(sequence, i)
        assert sequence == [1, 2, 5, 6, 7]
        assert undo.stack().undotext() == 'Undo add many'
        undo.stack().undo()
        assert sequence, [1, 2]
        assert undo.stack().redotext() == 'Redo add many'
        undo.stack().redo()
        assert sequence, [1, 2, 5, 6, 7]
        assert undo.stack().undotext() == 'Undo add many'

    def setup_groups2(self):
        @undo.undoable('Add 1 item')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq
        @add.undo
        def add(state):
            state['seq'].pop()
        return add

    def test_groups2(self):
        'Test more _Group behaviour.'
        add = self.setup_groups2()
        seq = []
        with undo._Group('Add many'):
            for item in [4, 6, 8]:
                add(seq, item)
        assert seq, [4, 6, 8]
        assert undo.stack().undocount() == 1
        undo.stack().undo()
        assert seq == []


class TestNested(TestCase):
    'Test nested actions'

    def setup(self):
        # Test a complicated nested case
        @undo.undoable('Add')
        def add(state, seq, item):
            seq.append(item)
            state['seq'] = seq

        @add.undo
        def add(state):
            delete(state['seq'])

        @undo.undoable('Delete')
        def delete(state, seq):
            state['value'] = seq.pop()
            state['seq'] = seq

        @delete.undo
        def delete(state):
            add(state['seq'], state['value'])

        self.add = add
        self.delete = delete
        super().setup()

    def test1(self):
        seq = [3, 6]
        self.add(seq, 4)
        assert seq == [3, 6, 4]
        undo.stack().undo()
        assert seq == [3, 6]
        self.delete(seq)
        assert seq == [3]
        undo.stack().undo()
        assert seq == [3, 6]

    def test2(self):
        seq = [3, 6]
        self.add(seq, 4)
        assert seq == [3, 6, 4]
        undo.stack().undo()
        assert seq == [3, 6]
        undo.stack().redo()
        assert seq == [3, 6, 4]
        assert undo.stack().canundo()
        undo.stack().undo()
        assert not undo.stack().canundo()


class TestExceptions(TestCase):
    'Test how exceptions within actions are handled.'

    def setup(self):
        def action(state): pass
        self.action = undo.undoable('', action, action)
        self.calls = 0
        super().setup()

    def setup_redo(self):
        @undo.undoable('desc')
        def add(state):
            if self.calls == 0:
                self.calls = 1
            else:
                raise TypeError

        @add.undo
        def add(state):
            pass
        return add

    def test_redo(self):
        'Test for an exception in the redo function.'
        add = self.setup_redo()
        self.action()
        self.action()
        add()
        assert undo.stack().undocount() == 3
        undo.stack().undo()
        assert undo.stack().undocount() == 2
        assert_raises(TypeError, undo.stack().redo)
        assert undo.stack().undocount() == 0
        assert undo.stack().redocount() == 0

    def setup_undo(self):
        @undo.undoable('desc')
        def add(state):
            pass

        @add.undo
        def add(state):
            if self.calls == 0:
                self.calls = 1
            else:
                raise TypeError

        return add

    def test_undo(self):
        'Test for an exception in the undo function.'
        add = self.setup_undo()
        self.action()
        self.action()
        add()
        undo.stack().undo()
        add()
        assert undo.stack().undocount() == 3
        assert_raises(TypeError, undo.stack().undo)
        assert undo.stack().undocount() == 0
        assert undo.stack().redocount() == 0

    def setup_do(self):
        @undo.undoable('desc')
        def add(state):
            raise TypeError

        @add.undo
        def add(state):
            self.fail('Undo should not be called')
        return add

    def test_do(self):
        'Test for an exception in the initial function call.'
        add = self.setup_do()
        self.action()
        self.action()
        assert undo.stack().undocount() == 2, undo.stack().undocount()
        assert_raises(TypeError, add)
        assert undo.stack().undocount() == 2



class TestGeneratorSystem(TestCase):
    'A series of system tests'

    def setup_common(self):
        @undo.undoable
        def add(seq, item):
            seq.append(item)
            pos = len(seq) - 1
            yield 'add @{pos} to {seq}'.format(pos, seq)
            del seq[pos]
        return add

    def setup_bound1(self):
        class List:
            def __init__(self):
                self._l = []

            @undo.undoable
            def add(self, item):
                self._l.append(item)
                yield 'Add an item'
                self._l.pop()
        return List

    def setup_bound2(self):
        class Mod:
            def __init__(self):
                self.l = set()

            @undo.undoable
            def add(self, value):
                self.l.add(value)
                yield 'Add {value}'
                self.l.remove(value)

            @undo.undoable
            def delete(self, value):
                self.l.remove(value)
                yield 'Delete {value}'
                self.l.add(value)

        return Mod

    def setup_groups1(self):
        @undo.undoable
        def add(state, seq, item):
            seq.append(item)
            pos = len(seq) - 1
            yield 'add @{pos} to {seq}'
            del seq[pos]
        return add

    def setup_groups2(self):
        @undo.undoable()
        def add(state, seq, item):
            seq.append(item)
            yield 'Add 1 item'
            seq.pop()
        return add


class TestGeneratorNested(TestCase):
    'Test nested actions'

    def setup(self):
        # Test a complicated nested case
        @undo.undoable
        def add(seq, item):
            seq.append(item)
            yield 'Add'
            delete(seq)

        @undo.undoable
        def delete(seq):
            value = seq.pop()
            yield 'Delete'
            add(seq, value)

        self.add = add
        self.delete = delete
        super().setup()


class TestGeneratorExceptions(TestCase):
    'Test how exceptions within actions are handled.'

    def setup(self):
        super().setup()
        @undo.undoable
        def action():
            yield
        self.action = action
        self.calls = 0

    def setup_redo(self):
        @undo.undoable
        def add():
            if self.calls == 0:
                self.calls = 1
            else:
                raise TypeError
            yield 'desc'
        return add

    def test_undo(self):
        @undo.undoable
        def add():
            yield 'desc'
            if self.calls == 0:
                self.calls = 1
            else:
                raise TypeError

        return add

    def setup_do(self):
        @undo.undoable
        def add(state):
            raise TypeError
            yield 'desc'
            self.fail('Undo should not be called')
        return add

