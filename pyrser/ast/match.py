"""
This module provide classes for PSL (Pyrser Selectors Language) implementation.
"""

from weakref import *
from pyrser import fmt

##########
class MatchExpr:
    """
    Ast Node for all match expression.
    """
    def get_stack_action(self, local_ev=None) -> list:
        raise TypeError("Not implemented")

    def ref_me(self, attr: str):
        # child reference this node
        child = getattr(self, attr)
        if child is not None:
            if type(child) is list:
                for c in child:
                    c.parent = self
            elif type(child) is dict:
                for c in child.values():
                    c.parent = self
            else:
                child.parent = self

    def get_root(self) -> 'MatchExpr':
        n = self
        while hasattr(n, 'parent'):
            n = n.parent
        return n

    def create_unknown_event(self) -> int:
        r = self.get_root()
        if not hasattr(r, 'max_unkev'):
            r.max_unkev = 0
            r.mapev = dict()
        uid = r.max_unkev
        r.mapev[uid] = '_%d' % uid
        r.max_unkev += 1
        return uid

    def create_depthreg(self) -> int:
        # depth reg are common for ancestors and siblings
        r = self.get_root()
        if not hasattr(r, 'max_depthreg'):
            r.max_depthreg = 0
            r.mapdreg = dict()
        uid = r.max_depthreg
        r.mapdreg[uid] = '_%d' % uid
        r.max_depthreg += 1
        return uid

class MatchIndice(MatchExpr):
    """
    Ast Node for matching one indice.
    """
    def __init__(self, idx: int, v=None):
        self.idx = idx
        if v is None:
            v = MatchValue()
        self.v = v
        self.ref_me('v')

    def __eq__(self, other) -> bool:
        return self.idx == other.idx

    def to_fmt(self) -> fmt.indentable:
        index = '*'
        if self.idx is not None:
            index = str(self.idx)
        res = fmt.sep('', [index + ': ', self.v.to_fmt()])
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = self.v.get_stack_action(local_ev)
        t = ('indice', )
        if self.idx is not None:
            t = ('indice', self.idx)
        tree[-1].append(t)
        return tree

class MatchList(MatchExpr):
    """
    Ast Node for matching indices.
    """
    def __init__(self, ls: [MatchIndice], strict=True):
        self.ls = sorted(ls, key=lambda x: x.idx)
        self.strict = strict
        self.ref_me('ls')

    def __eq__(self, other) -> bool:
        return self.ls == other.ls

    def to_fmt(self) -> fmt.indentable:
        res = fmt.block('[', ']', [])
        subls = []
        for item in self.ls:
            subls.append(item.to_fmt())
        if not self.strict:
            subls.append('...')
        res.lsdata.append(fmt.sep(', ', subls))
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = []
        list_ev = []
        for item in self.ls:
            subtree = item.get_stack_action(local_ev)
            unkev = self.create_unknown_event()
            subtree[-1].append(('set_event', unkev))
            tree += subtree
            list_ev.append(unkev)
        # final checks
        tree.append([])
        t = ('end_indices',)
        tree[-1].append(t)
        t = ('check_clean_event_and', list_ev)
        tree[-1].append(t)
        if self.strict:
            t = ('check_len', len(self.ls))
            tree[-1].append(t)
        return tree

class MatchKey(MatchExpr):
    """
    Ast Node for matching one key.
    """
    def __init__(self, key: str, v=None):
        self.key = key
        if v is None:
            v = MatchValue()
        self.v = v
        self.ref_me('v')

    def __eq__(self, other) -> bool:
        return self.key == other.key

    def to_fmt(self) -> fmt.indentable:
        key = '*'
        if self.key is not None:
            key = repr(self.key)
        res = fmt.sep('', [key + ': ', self.v.to_fmt()])
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = self.v.get_stack_action(local_ev)
        t = ('key', )
        if self.key is not None:
            t = ('key', self.key)
        tree[-1].append(t)
        return tree

class MatchDict(MatchExpr):
    """
    Ast Node for matching a Dict.
    """
    def __init__(self, d: [MatchKey], strict=True):
        self.d = sorted(d, key=lambda x: x.key)
        self.strict = strict
        self.ref_me('d')

    def __eq__(self, other) -> bool:
        return self.d == other.d

    def to_fmt(self) -> fmt.indentable:
        res = fmt.block('{', '}', [])
        subls = []
        for item in self.d:
            subls.append(item.to_fmt())
        if not self.strict:
            subls.append('...')
        res.lsdata.append(fmt.sep(', ', subls))
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = []
        list_ev = []
        for item in self.d:
            subtree = item.get_stack_action(local_ev)
            unkev = self.create_unknown_event()
            subtree[-1].append(('set_event', unkev))
            tree += subtree
            list_ev.append(unkev)
        # final checks
        tree.append([])
        t = ('end_keys',)
        tree[-1].append(t)
        t = ('check_clean_event_and', list_ev)
        tree[-1].append(t)
        if self.strict:
            t = ('check_len', len(self.d))
            tree[-1].append(t)
        return tree

