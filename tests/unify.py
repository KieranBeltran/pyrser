import unittest
import sys
from weakref import ref
from copy import *
from itertools import product

from pyrser import meta
from pyrser.passes import to_yml
from pyrser.parsing import node
from tests.grammar.tl4t import *

#### For debug
import subprocess as sp

def to_png(fpng, cnt):
    fdot = fpng + ".dot"
    with open(fdot, "w") as f:
        f.write(str(cnt))
    sp.run(["dot", "-Tpng", "-o", fpng, fdot])

### Type Expr component

class TypeExprComponent(list):
    contains = None
    minarity = None
    def __init__(self, *deflist):
        if self.minarity is not None and len(deflist) < self.minarity:
            raise TypeError("%s take minimum %d parameters" % (type(self).__name__, self.minarity))
        for t in deflist:
            if self.contains is not None and type(t).__name__ not in self.contains:
                raise TypeError("%s can't be put in %s" % (type(t), type(self)))
        list.__init__(self, deflist)

    @property
    def reprlist(self):
        r = []
        for it in self:
            t = str(it)
            if isinstance(it, list) and type(self) is not Overload and len(it) > 1:
                t = '(' + t + ')'
            r.append(t)
        return r

    def __repr__(self) -> str:
        return str(self)

class Define:
    def __init__(self, name: str, type_def: TypeExprComponent):
        self.name = name
        self.type_def = type_def

    def unify(self, oth_type_def: TypeExprComponent, blhs, brhs) -> TypeExprComponent:
        """
        unify a definition with a correspondant type_def
        """
        print("DEFINE TRY TO TYPE %s ?? %s" % (type(self.type_def), type(oth_type_def)))
        print("TRY TO unify %s ?? %s" % (self.type_def, oth_type_def))
        return self.type_def.unify(oth_type_def, blhs, brhs)

    def __len__(self) -> int:
        return len(self.type_def)

    def __getitem__(self, idx) -> TypeExprComponent:
        return self.type_def[idx]

    def __str__(self) -> str:
        return "%s: %s" % (self.name, self.type_def)

    def __repr__(self) -> str:
        return str(self)

class UnknownName:
    """
    Implement unknown names: ?0, ?1, ?2
    """
    count = 0
    minarity = 1
    def __init__(self):
        self.anonname = '?%d' % UnknownName.count
        self.type_def = None
        UnknownName.count += 1

    def unify(self, oth_type_def: TypeExprComponent, blhs, brhs) -> TypeExprComponent:
        """
        When we unify an Unknown Name vs another type def we always match
        """
        print("UNK TRY TO unify %s ?? %s" % (self, oth_type_def))
        if self.type_def is not None:
            if type(oth_type_def) is UnknownName:
                if oth_type_def is None:
                    oth_type_def.type_def = self.type_def
                    return self.type_def
            return self.type_def.unify(oth_type_def, blhs, brhs)
        # TODO: the type must be fixed by the feedback pass
        if self.type_def is None:
            self.type_def = Overload()
        if oth_type_def not in self.type_def:
            self.type_def.append(oth_type_def)
        return oth_type_def

    def __str__(self) -> str:
        return self.anonname

class AnonDefine(Define):
    """
    Implement the TypeVar: ?0, ?1, ?2, ...
    """
    def __init__(self, cnt: 'Constraints' = None):
        """
        TODO: not really the final version
        at begin, we create circular type
        """
        self.defname = UnknownName()
        self.defs = self.defname
        Define.__init__(self, self.defname, Overload(self.defs))
        if cnt is not None:
            self.cnt = cnt
            self.cnt.add_defines([self])

class Overload(TypeExprComponent):
    contains = {'Fun', 'T', 'N', 'UnknownName'}
    minarity = 0

    def unify(self, oth_type_def: TypeExprComponent, blhs, brhs) -> TypeExprComponent:
        """
        When we unify an overload vs another type def we match each fun and we return the rest.
    
        t1 & t2 ?? t1 match and we return t1
        t1 & t2 ?? t2 match and we return t2
        """
        print("OV TRY TO unify %s ?? %s" % (self, oth_type_def))
        ovres = Overload()
        for ov in self:
            if not ov.unify(oth_type_def, blhs, brhs):
                return None
            ovres.append(oth_type_def)
        return ovres

    def __str__(self) -> str:
        return "\n& ".join(self.reprlist)

