Finite
======

Introduction
------------
Yet another finite state automaton for python.

Example
-------
For an example of using finite for home automation, see: test/test1.dfa.

Configuration
-------------
The configuration format is yaml.

Each automata has a start state, a set of states and a set of transitions::

    automata1:
        start: Occupied
        states:
            Occupied:
                {}
            Alarmed:
                {}
        transitions:
            Occupied->Alarmed:
                when: house.presence.empty
            Occupied->Alarmed:
                when: house.presence.occupied

Transitions may have actions associated with them::

    Occupied->Alarmed:
        when: house.presence.empty
        actions:
        - speak('Alarm activated')

These callbacks are called on the 'callback' object passed when to a World.

A yaml file may list multiple automaton::

    automata1:
        start: State1
        states: ...
        transitions: ...

    automata2:
        start: State2
        states: ...
        transitions: ...

Code
----
Example::

    from finite import dfa
    automatons = dfa.Loader.load_file('my.dfa')
    worlds = dfa.Worlds()

    class Callback(object):
        def speak(self, msg):
            # do some speaking
            pass

    callback = Callback()

    for aut in auts:
        world = aut.make_world(callback)
        self.worlds.add(world)

Changelog
---------
0.1.0

- First release
