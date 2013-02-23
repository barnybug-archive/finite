#!/usr/bin/python

import datetime
import yaml
import logging

class DotFile(object):
    """Support for graphviz .dot file format"""

    def __init__(self, fout):
        self.fout = fout
        self.indent = ''
        self._out('digraph AppClass {')
        
    def start(self, name):
        self._out('subgraph %s {' % name)
        self.indent += '  '
        
    def _out(self, txt):
        print >>self.fout, self.indent + txt
        
    def node(self, df):
        self._out('node [%s];\n' % df)
        
    def state(self, name, label):
        self._out('%s [label="%s"];' % (name, label))
        
    def transition(self, sfrom, sto, label):
        self._out('%s -> %s [label="%s"];' % (sfrom, sto, label))
        
    def end(self):
        self.indent = self.indent[0:-2]
        self._out('}')
        
    def finish(self):
        self._out('}')

class ObjectDict(dict):
    """Dict with support for automatic keying by properties on values.
    eg:
        class MyClass(object):
            def __init__(self, name, value):
                self.name = name
                self.value = value
        d = ObjectDict()
        obj = MyClass("a", 1)
        d.add(obj)
        print d["a"]
    """

    def __init__(self, key=lambda x: x.name):
        self.key = key
        
    def __iter__(self):
        """Iterate the values of the dictionary. This replaces
        the normal behaviour of iterating keys."""
        return self.itervalues()
        
    def add(self, obj):
        """Adds an object to the dictionary indexed by key"""
        self[self.key(obj)] = obj

WILDCARD = 'XXX'

class Event(object):
    """An event / message to the automaton.
    Events support hierarchical matching, so a.b.c can be matched
    by an expression 'a' or 'a.b' or 'a.b.c'"""
    def __init__(self, k, v):
        self.id = k
        self.k = v
        acc = []
        # for pir.garage True
        # sets:
        #  pir True
        #  pir_garage True
        li = k.split('.')
        for el in li:
            acc.append(el)
            self.__dict__[ '_'.join(acc) ] = v
            
        for i in range(0, len(li)):
            # also wildcards
            self.__dict__[ '_'.join(li[0:i]+[WILDCARD]) ] = v
            self.__dict__[ '_'.join(li[0:i]+[WILDCARD]+li[i+1:]) ] = v

    def __getitem__(self, k):
        """Get the item from this event"""
        return self.__dict__.get(k, False)
        
    def __setitem__(self, k, v):
        """Set the item on this event"""
        self.__dict__[k] = v
        
    def __str__(self):
        if self.k is True:
            return self.id
        else:
            return '%s=%s' % (self.id, self.k)

class Condition(object):
    """A python conditional expression."""

    def __init__(self, expr):
        self.expr = expr
        py = expr.replace('.', '_').replace('*', WILDCARD)
        self.compiled = compile(py, py, 'eval')
        
    def __str__(self):
        return self.expr

    def eval(self, env):
        return eval(self.compiled, {}, env)

class ParseError(Exception):
    """Exception representing a configuration parsing error."""
    pass
        
class State(object):
    """A state"""
    def __init__(self, name):
        self.name = name
        self.entering = []
        self.leaving = []
        self.transitions = []
        
    def get_transition(self, event):
        try:
            # find first transition satisfying when condition
            for tr in self.transitions:
                if tr.when.eval(event):
                    return tr
        except KeyError:
            return None

class Transition(object):
    """A transition between two states"""
    def __init__(self, s_from, s_to, when, actions=None):
        self.s_from = s_from
        self.s_to = s_to
        self.when = when
        self.actions = actions or []

class Action(object):
    """A callback action"""
    def __init__(self, value):
        self.value = value
        self.compiled = compile('callback.' + self.value, self.value, 'eval')
        
    def eval(self, callback, ev):
        env = {'callback': callback,
               'event': ev}
        return eval(self.compiled, {}, env)

    def __str__(self):
        return self.value
    
    @classmethod
    def load(cls, v):
        """Load the action from configuration"""
        if v is None:
            return []
        if isinstance(v, list):
            return [ Action(s) for s in v ]
        elif isinstance(v, str):
            return [Action(v)]
        else:
            raise ParseError("Couldn't parse action: %r" % v)

class Loader(object):
    """Configuration loader"""
    @classmethod
    def load_file(cls, filename):
        """Load Automatons from a filename"""
        return cls.load_stream(file(filename, 'r'))
        
    @classmethod
    def load_string(cls, s):
        """Load Automatons from a string"""
        from cStringIO import StringIO
        return cls.load_stream(StringIO(s))
    
    @classmethod
    def load_stream(cls, st):
        """Load Automatons from a stream"""
        y = yaml.load(st)
        return [ Automaton(k, v) for k, v in y.iteritems() ]

    @classmethod
    def make_dot(self, filename_or_stream, auts):
        """Create a graphviz .dot representation of the automaton."""
        if isinstance(filename_or_stream, str):
            stream = file(filename_or_stream, 'w')
        else:
            stream = filename_or_stream
        
        dot = DotFile(stream)
        
        for aut in auts:
            dot.start(aut.name)
            dot.node('shape=Mrecord width=1.5')
    
            for st in aut.states:
                label = st.name
                if st.entering:
                    label += '|%s' % '\\l'.join(str(st) for st in st.entering)
                if st.leaving:
                    label += '|%s' % '\\l'.join(str(st) for st in st.leaving)
                label = '{%s}' % label
                    
                dot.state(st.name, label=label)
                
            for st in aut.states:
                for tr in st.transitions:
                    dot.transition(tr.s_from.name, tr.s_to.name, tr.when)
            
            dot.end()
            
        dot.finish()