class Fun(TypeExprComponent):
    contains = {'Fun', 'Union', 'Tuple', 'UnknownName', 'T', 'N'}
    minarity = 1

    def unify(self, oth_type_def: TypeExprComponent, blhs, brhs) -> TypeExprComponent:
        """
        When we unify a function vs another type def we match each term and we return the rest.
    
        t1 -> t2 -> t3 ?? t1 -> t2 match and we return t3
        t1 -> t2 ?? t1 -> t2 -> t3 didn't match

        Note: the first element is the return type
        """
        print("FUN TRY TO unify %s ?? %s" % (self, oth_type_def))
        if type(oth_type_def) is not Fun:
            if type(oth_type_def) is T:
                return self[0].unify(oth_type_def, blhs, brhs)
            raise "not implemented"
        diff_len = len(self) - len(oth_type_def)
        if diff_len < 0: ## TODO: ADD ELLIPSIS
            return None
        for a, b in zip(reversed(self), reversed(oth_type_def)):
            if not a.unify(b, blhs, brhs):
                return None
        # TODO: what to do with the rest
        return Fun(*self[:diff_len])

    def __str__(self) -> str:
        return " -> ".join(reversed(self.reprlist))

class Union(TypeExprComponent):
    contains = {'Union', 'T', 'N'}
    minarity = 2

    def __str__(self) -> str:
        return " | ".join(self.reprlist)

class Tuple(TypeExprComponent):
    contains = {'Fun', 'Union', 'Tuple', 'T', 'N'}
    minarity = 2

    def __str__(self) -> str:
        return ", ".join(self.reprlist)

class N(TypeExprComponent):
    """N for Namespaces"""
    contains = {'T'}
    minarity = 2

    def __str__(self) -> str:
        return ".".join(self.reprlist)

class T:
    """T for Type"""
    def __init__(self, name: str, parametric: Tuple or 'T'=None, attributes=None):
        self.name = name
        if parametric is not None and type(parametric) not in {Tuple, T}:
            raise TypeError("T parametric must be a Tuple")
        self.parametric = parametric
        self.attributes = attributes

    def unify(self, oth_type_def: TypeExprComponent, blhs, brhs) -> TypeExprComponent:
        """
        When we unify a type vs another type def we match each term to term
        
        t1 ?? t1 match
        t1 ?? t2 didn't match
        TODO: parametric
        """
        print("T TRY TO unify %s ?? %s" % (self, oth_type_def))
        return self.name == oth_type_def

    def __eq__(self, oth) -> bool:
        """
        Use by all __contains__ call when we do some 'in' test
        """
        # TODO: self and oth for comparaison with TypeVar, attributes and parametric
        return self.name == oth

    def __str__(self) -> str:
        r = self.name
        if self.parametric is not None:
            r += '<' + str(self.parametric) + '>'
        return r

    def __repr__(self) -> str:
        return str(self)

########### TODO voir pour Binding
from collections import ChainMap

