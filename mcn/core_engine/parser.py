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

from typing import List, Optional

from .lexer import Token, TT
from . import ast_nodes as ast


# ── Errors ─────────────────────────────────────────────────────────────────────

class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(
            f"[{token.line}:{token.col}] ParseError: {message} "
            f"(got {token.type.name} {token.value!r})"
        )
        self.token = token


# ── Parser ─────────────────────────────────────────────────────────────────────

# Built-in names that can be called in statement position without parentheses:
#   log "hello"   →  log("hello")
_STATEMENT_STYLE_BUILTINS = {
    "log", "echo", "trigger", "query", "workflow", "ai",
    "await", "env", "read_file", "write_file", "append_file", "fetch",
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

    # ── Entry point ────────────────────────────────────────────────────────────

    def parse(self) -> ast.Program:
        tok  = self._current()
        body: List[ast.Stmt] = []
        while not self._at_end():
            self._skip_newlines()
            if self._at_end():
                break
            stmt = self._statement()
            if stmt is not None:
                body.append(stmt)
        return ast.Program(body=body, line=tok.line, col=tok.col)

    # ── Statement dispatch ─────────────────────────────────────────────────────

    def _statement(self) -> Optional[ast.Stmt]:
        tok = self._current()
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
        # 2030 language primitives
        if tok.type == TT.PIPELINE: return self._pipeline_decl()
        if tok.type == TT.SERVICE:  return self._service_decl()
        if tok.type == TT.WORKFLOW: return self._workflow_decl()
        if tok.type == TT.CONTRACT: return self._contract_decl()
        # AI / intelligent primitives
        if tok.type == TT.PROMPT:   return self._prompt_decl()
        if tok.type == TT.AGENT:    return self._agent_decl()
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
        # Bare assignment: name = expr  (must come before _expr_stmt)
        if (tok.type == TT.IDENTIFIER and
                self._pos + 1 < len(self._tokens) and
                self._tokens[self._pos + 1].type == TT.ASSIGN):
            return self._assign_stmt()
        return self._expr_stmt()

    # ── Statement parsers ──────────────────────────────────────────────────────

    def _var_decl(self) -> ast.VarDecl:
        tok      = self._advance()            # consume VAR
        name_tok = self._consume(TT.IDENTIFIER, "Expected variable name after 'var'")
        self._consume(TT.ASSIGN, "Expected '=' after variable name")
        value    = self._expression()
        self._consume_end()
        return ast.VarDecl(name=name_tok.value, value=value,
                           line=tok.line, col=tok.col)

    def _assign_stmt(self) -> ast.AssignStmt:
        name_tok = self._advance()            # consume IDENTIFIER
        self._advance()                       # consume ASSIGN '='
        value    = self._expression()
        self._consume_end()
        return ast.AssignStmt(name=name_tok.value, value=value,
                              line=name_tok.line, col=name_tok.col)

    def _if_stmt(self) -> ast.IfStmt:
        tok       = self._advance()           # consume IF
        condition = self._expression()
        self._consume_end()
        then_body = self._block()
        else_body: List[ast.Stmt] = []
        if self._check(TT.ELSE):
            self._advance()
            self._consume_end()
            else_body = self._block()
        return ast.IfStmt(condition=condition, then_body=then_body,
                          else_body=else_body, line=tok.line, col=tok.col)

    def _for_stmt(self) -> ast.ForStmt:
        tok     = self._advance()             # consume FOR
        var_tok = self._consume(TT.IDENTIFIER, "Expected loop variable after 'for'")
        self._consume(TT.IN, "Expected 'in' after loop variable")
        iterable = self._expression()
        self._consume_end()
        body = self._block()
        return ast.ForStmt(variable=var_tok.value, iterable=iterable,
                           body=body, line=tok.line, col=tok.col)

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
        try_body  = self._block()
        catch_body: List[ast.Stmt] = []
        if self._check(TT.CATCH):
            self._advance()
            self._consume_end()
            catch_body = self._block()
        return ast.TryStmt(try_body=try_body, catch_body=catch_body,
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
        Parse a parenthesised parameter list with optional defaults.
        Caller must have already consumed the opening '('.
        Returns (params: List[str], defaults: dict).
        """
        params:   List[str] = []
        defaults: dict      = {}
        if not self._check(TT.RPAREN):
            p = self._consume(TT.IDENTIFIER, "Expected parameter name").value
            params.append(p)
            if self._match(TT.ASSIGN):
                defaults[p] = self._expression()
            while self._match(TT.COMMA):
                p = self._consume(TT.IDENTIFIER, "Expected parameter name").value
                params.append(p)
                if self._match(TT.ASSIGN):
                    defaults[p] = self._expression()
        return params, defaults

    def _function_decl(self) -> ast.FunctionDecl:
        tok      = self._advance()            # consume FUNCTION
        name_tok = self._consume(TT.IDENTIFIER, "Expected function name")
        self._consume(TT.LPAREN, "Expected '(' after function name")
        params, defaults = self._parse_params()
        self._consume(TT.RPAREN, "Expected ')' after parameters")
        self._consume_end()
        body = self._block()
        return ast.FunctionDecl(name=name_tok.value, params=params,
                                defaults=defaults, body=body,
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
            if not self._at_eol():
                args.append(self._expression())
            self._consume_end()
            callee = ast.Variable(name=func_tok.value,
                                  line=func_tok.line, col=func_tok.col)
            call   = ast.Call(callee=callee, arguments=args,
                              line=func_tok.line, col=func_tok.col)
            return ast.ExprStmt(expression=call, line=func_tok.line, col=func_tok.col)

        expr = self._expression()
        self._consume_end()
        return ast.ExprStmt(expression=expr, line=tok.line, col=tok.col)

    # ── Block parsing (INDENT / DEDENT) ────────────────────────────────────────

    def _block(self) -> List[ast.Stmt]:
        """
        Parse an indented block.

        Expects the lexer to have emitted INDENT before the first statement
        and DEDENT after the last statement of this block.
        An absent INDENT means an empty / missing block (we tolerate it).
        """
        self._skip_newlines()
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
        return self._or()

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
        while self._current().type in (TT.STAR, TT.SLASH):
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
                prop = self._consume(TT.IDENTIFIER,
                                     "Expected property name after '.'")
                expr = ast.Property(object=expr, name=prop.value, safe=False,
                                    line=prop.line, col=prop.col)
            elif self._match(TT.SAFE_DOT):
                # obj?.name — returns None if obj is None
                prop = self._consume(TT.IDENTIFIER,
                                     "Expected property name after '?.'")
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

        if self._match(TT.IDENTIFIER):
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
            # (x,) or (x, y) → tuple; (x) without trailing comma → grouped expr
            if len(elements) == 1 and not trailing_comma:
                return elements[0]
            return ast.MCNTuple(elements=elements, line=tok.line, col=tok.col)

        # Array literal: [a, b, c] or [a, b,]
        if self._match(TT.LBRACKET):
            elements = []
            if not self._check(TT.RBRACKET):
                elements.append(self._expression())
                while self._match(TT.COMMA):
                    if self._check(TT.RBRACKET):  # trailing comma
                        break
                    elements.append(self._expression())
            self._consume(TT.RBRACKET, "Expected ']' after array elements")
            return ast.Array(elements=elements, line=tok.line, col=tok.col)

        # Object literal: {key: value, ...}
        if self._match(TT.LBRACE):
            props = []
            if not self._check(TT.RBRACE):
                key = self._expression()
                self._consume(TT.COLON, "Expected ':' after object key")
                val = self._expression()
                props.append((key, val))
                while self._match(TT.COMMA):
                    key = self._expression()
                    self._consume(TT.COLON, "Expected ':' after object key")
                    val = self._expression()
                    props.append((key, val))
            self._consume(TT.RBRACE, "Expected '}' after object properties")
            return ast.MCNObject(properties=props, line=tok.line, col=tok.col)

        raise ParseError("Unexpected token", tok)

    # ── Helpers ────────────────────────────────────────────────────────────────

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
            params, defaults = self._parse_params()
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
                else:
                    self._advance()
            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.ServiceDecl(name=name_tok.value, port=port, endpoints=endpoints,
                               line=tok.line, col=tok.col)

    def _endpoint_decl(self) -> ast.EndpointDecl:
        tok      = self._advance()   # consume ENDPOINT
        name_tok = self._consume(TT.IDENTIFIER, "Expected endpoint name")
        params: List[str] = []
        defaults: dict    = {}
        if self._match(TT.LPAREN):
            params, defaults = self._parse_params()
            self._consume(TT.RPAREN, "Expected ')' after endpoint parameters")
        self._consume_end()
        body = self._block()
        return ast.EndpointDecl(name=name_tok.value, params=params, defaults=defaults,
                                body=body, line=tok.line, col=tok.col)

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
            params, defaults = self._parse_params()
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
                field_name = self._consume(TT.IDENTIFIER, "Expected field name")
                self._consume(TT.COLON, "Expected ':' after field name")
                type_tok   = self._consume(TT.IDENTIFIER, "Expected type name")
                self._consume_end()
                fields.append(ast.ContractField(
                    name=field_name.value, type_name=type_tok.value,
                    line=field_name.line, col=field_name.col,
                ))
            if self._check(TT.DEDENT):
                self._advance()      # consume DEDENT

        return ast.ContractDecl(name=name_tok.value, fields=fields,
                                line=tok.line, col=tok.col)

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
            params, defaults = self._parse_params()
            self._consume(TT.RPAREN, "Expected ')' after task parameters")
        self._consume_end()
        body = self._block()
        return ast.AgentTaskDecl(name=name_tok.value, params=params, defaults=defaults,
                                 body=body, line=tok.line, col=tok.col)


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
        self._consume_end()
        body = self._block()
        return ast.OnHandler(
            event=event_tok.value, body=body,
            line=tok.line, col=tok.col,
        )

    def _render_block(self) -> ast.RenderBlock:
        """render\n    ui_elements..."""
        tok = self._advance()                    # consume RENDER
        self._consume_end()
        elements: List[ast.UIElement] = []
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()                      # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                elements.append(self._ui_element())
            if self._check(TT.DEDENT):
                self._advance()
        return ast.RenderBlock(elements=elements, line=tok.line, col=tok.col)

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
        children: List[ast.UIElement] = []
        self._skip_newlines()
        if self._check(TT.INDENT):
            self._advance()                      # consume INDENT
            while not self._at_end() and not self._check(TT.DEDENT):
                self._skip_newlines()
                if self._check(TT.DEDENT) or self._at_end():
                    break
                children.append(self._ui_element())
            if self._check(TT.DEDENT):
                self._advance()

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
                                while not self._at_eol():
                                    k = self._current()
                                    if (k.type == TT.IDENTIFIER and
                                            self._pos + 1 < len(self._tokens) and
                                            self._tokens[self._pos + 1].type == TT.ASSIGN):
                                        key = self._advance().value
                                        self._advance()  # =
                                        val_tok = self._advance()
                                        val = val_tok.value.strip('"')
                                        if key == "icon":      icon = val
                                        if key == "component": comp = val
                                    else:
                                        break
                                self._consume_end()
                                sidebar.append(ast.NavItem(
                                    label=label_tok.value, icon=icon,
                                    component=comp,
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