class MatchAttr(MatchExpr):
    """
    Ast Node for matching one attribute.
    """
    def __init__(self, name: str=None, v=None):
        self.name = name
        if v is None:
            v = MatchValue()
        if type(v) in {int, str, float, bytes}:
            raise "Not literal"
        self.v = v
        self.ref_me('v')

    def __eq__(self, other) -> bool:
        return self.name == other.name

    def to_fmt(self) -> fmt.indentable:
        n = '*'
        if self.name is not None:
            n = self.name
        n = '.' + n
        v = '*'
        if self.v is not None:
            v = self.v.to_fmt()
        res = fmt.sep('=', [n, v])
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = self.v.get_stack_action()
        if local_ev is not None:
            tree[-1].append(('store_ancestor_depth', local_ev))
        t = ('attr',)
        if self.name is not None:
            t = ('attr', self.name)
        tree[-1].append(t)
        return tree

class MatchValue(MatchExpr):
    """
    Ast Node for matching one value.
    """
    def __init__(self, v=None):
        # if v is None -> wildcard
        self.v = v

    def __eq__(self, other) -> bool:
        return self.v == other.v

    def to_fmt(self) -> fmt.indentable:
        res = fmt.sep('', [])
        if self.v is None:
            res.lsdata.append('*')
        else:
            res.lsdata.append(repr(self.v))
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = [[]]
        tname = type(self.v).__name__
        if self.v is not None:
            t = ('value', self.v)
        else:
            t = ('value', )
            tname = ''
        tree[-1].append(t)
        if tname != '':
            t = ('type', tname)
        else:
            t = ('type', )
        tree[-1].append(t)
        t = ('end_node',)
        tree[-1].append(t)
        return tree

class MatchType(MatchExpr):
    """
    Ast Node for matching exactly one type.
    """
    def __init__(
        self,
        tname: str,
        attrs: [MatchExpr]=None,
        subs: [MatchDict or MatchList]=None,
        strict=True,
        iskindof=False
    ):
        self.t = tname
        self.attrs = None
        if attrs is not None:
            self.attrs = sorted(attrs, key=lambda x: x.name)
        self.subs = subs
        self.strict = strict
        self.iskindof = iskindof
        self.ref_me('attrs')
        self.ref_me('subs')

    def __eq__(self, other) -> bool:
        return self.t == other.t

    def to_fmt(self) -> fmt.indentable:
        res = fmt.sep('', [])
        res.lsdata.append(self.t)
        subs = None
        if self.subs is not None:
            subs = self.subs.to_fmt()
        iparen = fmt.sep(', ', [])
        if self.attrs is not None:
            for a in self.attrs:
                iparen.lsdata.append(a.to_fmt())
        if not self.strict:
            iparen.lsdata.append('...')
        data = None
        if subs is not None and iparen is not None:
            data = fmt.sep(" ", [subs, iparen])
        elif subs is None:
            data = iparen
        elif iparen is None:
            data = subs
        if self.iskindof:
            paren = fmt.block('?(', ')', data)
        else:
            paren = fmt.block('(', ')', data)
        res.lsdata.append(paren)
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = []
        list_ev = []
        list_depth = []
        # subs are Dict or List
        if self.subs is not None:
            tree = self.subs.get_stack_action()
            unkev = self.create_unknown_event()
            tree[-1].append(('set_event', unkev))
            list_ev.append(unkev)
        # TODO: first elem of subtree
        if self.attrs is not None:
            for idx, item in enumerate(self.attrs):
                regdepth = self.create_depthreg()
                subtree = item.get_stack_action(regdepth)
                list_depth.append(regdepth)
                unkev = self.create_unknown_event()
                subtree[-1].append(('set_event', unkev))
                tree += subtree
                list_ev.append(unkev)
        # final checks
        tree.append([])
        if self.strict:
            tree[-1].append(('end_attrs',))
            tree[-1].append(('check_attr_len', len(self.attrs)))
        t = ('value', )
        tree[-1].append(t)
        if self.iskindof:
            t = ('subtype', self.t)
        else:
            t = ('type', self.t)
        tree[-1].append(t)
        t = ('end_node',)
        tree[-1].append(t)
        #ancestor paternity
        if list_depth:
            for d in list_depth:
                tree[-1].append(('check_ancestor_depth', d, 1, False))
        # sync event
        if list_ev:
            t = ('check_clean_event_and', list_ev)
            tree[-1].append(t)
        return tree