class Bind:
    def __init__(self, ast_node, cnt: 'Constraints'):
        self._ast_node = None
        self.ref_ast_node(ast_node)
        self.cnt = cnt
        # top-down dependence on another Bind object
        self.td_depend = None
        # bottom-up dependence on another Bind object
        self.bu_depend = None
        # by default we need to resolve binds, after we need to propagate modification
        self.flag = {'to_resolve'}
        # the final type (a Define instance)
        # by default a polymorphical type: unknownType
        self.final_type = AnonDefine(cnt)
        if type(self.final_type) is Bind:
            raise "C'est la merde"
        self.unify_algo = None

    def ref_ast_node(self, ast_node):
        if ast_node is not None and self._ast_node is None:
            bid = id(self)
            if bid not in self.cnt.bind2node:
                self.cnt.bind2node[bid] = ast_node
                self._ast_node = ast_node

    @property
    def ast_node(self) -> object:
        return self._ast_node

    @staticmethod
    def createList(cnt: 'Constraints', parent_bind: 'Bind', size: int) -> ['Bind']:
        res = []
        lastid = cnt.get_id_by_bind(parent_bind)
        for it in range(size):
            b = Bind(None, cnt)
            b.bu_depend = lastid
            bid = cnt.get_id_by_bind(b)
            cnt.get_bind_by_id(lastid).td_depend = bid
            lastid = bid
            res.append(b)
        return res

    @staticmethod
    def createListNodeItem(cnt: 'Constraints', parent_list_node: node.ListNodeItem = None) -> ['Bind']:
        b = Bind(None, cnt)
        if parent_list_node is not None:
            parent_bind = parent_list_node.data
            lastid = cnt.get_id_by_bind(parent_bind)
            b.bu_depend = lastid
            bid = cnt.get_id_by_bind(b)
            parent_bind.td_depend = bid
            return parent_list_node.append(b)
        return node.ListNodeItem(b)

    @staticmethod
    def bu_walk(b: 'Bind'):
        cnt = b.cnt
        bid = cnt.get_id_by_bind(b)
        nid = b.bu_depend
        while True:
            yield (bid, nid)
            if nid is not None:
                b = cnt.get_bind_by_id(nid)
                bid = id(b)
                nid = b.bu_depend
            else:
                break

    @staticmethod
    def td_walk(b: 'Bind'):
        cnt = b.cnt
        bid = cnt.get_id_by_bind(b)
        nid = b.td_depend
        while True:
            yield (bid, nid)
            if nid is not None:
                b = cnt.get_bind_by_id(nid)
                bid = id(b)
                nid = b.td_depend
            else:
                break

    def __str__(self) -> str:
        r = "\nid: %d" % id(self)
        r += "\nflags: %s" % str(self.flag)
        if self.bu_depend is not None:
            r += "\nbu_depend: %d" % self.bu_depend
        if self.td_depend is not None:
            r += "\ntd_depend: %d" % self.td_depend
        print("\n")
        return r
    
    def __repr__(self) -> str:
        return str(self)

    def unify_here(self):
        print("Unify %s" % self.final_type)
        n = self.ast_node
        ft = self.final_type
        if self.unify_algo is not None:
            ft = self.unify_algo()
        if type(ft) is Bind:
            raise "C'est la merde"
        # ast && bind contain final_type
        print("FT T %s" % type(ft))
        print("FINAL TYPE for %s is <%s>" % (self.ast_node.to_tl4t(), ft))
        if type(ft) is AnonDefine:
            print("INSTANCIATE AS %s" % ft.defname.type_def)
        n.final_type = ft
        self.final_type = ft
        return True

    def fit_here(self):
        print("Fit to %s" % self.final_type)
        return True

#############


#############

class Unifier:
    def __init__(self, bind_depends):
        self.cnt_ref = bind_depends[0].cnt
        self.def_f = bind_depends[0]
        if len(bind_depends) > 1:
            self.def_args = bind_depends[1:]
            print("UNIFIER: %d ?? %d" % (len(bind_depends), len(self.def_args)))

    ### unify algo
    # TODO: tres crade
    def unify_as_fun(self):
        """
        On a pas le type de retour, il viendra par l'unification des types de retour possible
        de la fonction avec le receveur de la fonction. Et ca sera fit_here
        """
        fun_args = self.def_args
        # make the product of all possible signature
        selected_sig = Overload()
        arg_pos = [range(len(arg.final_type)) for arg in fun_args]
        for types_tuple in product(*arg_pos):
            print(types_tuple)
            # make a proposition
            possible_sig = Fun(*[arg.final_type[idx] for arg, idx in zip(fun_args, types_tuple)])
            print(possible_sig)
            # if is good, take it
            # unify a tuple or Fun with fun definition
            t = self.def_f.final_type.unify(possible_sig, self.def_f, self.def_args)
            if t is not None:
                selected_sig.append(t)
        print("END UNIFY %s" % selected_sig)
        if type(selected_sig[0]) is UnknownName:
            print("INSTANCIATE ON %s" % selected_sig[0].defname.type_def)
        return selected_sig

    def unify_as_term(self):
        print("AS TERM")
        return self.def_f.final_type

class Constraints:
    def __init__(self, initial_defs: [Define]=None):
        # store definitions
        self.defs = []
        # store bind->ast_node
        self.bind2node = {}
        # map name -> idx in defs
        self.name2id = ChainMap()
        if initial_defs is not None:
            self.add_defines(initial_defs)
        # ...
        self.top_down = []
        self.bottom_up = []
        self.mapbind = {}

    def add_defines(self, defs: [Define]):
        if defs is not None and type(defs) is not list:
            raise TypeError("Constraints took a list of Define.")
        for idx, it in enumerate(defs):
            if not issubclass(type(it), Define):
                raise TypeError("Param %d is not a define" % idx)
        nodef = len(self.defs)
        ndef = len(defs)
        self.defs += defs
        for it, idx in zip(defs, range(ndef)):
            self.name2id[it.name] = nodef + idx

    def push_context(self):
        self.name2id = self.name2id.new_child()

    def pop_context(self):
        for idx in sorted(self.name2id.maps[0].values(), reverse=True):
            self.defs.pop(idx)
        self.name2id = self.name2id.parents

    def __str__(self) -> str:
        return self.to_dot()

    def to_dot(self) -> str:
        r = 'digraph {'
        r += '\n\tlabel="%s";' % str(self.defs)
        if len(self.mapbind) > 0:
            for k in sorted(self.mapbind.keys()):
                f = self.mapbind[k].flag
                node_ast = self.mapbind[k].ast_node
                t = "..."
                if node_ast is not None:
                    t = node_ast.to_tl4t()
                r += '\n\tnode[shape="box", style="rounded", label="{idnode}: {txt} <{flag}>"] _{idnode};'.format(idnode=k, txt=t, flag=f)
            for k in sorted(self.mapbind.keys()):
                td = self.mapbind[k].td_depend
                bu = self.mapbind[k].bu_depend
                if td is not None:
                    r += '\n\t_%d -> _%d [label="TU"];' % (k, td)
                if bu is not None:
                    r += '\n\t_%d -> _%d [label="BU"];' % (k, bu)
        r += '\n}'
        return r

    def get_def(self, name: str) -> Define:
        return self.defs[self.name2id[name]]

    def get_bind_by_id(self, bid: int) -> Bind:
        return self.mapbind[bid]

    def get_id_by_bind(self, src) -> int:
        bid = id(src)
        if bid not in self.mapbind:
            self.mapbind[bid] = src
        return bid

    def add_BU_cnt(self, src) -> int:
        id_src = self.get_id_by_bind(src)
        self.bottom_up.append(id_src)
        return id_src

    def add_TD_cnt(self, src):
        id_src = self.get_id_by_bind(src)
        self.top_down.append(id_src)
        return id_src

    def resolve(self):
        while True:
            done_something = False
            # BU
            while True:
                if len(self.bottom_up) == 0:
                    break
                it = self.bottom_up.pop()
                b = self.mapbind[it]
                if 'to_resolve' in b.flag:
                    if b.unify_here():
                        if b.bu_depend is not None:
                            self.bottom_up.append(b.bu_depend)
                        b.flag = {'to_resolve'}
                    done_something = True
            # TD
            while True:
                if len(self.top_down) == 0:
                    break
                it = self.top_down.pop()
                b = self.mapbind[it]
                if 'to_propagate' in b.flag:
                    # not unify but fit to type
                    if b.fit_here():
                        if b.td_depend is not None:
                            self.top_down.append(b.td_depend)
                        b.flag = {'to_propagate'}
                    done_something = True
            if not done_something:
                break

#####################

## for each language you must visit your tree and populate the Constraints
## Create a Bind object and add it in the contraint object
## Add a TD if need
@meta.add_method(BlockStmt)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("Add %s constraint" % type(self).__name__)
    cnt.push_context()
    len_lst = len(self.body)
    sub = Bind.createList(cnt, parent_bind, len_lst)
    parent_bind.ref_ast_node(self)
    for idx, it in zip(range(len_lst), self.body):
        it.populate(cnt, sub[idx])
    cnt.pop_context()

@meta.add_method(DeclVar)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("Add %s constraint" % type(self).__name__)
    d = Define(self.name, T(self.t))
    cnt.add_defines([d])
    sub = Bind.createList(cnt, parent_bind, 1)
    parent_bind.ref_ast_node(self)
    self.expr.populate(cnt, sub[0])


@meta.add_method(DeclFun)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("Add %s constraint" % type(self).__name__)
    # TODO: namespace/parametric/variadic...
    # voir td_depend et bu_depend
    d = Define(self.name, Fun(T(self.t, *self.p)))
    cnt.add_defines([d])
    len_lst = len(self.block)
    sub = Bind.createList(cnt, parent_bind, len_lst)
    parent_bind.ref_ast_node(self)
    for idx, it in zip(range(len_lst), self.block):
        it.populate(cnt, sub[idx])


@meta.add_method(ExprStmt)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("Add %s constraint" % type(self).__name__)
    self.expr.populate(cnt, parent_bind)

@meta.add_method(Expr)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("() Add %s constraint" % type(self).__name__)
    len_lst = len(self.p)
    print("arity: %d" % len_lst)
    sub = Bind.createList(cnt, parent_bind, len_lst + 1)
    parent_bind.ref_ast_node(self)
    self.call_expr.populate(cnt, sub[0])
    # TODO: must do a Bind for return?
    for idx, it in zip(range(1, len_lst + 1), self.p):
        it.populate(cnt, sub[idx])
    ualgo = Unifier(sub)
    parent_bind.unify_algo = ualgo.unify_as_fun
    print("CALL EXPR: %s" % sub[0].ast_node.to_tl4t())
    for idx in range(len_lst):
        print("CALL P[%d]: %s" % (idx, sub[idx + 1].ast_node.to_tl4t()))
        print("CALL U[%d]: %s" % (idx, ualgo.def_args[idx].ast_node.to_tl4t()))


@meta.add_method(Id)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("Add %s constraint" % type(self).__name__)
    print(self.value)
    parent_bind.ref_ast_node(self)
    # add for future resolution
    cnt.add_BU_cnt(parent_bind)
    # DO A DEEP COPY OF DEFINITION TO UPDATE IT?
    # set type as definition
    d = cnt.get_def(self.value)
    print("PUT DEF %s" % d)
    parent_bind.final_type = cnt.get_def(self.value)
    if type(parent_bind.final_type) is Bind:
        raise "C'est la merde"
    ualgo = Unifier([parent_bind])
    parent_bind.unify_algo = ualgo.unify_as_term


@meta.add_method(Operator)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("Add %s constraint" % type(self).__name__)
    print(self.value)
    parent_bind.ref_ast_node(self)
    # TODO: Found the definition of operator, treat as a Fun
    cnt.add_BU_cnt(parent_bind)
    d = cnt.get_def(self.value)
    print("PUT DEF %s" % d)
    parent_bind.final_type = cnt.get_def(self.value)
    if type(parent_bind.final_type) is Bind:
        raise "C'est la merde"
    ualgo = Unifier([parent_bind])
    parent_bind.unify_algo = ualgo.unify_as_term


@meta.add_method(Literal)
def populate(self, cnt: Constraints, parent_bind: 'Bind'):
    print("Add %s constraint" % type(self).__name__)
    print(self.value)
    parent_bind.ref_ast_node(self)
    # TODO: Found the type of the literal

############## Must replace populate