class Automaton(object):
    """A finite-state automaton"""

    def __init__(self, name, config):
        """Construct an Automaton.

        :param string name: name of the automaton
        :param dict config: configuration
        """
        self.states = ObjectDict()
        self.name = name
        self.load(config)
        
    def load(self, config):
        """load the configuration"""
        self.config = config
        
        if 'start' not in self.config:
            raise ParseError('missing start entry')
        if 'states' not in self.config:
            raise ParseError('missing states entry')
        if 'transitions' not in self.config:
            raise ParseError('missing transitions entry')

        for state, val in self.config['states'].iteritems():
            state = State(state)
            state.entering = Action.load(val.get('entering'))
            state.leaving = Action.load(val.get('leaving'))
            
            self.states.add(state)
            
        self.start = self.states[self.config['start']]
        
        for transition, val in self.config['transitions'].iteritems():
            if '->' in transition:
                # from->to
                lft, rgt = transition.split('->')
                if lft == '*':
                    sfroms = self.states.keys()
                else:
                    sfroms = lft.split(',')
                if rgt == '*':
                    stos = self.states.keys()
                else:
                    stos = rgt.split(',')
                pairs = ((f, t) for f in sfroms for t in stos)
            else:
                # self transition 'from1,from2' = from1->from1, from2->from2
                if transition == '*':
                    ss = self.states.keys()
                else:
                    ss = transition.split(',')
                pairs = ((x, x) for x in ss)
                
            for sfrom, sto in pairs:
                if sfrom not in self.states:
                    raise ParseError("Could find state %r" % sfrom)
                if sto not in self.states:
                    raise ParseError("Could find state %r" % sto)

                s_from = self.states[sfrom]
                s_to = self.states[sto]
                
                if not isinstance(val, list):
                    val = [val]
                for v in val:
                    when = v['when']
                    actions = Action.load(v.get('actions'))
                    transition = Transition(s_from, s_to, Condition(when), actions)
                    s_from.transitions.append(transition)
        
    def make_world(self, callback):
        return World(self, callback)
        
class World(object):
    """Convenience wrapper for Automaton."""
    def __init__(self, aut, callback, name=None):
        self.aut = aut
        self.callback = callback
        self.name = name or aut.name
        self.state = aut.start
        self.changed_at = None
        self.logger = logging.getLogger('world.%s' % self.name)
        
    noop = object()

    def event(self, ev):
        generated = []
        
        def run_actions(self, actions):
            for action in actions:
                try:
                    nev = action.eval(self.callback, ev)
                    # actions themselves can feedback events, so add to queue when any generated
                    if nev:
                        generated.append(nev)
                except:
                    self.logger.exception('running action: %s' % action)
        
        tr = self.state.get_transition(ev)
        if not tr:
            return World.noop

        if self.state.name != tr.s_to.name:
            self.logger.info('Transitioning %s->%s on %s' % (self.state.name, tr.s_to.name, ev))
        
        if self.state != tr.s_to:
            # run state leaving actions
            run_actions(self, self.state.leaving)
                
        # run transition actions
        run_actions(self, tr.actions)
        
        if self.state != tr.s_to:
            # update state
            self.state = tr.s_to
            self.changed_at = datetime.datetime.utcnow()
            
            # run state entering actions
            run_actions(self, self.state.entering)
        
        return generated
    
    def get_state(self):
        state = {'state': self.state.name, 'changed_at': self.changed_at}
        return state
    
    def set_state(self, state):
        self.state = self.aut.states[state['state']]
        self.changed_at = state.get('changed_at', None)
    
class Worlds(list):
    """A collection of Worlds"""

    def __init__(self):
        pass
    
    # alias
    add=list.append
        
    def process(self, ev):
        # all events get broadcast to all worlds in sequence, and
        # likewise for all generated events from callback - allowing worlds to interact
        # with each other
        changes = []
        queue = [ev]
        for ev in queue:
            for world in self:
                generated = world.event(ev)
                if generated == World.noop:
                    pass
                else:
                    changes.append((world, world.state))
                    queue.extend(generated)
        
        return changes
                
    def get_state(self):
        state = {}
        for world in self:
            state[world.name] = world.get_state()
        return state
    
    def set_state(self, state):
        for world in self:
            if world.name in state:
                world.set_state(state[world.name])
    
class Callback(object):
    def emit(self, ev, value=True):
        return Event(ev, value)
