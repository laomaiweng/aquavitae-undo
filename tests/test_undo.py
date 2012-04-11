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

import undo


class TestSetStack:
    'Test setting and calling the current stack'

    def test_init_stack(self):
        'Test that a new stack is created'
        undo._stack = None
        stack = undo.stack()
        assert stack is undo._stack
        assert isinstance(stack, undo.Stack)

    def test_setstack(self):
        'Test that a new stack can be set'
        old = undo.stack()
        new = undo.Stack()
        undo.setstack(new)
        stack = undo.stack()
        assert stack is new
        assert stack is not old


class TestUndoable:
    'Test undoble as a generator.'

    def setup(self):
        #Set undo.stack() to a list, stored as self.stack
        self.stack = []
        undo.setstack(self.stack)

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

    def test_method_instances(self):
        'Test that multiple instances do not share actions.'
        class A:
            @undo.undoable
            def f(self, arg):
                self.value = arg
                yield

        a = A()
        b = A()
        a.f(1)
        b.f(2)
        assert a.value == 1
        assert b.value == 2

    def test_return_single(self):
        'Test a single return value'
        @undo.undoable
        def f():
            yield 'name', 32
        ret = f()
        assert ret == 32, ret

    def test_return_many(self):
        'Test multiple return values.'
        @undo.undoable
        def f():
            yield 'name', 32, ['a', 'list']
        assert f() == (32, ['a', 'list'])


class TestGroup:

    def setup(self):
        undo.setstack(undo.Stack())

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

    def test_group_multiple_undo(self):
        'Test that calling undo after a group undoes all actions.'
        @undo.undoable
        def add(seq, v):
            seq.append(v)
            yield 'add'
            seq.pop()

        l = []
        with undo.group('desc'):
            for i in range(3):
                add(l, i)

        assert l == [0, 1, 2], l
        assert undo.stack().undocount() == 1
        undo.stack().undo()
        assert undo.stack().undocount() == 0
        assert l == [], l


class TestStack:

    def setup(self):
        # Create a mock action for use in tests
        class Action:
            def do(self): pass
            def undo(self): pass
            def text(self):
                return 'blah'
        self.action = Action()
        undo.setstack(undo.Stack())

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


class TestSystem:
    'A series of system tests'

    def setup(self):
        undo.setstack(undo.Stack())

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


class TestNested:
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
        undo.setstack(undo.Stack())


class TestExceptions:
    'Test how exceptions within actions are handled.'

    def setup(self):
        undo.setstack(undo.Stack())
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