######### SPECIAL

class MatchAncestor(MatchExpr):
    """
    Ast Node for capturing sequence of ancestors
    """
    def __init__(self, left, right, depth=1, is_min=False):
        self.left = left
        self.right = right
        self.ref_me('left')
        self.ref_me('right')
        if depth < 1:
            raise TypeError("Subnodes can't be at a depth < 1")
        self.depth = depth
        # is_min have meaning only if depth > 1
        self.is_min = is_min
    
    def to_fmt(self) -> fmt.indentable:
        def get_with_bracket(tree):
            if type(tree) is MatchSibling:
                return fmt.block('< ', ' >', [tree.to_fmt()])
            return tree.to_fmt()
        thesep = ' /'
        if self.is_min:
            thesep += '+'
        if self.depth > 1:
            thesep += '%d' % self.depth
        thesep += ' '
        res = fmt.sep(thesep, [])
        res.lsdata.append(get_with_bracket(self.left))
        res.lsdata.append(get_with_bracket(self.right))
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        lsev = []
        unkev = self.create_unknown_event()
        tree = self.right.get_stack_action(unkev)
        lsev.append(unkev)
        # store depth
        regdepth = self.create_depthreg()
        tree[-1].append(('store_ancestor_depth', regdepth))
        unkev = self.create_unknown_event()
        tree += self.left.get_stack_action(unkev)
        lsev.append(unkev)
        # check depth
        tree[-1].append(('check_ancestor_depth', regdepth, self.depth, self.is_min))
        return tree

class MatchSibling(MatchExpr):
    """
    Ast Node for capturing sequence of siblings
    """

    def __init__(self, old, new):
        self.ls = None
        if type(old) is MatchSibling:
            self.ls = old.ls
            self.ls.append(new)
        else:
            self.ls = [old, new]
        self.ref_me('ls')
    
    def to_fmt(self) -> fmt.indentable:
        def get_with_bracket(tree):
            if type(tree) is MatchAncestor:
                return fmt.block('< ', ' >', [tree.to_fmt()])
            return tree.to_fmt()
        res = fmt.sep(' ~~ ', [])
        for it in self.ls:
            res.lsdata.append(get_with_bracket(it))
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = []
        lsdepth = []
        lsev = []
        for it in self.ls:
            unkev = self.create_unknown_event()
            tree += it.get_stack_action(unkev)
            lsev.append(unkev)
            regd = self.create_depthreg()
            tree[-1].append(('store_sibling_depth', regd))
            lsdepth.append(regd)
        tree[-1].append(('check_sibling_depth', lsdepth))
        return tree

class MatchCapture(MatchExpr):
    """
    Ast Node for capturing the current node during matching
    """
    def __init__(self, n: str, v: MatchExpr, capture_pair=False):
        self.name = n
        self.v = v
        self.ref_me('v')
        self.capture_pair = capture_pair
        if capture_pair:
            if type(v) is MatchIndice:
                self.idx = v.idx
            elif type(v) is MatchKey:
                self.key = v.key

    def to_fmt(self) -> fmt.indentable:
        res = fmt.sep('->', [])
        res.lsdata.append(self.v.to_fmt())
        res.lsdata.append(self.name)
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = self.v.get_stack_action(local_ev)
        # we add capture before leaving the node
        if self.capture_pair:
            tree[-1].insert(-1, ('capture_pair_second', self.name))
            tree[-1].append(('capture_pair_first', self.name))
        else:
            tree[-1].insert(-1, ('capture', self.name))
        return tree

class MatchPrecond(MatchExpr):
    """
    Ast Node for matching a precondition expression.
    """
    def __init__(
        self,
        precond,
        v: MatchExpr=None,
        clean_event=True
    ):
        self.precond = precond
        self.v = v
        self.clean_event = clean_event
        self.ref_me('v')
        self.ref_me('precond')

    def to_fmt(self) -> fmt.indentable:
        res = fmt.sep(' ', [])
        if self.v is not None:
            res.lsdata.append(self.v.to_fmt())
        if self.clean_event:
            res.lsdata.append('&&')
        else:
            res.lsdata.append('!!')
        res.lsdata.append(fmt.block('(', ')', [self.precond.to_fmt()]))
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        list_ev = []
        tree = self.v.get_stack_action()
        unkev = self.create_unknown_event()
        tree[-1].append(('set_event', unkev))
        list_ev.append(unkev)
        unkev = self.create_unknown_event()
        tree[-1].extend(self.precond.get_stack_action(unkev))
        list_ev.append(unkev)
        t = ('check_clean_event_and', list_ev)
        tree[-1].append(t)
        if self.clean_event:
            t = ('postpone_clean_named_event',)
            tree[-1].append(t)
        return tree

