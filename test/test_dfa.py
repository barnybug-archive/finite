#!/usr/bin/python

from twisted.trial import unittest
from finite.dfa import *
import os
import yaml
from cStringIO import StringIO

def _y(s):
    return yaml.load(StringIO(s))

example = '''
start: Hungry
states:
  Hungry: {}
  Eating:
    leaving: woof()
  Full:
    entering: digest()
  Sleepy: {}

transitions:
  Hungry->Eating:
    when: food
    actions:
    - woof()
    - eat('apple')
    - emit('full')
  Eating->Full:
    when: full
  Sleepy,Full:
    when: food
  Full->Hungry:
    when: run
  '*':
    - when: '*.scratch'
      actions: scratch()
    - when: 'sniff.*'
      actions: sniff()
'''
    
class TestCallback(Callback):
    def __init__(self):
        self.woofs = 0
        self.digests = 0
        self.eaten = None
        self.scratches = 0
        self.sniffs = 0

    def woof(self):
        self.woofs += 1

    def eat(self, food):
        self.eaten = food

    def digest(self):
        self.digests += 1

    def scratch(self):
        self.scratches += 1

    def sniff(self):
        self.sniffs += 1

class DfaTest(unittest.TestCase):
    def test_parse(self):
        aut = Automaton('test', _y(example))
        self.assertEqual(['Eating', 'Full', 'Hungry', 'Sleepy'], sorted(aut.states.keys()))
        self.assertEqual(3, len(aut.states['Eating'].transitions)) # 1 transition + 2 wildcards
        
    def test_make_dot(self):
        aut = Automaton('test', _y(example))
        fout = StringIO()
        Loader.make_dot(fout, [aut])
        self.assert_(fout.getvalue())
        
    def test_world(self):

        cb = TestCallback()
            
        aut = Automaton('test', _y(example))
        worlds = Worlds()
        dog = aut.make_world(cb)
        worlds.add(dog)
        self.assertEquals('Hungry', dog.state.name)

        # non-event
        worlds.process(Event('blob', True))
        self.assertEquals('Hungry', dog.state.name)
        self.assertEquals(0, cb.woofs)
        self.failIf(cb.eaten)
        
        # event caught by wildcard
        worlds.process(Event('dog.scratch', True))
        self.assertEquals('Hungry', dog.state.name)
        self.assertEquals(1, cb.scratches)
        
        # event caught by wildcard
        worlds.process(Event('sniff.on', True))
        self.assertEquals('Hungry', dog.state.name)
        self.assertEquals(1, cb.sniffs)
        
        # event
        worlds.process(Event('food.meat', True))
        self.assertEquals('Full', dog.state.name) # via Eating
        self.assertEquals(2, cb.woofs)
        self.assertEquals('apple', cb.eaten)

        worlds.process(Event('food.meat', True))
        self.assertEquals('Full', dog.state.name)
        self.assertEquals(1, cb.digests)
        
        worlds.process(Event('run', True))
        self.assertEquals('Hungry', dog.state.name)
        self.assertEquals(2, cb.woofs)

        self.assertEquals(1, cb.scratches)
        
    def test_persistance(self):
        aut = Automaton('test', _y(example))
        worlds = Worlds()
        dog = aut.make_world(TestCallback())
        worlds.add(dog)
        
        state1 = worlds.get_state()
        del state1['test']['changed_at']
        self.assertEqual({'test': {'state': 'Hungry'}}, state1)

        worlds.process(Event('food.meat', True))
        state2 = worlds.get_state()
        del state2['test']['changed_at']
        self.assertEqual({'test': {'state': 'Full'}}, state2)

        # test set state
        worlds.set_state(state1)
        state3 = worlds.get_state()
        del state3['test']['changed_at']
        self.assertEqual(state1, state3)
        
    def test_invalid(self):
        d = 'states: {}'
        self.assertRaises(ParseError, Automaton, 'test', _y(d))
        
class ConditionTest(unittest.TestCase):
    def test_conditions(self):
        ev1 = Event('pir.garage', True)
        ev2 = Event('door.front', True)
        
        self.assert_( Condition('pir.garage').eval(ev1) )
        self.assert_( Condition('pir').eval(ev1) )
        self.assert_( Condition('pir.garage or door.front').eval(ev1) )
        self.assert_( Condition('pir.garage or door.front').eval(ev2) )
        self.assert_( Condition('door.front or pir.garage').eval(ev2) )
        
    def test_str(self):
        self.assertEquals( 'pir.garage', str(Condition('pir.garage')) )
        
class LoaderTest(unittest.TestCase):
    def test_home(self):
        autsname = os.path.join(os.path.dirname(__file__), 'test1.dfa')
        auts = Loader.load_file(autsname)
        self.assertEquals(1, len(auts))
        aut = auts[0]
        self.assertEquals('home', aut.name)
