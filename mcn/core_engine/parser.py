"""
MCN Parser — converts a token stream into a typed AST.

Key improvements over v1:
  - Produces proper dataclass nodes (ast_nodes.py) instead of raw dicts
  - Uses INDENT / DEDENT tokens for block parsing — no heuristics, no
    hardcoded function names, no brace-depth counting
  - Every ParseError carries the offending token's line + col
  - Proper lexical scope: function bodies are delimited by INDENT/DEDENT,
    same as if/else/for/while/try/catch blocks
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .lexer import Token, TT, KEYWORDS
from . import ast_nodes as ast

# Token types that may appear as unquoted object literal keys
_KEYWORD_TYPES = frozenset(KEYWORDS.values())


# ── Errors ─────────────────────────────────────────────────────────────────────

class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(
            f"[{token.line}:{token.col}] ParseError: {message} "
            f"(got {token.type.name} {token.value!r})"
        )
        self.token = token


class ParseErrors(ParseError):
    """Raised at the end of parse() when one or more statements failed to parse.

    The parser recovers after each error so that every problem in the file is
    reported at once; ``errors`` holds the individual messages.
    """
    def __init__(self, errors: List[str], token: Token):
        Exception.__init__(self, "\n".join(errors))
        self.token  = token
        self.errors = errors


# ── Parser ─────────────────────────────────────────────────────────────────────

# Built-in names that can be called in statement position without parentheses:
#   log "hello"   →  log("hello")
_STATEMENT_STYLE_BUILTINS = {
    "log", "echo", "trigger", "query", "workflow", "ai",
    "await", "env", "read_file", "write_file", "append_file", "fetch",
    "device", "agent", "pipeline", "natural", "train", "predict", "preprocess", "translate"
}


class Parser:
    """
    Recursive-descent parser.

    Token stream rules assumed:
      - Blank / comment-only lines produce no tokens at all.
      - Each non-blank line ends with NEWLINE.
      - Indentation changes produce INDENT before the first token of the deeper
        block and DEDENT after the last token of that block.
    """

    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos    = 0

    # Soft keywords: domain words (task, test, state, tool, step, ...) that only
    # mean something at the start of a declaration.  Everywhere a *name* is
    # expected they are ordinary identifiers:  for task in tasks,
    # var state = ..., function f(test), task.done = true.
    _HARD_KEYWORDS = {
        TT.VAR, TT.IF, TT.ELSE, TT.FOR, TT.IN, TT.WHILE, TT.FUNCTION, TT.TRY,
        TT.CATCH, TT.FINALLY, TT.THROW, TT.RETURN, TT.AND, TT.OR, TT.NOT,
        TT.BREAK, TT.CONTINUE, TT.USE, TT.AWAIT,
    }
    _SOFT_KEYWORDS = frozenset(set(KEYWORDS.values()) - _HARD_KEYWORDS)

    def _soften(self) -> None:
        """If the current token is a soft keyword, re-tag it as an identifier."""
        tok = self._current()
        if tok.type in self._SOFT_KEYWORDS:
            self._tokens[self._pos] = Token(TT.IDENTIFIER, tok.value, tok.line, tok.col)

    def _name(self, message: str) -> Token:
        """Consume a name (identifier or soft keyword)."""
        self._soften()
        return self._consume(TT.IDENTIFIER, message)

    _CALLABLE_DECL_KEYWORDS = {
        TT.AGENT, TT.PIPELINE, TT.WORKFLOW, TT.SERVICE, TT.CONTRACT,
        TT.PROMPT, TT.MCP, TT.COMPONENT, TT.APP,
    }

    # ── Entry point ────────────────────────────────────────────────────────────

    def parse(self) -> ast.Program:
        tok  = self._current()
        body: List[ast.Stmt] = []
        self.errors: List[str] = []          # collected parse errors
        first_bad: Optional[Token] = None
        while not self._at_end():
            self._skip_newlines()
            if self._at_end():
                break
            if self.errors and self._check(TT.DEDENT):
                # Leftover block ends from recovering inside a nested block —
                # not a new problem, so don't report it.
                self._advance()
                continue
            try:
                stmt = self._statement()
                if stmt is not None:
                    body.append(stmt)
            except ParseError as e:
                if first_bad is None:
                    first_bad = e.token
                self.errors.append(str(e))
                self._synchronize()          # skip to next safe statement boundary
        if self.errors:
            # Never silently drop code: a statement that failed to parse would
            # otherwise just vanish (e.g. a whole function definition).
            raise ParseErrors(self.errors, first_bad)
        return ast.Program(body=body, line=tok.line, col=tok.col)

    def _synchronize(self) -> None:
        """Advance past the current bad token(s) to the next top-level statement.

        Strategy: consume tokens until we see a NEWLINE at indent depth 0, or
        one of the statement-starting keywords.  This prevents a single syntax
        error from cascading into dozens of confusing follow-on errors.
        """
        _STMT_STARTERS = {
            TT.VAR, TT.FUNCTION, TT.IF, TT.FOR, TT.WHILE, TT.RETURN,
            TT.TRY, TT.THROW, TT.USE, TT.PIPELINE, TT.SERVICE,
            TT.WORKFLOW, TT.CONTRACT, TT.PROMPT, TT.AGENT, TT.MCP,
            TT.TEST, TT.COMPONENT, TT.APP, TT.TASK,
        }
        depth = 0
        while not self._at_end():
            tok = self._current()
            if tok.type == TT.INDENT:
                depth += 1
                self._advance()
            elif tok.type == TT.DEDENT:
                depth = max(0, depth - 1)
                self._advance()
                if depth == 0:
                    return
            elif tok.type == TT.NEWLINE:
                self._advance()
                # An indented block right after the bad line belongs to the
                # failed statement (e.g. a broken `if`) — skip it too, instead
                # of reporting a confusing follow-on error.
                if depth == 0 and not self._check(TT.INDENT):
                    return
            elif depth == 0 and tok.type in _STMT_STARTERS:
                return
            else:
                self._advance()

    # ── Statement dispatch ─────────────────────────────────────────────────────

    def _statement(self) -> Optional[ast.Stmt]:
        tok = self._current()
        # `task = ...`, `task.done = true`, `test += 1`, `tool[0] = x`: a soft
        # keyword followed by one of these is a variable, never a declaration.
        if (tok.type in self._SOFT_KEYWORDS and self._pos + 1 < len(self._tokens) and
                self._tokens[self._pos + 1].type in (
                    TT.ASSIGN, TT.DOT, TT.LBRACKET, TT.SAFE_DOT, TT.PLUS_ASSIGN,
                    TT.MINUS_ASSIGN, TT.STAR_ASSIGN, TT.SLASH_ASSIGN, TT.PERCENT_ASSIGN)):
            self._soften()
            tok = self._current()
        # Declaration keywords used as function calls in statement position,
        # e.g. `agent("create", ...)` / `pipeline("run", ...)` from the v3
        # packages.  A declaration always has a name after the keyword, never '('.
        if (tok.type in self._CALLABLE_DECL_KEYWORDS and
                self._pos + 1 < len(self._tokens) and
                self._tokens[self._pos + 1].type == TT.LPAREN):
            return self._expr_stmt()
        if tok.type == TT.VAR:      return self._var_decl()
        if tok.type == TT.IF:       return self._if_stmt()
        if tok.type == TT.FOR:      return self._for_stmt()
        if tok.type == TT.WHILE:    return self._while_stmt()
        if tok.type == TT.TRY:      return self._try_stmt()
        if tok.type == TT.THROW:    return self._throw_stmt()
        if tok.type == TT.TASK:     return self._task_stmt()
        if tok.type == TT.USE:      return self._use_stmt()
        if tok.type == TT.FUNCTION: return self._function_decl()
        if tok.type == TT.RETURN:   return self._return_stmt()
        if (tok.type == TT.IDENTIFIER and tok.value == "auth" and
                self._pos + 1 < len(self._tokens) and
                self._tokens[self._pos + 1].type == TT.NEWLINE):
            return self._auth_decl()
        # 2030 language primitives
        if tok.type == TT.PIPELINE: return self._pipeline_decl()
        if tok.type == TT.SERVICE:  return self._service_decl()
        if tok.type == TT.WORKFLOW: return self._workflow_decl()
        if tok.type == TT.CONTRACT: return self._contract_decl()
        # AI / intelligent primitives
        if tok.type == TT.PROMPT:   return self._prompt_decl()
        if tok.type == TT.AGENT:    return self._agent_decl()
        if tok.type == TT.MCP:      return self._mcp_decl()
        # Loop control
        if tok.type == TT.BREAK:    return self._break_stmt()
        if tok.type == TT.CONTINUE: return self._continue_stmt()
        # Test framework
        if tok.type == TT.TEST:     return self._test_decl()
        if tok.type == TT.ASSERT:   return self._assert_stmt()
        # UI / Frontend primitives
        if tok.type == TT.COMPONENT: return self._component_decl()
        if tok.type == TT.APP:       return self._app_decl()
        if tok.type == TT.INCLUDE:   return self._include_stmt()
        if tok.type == TT.ON:        return self._on_statement()
        # Bare assignment variants: name = expr, name += expr, name -= expr ...
        _COMPOUND_OPS = {
            TT.PLUS_ASSIGN: "+", TT.MINUS_ASSIGN: "-",
            TT.STAR_ASSIGN: "*", TT.SLASH_ASSIGN: "/",
            TT.PERCENT_ASSIGN: "%",
        }
        if (tok.type == TT.IDENTIFIER and
                self._pos + 1 < len(self._tokens)):
            next_tt = self._tokens[self._pos + 1].type
            if next_tt == TT.ASSIGN:
                return self._assign_stmt()
            if next_tt in _COMPOUND_OPS:
                return self._compound_assign_stmt(_COMPOUND_OPS[next_tt])
        return self._expr_stmt()

    # ── Statement parsers ──────────────────────────────────────────────────────

    def _var_decl(self) -> ast.VarDecl:
        tok      = self._advance()            # consume VAR
        name_tok = self._name("Expected variable name after 'var'")
        # optional type hint: var x: int = 5
        type_hint: Optional[str] = None
        if self._match(TT.COLON):
            type_tok  = self._consume(TT.IDENTIFIER, "Expected type name after ':'")
            type_hint = type_tok.value
        self._consume(TT.ASSIGN, "Expected '=' after variable name")
        value    = self._expression()
        self._consume_end()
        return ast.VarDecl(name=name_tok.value, value=value, type_hint=type_hint,
                           line=tok.line, col=tok.col)

    def _assign_stmt(self) -> ast.AssignStmt:
        name_tok = self._advance()            # consume IDENTIFIER
        self._advance()                       # consume ASSIGN '='
        value    = self._expression()
        self._consume_end()
        return ast.AssignStmt(name=name_tok.value, value=value,
                              line=name_tok.line, col=name_tok.col)

    def _compound_assign_stmt(self, op: str) -> ast.CompoundAssignStmt:
        """x += expr, x -= expr, x *= expr, x /= expr, x %= expr"""
        name_tok = self._advance()   # consume IDENTIFIER
        self._advance()              # consume +=/-=/etc.
        value    = self._expression()
        self._consume_end()
        return ast.CompoundAssignStmt(name=name_tok.value, op=op, value=value,
                                      line=name_tok.line, col=name_tok.col)

    def _if_stmt(self) -> ast.IfStmt:
        tok       = self._advance()           # consume IF
        condition = self._expression()
        self._consume_end()
        then_body = self._block()
        else_body: List[ast.Stmt] = []
        # Curly-brace style allows `}` and `else {` on separate lines.
        if self._pos > 0 and self._tokens[self._pos - 1].type == TT.RBRACE:
            save = self._pos
            self._skip_newlines()
            if not self._check(TT.ELSE):
                self._pos = save
        if self._check(TT.ELSE):
            self._advance()                   # consume ELSE
            if self._check(TT.IF):
                # else if → wrap the nested if as the else_body (one-item list)
                else_body = [self._if_stmt()]
            else:
                self._consume_end()
                else_body = self._block()
        return ast.IfStmt(condition=condition, then_body=then_body,
                          else_body=else_body, line=tok.line, col=tok.col)

    def _for_stmt(self) -> ast.ForStmt:
        tok     = self._advance()             # consume FOR
        first   = self._name("Expected loop variable after 'for'")

        # for i, val in list  →  index_var=i, variable=val
        index_var: Optional[str] = None
        if self._check(TT.COMMA):
            self._advance()                   # consume ','
            second    = self._name("Expected value variable after ','")
            index_var = first.value
            var_name  = second.value
        else:
            var_name  = first.value

        self._consume(TT.IN, "Expected 'in' after loop variable")
        iterable = self._expression()
        self._consume_end()
        body = self._block()
        return ast.ForStmt(variable=var_name, index_var=index_var,
                           iterable=iterable, body=body,
                           line=tok.line, col=tok.col)

    def _while_stmt(self) -> ast.WhileStmt:
        tok       = self._advance()           # consume WHILE
        condition = self._expression()
        self._consume_end()
        body = self._block()
        return ast.WhileStmt(condition=condition, body=body,
                             line=tok.line, col=tok.col)

    def _try_stmt(self) -> ast.TryStmt:
        tok      = self._advance()            # consume TRY
        self._consume_end()
        try_body     = self._block()
        catch_var:    Optional[str]   = None
        catch_body:   List[ast.Stmt]  = []
        finally_body: List[ast.Stmt]  = []

        if self._check(TT.CATCH):
            self._advance()                   # consume CATCH
            # Optional binding: catch e  or  catch (e)
            if self._check(TT.IDENTIFIER):
                catch_var = self._advance().value
            elif self._check(TT.LPAREN):
                self._advance()               # consume (
                catch_var = self._name("Expected variable name").value
                self._consume(TT.RPAREN, "Expected ')' after catch variable")
            self._consume_end()
            catch_body = self._block()

        if self._check(TT.FINALLY):
            self._advance()                   # consume FINALLY
            self._consume_end()
            finally_body = self._block()

        return ast.TryStmt(try_body=try_body, catch_var=catch_var,
                           catch_body=catch_body, finally_body=finally_body,
                           line=tok.line, col=tok.col)

    def _throw_stmt(self) -> ast.ThrowStmt:
        tok     = self._advance()             # consume THROW
        message = self._expression()
        self._consume_end()
        return ast.ThrowStmt(message=message, line=tok.line, col=tok.col)

    def _task_stmt(self) -> ast.TaskStmt:
        tok  = self._advance()                # consume TASK
        name = self._expression()
        func = self._expression()
        args: List[ast.Expr] = []
        while not self._at_eol():
            args.append(self._expression())
        self._consume_end()
        return ast.TaskStmt(name=name, function=func, arguments=args,
                            line=tok.line, col=tok.col)

    def _use_stmt(self) -> ast.UseStmt:
        tok     = self._advance()             # consume USE
        package = self._expression()
        self._consume_end()
        return ast.UseStmt(package=package, line=tok.line, col=tok.col)

    def _parse_params(self) -> tuple:
        """
        Parse a parenthesised parameter list with optional type hints and defaults.
        Caller must have already consumed the opening '('.
        Returns (params: List[str], defaults: dict, param_types: dict).
        Supports: foo(x: int, y: str = "hi")
        """
        params:      List[str] = []
        defaults:    dict      = {}
        param_types: dict      = {}

        def _one_param():
            p = self._name("Expected parameter name").value
            params.append(p)
            # optional type hint: param: type
            if self._match(TT.COLON):
                type_tok = self._consume(TT.IDENTIFIER, "Expected type name after ':'")
                param_types[p] = type_tok.value
            if self._match(TT.ASSIGN):
                defaults[p] = self._expression()

        if not self._check(TT.RPAREN):
            _one_param()
            while self._match(TT.COMMA):
                _one_param()
        return params, defaults, param_types

    def _function_decl(self) -> ast.FunctionDecl:
        tok      = self._advance()            # consume FUNCTION
        name_tok = self._name("Expected function name")
        self._consume(TT.LPAREN, "Expected '(' after function name")
        params, defaults, param_types = self._parse_params()
        self._consume(TT.RPAREN, "Expected ')' after parameters")
        # optional return type: function foo(x): bool
        return_type: Optional[str] = None
        if self._match(TT.COLON):
            rt = self._consume(TT.IDENTIFIER, "Expected return type after ':'")
            return_type = rt.value
        self._consume_end()
        body = self._block()
        return ast.FunctionDecl(name=name_tok.value, params=params,
                                defaults=defaults, body=body,
                                param_types=param_types, return_type=return_type,
                                line=tok.line, col=tok.col)

    def _return_stmt(self) -> ast.ReturnStmt:
        tok   = self._advance()               # consume RETURN
        value: Optional[ast.Expr] = None
        if not self._at_eol():
            value = self._expression()
        self._consume_end()
        return ast.ReturnStmt(value=value, line=tok.line, col=tok.col)

    def _expr_stmt(self) -> ast.ExprStmt:
        tok = self._current()

        # Statement-style built-in calls: log "msg", echo "msg", etc.
        # If the identifier is immediately followed by '(' it's a normal function
        # call (e.g. query("SQL", params)) so fall through to expression parsing.
        next_is_paren = (self._pos + 1 < len(self._tokens) and
                         self._tokens[self._pos + 1].type == TT.LPAREN)
        if (tok.type == TT.IDENTIFIER and tok.value in _STATEMENT_STYLE_BUILTINS
                and not next_is_paren):
            func_tok = self._advance()
            args: List[ast.Expr] = []
            while not self._at_eol():
                args.append(self._expression())
                self._match(TT.COMMA)
            self._consume_end()
            callee = ast.Variable(name=func_tok.value,
                                  line=func_tok.line, col=func_tok.col)
            call   = ast.Call(callee=callee, arguments=args,
                              line=func_tok.line, col=func_tok.col)
            return ast.ExprStmt(expression=call, line=func_tok.line, col=func_tok.col)

        expr = self._expression()

        # Property/index assignment: obj.key = val  or  arr[i] = val
        if self._check(TT.ASSIGN):
            self._advance()           # consume '='
            value = self._expression()
            self._consume_end()
            if isinstance(expr, ast.Property):
                return ast.PropertyAssignStmt(
                    object=expr.object, prop=expr.name, value=value,
                    line=expr.line, col=expr.col)
            if isinstance(expr, ast.Index):
                return ast.IndexAssignStmt(
                    object=expr.object, index=expr.index, value=value,
                    line=expr.line, col=expr.col)
            # Fall through — treat as error or re-wrap (shouldn't happen after
            # the IDENTIFIER fast-path above handled simple name = val)

        self._consume_end()
        return ast.ExprStmt(expression=expr, line=tok.line, col=tok.col)

    # ── Block parsing (INDENT / DEDENT) ────────────────────────────────────────

    def _block(self) -> List[ast.Stmt]:
        """
        Parse an indented block or a curly-braced block.
        """
        self._skip_newlines()
        if self._check(TT.LBRACE):
            self._advance()  # consume '{'
            self._skip_newlines()

            has_indent = False
            if self._check(TT.INDENT):
                self._advance()
                has_indent = True

            stmts: List[ast.Stmt] = []
            while not self._at_end():
                self._skip_newlines()
                if has_indent and self._check(TT.DEDENT):
                    self._advance()
                    has_indent = False
                    self._skip_newlines()
                if self._check(TT.RBRACE) or self._at_end():
                    break
                stmt = self._statement()
                if stmt is not None:
                    stmts.append(stmt)

            self._consume(TT.RBRACE, "Expected '}' at the end of block")
            return stmts

        if not self._check(TT.INDENT):
            return []                         # empty block — tolerated

        self._advance()                       # consume INDENT
        stmts: List[ast.Stmt] = []

        while not self._at_end() and not self._check(TT.DEDENT):
            self._skip_newlines()
            if self._check(TT.DEDENT) or self._at_end():
                break
            stmt = self._statement()
            if stmt is not None:
                stmts.append(stmt)

        if self._check(TT.DEDENT):
            self._advance()                   # consume DEDENT

        return stmts

    # ── Expression grammar (Pratt-style precedence) ────────────────────────────

    def _expression(self) -> ast.Expr:
        """Top-level expression. Handles ternary: condition ? then : else"""
        expr = self._or()
        if self._check(TT.QUESTION):
            q        = self._advance()        # consume '?'
            then_ex  = self._expression()
            self._consume(TT.COLON, "Expected ':' in ternary expression")
            else_ex  = self._expression()     # right-associative: a ? b : c ? d : e
            return ast.TernaryExpr(condition=expr, then_expr=then_ex, else_expr=else_ex,
                                   line=q.line, col=q.col)
        return expr

    def _or(self) -> ast.Expr:
        left = self._and()
        while self._check(TT.OR):
            op  = self._advance()
            right = self._and()
            left = ast.Binary(left=left, operator="or", right=right,
                              line=op.line, col=op.col)
        return left

    def _and(self) -> ast.Expr:
        left = self._equality()
        while self._check(TT.AND):
            op    = self._advance()
            right = self._equality()
            left  = ast.Binary(left=left, operator="and", right=right,
                               line=op.line, col=op.col)
        return left

    def _equality(self) -> ast.Expr:
        left = self._comparison()
        while self._current().type in (TT.EQ, TT.NEQ):
            op    = self._advance()
            right = self._comparison()
            left  = ast.Binary(left=left, operator=op.value, right=right,
                               line=op.line, col=op.col)
        return left

    def _comparison(self) -> ast.Expr:
        left = self._term()
        while self._current().type in (TT.GT, TT.GTE, TT.LT, TT.LTE):
            op    = self._advance()
            right = self._term()
            left  = ast.Binary(left=left, operator=op.value, right=right,
                               line=op.line, col=op.col)
        return left

    def _term(self) -> ast.Expr:
        left = self._factor()
        while self._current().type in (TT.PLUS, TT.MINUS):
            op    = self._advance()
            right = self._factor()
            left  = ast.Binary(left=left, operator=op.value, right=right,
                               line=op.line, col=op.col)
        return left

    def _factor(self) -> ast.Expr:
        left = self._unary()
        while self._current().type in (TT.STAR, TT.SLASH, TT.PERCENT):
            op    = self._advance()
            right = self._unary()
            left  = ast.Binary(left=left, operator=op.value, right=right,
                               line=op.line, col=op.col)
        return left

    def _unary(self) -> ast.Expr:
        if self._current().type in (TT.NOT, TT.MINUS):
            op      = self._advance()
            operand = self._unary()
            return ast.Unary(operator=op.value, operand=operand,
                             line=op.line, col=op.col)
        return self._call()

    def _call(self) -> ast.Expr:
        expr = self._primary()
        while True:
            if self._match(TT.LPAREN):
                args: List[ast.Expr] = []
                if not self._check(TT.RPAREN):
                    args.append(self._expression())
                    while self._match(TT.COMMA):
                        args.append(self._expression())
                close = self._consume(TT.RPAREN, "Expected ')' after arguments")
                expr  = ast.Call(callee=expr, arguments=args,
                                 line=close.line, col=close.col)
            elif self._match(TT.LBRACKET):
                index = self._expression()
                close = self._consume(TT.RBRACKET, "Expected ']' after index")
                expr  = ast.Index(object=expr, index=index,
                                  line=close.line, col=close.col)
            elif self._match(TT.DOT):
                tok = self._current()
                if tok.type == TT.IDENTIFIER or tok.type in _KEYWORD_TYPES:
                    self._advance()
                    prop = tok
                else:
                    raise ParseError("Expected property name after '.'", tok)
                expr = ast.Property(object=expr, name=prop.value, safe=False,
                                    line=prop.line, col=prop.col)
            elif self._match(TT.SAFE_DOT):
                # obj?.name — returns None if obj is None
                tok = self._current()
                if tok.type == TT.IDENTIFIER or tok.type in _KEYWORD_TYPES:
                    self._advance()
                    prop = tok
                else:
                    raise ParseError("Expected property name after '?.'", tok)
                expr = ast.Property(object=expr, name=prop.value, safe=True,
                                    line=prop.line, col=prop.col)
            else:
                break
        return expr

    def _primary(self) -> ast.Expr:
        tok = self._current()

        if self._match(TT.NUMBER):
            v = tok.value
            return ast.Literal(
                value=float(v) if "." in v else int(v),
                line=tok.line, col=tok.col,
            )

        if self._match(TT.STRING):
            return ast.Literal(value=tok.value, line=tok.line, col=tok.col)

        _IDENTIFIER_LIKE_KEYWORDS = self._SOFT_KEYWORDS | {TT.USE}
        if self._check(TT.IDENTIFIER) or self._current().type in _IDENTIFIER_LIKE_KEYWORDS:
            tok = self._advance()
            # Arrow function: single param shorthand   x => expr
            if self._check(TT.ARROW):
                self._advance()              # consume '=>'
                body = self._expression()
                return ast.ArrowFunc(params=[tok.value], body=body,
                                     line=tok.line, col=tok.col)
            return ast.Variable(name=tok.value, line=tok.line, col=tok.col)

        # await keyword used as an expression
        if self._match(TT.AWAIT):
            args: List[ast.Expr] = []
            while not self._at_eol():
                args.append(self._expression())
            callee = ast.Variable(name="await", line=tok.line, col=tok.col)
            return ast.Call(callee=callee, arguments=args,
                            line=tok.line, col=tok.col)

        # Parenthesised expression or tuple: (expr) or (a, b, c) or (a,)
        if self._match(TT.LPAREN):
            elements: List[ast.Expr] = []
            trailing_comma = False
            if not self._check(TT.RPAREN):
                elements.append(self._expression())
                while self._match(TT.COMMA):
                    if self._check(TT.RPAREN):   # trailing comma
                        trailing_comma = True
                        break
                    elements.append(self._expression())
            self._consume(TT.RPAREN, "Expected ')' after expression")
            # Arrow function: (x, y) => expr  or  (x) => expr
            if self._check(TT.ARROW):
                self._advance()              # consume '=>'
                # params must all be plain identifiers
                params = []
                for el in elements:
                    if isinstance(el, ast.Variable):
                        params.append(el.name)
                    else:
                        raise ParseError("Arrow function params must be identifiers", tok)
                body = self._expression()
                return ast.ArrowFunc(params=params, body=body,
                                     line=tok.line, col=tok.col)

            # (x,) or (x, y) → tuple; (x) without trailing comma → grouped expr
            if len(elements) == 1 and not trailing_comma:
                return elements[0]
            return ast.MCNTuple(elements=elements, line=tok.line, col=tok.col)

        # Array literal: [a, b, c] or [a, b,] — may span multiple lines
        if self._match(TT.LBRACKET):
            elements = []
            self._skip_whitespace()
            if not self._check(TT.RBRACKET):
                elements.append(self._expression())
                self._skip_whitespace()
                while self._match(TT.COMMA):
                    self._skip_whitespace()
                    if self._check(TT.RBRACKET):  # trailing comma
                        break
                    elements.append(self._expression())
                    self._skip_whitespace()
            self._consume(TT.RBRACKET, "Expected ']' after array elements")
            return ast.Array(elements=elements, line=tok.line, col=tok.col)

        # Object literal: {key: value, ...} — may span multiple lines
        # Keys may be identifiers, string literals, OR reserved keywords used
        # as property names (e.g. {task: "send_email", type: "job"}).
        if self._match(TT.LBRACE):
            props = []
            self._skip_whitespace()
            if not self._check(TT.RBRACE):
                key = self._object_key()
                self._consume(TT.COLON, "Expected ':' after object key")
                val = self._expression()
                props.append((key, val))
                self._skip_whitespace()
                while self._match(TT.COMMA):
                    self._skip_whitespace()
                    if self._check(TT.RBRACE):   # trailing comma
                        break
                    key = self._object_key()
                    self._consume(TT.COLON, "Expected ':' after object key")
                    val = self._expression()
                    props.append((key, val))
                    self._skip_whitespace()
            self._consume(TT.RBRACE, "Expected '}' after object properties")
            return ast.MCNObject(properties=props, line=tok.line, col=tok.col)

        raise ParseError("Unexpected token", tok)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _object_key(self) -> ast.Expr:
        """
        Parse an object literal key.  Accepts:
          - identifiers:       {name: ...}
          - string literals:   {"key": ...}
          - any keyword token: {task: ..., type: ..., service: ...}
        Returns a Literal (string) or Variable node.
        """
        t = self._current()
        if t.type == TT.IDENTIFIER:
            self._advance()
            return ast.Variable(name=t.value, line=t.line, col=t.col)
        if t.type == TT.STRING:
            self._advance()
            return ast.Literal(value=t.value, line=t.line, col=t.col)
        if t.type in _KEYWORD_TYPES:
            # Treat keyword as a plain string key so {task: x, type: y} works
            self._advance()
            return ast.Literal(value=t.value, line=t.line, col=t.col)
        raise ParseError("Expected object key (identifier or string)", t)

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if not self._at_end():
            self._pos += 1
        return tok

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _check(self, tt: TT) -> bool:
        return self._current().type == tt

    def _match(self, tt: TT) -> bool:
        if self._check(tt):
            self._advance()
            return True
        return False

    def _consume(self, tt: TT, message: str) -> Token:
        if self._check(tt):
            return self._advance()
        raise ParseError(message, self._current())

    def _consume_end(self):
        """Consume a trailing NEWLINE if present; silently accept EOF / DEDENT."""
        self._skip_newlines()

    def _skip_newlines(self):
        while self._check(TT.NEWLINE):
            self._advance()

    def _skip_whitespace(self):
        """Skip NEWLINE, INDENT, and DEDENT — used inside multi-line collections."""
        while self._current().type in (TT.NEWLINE, TT.INDENT, TT.DEDENT):
            self._advance()

    def _at_end(self) -> bool:
        return self._current().type == TT.EOF

    def _at_eol(self) -> bool:
        """True when we are at a logical end-of-line (can't parse more on this line)."""
        return self._current().type in (TT.NEWLINE, TT.EOF, TT.DEDENT)


    # ── 2030 Language Primitive Parsers ────────────────────────────────────────

    def _pipeline_decl(self) -> ast.PipelineDecl:
        """
        pipeline name
            stage stage_name[(params)]
                body
            stage ...
        """
        tok      = self._advance()   # consume PIPELINE
        name_tok = self._consume(TT.IDENTIFIER, "Expected pipeline name")
        self._consume_end()

        stages: List[ast.StageDecl] = []
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()          # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                if self._check(TT.STAGE):
                    stages.append(self._stage_decl())
                else:
                    self._advance()  # skip unexpected token
            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.PipelineDecl(name=name_tok.value, stages=stages,
                                line=tok.line, col=tok.col)

    def _stage_decl(self) -> ast.StageDecl:
        tok      = self._advance()   # consume STAGE
        name_tok = self._consume(TT.IDENTIFIER, "Expected stage name")
        params: List[str] = []
        defaults: dict    = {}
        if self._match(TT.LPAREN):
            params, defaults, _ = self._parse_params()
            self._consume(TT.RPAREN, "Expected ')' after stage parameters")
        self._consume_end()
        body = self._block()
        return ast.StageDecl(name=name_tok.value, params=params, defaults=defaults,
                             body=body, line=tok.line, col=tok.col)

    def _service_decl(self) -> ast.ServiceDecl:
        """
        service name
            port 8080
            endpoint name[(params)]
                body
        """
        tok      = self._advance()   # consume SERVICE
        name_tok = self._consume(TT.IDENTIFIER, "Expected service name")
        self._consume_end()

        port: Optional[int] = None
        endpoints: List[ast.EndpointDecl] = []
        cruds: List[ast.CrudDecl] = []
        triggers: List[ast.TriggerDecl] = []
        jobs: List[ast.JobDecl] = []

        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()          # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                if self._check(TT.PORT):
                    self._advance()  # consume PORT
                    port_tok = self._consume(TT.NUMBER, "Expected port number")
                    port = int(float(port_tok.value))
                    self._consume_end()
                elif self._check(TT.ENDPOINT):
                    endpoints.append(self._endpoint_decl())
                elif self._check(TT.IDENTIFIER) and self._current().value == "crud":
                    cruds.append(self._crud_decl())
                elif self._check(TT.ON):
                    triggers.append(self._trigger_decl())
                elif self._check(TT.IDENTIFIER) and self._current().value == "job":
                    jobs.append(self._job_decl())
                else:
                    raise ParseError("Expected 'port', 'endpoint', 'crud', 'on' or 'job' "
                                     "inside a service", self._current())
            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.ServiceDecl(name=name_tok.value, port=port, endpoints=endpoints,
                               cruds=cruds, triggers=triggers, jobs=jobs,
                               line=tok.line, col=tok.col)

    _TRIGGER_EVENTS = ("create", "update", "delete", "approve", "reject")
    _JOB_UNITS = {"minute": "minute", "minutes": "minute", "hour": "hour", "hours": "hour",
                  "day": "day", "days": "day", "week": "week", "weeks": "week",
                  "monday": "monday", "tuesday": "tuesday", "wednesday": "wednesday",
                  "thursday": "thursday", "friday": "friday", "saturday": "saturday",
                  "sunday": "sunday"}

    def _trigger_decl(self) -> ast.TriggerDecl:
        """on create|update|delete|approve|reject Contract  + indented body"""
        tok = self._advance()                    # consume ON
        ev = self._name("Expected create, update, delete, approve or reject after 'on'")
        if ev.value not in self._TRIGGER_EVENTS:
            raise ParseError(f"Unknown trigger '{ev.value}' (expected create, update, "
                             "delete, approve or reject)", ev)
        contract = self._consume(TT.IDENTIFIER, f"Expected a contract name, e.g. on {ev.value} Lead").value
        self._consume_end()
        body = self._block()
        return ast.TriggerDecl(event=ev.value, contract=contract, body=body,
                               line=tok.line, col=tok.col)

    def _job_decl(self) -> ast.JobDecl:
        """job name every [N] minute(s)|hour(s)|day(s)|week(s)|monday… [at "HH:MM"]"""
        tok = self._advance()                    # consume `job`
        name = self._name("Expected a job name, e.g. job daily_digest every day")
        every_tok = self._name("Expected 'every' after the job name")
        if every_tok.value != "every":
            raise ParseError("Expected 'every', e.g. job sync every 15 minutes", every_tok)
        every = 1
        if self._check(TT.NUMBER):
            every = int(float(self._advance().value))
        unit_tok = self._name("Expected minutes, hours, day(s), week(s) or a weekday")
        unit = self._JOB_UNITS.get(unit_tok.value)
        if unit is None or every < 1:
            raise ParseError(f"Unknown schedule '{unit_tok.value}' (use minutes, hours, days, "
                             "weeks or monday … sunday)", unit_tok)
        at = ""
        if self._check(TT.IDENTIFIER) and self._current().value == "at":
            self._advance()
            at_tok = self._consume(TT.STRING, 'Expected a time like "09:00"')
            import re as _re
            if not _re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", at_tok.value):
                raise ParseError('Time must look like "09:00" (24-hour)', at_tok)
            if unit in ("minute", "hour"):
                raise ParseError("'at' only works with days, weeks or weekdays", at_tok)
            at = at_tok.value
        self._consume_end()
        body = self._block()
        return ast.JobDecl(name=name.value, every=every, unit=unit, at=at, body=body,
                           line=tok.line, col=tok.col)

    def _endpoint_decl(self) -> ast.EndpointDecl:
        tok      = self._advance()   # consume ENDPOINT
        name_tok = self._consume(TT.IDENTIFIER, "Expected endpoint name")
        params: List[str] = []
        defaults: dict    = {}
        if self._match(TT.LPAREN):
            params, defaults, _ = self._parse_params()
            self._consume(TT.RPAREN, "Expected ')' after endpoint parameters")
        allow: List[str] = []
        public = False
        if self._check(TT.IDENTIFIER) and self._current().value == "allow":
            self._advance()
            allow = self._name_list("Expected a role name after 'allow'")
        elif self._check(TT.IDENTIFIER) and self._current().value == "public":
            self._advance()
            public = True
        self._consume_end()
        body = self._block()
        return ast.EndpointDecl(name=name_tok.value, params=params, defaults=defaults,
                                body=body, allow=allow, public=public,
                                line=tok.line, col=tok.col)

    def _name_list(self, message: str) -> List[str]:
        """a, b, c  — one or more names separated by commas."""
        names = [self._name(message).value]
        while self._match(TT.COMMA):
            names.append(self._name(message).value)
        return names

    def _auth_decl(self) -> ast.AuthDecl:
        """
        auth
            roles         admin, sales, viewer
            session_hours 12
        """
        tok = self._advance()                    # consume `auth`
        self._consume_end()
        roles: List[str] = []
        hours = 12
        sso: Optional[ast.SSODecl] = None
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                opt = self._name("Expected an auth option (roles or session_hours)")
                if opt.value == "roles":
                    roles = self._name_list("Expected a role name")
                elif opt.value == "session_hours":
                    hours = int(float(self._consume(TT.NUMBER, "Expected a number of hours").value))
                elif opt.value == "sso":
                    sso = self._sso_decl(opt)
                    continue                     # block consumed its own lines
                else:
                    raise ParseError(f"Unknown auth option '{opt.value}' "
                                     "(expected roles, session_hours or sso)", opt)
                self._consume_end()
            if self._check(TT.DEDENT):
                self._advance()
        if not roles:
            raise ParseError("auth needs a roles line, e.g. roles admin, staff", tok)
        if sso is not None and sso.default_role and sso.default_role not in roles:
            raise ParseError(f"sso default_role '{sso.default_role}' is not one of the roles "
                             f"({', '.join(roles)})", tok)
        return ast.AuthDecl(roles=roles, session_hours=hours, sso=sso,
                            line=tok.line, col=tok.col)

    def _sso_decl(self, tok: Token) -> ast.SSODecl:
        """sso / issuer … / client_id … / client_secret … / allow_domains … / default_role …"""
        self._consume_end()
        d = ast.SSODecl(line=tok.line, col=tok.col)
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                opt = self._name("Expected an sso option")
                if opt.value in ("issuer", "client_id", "client_secret", "label"):
                    setattr(d, opt.value, self._expression())
                elif opt.value == "allow_domains":
                    d.allow_domains = [self._expression()]
                    while self._match(TT.COMMA):
                        d.allow_domains.append(self._expression())
                elif opt.value == "default_role":
                    d.default_role = self._name("Expected a role name").value
                elif opt.value == "auto_create":
                    d.auto_create = self._name("Expected true or false").value == "true"
                else:
                    raise ParseError(f"Unknown sso option '{opt.value}' (expected issuer, "
                                     "client_id, client_secret, allow_domains, default_role, "
                                     "label or auto_create)", opt)
                self._consume_end()
            if self._check(TT.DEDENT):
                self._advance()
        for need in ("issuer", "client_id", "client_secret"):
            if getattr(d, need) is None:
                raise ParseError(f"sso needs '{need}'", tok)
        return d

    def _workflow_decl(self) -> ast.WorkflowDecl:
        """
        workflow name
            step name[(params)]
                body
        """
        tok      = self._advance()   # consume WORKFLOW
        name_tok = self._consume(TT.IDENTIFIER, "Expected workflow name")
        self._consume_end()

        steps: List[ast.StepDecl] = []
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()          # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                if self._check(TT.STEP):
                    steps.append(self._step_decl())
                else:
                    self._advance()
            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.WorkflowDecl(name=name_tok.value, steps=steps,
                                line=tok.line, col=tok.col)

    def _step_decl(self) -> ast.StepDecl:
        tok      = self._advance()   # consume STEP
        name_tok = self._consume(TT.IDENTIFIER, "Expected step name")
        params: List[str] = []
        defaults: dict    = {}
        if self._match(TT.LPAREN):
            params, defaults, _ = self._parse_params()
            self._consume(TT.RPAREN, "Expected ')' after step parameters")
        self._consume_end()
        body = self._block()
        return ast.StepDecl(name=name_tok.value, params=params, defaults=defaults,
                            body=body, line=tok.line, col=tok.col)

    def _contract_decl(self) -> ast.ContractDecl:
        """
        contract name
            field_name: type_name
            ...
        """
        tok      = self._advance()   # consume CONTRACT
        name_tok = self._consume(TT.IDENTIFIER, "Expected contract name")
        self._consume_end()

        fields: List[ast.ContractField] = []
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()          # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                fields.append(self._contract_field())
            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.ContractDecl(name=name_tok.value, fields=fields,
                                line=tok.line, col=tok.col)

    def _contract_field(self) -> ast.ContractField:
        """name: type[?] [unique] [= default]   — type may be choice("a", "b") or ref Contract"""
        name_tok = self._name("Expected field name")
        self._consume(TT.COLON, "Expected ':' after field name")
        type_tok = self._name("Expected type name (str, int, float, bool, "
                              "text, date, datetime, choice(...) or ref Contract)")
        type_name = type_tok.value
        choices: List[str] = []
        ref = ""
        if type_name == "ref":
            ref = self._consume(TT.IDENTIFIER, "Expected a contract name after 'ref', "
                                "e.g. company: ref Company").value
        if type_name == "choice":
            self._consume(TT.LPAREN, "Expected '(' after choice")
            while True:
                choices.append(self._consume(TT.STRING, "Expected a quoted choice value").value)
                if not self._match(TT.COMMA):
                    break
            self._consume(TT.RPAREN, "Expected ')' after choice values")
        optional = bool(self._match(TT.QUESTION))
        unique = False
        default: Optional[ast.Expr] = None
        read_roles: List[str] = []
        write_roles: List[str] = []
        while not self._at_eol():
            if self._check(TT.IDENTIFIER) and self._current().value == "unique":
                self._advance()
                unique = True
            elif self._check(TT.IDENTIFIER) and self._current().value in ("read", "write"):
                which = self._advance().value
                roles = self._name_list(f"Expected a role name after '{which}'")
                (read_roles if which == "read" else write_roles).extend(roles)
            elif self._match(TT.ASSIGN):
                default = self._expression()
            else:
                raise ParseError("Expected 'unique', 'read …', 'write …', '= default' or end "
                                 "of line after the field type", self._current())
        self._consume_end()
        return ast.ContractField(
            name=name_tok.value, type_name=type_name, optional=optional,
            default=default, unique=unique, choices=choices, ref=ref,
            read_roles=read_roles, write_roles=write_roles,
            line=name_tok.line, col=name_tok.col,
        )

    def _crud_decl(self) -> ast.CrudDecl:
        """
        crud Contract
            search    field, field
            sort      field [asc|desc]
            page_size 25
        """
        tok = self._advance()                    # consume `crud`
        contract = self._consume(TT.IDENTIFIER, "Expected contract name after 'crud'").value
        self._consume_end()
        search: List[str] = []
        sort, page_size = "", 25
        allow: Dict[str, List[str]] = {}
        audit = False
        approval: Optional[ast.ApprovalDecl] = None
        csv_import = csv_export = False
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                opt = self._name("Expected a crud option (search, sort or page_size)")
                if opt.value == "search":
                    search.append(self._name("Expected a field name to search").value)
                    while self._match(TT.COMMA):
                        search.append(self._name("Expected a field name to search").value)
                elif opt.value == "sort":
                    sort = self._name("Expected a field name to sort by").value
                    if self._check(TT.IDENTIFIER) and self._current().value in ("asc", "desc"):
                        sort += " " + self._advance().value
                elif opt.value == "page_size":
                    page_size = int(float(self._consume(TT.NUMBER, "Expected a number").value))
                elif opt.value == "audit":
                    audit = True
                elif opt.value == "import":
                    csv_import = True
                elif opt.value == "export":
                    csv_export = True
                elif opt.value == "approval":
                    approval = self._approval_decl(opt)
                    continue                     # block already consumed its lines
                elif opt.value == "allow":
                    # allow read: a, b  |  allow write: a  |  allow delete: a  |  allow a, b
                    actions = ["read", "write", "delete"]
                    if (self._check(TT.IDENTIFIER) and self._current().value in actions and
                            self._pos + 1 < len(self._tokens) and
                            self._tokens[self._pos + 1].type == TT.COLON):
                        actions = [self._advance().value]
                        self._advance()          # ':'
                    roles = self._name_list("Expected a role name")
                    for a in actions:
                        allow[a] = roles
                else:
                    raise ParseError(f"Unknown crud option '{opt.value}' (expected search, sort, "
                                     "page_size, allow, audit, approval, import or export)", opt)
                self._consume_end()
            if self._check(TT.DEDENT):
                self._advance()
        return ast.CrudDecl(contract=contract, search=search, sort=sort,
                            page_size=page_size, allow=allow, audit=audit,
                            approval=approval, csv_import=csv_import, csv_export=csv_export,
                            line=tok.line, col=tok.col)

    def _approval_decl(self, tok: Token) -> ast.ApprovalDecl:
        """approval  /  approvers a, b  /  when <expr>"""
        self._consume_end()
        approvers: List[str] = []
        when: Optional[ast.Expr] = None
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                opt = self._name("Expected 'approvers' or 'when'")
                if opt.value == "approvers":
                    approvers = self._name_list("Expected a role name")
                elif opt.value == "when":
                    when = self._expression()
                else:
                    raise ParseError(f"Unknown approval option '{opt.value}' "
                                     "(expected approvers or when)", opt)
                self._consume_end()
            if self._check(TT.DEDENT):
                self._advance()
        if not approvers:
            raise ParseError("approval needs an 'approvers' line, e.g. approvers manager", tok)
        return ast.ApprovalDecl(approvers=approvers, when=when, line=tok.line, col=tok.col)

    def _prompt_decl(self) -> ast.PromptDecl:
        """
        prompt name
            system "..."
            user   "..."
            format text | json

        `system`, `user`, `format` are parsed as plain identifiers (not keywords)
        so they remain usable as variable names elsewhere.
        """
        tok      = self._advance()   # consume PROMPT
        name_tok = self._consume(TT.IDENTIFIER, "Expected prompt name")
        self._consume_end()

        system_str = ""
        user_str   = ""
        fmt_str    = "text"

        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()          # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                if self._check(TT.IDENTIFIER):
                    key_tok = self._advance()
                    key     = key_tok.value
                    if key == "system":
                        str_tok    = self._consume(TT.STRING, "Expected string after 'system'")
                        system_str = str_tok.value
                        self._consume_end()
                    elif key == "user":
                        str_tok  = self._consume(TT.STRING, "Expected string after 'user'")
                        user_str = str_tok.value
                        self._consume_end()
                    elif key == "format":
                        # format text | format json
                        if self._check(TT.IDENTIFIER) or self._check(TT.STRING):
                            fmt_str = self._advance().value
                        self._consume_end()
                    else:
                        # Unknown config line — skip to end of line
                        while not self._at_end() and not self._check(TT.NEWLINE):
                            self._advance()
                        self._consume_end()
                else:
                    self._advance()  # skip unexpected
            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.PromptDecl(name=name_tok.value, system=system_str,
                              user=user_str, format=fmt_str,
                              line=tok.line, col=tok.col)

    def _agent_decl(self) -> ast.AgentDecl:
        """
        agent name
            model  "claude-3-5-sonnet"
            tools  fetch, query, ai
            memory session

            task task_name(params)
                body...
        """
        tok      = self._advance()   # consume AGENT
        name_tok = self._consume(TT.IDENTIFIER, "Expected agent name")
        self._consume_end()

        model_str  = ""
        tools_list: List[str] = []
        memory_str = ""
        tasks: List[ast.AgentTaskDecl] = []

        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()          # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break

                # task keyword → parse task block
                if self._check(TT.TASK):
                    tasks.append(self._agent_task_decl())
                    continue

                # config lines: model / tools / memory  (plain identifiers)
                if self._check(TT.IDENTIFIER):
                    key_tok = self._advance()
                    key     = key_tok.value

                    if key == "model":
                        str_tok   = self._consume(TT.STRING,
                                                  "Expected model name string after 'model'")
                        model_str = str_tok.value
                        self._consume_end()

                    elif key == "tools":
                        # tools fetch, query, ai
                        if self._check(TT.IDENTIFIER):
                            tools_list.append(self._advance().value)
                            while self._match(TT.COMMA):
                                if self._check(TT.IDENTIFIER):
                                    tools_list.append(self._advance().value)
                        self._consume_end()

                    elif key == "memory":
                        if self._check(TT.IDENTIFIER) or self._check(TT.STRING):
                            memory_str = self._advance().value
                        self._consume_end()

                    else:
                        # Unknown config — skip line
                        while not self._at_end() and not self._check(TT.NEWLINE):
                            self._advance()
                        self._consume_end()
                else:
                    self._advance()  # skip unexpected token

            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.AgentDecl(name=name_tok.value, model=model_str,
                             tools=tools_list, memory=memory_str, tasks=tasks,
                             line=tok.line, col=tok.col)

    def _break_stmt(self) -> ast.BreakStmt:
        tok = self._advance()          # consume BREAK
        self._consume_end()
        return ast.BreakStmt(line=tok.line, col=tok.col)

    def _continue_stmt(self) -> ast.ContinueStmt:
        tok = self._advance()          # consume CONTINUE
        self._consume_end()
        return ast.ContinueStmt(line=tok.line, col=tok.col)

    def _assert_stmt(self) -> ast.AssertStmt:
        """
        assert condition
        assert condition, "message"
        """
        tok       = self._advance()    # consume ASSERT
        condition = self._expression()
        message: Optional[ast.Expr] = None
        if self._match(TT.COMMA):
            message = self._expression()
        self._consume_end()
        return ast.AssertStmt(condition=condition, message=message,
                              line=tok.line, col=tok.col)

    def _on_statement(self) -> ast.Stmt:
        tok = self._advance()  # consume ON
        # Handle "on event 'name'" or "on 'name'"
        if self._current().type == TT.IDENTIFIER and self._current().value == "event":
            self._advance()  # consume "event"
        event_expr = self._expression()
        args = [event_expr]
        if not self._at_eol():
            args.append(self._expression())
        self._consume_end()
        callee = ast.Variable(name="on", line=tok.line, col=tok.col)
        call = ast.Call(callee=callee, arguments=args, line=tok.line, col=tok.col)
        return ast.ExprStmt(expression=call, line=tok.line, col=tok.col)

    def _test_decl(self) -> ast.TestDecl:
        """
        test "description"
            assert condition
            assert condition, "message"
            ...
        """
        tok      = self._advance()     # consume TEST
        desc_tok = self._consume(TT.STRING, "Expected test description string")
        self._consume_end()
        body = self._block()
        return ast.TestDecl(description=desc_tok.value, body=body,
                            line=tok.line, col=tok.col)

    def _agent_task_decl(self) -> ast.AgentTaskDecl:
        """
        task task_name(param1, param2)
            body...
        """
        tok      = self._advance()   # consume TASK
        name_tok = self._consume(TT.IDENTIFIER, "Expected task name")
        params: List[str] = []
        defaults: dict    = {}
        if self._match(TT.LPAREN):
            params, defaults, _ = self._parse_params()
            self._consume(TT.RPAREN, "Expected ')' after task parameters")
        self._consume_end()
        body = self._block()
        return ast.AgentTaskDecl(name=name_tok.value, params=params, defaults=defaults,
                                 body=body, line=tok.line, col=tok.col)


    def _mcp_decl(self) -> ast.MCPServerDecl:
        """
        mcp server_name
            transport "stdio"
            command   "npx"
            args      ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
            url       "http://localhost:3000/sse"   # for sse/http transport

            tool read_file(path)
            tool write_file(path, content)
        """
        tok      = self._advance()   # consume MCP
        name_tok = self._consume(TT.IDENTIFIER, "Expected MCP server name")
        self._consume_end()

        transport = "stdio"
        command   = ""
        args:  List[str]         = []
        url    = ""
        tools: List[ast.MCPToolDecl] = []

        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()          # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break

                if self._check(TT.TOOL):
                    tools.append(self._mcp_tool_decl())
                    continue

                if self._check(TT.IDENTIFIER):
                    key_tok = self._advance()
                    key     = key_tok.value

                    if key == "transport":
                        transport = self._consume(TT.STRING, "Expected transport string").value
                        self._consume_end()

                    elif key == "command":
                        command = self._consume(TT.STRING, "Expected command string").value
                        self._consume_end()

                    elif key == "url":
                        url = self._consume(TT.STRING, "Expected URL string").value
                        self._consume_end()

                    elif key == "args":
                        # args ["a", "b", "c"]
                        if self._match(TT.LBRACKET):
                            self._skip_whitespace()
                            while not self._check(TT.RBRACKET) and not self._at_end():
                                if self._check(TT.STRING):
                                    args.append(self._advance().value)
                                self._skip_whitespace()
                                self._match(TT.COMMA)
                                self._skip_whitespace()
                            self._consume(TT.RBRACKET, "Expected ']' after args")
                        self._consume_end()

                    else:
                        while not self._at_end() and not self._check(TT.NEWLINE):
                            self._advance()
                        self._consume_end()
                else:
                    self._advance()

            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.MCPServerDecl(
            name=name_tok.value, transport=transport, command=command,
            args=args, url=url, tools=tools,
            line=tok.line, col=tok.col,
        )

    def _mcp_tool_decl(self) -> ast.MCPToolDecl:
        """tool name(param1, param2)"""
        tok      = self._advance()   # consume TOOL
        name_tok = self._consume(TT.IDENTIFIER, "Expected tool name")
        params: List[str] = []
        if self._match(TT.LPAREN):
            if not self._check(TT.RPAREN):
                params.append(self._consume(TT.IDENTIFIER, "Expected param name").value)
                while self._match(TT.COMMA):
                    params.append(self._consume(TT.IDENTIFIER, "Expected param name").value)
            self._consume(TT.RPAREN, "Expected ')' after tool parameters")
        self._consume_end()
        return ast.MCPToolDecl(name=name_tok.value, params=params,
                               line=tok.line, col=tok.col)


    # ── UI / Frontend Parsers ──────────────────────────────────────────────────

    def _component_decl(self) -> ast.ComponentDecl:
        """
        component Name
            state name = default
            on event
                body
            render
                ui_element [attrs] [text]
                    child_element [attrs]
        """
        tok      = self._advance()               # consume COMPONENT
        name_tok = self._consume(TT.IDENTIFIER, "Expected component name")
        self._consume_end()

        states:   List[ast.ComponentStateDecl] = []
        handlers: List[ast.OnHandler]          = []
        render:   Optional[ast.RenderBlock]    = None

        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()                      # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                cur = self._current()

                if cur.type == TT.STATE:
                    states.append(self._component_state_decl())

                elif cur.type == TT.ON:
                    handlers.append(self._on_handler())

                elif cur.type == TT.RENDER:
                    render = self._render_block()

                else:
                    self._advance()   # skip unknown token

            if self._check(TT.DEDENT):
                self._advance()

        return ast.ComponentDecl(
            name=name_tok.value, states=states,
            handlers=handlers, render=render,
            line=tok.line, col=tok.col,
        )

    def _component_state_decl(self) -> ast.ComponentStateDecl:
        """state name = default_expr"""
        tok      = self._advance()               # consume STATE
        name_tok = self._consume(TT.IDENTIFIER, "Expected state variable name")
        self._consume(TT.ASSIGN, "Expected '=' after state name")
        value    = self._expression()
        self._consume_end()
        return ast.ComponentStateDecl(
            name=name_tok.value, value=value,
            line=tok.line, col=tok.col,
        )

    def _on_handler(self) -> ast.OnHandler:
        """on event_name\n    body"""
        tok       = self._advance()              # consume ON
        event_tok = self._consume(TT.IDENTIFIER, "Expected event name after 'on'")
        params: List[str] = []
        if self._match(TT.LPAREN):               # on remove(id)
            params, _, _ = self._parse_params()
            self._consume(TT.RPAREN, "Expected ')' after handler parameters")
        self._consume_end()
        body = self._block()
        return ast.OnHandler(
            event=event_tok.value, body=body, params=params,
            line=tok.line, col=tok.col,
        )

    def _render_block(self) -> ast.RenderBlock:
        """render\n    ui_elements..."""
        tok = self._advance()                    # consume RENDER
        self._consume_end()
        elements = self._ui_block()
        return ast.RenderBlock(elements=elements, line=tok.line, col=tok.col)

    def _ui_block(self) -> List[ast.UIElement]:
        """An indented block of UI nodes (elements, `if`, `for`), or []."""
        nodes: List[ast.UIElement] = []
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()                      # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                nodes.append(self._ui_node())
            if self._check(TT.DEDENT):
                self._advance()
        return nodes

    def _ui_node(self):
        if self._check(TT.IF):
            return self._ui_if()
        if self._check(TT.FOR):
            return self._ui_for()
        return self._ui_element()

    def _ui_if(self) -> ast.UIIf:
        """
        if cond
            ui...
        else if cond
            ui...
        else
            ui...
        """
        tok       = self._advance()              # consume IF
        condition = self._expression()
        self._consume_end()
        then_children = self._ui_block()
        else_children: List[ast.UIElement] = []
        if self._check(TT.ELSE):
            self._advance()                      # consume ELSE
            if self._check(TT.IF):
                else_children = [self._ui_if()]  # else if → nested UIIf
            else:
                self._consume_end()
                else_children = self._ui_block()
        return ast.UIIf(condition=condition, then_children=then_children,
                        else_children=else_children, line=tok.line, col=tok.col)

    def _ui_for(self) -> ast.UIFor:
        """
        for item in items          (or: for i, item in items)
            ui...
        empty
            ui...                  (optional: shown when items is empty)
        """
        tok   = self._advance()                  # consume FOR
        first = self._name("Expected loop variable after 'for'")
        index_var: Optional[str] = None
        var_name = first.value
        if self._match(TT.COMMA):
            second    = self._name("Expected item variable after ','")
            index_var = first.value
            var_name  = second.value
        self._consume(TT.IN, "Expected 'in' after loop variable")
        iterable = self._expression()
        self._consume_end()
        body = self._ui_block()
        empty: List[ast.UIElement] = []
        # `empty` is only special directly after a `for` block
        if (self._check(TT.IDENTIFIER) and self._current().value == "empty" and
                self._pos + 1 < len(self._tokens) and
                self._tokens[self._pos + 1].type in (TT.NEWLINE, TT.INDENT)):
            self._advance()                      # consume `empty`
            self._consume_end()
            empty = self._ui_block()
        return ast.UIFor(variable=var_name, index_var=index_var, iterable=iterable,
                         body=body, empty=empty, line=tok.line, col=tok.col)

    def _ui_element(self) -> ast.UIElement:
        """
        tag_name [key=value ...] ["text"]
            child_element ...
        """
        tok     = self._current()
        tag_tok = self._consume(TT.IDENTIFIER, "Expected UI element tag name")
        tag     = tag_tok.value

        attrs: List[ast.UIAttr] = []
        text:  Optional[ast.Expr] = None

        # Parse inline attrs and optional text on the same line
        while not self._at_eol():
            cur = self._current()

            # key=value attribute  (IDENTIFIER ASSIGN expr)
            if (cur.type == TT.IDENTIFIER and
                    self._pos + 1 < len(self._tokens) and
                    self._tokens[self._pos + 1].type == TT.ASSIGN):
                key_tok = self._advance()        # consume key
                self._advance()                  # consume =
                val = self._expression()
                attrs.append(ast.UIAttr(key=key_tok.value, value=val,
                                        line=key_tok.line, col=key_tok.col))

            # bare identifier attribute (boolean flag, e.g. `disabled`)
            elif cur.type == TT.IDENTIFIER:
                key_tok = self._advance()
                attrs.append(ast.UIAttr(key=key_tok.value, value=None,
                                        line=key_tok.line, col=key_tok.col))

            # string → inline text content: button "Submit"
            elif cur.type == TT.STRING:
                str_tok = self._advance()
                text = ast.Literal(value=str_tok.value,
                                   line=str_tok.line, col=str_tok.col)

            else:
                break  # stop at NEWLINE / DEDENT / other

        self._consume_end()

        # Parse indented children
        children = self._ui_block()

        return ast.UIElement(
            tag=tag, attrs=attrs, text=text, children=children,
            line=tok.line, col=tok.col,
        )

    def _app_decl(self) -> ast.AppDecl:
        """
        app AppName
            title  "App Title"
            theme  "professional"
            layout
                sidebar
                    nav "Label" icon="home"
                tabs
                    tab "Label" → ComponentName
                main
                    ComponentName
        """
        tok      = self._advance()               # consume APP
        name_tok = self._consume(TT.IDENTIFIER, "Expected app name")
        self._consume_end()

        title  = ""
        theme  = "default"
        layout: Optional[ast.LayoutBlock] = None

        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()                      # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                cur = self._current()

                if cur.type == TT.IDENTIFIER and cur.value == "title":
                    self._advance()
                    str_tok = self._consume(TT.STRING, "Expected string after 'title'")
                    title = str_tok.value
                    self._consume_end()

                elif cur.type == TT.IDENTIFIER and cur.value == "theme":
                    self._advance()
                    str_tok = self._consume(TT.STRING, "Expected string after 'theme'")
                    theme = str_tok.value
                    self._consume_end()

                elif cur.type == TT.LAYOUT:
                    layout = self._layout_block()

                else:
                    self._advance()

            if self._check(TT.DEDENT):
                self._advance()

        return ast.AppDecl(
            name=name_tok.value, title=title, theme=theme, layout=layout,
            line=tok.line, col=tok.col,
        )

    def _layout_block(self) -> ast.LayoutBlock:
        """
        layout
            sidebar
                nav "Label" icon="icon"
            tabs
                tab "Label" ComponentName
            main
                ComponentName
        """
        self._advance()      # consume LAYOUT
        self._consume_end()

        sidebar: List[ast.NavItem]  = []
        tabs:    List[ast.TabItem]  = []
        main:    List[str]          = []

        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()  # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                cur = self._current()

                # sidebar block
                if cur.type == TT.IDENTIFIER and cur.value == "sidebar":
                    self._advance(); self._consume_end()
                    self._skip_newlines()
                    if self._check(TT.INDENT):
                        self._advance()
                        while not self._check(TT.DEDENT) and not self._at_end():
                            self._skip_newlines()
                            if self._check(TT.DEDENT): break
                            c = self._current()
                            if c.type == TT.IDENTIFIER and c.value == "nav":
                                self._advance()
                                label_tok = self._consume(TT.STRING, "Expected nav label")
                                icon = ""
                                comp = ""
                                nav_allow: List[str] = []
                                while not self._at_eol():
                                    k = self._current()
                                    # key=value; the key may lex as a keyword
                                    # (`component=Foo` → TT.COMPONENT)
                                    if (k.type != TT.STRING and k.value.isidentifier() and
                                            self._pos + 1 < len(self._tokens) and
                                            self._tokens[self._pos + 1].type == TT.ASSIGN):
                                        key = self._advance().value
                                        self._advance()  # =
                                        val_tok = self._advance()
                                        val = val_tok.value.strip('"')
                                        if key == "icon":      icon = val
                                        if key == "component": comp = val
                                    elif k.type == TT.IDENTIFIER and k.value == "allow":
                                        self._advance()
                                        nav_allow = self._name_list("Expected a role name")
                                    elif k.type == TT.IDENTIFIER and not comp:
                                        # positional form: nav "Label" ComponentName
                                        comp = self._advance().value
                                    else:
                                        break
                                self._consume_end()
                                sidebar.append(ast.NavItem(
                                    label=label_tok.value, icon=icon,
                                    component=comp, allow=nav_allow,
                                    line=c.line, col=c.col,
                                ))
                            else:
                                self._advance()
                        if self._check(TT.DEDENT): self._advance()

                # tabs block
                elif cur.type == TT.IDENTIFIER and cur.value == "tabs":
                    self._advance(); self._consume_end()
                    self._skip_newlines()
                    if self._check(TT.INDENT):
                        self._advance()
                        while not self._check(TT.DEDENT) and not self._at_end():
                            self._skip_newlines()
                            if self._check(TT.DEDENT): break
                            c = self._current()
                            if c.type == TT.IDENTIFIER and c.value == "tab":
                                self._advance()
                                label_tok = self._consume(TT.STRING, "Expected tab label")
                                comp = ""
                                if not self._at_eol() and self._current().type == TT.IDENTIFIER:
                                    comp = self._advance().value
                                self._consume_end()
                                tabs.append(ast.TabItem(
                                    label=label_tok.value, component=comp,
                                    line=c.line, col=c.col,
                                ))
                            else:
                                self._advance()
                        if self._check(TT.DEDENT): self._advance()

                # main block
                elif cur.type == TT.IDENTIFIER and cur.value == "main":
                    self._advance(); self._consume_end()
                    self._skip_newlines()
                    if self._check(TT.INDENT):
                        self._advance()
                        while not self._check(TT.DEDENT) and not self._at_end():
                            self._skip_newlines()
                            if self._check(TT.DEDENT): break
                            c = self._current()
                            if c.type == TT.IDENTIFIER:
                                main.append(self._advance().value)
                                self._consume_end()
                            else:
                                self._advance()
                        if self._check(TT.DEDENT): self._advance()

                # routes block
                elif cur.type == TT.IDENTIFIER and cur.value == "routes":
                    self._advance(); self._consume_end()
                    self._skip_newlines()
                    if self._check(TT.INDENT):
                        self._advance()
                        routes_list: List[ast.RouteItem] = []
                        while not self._check(TT.DEDENT) and not self._at_end():
                            self._skip_newlines()
                            if self._check(TT.DEDENT): break
                            c = self._current()
                            if c.type == TT.ROUTE:
                                self._advance()
                                path_tok = self._consume(TT.STRING, "Expected route path string")
                                comp = ""
                                if not self._at_eol() and self._current().type == TT.IDENTIFIER:
                                    comp = self._advance().value
                                self._consume_end()
                                routes_list.append(ast.RouteItem(
                                    path=path_tok.value, component=comp,
                                    line=c.line, col=c.col,
                                ))
                            else:
                                self._advance()
                        if self._check(TT.DEDENT): self._advance()
                        # Attach routes to layout; store temporarily
                        main.extend([f"__route__:{r.path}:{r.component}" for r in routes_list])

                else:
                    self._advance()

            if self._check(TT.DEDENT):
                self._advance()

        # Extract route markers back out
        routes: List[ast.RouteItem] = []
        clean_main: List[str] = []
        for entry in main:
            if entry.startswith("__route__:"):
                _, path, comp = entry.split(":", 2)
                routes.append(ast.RouteItem(path=path, component=comp))
            else:
                clean_main.append(entry)

        return ast.LayoutBlock(
            sidebar=sidebar, tabs=tabs, main=clean_main, routes=routes,
        )


    def _include_stmt(self) -> ast.IncludeStmt:
        """include "path/to/file.mcn" """
        tok = self._advance()   # consume INCLUDE
        path_tok = self._consume(TT.STRING, "Expected file path string after 'include'")
        self._consume_end()
        return ast.IncludeStmt(path=path_tok.value, line=tok.line, col=tok.col)


# ── Backward-compat alias ──────────────────────────────────────────────────────
MCNParser = Parser