def bind_ast(root_node, cnt: Constraints, parent_list_node: node.ListNodeItem):
    print(type(root_node))
    parent_bind = parent_list_node.data
    if type(root_node).__name__ == "generator":
        try:
            while (True):
                n = root_node.send(None)
                if type(n) is tuple:
                    t = n[0]
                    s = len(n)
                    print(s)
                    print(t.upper())
                    if s > 1:
                        if t == "term":
                            node = n[1]
                            print(type(node))
                            parent_bind = parent_list_node.data
                            parent_bind.ref_ast_node(node)
                            d = cnt.get_def(n[2])
                            parent_bind.final_type = d
                            cnt.add_BU_cnt(parent_bind)
                            if type(parent_bind.final_type) is Bind:
                                raise "c'est la merde"
                            ualgo = Unifier([parent_bind])
                            parent_bind.unify_algo = ualgo.unify_as_term
                        elif t == "literal":
                            node = n[1]
                            parent_bind = parent_list_node.data
                            parent_bind.ref_ast_node(node)
                            # User must provide type for literal
                            parent_bind.final_type = n[2]
                            cnt.add_BU_cnt(parent_bind)
                            ualgo = Unifier([parent_bind])
                            parent_bind.unify_algo = ualgo.unify_as_term
                        elif t == "block":
                            block = n[1]
                            print(type(block))
                            cnt.push_context()
                            # need linked list
                            item_list = Bind.createListNodeItem(cnt, parent_list_node)
                            bind_ast(block, cnt, item_list)
                            cnt.pop_context()
                        elif t == "fun":
                            fun = n[1]
                            print(type(fun))
                            # need linked list
                            parent_bind = parent_list_node.data
                            parent_bind.ref_ast_node(fun)
                            item_list = Bind.createListNodeItem(cnt, parent_list_node)
                            bind_ast(fun, cnt, item_list)
                            ualgo = Unifier(item_list.thelist())
                            parent_bind.unify_algo = ualgo.unify_as_fun
                        # TODO: add defines
                elif type(n).__name__ == "generator":
                    bind_ast(n, cnt, parent_list_node)
                else:
                    print("something else")
        except StopIteration:
            # as expected we end the loop
            pass
        except ValueError as e:
            raise e
        except Exception as e:
            print("receive :%s" % e)
            print("detail: %s" % repr(sys.exc_info()))
    else:
        raise TypeError("walk() return something wrong! get %s expect a generator" % type(root_node))


#########################