class MatchEvent(MatchExpr):
    """
    Ast Node for a Resulting Event or intermediate Event.
    """

    def __init__(self, n: str, v: MatchExpr):
        self.n = n
        self.v = v
        self.ref_me('v')

    def __eq__(self, other) -> bool:
        return self.n == other.n

    def to_fmt(self) -> fmt.indentable:
        res = fmt.sep(' => ', [self.v.to_fmt(), self.n + ';'])
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = self.v.get_stack_action()
        t = ('set_named_event', self.n)
        tree[-1].append(t)
        return tree

class MatchHook(MatchExpr):
    """
    Ast Node for a Resulting Hook.
    """
    def __init__(self, call: str, v: MatchValue):
        self.n = call
        self.v = v
        self.ref_me('v')

    def __eq__(self, other) -> bool:
        return id(self.call) == id(other.call)

    def to_fmt(self) -> fmt.indentable:
        res = fmt.sep(' => ', [self.v.to_fmt(), '#' + self.n + ';'])
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        unkev = self.create_unknown_event()
        tree = self.v.get_stack_action(unkev)
        t = ('hook', self.n)
        tree[-1].append(t)
        return tree

class MatchBlock(MatchExpr):
    """ Ast Node for a block of PSL statement. """
    def __init__(self, stmts: [MatchExpr]):
        self.stmts = stmts
        self.root_edge = None
        self.ref_me('stmts')

    def to_fmt(self) -> fmt.indentable:
        res = fmt.block('{\n', '}', [fmt.tab([])])
        lines = res.lsdata[0].lsdata
        for stmt in self.stmts:
            lines.append(fmt.end('\n', stmt.to_fmt()))
        return res

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        tree = []
        for idx, s in enumerate(self.stmts):
            tree.append([(0, idx), s.get_stack_action()])
        return tree

class PrecondEvent(MatchExpr):
    def __init__(self, name):
        self.name = name

    def to_fmt(self) -> fmt.indentable:
        return self.name

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        return [('check_named_event', self.name, local_ev)]

class PrecondAnd(MatchExpr):
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs
        self.ref_me('lhs')
        self.ref_me('rhs')

    def to_fmt(self) -> fmt.indentable:
        return fmt.sep(' & ', [self.lhs.to_fmt(), self.rhs.to_fmt()])

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        list_ev = []
        unkev = self.create_unknown_event()
        tree = self.lhs.get_stack_action(unkev)
        list_ev.append(unkev)
        unkev = self.create_unknown_event()
        tree.extend(self.rhs.get_stack_action(unkev))
        list_ev.append(unkev)
        t = ('check_clean_event_and', list_ev)
        tree.append(t)
        tree.append(('set_event', local_ev))
        return tree

class PrecondOr(MatchExpr):
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs
        self.ref_me('lhs')
        self.ref_me('rhs')

    def to_fmt(self) -> fmt.indentable:
        return fmt.sep(' | ', [self.lhs.to_fmt(), self.rhs.to_fmt()])

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        list_ev = []
        unkev = self.create_unknown_event()
        tree = self.lhs.get_stack_action(unkev)
        list_ev.append(unkev)
        unkev = self.create_unknown_event()
        tree.extend(self.rhs.get_stack_action(unkev))
        list_ev.append(unkev)
        t = ('check_clean_event_or', list_ev)
        tree.append(t)
        tree.append(('set_event', local_ev))
        return tree

class PrecondXor(MatchExpr):
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs
        self.ref_me('lhs')
        self.ref_me('rhs')

    def to_fmt(self) -> fmt.indentable:
        return fmt.sep(' ^ ', [self.lhs.to_fmt(), self.rhs.to_fmt()])

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        list_ev = []
        unkev = self.create_unknown_event()
        tree = self.lhs.get_stack_action(unkev)
        list_ev.append(unkev)
        unkev = self.create_unknown_event()
        tree.extend(self.rhs.get_stack_action(unkev))
        list_ev.append(unkev)
        t = ('check_clean_event_xor', list_ev)
        tree.append(t)
        tree.append(('set_event', local_ev))
        return tree

class PrecondNot(MatchExpr):
    def __init__(self, expr):
        self.expr = expr
        self.ref_me('expr')

    def to_fmt(self) -> fmt.indentable:
        return fmt.sep('', ['!', self.expr.to_fmt()])

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        #TODO
        return tree

class PrecondParen(MatchExpr):
    def __init__(self, expr):
        self.expr = expr
        self.ref_me('expr')

    def to_fmt(self) -> fmt.indentable:
        return fmt.block('(', ')', [self.expr.to_fmt()])

    def __repr__(self) -> str:
        return str(self.to_fmt())

    def get_stack_action(self, local_ev=None):
        return tree.expr.get_stack_action(local_ev)
