.. module:: dtlibs.undo

.. testsetup::

   from dtlibs.undo import *
   
   
dtlibs.undo
===========

This is an undo/redo framework based on a functional approach which uses
a undoable stack to track actions.  Actions are the result of a function
call and know how to undo and redo themselves, assuming that any objects
they act on will always be in the same state before and after the action
occurs respectively.  The `stack` is a singleton object which tracks all
actions which can be done or undone.


Basic Usage
-----------

The easiest way to use this framework is by defining actions using
the `undoable` decorator on a generator object.  This is a very similar
syntax to that used by Pythons's `contextlib.contextmanager`.  For example,

.. doctest::

   >>> @undoable
   ... def add(sequence, item):
   ...     # Do the action
   ...     sequence.append(item)
   ...     position = len(sequence) - 1
   ...     # Yield a string describing the action 
   ...     yield "Add '{}' at psn '{}'".format(item, position)
   ...     # Undo the action
   ...     del sequence[position]


This defines a new action, *add*, which appends an item to a sequence.
The resulting object is an factory which creates a new action instance
and adds it to the stack.

.. doctest::

   >>> s = [1, 2, 3]
   >>> add(s, 4)
   >>> s
   [1, 2, 3, 4]
   >>> stack().undotext()
   "Undo Add '4' at psn '3'"
   >>> stack().undo()
   >>> s
   [1, 2, 3]

.. note:

   While all the example show here use functions, they will work perfectly
   well with class methods too.  E.g.
   
   .. doctest::
   
      >>> class Cls:
      ...     @undoable
      ...     def undoable_method(self, arg1, arg2):
      ...         self.value = arg1 + arg2
      ...         yield 'Action'
      ...         self.value = 0


Return values and exceptions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The first call to the action may have a return value by adding it to the
*yield* statement.  However, it will be ignored in subsequent redos or undos.

.. doctest::
   
   >>> @undoable
   ... def process(obj):
   ...     obj[0] += 1
   ...     yield 'Process', obj
   ...     obj[0] -=1
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

It is safe for actions to call each other.  Only the top-most action
is added to the stack.

.. doctest::
   
   >>> @undoable
   ... def add(seq, item):
   ...     seq.append(item)
   ...     yield 'Add'
   ...     pop(seq)
   ... 
   >>> @undoable
   ... def pop(seq):
   ...     value = seq.pop()
   ...     yield 'Pop'
   ...     add(seq, value)
   ... 
   >>> seq = [3, 6]
   >>> add(seq, 4)
   >>> seq
   [3, 6, 4]
   >>> stack().undo()
   >>> seq
   [3, 6]
   >>> pop(seq)
   >>> seq
   [3]
   >>> stack().undo()
   >>> seq
   [3, 6]


Clearing the stack
^^^^^^^^^^^^^^^^^^

The stack may be cleared if, for example, the document is saved.

.. doctest::
   
   >>> stack().canundo()
   True
   >>> stack().clear()
   >>> stack().canundo()
   False

It is also possible to record a savepoint to check if there have been any
changes.

.. doctest::

   >>> add(seq, 5)
   >>> stack().haschanged()
   True
   >>> stack().savepoint()
   >>> stack().haschanged()
   False
   >>> stack().undo()
   >>> stack().haschanged()
   True


Groups
^^^^^^

A series of actions may be grouped into a sngle action using the
`group` context manager.

.. doctest::

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


Advanced Usage
--------------

Actions can be created in a variety of ways.  All that is required is that
an action which has occurred has *do*, *undo* and *text* methods, none of
which accept any arguments.  The action must also be added to the stack
manually using `stack.append`.  The simplest way of creating custom
actions is to create a class which provides these methods and adds
itself to the stack when created.


Members
-------

.. autofunction:: dtlibs.undo.undoable

.. autofunction:: dtlibs.undo.group
 
.. autoclass:: dtlibs.undo.stack
   :members:
