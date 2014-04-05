from pyrser import parsing
from pyrser import meta
from pyrser import error
from pyrser.directives import ignore


class EBNF(parsing.Parser):
    """
    Basic class for BNF DSL PARSING.

    A full parser for the BNF is provided by this class.
    We construct a tree to represents, thru functors, BNF semantics.
    """

    def get_rules(self) -> parsing.Node:
        """
        Parse the DSL and provide a dictionnaries of all resulting rules.
        Call by the MetaGrammar class.
        """
        # TODO:
        res = None
        try:
            res = self.eval_rule('bnf_dsl')
        except error.Diagnostic as d:
            d.notify(
                error.Severity.ERROR,
                "Parse error with the rule %s" % self._lastRule,
                error.StreamInfo(self._stream)
            )
            res = d
        return res

    def __init__(self, content='', sname='BNF'):
        """
        Define the DSL parser.
        """
        super().__init__(content, sname)
        self.set_rules({
            #
            # bnf_dsl = [ @ignore("C/C++") bnf_stmts ]
            #
            'bnf_dsl': parsing.Seq(
                # tree is not already construct but Directive need it
                # forward it thru a lambda
                parsing.Directive(ignore.Ignore(),
                                  [("C/C++", str)],
                                  lambda parser:
                                  self.__class__._rules['bnf_stmts'](parser)),
            ),

            #
            # bnf_stmts = [ [rule : r #add_rules(_, r) ]+ Base.eof ]
            #
            'bnf_stmts': parsing.Seq(
                parsing.Rep1N(parsing.Seq(
                    parsing.Capture("r", parsing.Rule('rule')),
                    parsing.Hook('add_rules', [("_", parsing.Node),
                                               ("r", parsing.Node)])
                )),
                parsing.Rule('Base.eof')
            ),

            # TODO: add directive hooks / change ns_name by def_rule
            #
            # rule = [ ns_name : rn '=' '[' alternatives : alts
            #                             #add_rule(_, rn, alts) ']' ]
            #
            'rule': parsing.Seq(
                parsing.Capture("rn", parsing.Rule('ns_name')),
                parsing.Alt(
                    parsing.Call(parsing.Parser.read_text, "="),
                    parsing.Error("Expected '='")),
                parsing.Alt(
                    parsing.Call(parsing.Parser.read_text, "["),
                    parsing.Error("Expected '['")),
                parsing.Capture("alts", parsing.Rule('alternatives')),
                parsing.Hook('add_rule', [("_", parsing.Node),
                                          ("rn", parsing.Node),
                                          ("alts", parsing.Node)]),
                parsing.Alt(
                    parsing.Call(parsing.Parser.read_char, ']'),
                    parsing.Error("Expected ']'"))
            ),

            #
            # alternatives =
            # [
            #       sequences : alt #add_alt(_, alt)
            #       ['|' sequences : alt #add_alt(_, alt) ]*
            # ]
            #
            'alternatives': parsing.Seq(
                parsing.Capture('alt', parsing.Rule('sequences')),
                parsing.Hook('add_alt', [("_", parsing.Node),
                                         ("alt", parsing.Node)]),
                parsing.Rep0N(
                    parsing.Seq(
                        parsing.Call(parsing.Parser.read_char, '|'),
                        parsing.Capture('alt', parsing.Rule('sequences')),
                        parsing.Hook('add_alt',
                                     [("_", parsing.Node),
                                      ("alt", parsing.Node)])
                    )
                )
            ),

            #
            # sequences = [ [ sequence : cla #add_sequences(_, cla) ]+ ]
            #
            'sequences': parsing.Rep1N(
                parsing.Seq(
                    parsing.Capture('cla', parsing.Rule('sequence')),
                    parsing.Hook('add_sequences',
                                 [("_", parsing.Node),
                                  ("cla", parsing.Node)])
                )
            ),

            #
            # sequence = [
            #   [
            #     [ '~' | "!!" | '!' | "->" ]?: mod
            #     [ ns_name : rid #add_ruleclause_name(_, rid)
            #       | Base.string : txt #add_text(_, txt)
            #       | Base.char : begin ".." Base.char : end
            #         #add_range(_, begin, end)
            #       | Base.char : c #add_char(_, c)
            #       | '[' alternatives : subsequence ']'
            #         #add_subsequence(_, subsequence)
            #     ] #add_mod(_, mod)
            #     [ repeat : rpt #add_rpt(_, mod, rpt) ]?
            #   | hook : h #add_hook(_, h)
            #   | directive : d sequences : s #add_directive(_, d, s)
            #   ]
            #     [
            #       ":>" Base.id : bind #add_bind(_, bind)
            #       | ':' Base.id : cpt #add_capture(_, cpt)
            #     ]?
            # ]
            #
            'sequence':
            parsing.Seq(
                parsing.Alt(
                    parsing.Seq(
                        parsing.Capture(
                            'mod',
                            parsing.RepOptional(
                                parsing.Alt(
                                    parsing.Call(
                                        parsing.Parser.read_char,
                                        '~'
                                    ),
                                    parsing.Call(
                                        parsing.Parser.read_text,
                                        '!!'
                                    ),
                                    parsing.Call(
                                        parsing.Parser.read_char,
                                        '!'
                                    ),
                                    parsing.Call(
                                        parsing.Parser.read_text,
                                        '->'
                                    )
                                )
                            )
                        ),
                        parsing.Alt(
                            parsing.Seq(
                                parsing.Capture(
                                    'rid',
                                    parsing.Rule('ns_name')
                                ),
                                parsing.Hook('add_ruleclause_name',
                                             [("_", parsing.Node),
                                              ("rid", parsing.Node)])
                            ),
                            parsing.Seq(
                                parsing.Capture('txt',
                                                parsing.Rule('Base.string')),
                                parsing.Hook('add_text',
                                             [("_", parsing.Node),
                                              ("txt", parsing.Node)])
                            ),
                            parsing.Seq(
                                parsing.Capture('begin',
                                                parsing.Rule('Base.char')),
                                parsing.Call(parsing.Parser.read_text, ".."),
                                parsing.Capture(
                                    'end',
                                    parsing.Rule('Base.char')
                                ),
                                parsing.Hook('add_range',
                                             [("_", parsing.Node),
                                              ("begin", parsing.Node),
                                              ("end", parsing.Node)])
                            ),
                            parsing.Seq(
                                parsing.Capture(
                                    'c',
                                    parsing.Rule('Base.char')
                                ),
                                parsing.Hook('add_char',
                                             [("_", parsing.Node),
                                              ("c", parsing.Node)])
                            ),
                            parsing.Seq(
                                parsing.Call(parsing.Parser.read_char, "["),
                                parsing.Capture(
                                    'subsequence',
                                    parsing.Alt(
                                        parsing.Rule('alternatives'),
                                        parsing.Error("Expected sequences"))),
                                parsing.Alt(
                                    parsing.Call(
                                        parsing.Parser.read_char,
                                        "]"
                                    ),
                                    parsing.Error("Expected ']'")),
                                parsing.Hook('add_subsequence',
                                             [("_", parsing.Node),
                                              ("subsequence", parsing.Node)]),
                            )
                        ),
                        parsing.Hook('add_mod', [("_", parsing.Node),
                                                 ("mod", parsing.Node)]),
                        parsing.RepOptional(
                            parsing.Seq(
                                parsing.Capture(
                                    'rpt',
                                    parsing.Rule('repeat')
                                ),
                                parsing.Hook('add_rpt',
                                             [("_", parsing.Node),
                                              ("mod", parsing.Node),
                                              ("rpt", parsing.Node)])
                            )
                        ),
                    ),
                    parsing.Seq(
                        parsing.Capture('h', parsing.Rule('hook')),
                        parsing.Hook('add_hook', [('_', parsing.Node),
                                                  ('h', parsing.Node)])
                    ),
                    parsing.Seq(
                        parsing.Capture('d', parsing.Rule('directive')),
                        parsing.Capture('s', parsing.Rule('sequences')),
                        parsing.Hook('add_directive', [('_', parsing.Node),
                                                       ('d', parsing.Node),
                                                       ('s', parsing.Node)])
                    )
                ),
                parsing.RepOptional(
                    parsing.Alt(
                        parsing.Seq(
                            parsing.Call(parsing.Parser.read_text, ":>"),
                            parsing.Capture(
                                'bind',
                                parsing.Rule('Base.id')),
                            parsing.Hook('add_bind',
                                         [('_', parsing.Node),
                                          ('bind', parsing.Node)])
                        ),
                        parsing.Seq(
                            parsing.Call(parsing.Parser.read_text, ":"),
                            parsing.Capture(
                                'cpt',
                                parsing.Rule('Base.id')),
                            parsing.Hook('add_capture',
                                         [('_', parsing.Node),
                                          ('cpt', parsing.Node)])
                        )
                    )
                )
            ),

            # ns_name = [ [@ignore("null") [ Base.id ['.' Base.id]* ]]: rid ]
            #
            'ns_name': parsing.Capture(
                'rid',
                parsing.Scope(
                    parsing.Call(parsing.Parser.push_ignore,
                                 parsing.Parser.ignore_null),
                    parsing.Call(parsing.Parser.pop_ignore),
                    parsing.Seq(
                        parsing.Rule('Base.id'),
                        parsing.Rep0N(
                            parsing.Seq(
                                parsing.Call(parsing.Parser.read_text, "."),
                                parsing.Alt(
                                    parsing.Rule('Base.id'),
                                    parsing.Error(
                                        "Expected identifier after '.'"))
                            )
                        )
                    )
                )
            ),

            #
            # repeat = [ '?' #add_optional(_)
            #          | '*' #add_0N(_)
            #          | '+' #add_1N(_)
            # ]
            #
            'repeat': parsing.Alt(
                parsing.Seq(
                    parsing.Call(parsing.Parser.read_char, '?'),
                    parsing.Hook('add_optional', [("_", parsing.Node)])
                ),
                parsing.Seq(
                    parsing.Call(parsing.Parser.read_char, '*'),
                    parsing.Hook('add_0N', [("_", parsing.Node)])
                ),
                parsing.Seq(
                    parsing.Call(parsing.Parser.read_char, '+'),
                    parsing.Hook('add_1N', [("_", parsing.Node)])
                ),
            ),

            #
            # hook = [ '#' ns_name : n #hook_name(_, n)
            #          ['(' param : p #hook_param(_, p)
            #              [',' param : p #hook_param(_, p)]*
            #           ')']?
            # ]
            #
            'hook': parsing.Seq(
                parsing.Call(parsing.Parser.read_char, '#'),
                parsing.Capture('n', parsing.Rule('ns_name')),
                parsing.Hook('hook_name',
                             [('_', parsing.Node), ('n', parsing.Node)]),
                parsing.RepOptional(
                    parsing.Seq(
                        parsing.Call(parsing.Parser.read_char, '('),
                        parsing.Capture(
                            'p',
                            parsing.Alt(
                                parsing.Rule('param'),
                                parsing.Error("Expected parameter"))),
                        parsing.Hook('hook_param', [('_', parsing.Node),
                                                    ('p', parsing.Node)]),
                        parsing.Rep0N(
                            parsing.Seq(
                                parsing.Call(parsing.Parser.read_char, ','),
                                parsing.Capture(
                                    'p',
                                    parsing.Alt(
                                        parsing.Rule('param'),
                                        parsing.Error("Expected parameter"))),
                                parsing.Hook('hook_param',
                                             [('_', parsing.Node),
                                              ('p', parsing.Node)]))
                        ),
                        parsing.Alt(
                            parsing.Call(parsing.Parser.read_char, ')'),
                            parsing.Error("Expected ')'"))
                    )
                ),
            ),

            #
            # directive = [ '@' ns_name : n #hook_name(_, n)
            #               ['(' param : p #hook_param(_, p)
            #                   [',' param : p #hook_param(_, p)]*
            #                ')']?
            # ]
            'directive': parsing.Seq(
                parsing.Call(parsing.Parser.read_char, '@'),
                parsing.Capture('n', parsing.Rule('ns_name')),
                parsing.Hook('hook_name', [('_', parsing.Node),
                                           ('n', parsing.Node)]),
                parsing.RepOptional(
                    parsing.Seq(
                        parsing.Call(parsing.Parser.read_char, '('),
                        parsing.Capture(
                            'p',
                            parsing.Alt(
                                parsing.Rule('param'),
                                parsing.Error("Expected parameter"))),
                        parsing.Hook('hook_param',
                                     [('_', parsing.Node),
                                      ('p', parsing.Node)]),
                        parsing.Rep0N(
                            parsing.Seq(
                                parsing.Call(parsing.Parser.read_char, ','),
                                parsing.Capture(
                                    'p',
                                    parsing.Alt(
                                        parsing.Rule('param'),
                                        parsing.Error("Expected parameter"))),
                                parsing.Hook('hook_param',
                                             [('_', parsing.Node),
                                              ('p', parsing.Node)]),
                            )
                        ),
                        parsing.Alt(
                            parsing.Call(parsing.Parser.read_char, ')'),
                            parsing.Error("Expected ')'"))
                    )
                ),
            ),

            #
            # param = [ Base.num :n #param_num(_, n)
            #         | Base.string : s #param_str(_, s)
            #         | Base.char : c #param_char(_, c)
            #         | ns_name : i #param_id(_, i)
            # ]
            #
            'param': parsing.Alt(
                parsing.Seq(
                    parsing.Capture('n', parsing.Rule('Base.num')),
                    parsing.Hook('param_num', [('_', parsing.Node),
                                               ('n', parsing.Node)])
                ),
                parsing.Seq(
                    parsing.Capture('s', parsing.Rule('Base.string')),
                    parsing.Hook('param_str', [('_', parsing.Node),
                                               ('s', parsing.Node)])
                ),
                parsing.Seq(
                    parsing.Capture('c', parsing.Rule('Base.char')),
                    parsing.Hook('param_char', [('_', parsing.Node),
                                                ('c', parsing.Node)])
                ),
                parsing.Seq(
                    parsing.Capture('i', parsing.Rule('ns_name')),
                    parsing.Hook('param_id', [('_', parsing.Node),
                                              ('i', parsing.Node)])
                ),
            ),
        })

# Hooks part
# ----------
# All these functions are automatically added to class EBNF


@meta.hook(EBNF, "EBNF.add_mod")
def add_mod(self, seq, mod):
    """Create a tree.{Complement, LookAhead, Neg, Until}"""
    modstr = self.value(mod)
    if modstr == '~':
        seq.parser_tree = parsing.Complement(seq.parser_tree)
    elif modstr == '!!':
        seq.parser_tree = parsing.LookAhead(seq.parser_tree)
    elif modstr == '!':
        seq.parser_tree = parsing.Neg(seq.parser_tree)
    elif modstr == '->':
        seq.parser_tree = parsing.Until(seq.parser_tree)
    return True


@meta.hook(EBNF, "EBNF.add_ruleclause_name")
def add_ruleclause_name(self, ns_name, rid) -> bool:
    """Create a tree.Rule"""
    ns_name.parser_tree = parsing.Rule(self.value(rid))
    return True


@meta.hook(EBNF, "EBNF.add_rules")
def add_rules(self, bnf, r) -> bool:
    """Attach a parser tree to the dict of rules"""
    bnf[r.rulename] = r.parser_tree
    return True


@meta.hook(EBNF, "EBNF.add_rule")
def add_rule(self, rule, rn, alts) -> bool:
    """Add the rule name"""
    rule.rulename = self.value(rn)
    rule.parser_tree = alts.parser_tree
    return True