class Unifying_Test(unittest.TestCase):

    def test_000(self):
        """Pretty Print Test"""
        d = Overload(T("t1"), T("t2"))
        self.assertEqual(str(d), "t1\n& t2")
        d = Fun(T("t1"), T("t2"))
        self.assertEqual(str(d), "t2 -> t1")
        d = Fun(T("t1"), T("t2"))
        self.assertEqual(str(d), "t2 -> t1")
        d = Union(T("t1"), T("t2"))
        self.assertEqual(str(d), "t1 | t2")
        d = Tuple(T("t1"), T("t2"))
        self.assertEqual(str(d), "t1, t2")
        d = Fun(T('t3'), Tuple(T("t1"), T("t2")))
        self.assertEqual(str(d), "(t1, t2) -> t3")
        def1 = Define('v1', T('t1'))
        self.assertEqual(str(def1), "v1: t1")
        def1 = Define('v1', N(T('m1'), T('m2'), T('t1')))
        self.assertEqual(str(def1), "v1: m1.m2.t1")
        def1 = Define('v1', N(T('m1', T('T')), T('t1')))
        self.assertEqual(str(def1), "v1: m1<T>.t1")

    def test_001(self):
        """Composition Test"""
        d = Overload(Fun(T("t1"), Tuple(T("t2"), T("t3"))),
            Fun(T("t4"), Tuple(T("t2"), T("t4")))
            )
        self.assertEqual(str(d), "(t2, t3) -> t1\n& (t2, t4) -> t4")
        with self.assertRaises(TypeError):
            d = Overload(Overload(T("t2"), T("t3")))
        with self.assertRaises(TypeError):
            d = Overload(Union(T("t2"), T("t3")))
        with self.assertRaises(TypeError):
            d = Overload(Tuple(T("t2"), T("t3")))
        with self.assertRaises(TypeError):
            d = Fun(Overload(T("t2"), T("t3")))
        with self.assertRaises(TypeError):
            d = Union(Overload(T("t2"), T("t3")))
        with self.assertRaises(TypeError):
            d = Union(Fun(T("t2"), T("t3")))
        with self.assertRaises(TypeError):
            d = Tuple(Overload(T("t2"), T("t3")))

    def test_002(self):
        """Constraints class tests"""
        basic_a =Define("A", None)
        cnt = Constraints([basic_a, Define("B", None), Define("C", None)])
        self.assertEqual(cnt.get_def("A").name, "A", "Can't find a basic define")
        self.assertEqual(cnt.get_def("B").name, "B", "Can't find a basic define")
        cnt.push_context()
        d = Define("A", Fun(T("t1"), T("t2")))
        cnt.add_defines([d])
        self.assertEqual(cnt.get_def("A"), d, "Can't find a basic define")
        cnt.pop_context()
        self.assertEqual(cnt.get_def("A"), basic_a, "Can't find a basic define")
        cnt.push_context()
        d1 = Define("A", Fun(T("t3"), T("t4")))
        d2 = Define("B", Fun(T("t5"), T("t6")))
        d3 = Define("Z", Fun(T("t7"), T("t8")))
        d4 = Define("X", Fun(T("t9"), T("t10")))
        cnt.add_defines([d1, d2, d3, d4])
        self.assertEqual(cnt.get_def("X"), d4, "Can't find a basic define")
        self.assertEqual(cnt.get_def("A"), d1, "Can't find a basic define")
        self.assertEqual(cnt.get_def("Z"), d3, "Can't find a basic define")
        self.assertEqual(cnt.get_def("B"), d2, "Can't find a basic define")
        cnt.pop_context()
        self.assertEqual(cnt.get_def("A"), basic_a, "Can't find a basic define")

    def test_003(self):
        """Bind object and list
        """
        cnt = Constraints()
        b = Bind(None, cnt)
        lstb = Bind.createList(cnt, b, 5)
        self.assertEqual(b.td_depend, id(lstb[0]), "List return by createList seems buggy")
        self.assertEqual(id(b), lstb[0].bu_depend, "List return by createList seems buggy")
        self.assertEqual(lstb[0].td_depend, id(lstb[1]), "List return by createList seems buggy")
        self.assertEqual(id(lstb[0]), lstb[1].bu_depend, "List return by createList seems buggy")
        self.assertEqual(lstb[1].td_depend, id(lstb[2]), "List return by createList seems buggy")
        self.assertEqual(id(lstb[1]), lstb[2].bu_depend, "List return by createList seems buggy")
        self.assertEqual(lstb[2].td_depend, id(lstb[3]), "List return by createList seems buggy")
        self.assertEqual(id(lstb[2]), lstb[3].bu_depend, "List return by createList seems buggy")
        self.assertEqual(lstb[3].td_depend, id(lstb[4]), "List return by createList seems buggy")
        self.assertEqual(id(lstb[3]), lstb[4].bu_depend, "List return by createList seems buggy")
        self.assertEqual(lstb[4].td_depend, None, "List return by createList seems buggy")
        to_png("ctx0.png", cnt)
        lsbu = list(Bind.bu_walk(lstb[-1]))
        lsburef = []
        what = lstb[-1]
        while what is not None:
            (bid, nid) = (id(what), what.bu_depend)
            lsburef.append((bid, nid))
            if nid is not None:
                what = what.cnt.get_bind_by_id(nid)
            else:
                what = None
        self.assertEqual(lsbu, lsburef, "List walked by bu_walk seems buggy")
        lstd = list(Bind.td_walk(b))
        lstdref = []
        what = b
        while what is not None:
            (bid, nid) = (id(what), what.td_depend)
            lstdref.append((bid, nid))
            if nid is not None:
                what = what.cnt.get_bind_by_id(nid)
            else:
                what = None
        self.assertEqual(lstd, lstdref, "List walked by bu_walk seems buggy")
        # Test it with a little grammar
        test = TL4T()
        res = test.parse("""
            v = f(a, b, c, d);
        """)
        # get AST nodes
        blockstmt = res
        exprstmt = blockstmt.body[0]
        eqexpr = exprstmt.expr
        eq = eqexpr.call_expr
        self.assertEqual(eq.value, '=', "bad access to parameter")
        v = eqexpr.p[0]
        self.assertEqual(v.value, 'v', "bad access to parameter")
        funexpr = eqexpr.p[1]
        f = funexpr.call_expr
        self.assertEqual(f.value, 'f', "bad access to parameter")
        a = funexpr.p[0]
        self.assertEqual(a.value, 'a', "bad access to parameter")
        b = funexpr.p[1]
        self.assertEqual(b.value, 'b', "bad access to parameter")
        c = funexpr.p[2]
        self.assertEqual(c.value, 'c', "bad access to parameter")
        # unification and grammar
        # f: t2 -> t1
        def1 = Define("f", Fun(T("t1"), T("t2")))
        # a: t2
        def2 = Define("a", Overload(T("t2")))
        # g: t1
        def3 = Define("g", Overload(T("t1")))
        # f: ?0 -> ?0 -> ?0
        p1 = UnknownName()
        def4 = Define("=", Fun(p1, p1, p1))
        # Test it with a little grammar
        test = TL4T()
        res = test.parse("""
            g = f(a);
        """)
        txt = res.to_tl4t()
        print(txt)
        cnt = Constraints([def1, def2, def3, def4])
        b = Bind(None, cnt)
        res.populate(cnt, b)
        print("-" * 10)
        to_png("ctx1.png", cnt)
        cnt.resolve()

    def test_04(self):
        """Basic unification.
         We assume the Binding (link item to type definition is done.
         """
        # just unification for a Fun
        overloads = Overload(
                Fun(T("t1"), T("t2"), T("t3")),
                Fun(T("t4"), T("t2"), T("t5"))
            )
        def_f = Define("f", overloads)
        print(def_f)
        # v = f(a, b)
        def_a = Define("a", Overload(T("t1"), T("t2")))
        def_b = Define("b", Overload(T("t3"), T("t0")))
        def_v = Define("v", Overload(T("t1"), T("t4")))

        ####
        fun_args = [def_v, def_a, def_b]
        # make the product of all possible signature
        selected_sig = []
        arg_pos = [range(len(arg)) for arg in fun_args]
        for types_tuple in product(*arg_pos):
            print(types_tuple)
            # make a proposition
            possible_sig = [arg[idx] for arg, idx in zip(fun_args, types_tuple)]
            print(possible_sig)
            # if is good, take it
            if possible_sig in def_f:
                selected_sig.append(possible_sig)
        print("possible sig: %s" % selected_sig)

    def test_05(self):
        test = TL4T()
        res = test.parse("""
            fun toto(x, y, z)
            {
                x = sqrt(y) / z * 2;
            }
        """)
        #print("-" * 20)
        #print(res.to_tl4t())
        #print("-" * 20)
        #print(res.to_yml())
        print("-" * 20)
        def_x = Define("x", UnknownName())
        def_y = Define("y", UnknownName())
        def_z = Define("z", UnknownName())
        def_sqrt = Define("sqrt", Fun(T("float"), T("float")))
        p = UnknownName()
        def_eq = Define("=", Fun(p, p, p))
        def_mul = Define("*", Fun(p, p, p))
        def_div = Define("/", Fun(p, p, p))
        cnt = Constraints([def_x, def_y, def_z, def_sqrt, def_eq, def_mul, def_div])
        b = Bind.createListNodeItem(cnt)
        bind_ast(res.walk(), cnt, b)