@meta.hook(EBNF, "EBNF.add_sequences")
def add_sequences(self, sequences, cla) -> bool:
    """Create a tree.Seq"""
    if not hasattr(sequences, 'parser_tree'):
        # forward sublevel of sequence as is
        sequences.parser_tree = cla.parser_tree
    else:
        oldnode = sequences
        if isinstance(oldnode.parser_tree, parsing.Seq):
            oldpt = list(oldnode.parser_tree.ptlist)
        else:
            oldpt = [oldnode.parser_tree]
        oldpt.append(cla.parser_tree)
        sequences.parser_tree = parsing.Seq(*tuple(oldpt))
    return True


@meta.hook(EBNF, "EBNF.add_alt")
def add_alt(self, alternatives, alt) -> bool:
    """Create a tree.Alt"""
    if not hasattr(alternatives, 'parser_tree'):
        # forward sublevel of alt as is
        if hasattr(alt, 'parser_tree'):
            alternatives.parser_tree = alt.parser_tree
        else:
            alternatives.parser_tree = alt
    else:
        oldnode = alternatives
        if isinstance(oldnode.parser_tree, parsing.Alt):
            oldpt = list(oldnode.parser_tree.ptlist)
        else:
            oldpt = [oldnode.parser_tree]
        oldpt.append(alt.parser_tree)
        alternatives.parser_tree = parsing.Alt(*tuple(oldpt))
    return True


@meta.hook(EBNF, "EBNF.add_char")
def add_char(self, sequence, c):
    """Add a read_char primitive"""
    sequence.parser_tree = parsing.Call(parsing.Parser.read_char,
                                        self.value(c).strip("'"))
    return True


@meta.hook(EBNF, "EBNF.add_text")
def add_text(self, sequence, txt):
    """Add a read_text primitive"""
    sequence.parser_tree = parsing.Call(parsing.Parser.read_text,
                                        self.value(txt).strip('"'))
    return True


@meta.hook(EBNF, "EBNF.add_range")
def add_range(self, sequence, begin, end):
    """Add a read_range primitive"""
    sequence.parser_tree = parsing.Call(parsing.Parser.read_range,
                                        self.value(begin).strip("'"),
                                        self.value(end).strip("'"))
    return True


@meta.hook(EBNF, "EBNF.add_rpt")
def add_rpt(self, sequence, mod, pt):
    """Add a repeater to the previous sequence"""
    modstr = self.value(mod)
    if modstr == '!!':
        error.throw("Cannot repeat a lookahead rule", self)
    if modstr == '!':
        error.throw("Cannot repeat a negated rule", self)
    oldnode = sequence
    sequence.parser_tree = pt.functor(oldnode.parser_tree)
    return True


@meta.hook(EBNF, "EBNF.add_capture")
def add_capture(self, sequence, cpt):
    """Create a tree.Capture"""
    cpt_value = self.value(cpt)
    sequence.parser_tree = parsing.Capture(cpt_value, sequence.parser_tree)
    return True


@meta.hook(EBNF, "EBNF.add_bind")
def add_bind(self, sequence, cpt):
    """Create a tree.Bind"""
    cpt_value = self.value(cpt)
    sequence.parser_tree = parsing.Bind(cpt_value, sequence.parser_tree)
    return True


@meta.hook(EBNF, "EBNF.add_subsequence")
def add_subsequence(self, sequence, subsequence):
    """Add a subsequence into a sequence"""
    sequence.parser_tree = subsequence.parser_tree
    return True


@meta.hook(EBNF, "EBNF.add_optional")
def add_optional(self, repeat):
    """Create a tree.RepOptional"""
    repeat.functor = parsing.RepOptional
    return True


@meta.hook(EBNF, "EBNF.add_0N")
def add_0N(self, repeat):
    """Create a tree.Rep0N"""
    repeat.functor = parsing.Rep0N
    return True


@meta.hook(EBNF, "EBNF.add_1N")
def add_1N(self, repeat):
    """Create a tree.Rep1N"""
    repeat.functor = parsing.Rep1N
    return True


@meta.hook(EBNF, "EBNF.add_hook")
def add_hook(self, sequence, h):
    """Create a tree.Hook"""
    sequence.parser_tree = parsing.Hook(h.name, h.listparam)
    return True


@meta.hook(EBNF, "EBNF.param_num")
def param_num(self, param, n):
    """Parse a int in parameter list"""
    param.pair = (int(self.value(n)), int)
    return True


@meta.hook(EBNF, "EBNF.param_str")
def param_str(self, param, s):
    """Parse a str in parameter list"""
    param.pair = (self.value(s).strip('"'), str)
    return True


@meta.hook(EBNF, "EBNF.param_char")
def param_char(self, param, c):
    """Parse a char in parameter list"""
    param.pair = (self.value(c).strip("'"), str)
    return True


@meta.hook(EBNF, "EBNF.param_id")
def param_id(self, param, i):
    """Parse a node name in parameter list"""
    param.pair = (self.value(i), parsing.Node)
    return True


@meta.hook(EBNF, "EBNF.hook_name")
def hook_name(self, hook, n):
    """Parse a hook name"""
    hook.name = self.value(n)
    hook.listparam = []
    return True


@meta.hook(EBNF, "EBNF.hook_param")
def hook_param(self, hook, p):
    """Parse a hook parameter"""
    hook.listparam.append(p.pair)
    return True


@meta.hook(EBNF, "EBNF.add_directive")
def add_directive(self, sequence, d, s):
    """Add a directive in the sequence"""
    if d.name in meta._directives:
        the_class = meta._directives[d.name]
        sequence.parser_tree = parsing.Directive(the_class(), d.listparam,
                                                 s.parser_tree)
    elif d.name in meta._decorators:
        the_class = meta._decorators[d.name]
        sequence.parser_tree = parsing.Decorator(the_class, d.listparam,
                                                 s.parser_tree)
    else:
        raise TypeError("Unkown directive or decorator %s" % d.name)
    return True
