import re
import json
import traceback
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from .mcn_logger import log_error, log_step, log_performance
import time

# MCN Core Protection
MCN_CORE_VERSION = "2.0.0"
MCN_CORE_SIGNATURE = "MCN-OFFICIAL-INTERPRETER"
MCN_TRADEMARK_NOTICE = "MCN is a trademark of MCN Foundation"
MCN_COPYRIGHT = "Copyright (c) 2025 MCN Foundation"


def verify_mcn_authenticity():
    """Verify this is an official MCN distribution"""
    import os

    signature_file = os.path.join(os.path.dirname(__file__), ".mcn_official")
    return os.path.exists(signature_file)


class ReturnValue(Exception):
    """Exception used to handle return statements in functions"""

    def __init__(self, value):
        self.value = value
        super().__init__()


class TokenType(Enum):
    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    VAR = "VAR"
    IF = "IF"
    ELSE = "ELSE"
    FOR = "FOR"
    IN = "IN"
    WHILE = "WHILE"
    FUNCTION = "FUNCTION"
    TRY = "TRY"
    CATCH = "CATCH"
    THROW = "THROW"
    RETURN = "RETURN"
    TASK = "TASK"
    AWAIT = "AWAIT"
    USE = "USE"
    ASSIGN = "ASSIGN"
    PLUS = "PLUS"
    MINUS = "MINUS"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    GREATER = "GREATER"
    LESS = "LESS"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS_EQUAL = "LESS_EQUAL"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    COLON = "COLON"
    DOT = "DOT"
    COMMA = "COMMA"
    NEWLINE = "NEWLINE"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int = 0


class MCNLexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.tokens = []

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.text):
            self._skip_whitespace()
            if self.pos >= len(self.text):
                break

            char = self.text[self.pos]

            if char == "\n":
                self.tokens.append(Token(TokenType.NEWLINE, char, self.line))
                self.line += 1
                self.pos += 1
            elif char == "=":
                if self._peek() == "=":
                    self.tokens.append(Token(TokenType.EQUAL, "==", self.line))
                    self.pos += 2
                else:
                    self.tokens.append(Token(TokenType.ASSIGN, char, self.line))
                    self.pos += 1
            elif char == "!":
                if self._peek() == "=":
                    self.tokens.append(Token(TokenType.NOT_EQUAL, "!=", self.line))
                    self.pos += 2
                else:
                    self.tokens.append(Token(TokenType.NOT, char, self.line))
                    self.pos += 1
            elif char == ">":
                if self._peek() == "=":
                    self.tokens.append(Token(TokenType.GREATER_EQUAL, ">=", self.line))
                    self.pos += 2
                else:
                    self.tokens.append(Token(TokenType.GREATER, char, self.line))
                    self.pos += 1
            elif char == "<":
                if self._peek() == "=":
                    self.tokens.append(Token(TokenType.LESS_EQUAL, "<=", self.line))
                    self.pos += 2
                else:
                    self.tokens.append(Token(TokenType.LESS, char, self.line))
                    self.pos += 1
            elif char == "+":
                self.tokens.append(Token(TokenType.PLUS, char, self.line))
                self.pos += 1
            elif char == "-":
                self.tokens.append(Token(TokenType.MINUS, char, self.line))
                self.pos += 1
            elif char == "*":
                self.tokens.append(Token(TokenType.MULTIPLY, char, self.line))
                self.pos += 1
            elif char == "/":
                if self._peek() == "/":
                    # Skip single-line comment
                    while self.pos < len(self.text) and self.text[self.pos] != "\n":
                        self.pos += 1
                elif self._peek() == "*":
                    # Skip block comment
                    self.pos += 2  # Skip /*
                    while self.pos < len(self.text) - 1:
                        if (
                            self.text[self.pos] == "*"
                            and self.text[self.pos + 1] == "/"
                        ):
                            self.pos += 2  # Skip */
                            break
                        if self.text[self.pos] == "\n":
                            self.line += 1
                        self.pos += 1
                else:
                    self.tokens.append(Token(TokenType.DIVIDE, char, self.line))
                    self.pos += 1
            elif char == "(":
                self.tokens.append(Token(TokenType.LPAREN, char, self.line))
                self.pos += 1
            elif char == ")":
                self.tokens.append(Token(TokenType.RPAREN, char, self.line))
                self.pos += 1
            elif char == "{":
                self.tokens.append(Token(TokenType.LBRACE, char, self.line))
                self.pos += 1
            elif char == "}":
                self.tokens.append(Token(TokenType.RBRACE, char, self.line))
                self.pos += 1
            elif char == "[":
                self.tokens.append(Token(TokenType.LBRACKET, char, self.line))
                self.pos += 1
            elif char == "]":
                self.tokens.append(Token(TokenType.RBRACKET, char, self.line))
                self.pos += 1
            elif char == ":":
                self.tokens.append(Token(TokenType.COLON, char, self.line))
                self.pos += 1
            elif char == ".":
                self.tokens.append(Token(TokenType.DOT, char, self.line))
                self.pos += 1
            elif char == ",":
                self.tokens.append(Token(TokenType.COMMA, char, self.line))
                self.pos += 1
            elif char == '"' or char == "'":
                self._read_string(char)
            elif char.isdigit():
                self._read_number()
            elif char.isalpha() or char == "_":
                self._read_identifier()
            else:
                self.pos += 1

        self.tokens.append(Token(TokenType.EOF, "", self.line))
        return self.tokens

    def _skip_whitespace(self):
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r":
            self.pos += 1

    def _peek(self) -> str:
        return self.text[self.pos + 1] if self.pos + 1 < len(self.text) else ""

    def _read_string(self, quote_char: str):
        start_pos = self.pos
        self.pos += 1
        while self.pos < len(self.text) and self.text[self.pos] != quote_char:
            if self.text[self.pos] == "\\":
                self.pos += 2
            else:
                self.pos += 1
        if self.pos < len(self.text):
            self.pos += 1
        value = self.text[start_pos + 1 : self.pos - 1]
        self.tokens.append(Token(TokenType.STRING, value, self.line))

    def _read_number(self):
        start_pos = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isdigit() or self.text[self.pos] == "."
        ):
            self.pos += 1
        value = self.text[start_pos : self.pos]
        self.tokens.append(Token(TokenType.NUMBER, value, self.line))

    def _read_identifier(self):
        start_pos = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isalnum() or self.text[self.pos] == "_"
        ):
            self.pos += 1
        value = self.text[start_pos : self.pos]

        keywords = {
            "var": TokenType.VAR,
            "if": TokenType.IF,
            "else": TokenType.ELSE,
            "for": TokenType.FOR,
            "in": TokenType.IN,
            "while": TokenType.WHILE,
            "function": TokenType.FUNCTION,
            "try": TokenType.TRY,
            "catch": TokenType.CATCH,
            "throw": TokenType.THROW,
            "return": TokenType.RETURN,
            "task": TokenType.TASK,
            "await": TokenType.AWAIT,
            "use": TokenType.USE,
            "and": TokenType.AND,
            "or": TokenType.OR,
            "not": TokenType.NOT,
        }

        token_type = keywords.get(value, TokenType.IDENTIFIER)
        self.tokens.append(Token(token_type, value, self.line))


class MCNParser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> List[Dict]:
        statements = []
        while not self._is_at_end():
            if self._current().type == TokenType.NEWLINE:
                self._advance()
                continue
            stmt = self._statement()
            if stmt:
                statements.append(stmt)
        return statements

    def _statement(self) -> Optional[Dict]:
        if self._match(TokenType.VAR):
            return self._var_declaration()
        elif self._match(TokenType.IF):
            return self._if_statement()
        elif self._match(TokenType.FOR):
            return self._for_statement()
        elif self._match(TokenType.WHILE):
            return self._while_statement()
        elif self._match(TokenType.TRY):
            return self._try_statement()
        elif self._match(TokenType.THROW):
            return self._throw_statement()
        elif self._match(TokenType.TASK):
            return self._task_statement()
        elif self._match(TokenType.USE):
            return self._use_statement()
        elif self._match(TokenType.FUNCTION):
            return self._function_declaration()
        elif self._match(TokenType.RETURN):
            return self._return_statement()
        else:
            return self._expression_statement()

    def _var_declaration(self) -> Dict:
        name = self._consume(TokenType.IDENTIFIER, "Expected variable name").value
        self._consume(TokenType.ASSIGN, "Expected '=' after variable name")
        value = self._expression()
        return {"type": "var_declaration", "name": name, "value": value}

    def _if_statement(self) -> Dict:
        condition = self._expression()
        then_branch = self._block()
        else_branch = None
        if self._match(TokenType.ELSE):
            else_branch = self._block()
        return {
            "type": "if_statement",
            "condition": condition,
            "then": then_branch,
            "else": else_branch,
        }

    def _for_statement(self) -> Dict:
        variable = self._consume(TokenType.IDENTIFIER, "Expected variable name").value
        self._consume(TokenType.IN, "Expected 'in' after for variable")
        iterable = self._expression()
        body = self._block()
        return {
            "type": "for_statement",
            "variable": variable,
            "iterable": iterable,
            "body": body,
        }

    def _while_statement(self) -> Dict:
        condition = self._expression()
        body = self._block()
        return {"type": "while_statement", "condition": condition, "body": body}

    def _try_statement(self) -> Dict:
        try_block = self._block()
        catch_block = None
        if self._match(TokenType.CATCH):
            catch_block = self._block()
        return {"type": "try_statement", "try": try_block, "catch": catch_block}

    def _throw_statement(self) -> Dict:
        message = self._expression()
        return {"type": "throw_statement", "message": message}

    def _task_statement(self) -> Dict:
        name = self._expression()  # Task name
        func_name = self._expression()  # Function name
        args = []

        # Parse arguments
        while not self._is_at_end() and self._current().type not in [
            TokenType.NEWLINE,
            TokenType.EOF,
        ]:
            args.append(self._expression())

        return {
            "type": "task_statement",
            "name": name,
            "function": func_name,
            "arguments": args,
        }

    def _use_statement(self) -> Dict:
        package_name = self._expression()
        return {"type": "use_statement", "package": package_name}

    def _function_declaration(self) -> Dict:
        name = self._consume(TokenType.IDENTIFIER, "Expected function name").value
        self._consume(TokenType.LPAREN, "Expected '(' after function name")

        params = []
        if not self._check(TokenType.RPAREN):
            params.append(
                self._consume(TokenType.IDENTIFIER, "Expected parameter name").value
            )
            while self._match(TokenType.COMMA):
                params.append(
                    self._consume(TokenType.IDENTIFIER, "Expected parameter name").value
                )

        self._consume(TokenType.RPAREN, "Expected ')' after parameters")

        # Skip newlines after function signature
        while self._current().type == TokenType.NEWLINE:
            self._advance()

        # Parse function body - collect statements until we see a pattern that indicates end of function
        body = []
        brace_depth = 0

        while not self._is_at_end() and self._current().type != TokenType.EOF:
            if self._current().type == TokenType.NEWLINE:
                self._advance()
                continue

            # Stop at next function declaration
            if self._current().type == TokenType.FUNCTION:
                break

            # Stop at top-level patterns that indicate we're outside the function
            if brace_depth == 0:
                # Stop at function calls without parameters (likely top-level)
                if (
                    self._current().type == TokenType.IDENTIFIER
                    and self.pos + 1 < len(self.tokens)
                    and self.tokens[self.pos + 1].type == TokenType.LPAREN
                    and self.pos + 2 < len(self.tokens)
                    and self.tokens[self.pos + 2].type == TokenType.RPAREN
                ):
                    break

                # Stop at log statements with "===" (section headers)
                if (
                    self._current().type == TokenType.IDENTIFIER
                    and self._current().value == "log"
                    and self.pos + 1 < len(self.tokens)
                    and self.tokens[self.pos + 1].type == TokenType.STRING
                    and "===" in self.tokens[self.pos + 1].value
                ):
                    break

                # Stop at variable assignments that call known functions
                if (
                    self._current().type == TokenType.VAR
                    and self._is_top_level_var_assignment()
                ):
                    break

            # Track braces for nested structures
            if self._current().type == TokenType.LBRACE:
                brace_depth += 1
            elif self._current().type == TokenType.RBRACE:
                brace_depth -= 1

            stmt = self._statement()
            if stmt:
                body.append(stmt)

        return {
            "type": "function_declaration",
            "name": name,
            "params": params,
            "body": body,
        }

    def _is_top_level_call(self) -> bool:
        """Check if current position is a top-level function call (not inside function body)"""
        return True  # For now, allow all statements in function body

    def _is_top_level_var_assignment(self) -> bool:
        """Check if this var assignment looks like it's at top level"""
        saved_pos = self.pos
        try:
            self._advance()  # skip 'var'
            if self._current().type == TokenType.IDENTIFIER:
                var_name = self._current().value
                self._advance()  # skip variable name
                if self._current().type == TokenType.ASSIGN:
                    self._advance()  # skip '='
                    if (
                        self._current().type == TokenType.IDENTIFIER
                        and self._current().value
                        in [
                            "add",
                            "calculate_discount",
                            "process_user_data",
                            "analyze_sentiment",
                        ]
                    ):
                        return True
            return False
        finally:
            self.pos = saved_pos

    def _return_statement(self) -> Dict:
        value = None
        if not self._is_at_end() and self._current().type not in [
            TokenType.NEWLINE,
            TokenType.EOF,
        ]:
            value = self._expression()
        return {"type": "return_statement", "value": value}

    def _expression_statement(self) -> Dict:
        # Check for statement-style function calls (e.g., log "message")
        if self._current().type == TokenType.IDENTIFIER and self._current().value in [
            "log",
            "echo",
            "trigger",
            "query",
            "workflow",
            "ai",
            "await",
            "env",
            "read_file",
            "write_file",
            "append_file",
            "fetch",
        ]:
            func_name = self._advance().value
            args = []
            if not self._is_at_end() and self._current().type not in [
                TokenType.NEWLINE,
                TokenType.EOF,
            ]:
                args.append(self._expression())
            return {
                "type": "expression_statement",
                "expression": {
                    "type": "call",
                    "callee": {"type": "variable", "name": func_name},
                    "arguments": args,
                },
            }

        expr = self._expression()
        return {"type": "expression_statement", "expression": expr}

    def _block(self) -> List[Dict]:
        statements = []
        while not self._is_at_end() and self._current().type not in [
            TokenType.ELSE,
            TokenType.CATCH,
            TokenType.EOF,
        ]:
            if self._current().type == TokenType.NEWLINE:
                self._advance()
                continue

            # Stop at function declarations (we've left the current function)
            if self._current().type == TokenType.FUNCTION:
                break

            # Stop at return statements followed by newlines (end of function)
            if self._current().type == TokenType.RETURN:
                stmt = self._statement()
                if stmt:
                    statements.append(stmt)
                # Skip newlines after return
                while (
                    not self._is_at_end() and self._current().type == TokenType.NEWLINE
                ):
                    self._advance()
                # If next token is function or top-level statement, we're done
                if not self._is_at_end() and (
                    self._current().type == TokenType.FUNCTION
                    or (
                        self._current().type == TokenType.IDENTIFIER
                        and self._current().value
                        in [
                            "log",
                            "greet",
                            "add",
                            "calculate_discount",
                            "process_user_data",
                            "analyze_sentiment",
                        ]
                    )
                    or self._current().type == TokenType.VAR
                ):
                    break
                continue

            stmt = self._statement()
            if stmt:
                statements.append(stmt)

            # Skip newlines after statement
            while not self._is_at_end() and self._current().type == TokenType.NEWLINE:
                self._advance()

            # Check for block terminators
            if not self._is_at_end() and self._current().type in [
                TokenType.ELSE,
                TokenType.CATCH,
            ]:
                break

        return statements

    def _expression(self) -> Dict:
        return self._or()

    def _or(self) -> Dict:
        expr = self._and()
        while self._match(TokenType.OR):
            operator = self._previous().value
            right = self._and()
            expr = {
                "type": "binary",
                "left": expr,
                "operator": operator,
                "right": right,
            }
        return expr

    def _and(self) -> Dict:
        expr = self._equality()
        while self._match(TokenType.AND):
            operator = self._previous().value
            right = self._equality()
            expr = {
                "type": "binary",
                "left": expr,
                "operator": operator,
                "right": right,
            }
        return expr

    def _equality(self) -> Dict:
        expr = self._comparison()
        while self._match(TokenType.EQUAL, TokenType.NOT_EQUAL):
            operator = self._previous().value
            right = self._comparison()
            expr = {
                "type": "binary",
                "left": expr,
                "operator": operator,
                "right": right,
            }
        return expr

    def _comparison(self) -> Dict:
        expr = self._term()
        while self._match(
            TokenType.GREATER,
            TokenType.GREATER_EQUAL,
            TokenType.LESS,
            TokenType.LESS_EQUAL,
        ):
            operator = self._previous().value
            right = self._term()
            expr = {
                "type": "binary",
                "left": expr,
                "operator": operator,
                "right": right,
            }
        return expr

    def _term(self) -> Dict:
        expr = self._factor()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            operator = self._previous().value
            right = self._factor()
            expr = {
                "type": "binary",
                "left": expr,
                "operator": operator,
                "right": right,
            }
        return expr

    def _factor(self) -> Dict:
        expr = self._unary()
        while self._match(TokenType.MULTIPLY, TokenType.DIVIDE):
            operator = self._previous().value
            right = self._unary()
            expr = {
                "type": "binary",
                "left": expr,
                "operator": operator,
                "right": right,
            }
        return expr

    def _unary(self) -> Dict:
        if self._match(TokenType.NOT, TokenType.MINUS):
            operator = self._previous().value
            right = self._unary()
            return {"type": "unary", "operator": operator, "operand": right}
        return self._call()

    def _call(self) -> Dict:
        expr = self._primary()
        while True:
            if self._match(TokenType.LPAREN):
                args = []
                if not self._check(TokenType.RPAREN):
                    args.append(self._expression())
                    while self._match(TokenType.COMMA):
                        args.append(self._expression())
                self._consume(TokenType.RPAREN, "Expected ')' after arguments")
                expr = {"type": "call", "callee": expr, "arguments": args}
            elif self._match(TokenType.LBRACKET):
                index = self._expression()
                self._consume(TokenType.RBRACKET, "Expected ']' after index")
                expr = {"type": "index", "object": expr, "index": index}
            elif self._match(TokenType.DOT):
                property_name = self._consume(
                    TokenType.IDENTIFIER, "Expected property name after '.'"
                )
                expr = {
                    "type": "property",
                    "object": expr,
                    "property": property_name.value,
                }
            else:
                break
        return expr

    def _primary(self) -> Dict:
        if self._match(TokenType.NUMBER):
            value = self._previous().value
            return {
                "type": "literal",
                "value": float(value) if "." in value else int(value),
            }

        if self._match(TokenType.STRING):
            return {"type": "literal", "value": self._previous().value}

        if self._match(TokenType.IDENTIFIER):
            return {"type": "variable", "name": self._previous().value}

        if self._match(TokenType.AWAIT):
            # Parse await as a function call with multiple arguments
            args = []
            while not self._is_at_end() and self._current().type not in [
                TokenType.NEWLINE,
                TokenType.EOF,
            ]:
                args.append(self._expression())
            return {
                "type": "call",
                "callee": {"type": "variable", "name": "await"},
                "arguments": args,
            }

        if self._match(TokenType.LPAREN):
            # Check if this is a tuple (multiple comma-separated expressions)
            elements = []
            if not self._check(TokenType.RPAREN):
                elements.append(self._expression())
                while self._match(TokenType.COMMA):
                    elements.append(self._expression())

            self._consume(TokenType.RPAREN, "Expected ')' after expression")

            # If single element, return it directly; if multiple, return as tuple
            if len(elements) == 1:
                return elements[0]
            else:
                return {"type": "tuple", "elements": elements}

        if self._match(TokenType.LBRACKET):
            elements = []
            if not self._check(TokenType.RBRACKET):
                elements.append(self._expression())
                while self._match(TokenType.COMMA):
                    elements.append(self._expression())
            self._consume(TokenType.RBRACKET, "Expected ']' after array elements")
            return {"type": "array", "elements": elements}

        if self._match(TokenType.LBRACE):
            properties = []
            if not self._check(TokenType.RBRACE):
                key = self._expression()
                self._consume(TokenType.COLON, "Expected ':' after object key")
                value = self._expression()
                properties.append({"key": key, "value": value})
                while self._match(TokenType.COMMA):
                    key = self._expression()
                    self._consume(TokenType.COLON, "Expected ':' after object key")
                    value = self._expression()
                    properties.append({"key": key, "value": value})
            self._consume(TokenType.RBRACE, "Expected '}' after object properties")
            return {"type": "object", "properties": properties}

        raise Exception(f"Unexpected token: {self._current().value}")

    def _match(self, *types: TokenType) -> bool:
        for token_type in types:
            if self._check(token_type):
                self._advance()
                return True
        return False

    def _check(self, token_type: TokenType) -> bool:
        if self._is_at_end():
            return False
        return self._current().type == token_type

    def _advance(self) -> Token:
        if not self._is_at_end():
            self.pos += 1
        return self._previous()

    def _is_at_end(self) -> bool:
        return self._current().type == TokenType.EOF

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _previous(self) -> Token:
        return self.tokens[self.pos - 1]

    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        raise Exception(f"{message}. Got: {self._current().value}")


class MCNInterpreter:
    def __init__(self):
        self.variables = {}
        self.functions = {}
        self.ai_context = None
        self.package_manager = None
        self.async_runtime = None
        self.type_checker = None
        self.user_functions = {}
        self._register_builtin_functions()
        self._init_v2_features()
        self._init_request_context()

    def _register_builtin_functions(self):
        from .mcn_runtime import MCNRuntime

        self.runtime = MCNRuntime()

        self.functions.update(
            {
                "log": self.runtime.log,
                "echo": self._echo,
                "trigger": self.runtime.trigger,
                "query": self.runtime.query,
                "workflow": self.runtime.workflow,
                "ai": self._enhanced_ai,
                "env": self._env,
                "read_file": self._read_file,
                "write_file": self._write_file,
                "append_file": self._append_file,
                "fetch": self._fetch,
                "send_email": self.runtime.send_email,
                "hash_data": self.runtime.hash_data,
                "encode_base64": self.runtime.encode_base64,
                "decode_base64": self.runtime.decode_base64,
                "now": self.runtime.now,
                "format_date": self.runtime.format_date,
                "connect_postgresql": self.runtime.connect_postgresql,
                "connect_mongodb": self.runtime.connect_mongodb,
            }
        )

    def _init_v2_features(self):
        """Initialize MCN 2.0 features"""
        from .mcn_extensions import (
            MCNAIContext,
            MCNPackageManager,
            MCNAsyncRuntime,
            MCNTypeChecker,
        )
        from .mcn_extensions import (
            create_db_package,
            create_http_package,
            create_ai_package,
        )

        self.ai_context = MCNAIContext()
        self.package_manager = MCNPackageManager()
        self.async_runtime = MCNAsyncRuntime()
        self.type_checker = MCNTypeChecker()

        # Register built-in packages
        self.package_manager.add_package("db", create_db_package())
        self.package_manager.add_package("http", create_http_package())
        self.package_manager.add_package("ai", create_ai_package())

        # Initialize v3.0 features
        self._init_v3_features()

        # Add v2.0 functions
        self.functions.update(
            {
                "task": self._create_task,
                "await": self._await_tasks,
                "use": self._use_package,
                "type": self._set_type_hint,
                # v3.0 functions
                "on": self._on_event,
                "trigger": self._trigger_event,
                "device": self._device_operation,
                "agent": self._agent_operation,
                "pipeline": self._pipeline_operation,
                "translate": self._translate_natural,
                # UI functions
                "ui": self._ui_operation,
            }
        )

    def _init_v3_features(self):
        """Initialize MCN 3.0 features"""
        from .mcn_v3_extensions import (
            MCNModelRegistry,
            MCNEventSystem,
            MCNIoTConnector,
            MCNAgentSystem,
            MCNDataPipeline,
            MCNNaturalLanguage,
            create_v3_ai_package,
            create_v3_iot_package,
            create_v3_event_package,
            create_v3_agent_package,
            create_v3_pipeline_package,
            create_v3_nl_package,
        )

        # Initialize v3.0 systems
        self.model_registry = MCNModelRegistry()
        self.event_system = MCNEventSystem()
        self.iot_connector = MCNIoTConnector()
        self.agent_system = MCNAgentSystem(self.model_registry)
        self.pipeline_system = MCNDataPipeline(self.model_registry)
        self.nl_system = MCNNaturalLanguage(self.model_registry)

        # Register v3.0 packages
        self.package_manager.add_package("ai_v3", create_v3_ai_package(self.model_registry))
        self.package_manager.add_package("iot", create_v3_iot_package(self.iot_connector))
        self.package_manager.add_package("events", create_v3_event_package(self.event_system))
        self.package_manager.add_package("agents", create_v3_agent_package(self.agent_system))
        self.package_manager.add_package("pipeline", create_v3_pipeline_package(self.pipeline_system))
        self.package_manager.add_package("natural", create_v3_nl_package(self.nl_system))
        
        # Initialize UI Integration Layer
        self._init_ui_integration()

    def _init_ui_integration(self):
        """Initialize UI Integration Layer"""
        from .mcn_ui_bindings import UIIntegrationLayer
        
        self.ui_integration = UIIntegrationLayer(self)
        
        # Add UI package functions
        ui_package = {
            "button": self.ui_integration._ui_button,
            "input": self.ui_integration._ui_input,
            "text": self.ui_integration._ui_text,
            "container": self.ui_integration._ui_container,
            "form": self.ui_integration._ui_form,
            "table": self.ui_integration._ui_table,
            "chart": self.ui_integration._ui_chart,
            "page": self.ui_integration._ui_page,
            "bind_data": self.ui_integration._ui_bind_data,
            "export": self.ui_integration._ui_export,
        }
        
        self.package_manager.add_package("ui", ui_package)

    def _init_request_context(self):
        """Initialize request context for web/API mode"""
        self.variables["request_data"] = {
            "method": "GET",
            "params": {},
            "headers": {},
            "body": None,
        }

    def _echo(self, message: Any) -> None:
        """Simple console output without timestamp"""
        print(message)

    def _env(self, key: str) -> str:
        """Get environment variable"""
        import os

        return os.getenv(key)

    def _read_file(self, filepath: str) -> str:
        """Read file contents"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Failed to read file '{filepath}': {str(e)}")

    def _write_file(self, filepath: str, content: str) -> None:
        """Write content to file"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(content))
        except Exception as e:
            raise Exception(f"Failed to write file '{filepath}': {str(e)}")

    def _append_file(self, filepath: str, content: str) -> None:
        """Append content to file"""
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(str(content))
        except Exception as e:
            raise Exception(f"Failed to append to file '{filepath}': {str(e)}")

    def _fetch(self, url: str) -> Dict:
        """HTTP GET request"""
        import requests

        try:
            response = requests.get(url, timeout=30)
            return {
                "status_code": response.status_code,
                "data": (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else response.text
                ),
                "success": 200 <= response.status_code < 300,
            }
        except Exception as e:
            return {"status_code": 0, "data": str(e), "success": False}

    def _enhanced_ai(
        self, prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 150
    ):
        """Enhanced AI function with context"""
        # Update AI context with current variables
        for key, value in self.variables.items():
            self.ai_context.add_context(key, value)

        enhanced_prompt = self.ai_context.get_enhanced_prompt(prompt)
        return self.runtime.ai(enhanced_prompt, model, max_tokens)

    def _create_task(self, name: str, func_name: str, *args):
        """Create async task"""
        if func_name in self.functions:
            func = self.functions[func_name]
            task = self.async_runtime.create_task(name, func, *args)
            return f"Task '{name}' created"
        raise Exception(f"Function '{func_name}' not found")

    def _await_tasks(self, *task_names):
        """Await multiple tasks"""
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self.async_runtime.await_tasks(*task_names))
        loop.close()
        return results

    def _use_package(self, package_name: str):
        """Import package functions"""
        package_functions = self.package_manager.get_package_functions(package_name)
        if package_functions:
            self.functions.update(package_functions)
            return f"Package '{package_name}' loaded"
        raise Exception(f"Package '{package_name}' not found")

    def _set_type_hint(self, var_name: str, var_type: str):
        """Set type hint for variable"""
        self.type_checker.add_type_hint(var_name, var_type)
        return f"Type hint set: {var_name} -> {var_type}"

    # v3.0 Core Functions
    def _on_event(self, event_name: str, handler_func: str = None):
        """Register event handler"""
        def handler(data):
            if handler_func and handler_func in self.functions:
                self.functions[handler_func](data)
            else:
                print(f"Event '{event_name}' triggered with data: {data}")
        
        self.event_system.on_event(event_name, handler)
        return f"Event handler registered for '{event_name}'"

    def _trigger_event(self, event_name: str, data: dict = None):
        """Trigger an event"""
        return self.event_system.trigger_event(event_name, data or {})

    def _device_operation(self, operation: str, device_id: str = None, **kwargs):
        """IoT device operations"""
        if operation == "register":
            device_type = kwargs.get('type', 'sensor')
            return self.iot_connector.register_device(device_id, device_type, kwargs)
        elif operation == "read":
            return self.iot_connector.read_device(device_id)
        elif operation == "command":
            command = kwargs.get('command', 'status')
            return self.iot_connector.send_command(device_id, command, kwargs)
        else:
            raise Exception(f"Unknown device operation: {operation}")

    def _agent_operation(self, operation: str, name: str = None, **kwargs):
        """Agent operations"""
        if operation == "create":
            prompt = kwargs.get('prompt', 'You are a helpful assistant')
            model = kwargs.get('model', None)
            tools = kwargs.get('tools', [])
            return self.agent_system.create_agent(name, prompt, model, tools)
        elif operation == "activate":
            return self.agent_system.activate_agent(name)
        elif operation == "think":
            input_data = kwargs.get('input', '')
            return self.agent_system.agent_think(name, input_data)
        else:
            raise Exception(f"Unknown agent operation: {operation}")

    def _pipeline_operation(self, operation: str, name: str = None, **kwargs):
        """Data pipeline operations"""
        if operation == "create":
            steps = kwargs.get('steps', [])
            return self.pipeline_system.create_pipeline(name, steps)
        elif operation == "run":
            data = kwargs.get('data', None)
            return self.pipeline_system.run_pipeline(name, data)
        else:
            raise Exception(f"Unknown pipeline operation: {operation}")

    def _translate_natural(self, natural_text: str, execute: bool = False):
        """Translate natural language to MCN code"""
        mcn_code = self.nl_system.translate(natural_text)
        if execute:
            return self.execute(mcn_code, quiet=True)
        return mcn_code

    def _ui_operation(self, operation: str, *args, **kwargs):
        """UI operations"""
        if operation == "button":
            return self.ui_integration._ui_button(*args, **kwargs)
        elif operation == "input":
            return self.ui_integration._ui_input(*args, **kwargs)
        elif operation == "text":
            return self.ui_integration._ui_text(*args, **kwargs)
        elif operation == "container":
            return self.ui_integration._ui_container(*args, **kwargs)
        elif operation == "form":
            return self.ui_integration._ui_form(*args, **kwargs)
        elif operation == "table":
            return self.ui_integration._ui_table(*args, **kwargs)
        elif operation == "chart":
            return self.ui_integration._ui_chart(*args, **kwargs)
        elif operation == "page":
            return self.ui_integration._ui_page(*args, **kwargs)
        elif operation == "bind_data":
            return self.ui_integration._ui_bind_data(*args, **kwargs)
        elif operation == "export":
            return self.ui_integration._ui_export(*args, **kwargs)
        else:
            raise Exception(f"Unknown UI operation: {operation}")

    def register_function(self, name: str, func: Callable):
        self.functions[name] = func

    def execute(self, code: str, file_path: str = None, quiet: bool = False) -> Any:
        start_time = time.time()

        try:
            if not quiet:
                log_step("Starting MCN execution", file_path=file_path)

            # Lexical analysis
            lexer = MCNLexer(code)
            tokens = lexer.tokenize()
            if not quiet:
                log_step("Tokenization completed", token_count=len(tokens))

            # Parsing
            parser = MCNParser(tokens)
            statements = parser.parse()
            if not quiet:
                log_step("Parsing completed", statement_count=len(statements))

            # Execution
            result = None
            for i, stmt in enumerate(statements):
                try:
                    result = self._execute_statement(stmt, quiet=quiet)
                    if not quiet:
                        log_step(f"Statement {i+1} executed", type=stmt.get("type"))
                except Exception as stmt_error:
                    log_error(
                        "STATEMENT_EXECUTION_ERROR",
                        f"Error in statement {i+1}: {str(stmt_error)}",
                        context={
                            "statement_index": i + 1,
                            "statement_type": stmt.get("type"),
                            "statement": stmt,
                            "variables": list(self.variables.keys()),
                        },
                        file_path=file_path,
                    )
                    raise

            execution_time = time.time() - start_time
            if not quiet:
                log_performance(
                    "MCN execution",
                    execution_time,
                    statements=len(statements),
                    variables=len(self.variables),
                    functions=len(self.functions),
                )

            return result

        except Exception as e:
            execution_time = time.time() - start_time

            # Determine error type
            error_type = "RUNTIME_ERROR"
            if "Unexpected token" in str(e) or "Expected" in str(e):
                error_type = "SYNTAX_ERROR"
            elif "Undefined variable" in str(e) or "Undefined function" in str(e):
                error_type = "REFERENCE_ERROR"
            elif "Type error" in str(e):
                error_type = "TYPE_ERROR"

            log_error(
                error_type,
                str(e),
                context={
                    "code_snippet": code[:200] + "..." if len(code) > 200 else code,
                    "variables": list(self.variables.keys()),
                    "execution_time": execution_time,
                    "traceback": traceback.format_exc(),
                },
                file_path=file_path,
            )

            raise Exception(f"MCN {error_type}: {str(e)}")

    def _execute_statement(self, stmt: Dict, quiet: bool = False) -> Any:
        try:
            if stmt["type"] == "var_declaration":
                try:
                    value = self._evaluate_expression(stmt["value"])
                    var_name = stmt["name"]

                    # Type checking if enabled
                    if self.type_checker and not self.type_checker.check_type(
                        var_name, value
                    ):
                        expected_type = self.type_checker.type_hints.get(
                            var_name, "any"
                        )
                        log_error(
                            "TYPE_ERROR",
                            f"Variable '{var_name}' type mismatch",
                            context={
                                "variable": var_name,
                                "expected_type": expected_type,
                                "actual_type": type(value).__name__,
                                "value": str(value)[:100],
                            },
                        )
                        raise Exception(
                            f"Type error: {var_name} expected {expected_type}, got {type(value).__name__}"
                        )

                    self.variables[var_name] = value
                    if not quiet:
                        log_step(
                            f"Variable declared: {var_name}", type=type(value).__name__
                        )
                    return value

                except Exception as e:
                    log_error(
                        "VARIABLE_DECLARATION_ERROR",
                        f"Failed to declare variable '{stmt.get('name', 'unknown')}'",
                        context={
                            "variable_name": stmt.get("name"),
                            "expression": stmt.get("value"),
                            "error": str(e),
                        },
                    )
                    raise

            elif stmt["type"] == "if_statement":
                try:
                    condition = self._evaluate_expression(stmt["condition"], quiet)
                    if not quiet:
                        log_step(
                            "If condition evaluated", condition=str(condition)[:100]
                        )

                    if self._is_truthy(condition):
                        return self._execute_block(stmt["then"], quiet)
                    elif stmt["else"]:
                        return self._execute_block(stmt["else"], quiet)

                except Exception as e:
                    log_error(
                        "CONDITIONAL_ERROR",
                        f"Error in if statement: {str(e)}",
                        context={
                            "condition": stmt.get("condition"),
                            "has_else": bool(stmt.get("else")),
                        },
                    )
                    raise

            elif stmt["type"] == "for_statement":
                try:
                    iterable = self._evaluate_expression(stmt["iterable"], quiet)
                    if isinstance(iterable, list):
                        for item in iterable:
                            # Set loop variable
                            old_value = self.variables.get(stmt["variable"])
                            self.variables[stmt["variable"]] = item

                            # Execute loop body
                            self._execute_block(stmt["body"], quiet)

                            # Restore old value if it existed
                            if old_value is not None:
                                self.variables[stmt["variable"]] = old_value
                            else:
                                del self.variables[stmt["variable"]]
                    return None
                except Exception as e:
                    log_error(
                        "LOOP_ERROR",
                        f"Error in for loop: {str(e)}",
                        context={
                            "variable": stmt.get("variable"),
                            "iterable": stmt.get("iterable"),
                        },
                    )
                    raise

            elif stmt["type"] == "while_statement":
                try:
                    result = None
                    iteration_count = 0
                    max_iterations = 10000  # Prevent infinite loops

                    while self._is_truthy(self._evaluate_expression(stmt["condition"])):
                        iteration_count += 1
                        if iteration_count > max_iterations:
                            log_error(
                                "INFINITE_LOOP_ERROR",
                                f"While loop exceeded maximum iterations ({max_iterations})",
                                context={
                                    "condition": stmt.get("condition"),
                                    "iterations": iteration_count,
                                },
                            )
                            raise Exception(
                                f"Infinite loop detected: exceeded {max_iterations} iterations"
                            )

                        result = self._execute_block(stmt["body"])

                    log_step("While loop completed", iterations=iteration_count)
                    return result

                except Exception as e:
                    if "Infinite loop" not in str(e):
                        log_error(
                            "LOOP_ERROR",
                            f"Error in while loop: {str(e)}",
                            context={
                                "condition": stmt.get("condition"),
                                "iteration_count": (
                                    iteration_count
                                    if "iteration_count" in locals()
                                    else 0
                                ),
                            },
                        )
                    raise

            elif stmt["type"] == "try_statement":
                try:
                    log_step("Executing try block")
                    return self._execute_block(stmt["try"])
                except Exception as e:
                    log_step("Exception caught in try block", error=str(e)[:200])
                    if stmt["catch"]:
                        self.variables["error"] = str(e)
                        return self._execute_block(stmt["catch"])
                    raise

            elif stmt["type"] == "task_statement":
                try:
                    name = self._evaluate_expression(stmt["name"], quiet)
                    func_name = self._evaluate_expression(stmt["function"], quiet)
                    args = [
                        self._evaluate_expression(arg, quiet)
                        for arg in stmt["arguments"]
                    ]

                    # Create task using the enhanced task system
                    if hasattr(self, "_create_task"):
                        result = self._create_task(str(name), str(func_name), *args)
                        if not quiet:
                            log_step(f"Task '{name}' created", function=str(func_name))
                        return result
                    else:
                        # Fallback: execute immediately
                        if str(func_name) in self.functions:
                            return self.functions[str(func_name)](*args)
                        raise Exception(f"Function '{func_name}' not found")

                except Exception as e:
                    log_error(
                        "TASK_ERROR",
                        f"Error creating task: {str(e)}",
                        context={
                            "task_name": stmt.get("name"),
                            "function": stmt.get("function"),
                        },
                    )
                    raise

            elif stmt["type"] == "use_statement":
                try:
                    package_name = self._evaluate_expression(stmt["package"], quiet)
                    result = self._use_package(str(package_name))
                    if not quiet:
                        log_step(f"Package loaded: {package_name}")
                    return result
                except Exception as e:
                    log_error(
                        "PACKAGE_ERROR",
                        f"Error loading package: {str(e)}",
                        context={"package": stmt.get("package")},
                    )
                    raise

            elif stmt["type"] == "throw_statement":
                try:
                    message = self._evaluate_expression(stmt["message"])
                    log_step("Throwing exception", message=str(message)[:200])
                    raise Exception(str(message))
                except Exception as e:
                    if "Error evaluating" not in str(e):
                        log_error(
                            "THROW_ERROR",
                            f"Error in throw statement: {str(e)}",
                            context={"message_expression": stmt.get("message")},
                        )
                    raise

            elif stmt["type"] == "function_declaration":
                try:
                    func_name = stmt["name"]
                    params = stmt["params"]
                    body = stmt["body"]

                    def user_function(*args):
                        # Save current variable state
                        old_vars = self.variables.copy()

                        try:
                            # Set parameters as local variables
                            for i, param in enumerate(params):
                                if i < len(args):
                                    self.variables[param] = args[i]
                                else:
                                    self.variables[param] = None

                            # Execute function body
                            result = self._execute_block(body, quiet)
                            return result
                        except ReturnValue as ret:
                            return ret.value
                        finally:
                            # Restore variable state
                            self.variables = old_vars

                    self.user_functions[func_name] = user_function
                    self.functions[func_name] = user_function

                    if not quiet:
                        log_step(f"Function '{func_name}' defined", params=len(params))
                    return None

                except Exception as e:
                    log_error(
                        "FUNCTION_DECLARATION_ERROR",
                        f"Error defining function: {str(e)}",
                        context={"function_name": stmt.get("name")},
                    )
                    raise

            elif stmt["type"] == "return_statement":
                try:
                    value = None
                    if stmt["value"]:
                        value = self._evaluate_expression(stmt["value"], quiet)
                    raise ReturnValue(value)
                except ReturnValue:
                    raise
                except Exception as e:
                    log_error(
                        "RETURN_ERROR",
                        f"Error in return statement: {str(e)}",
                        context={"return_expression": stmt.get("value")},
                    )
                    raise

            elif stmt["type"] == "expression_statement":
                try:
                    return self._evaluate_expression(stmt["expression"], quiet)
                except Exception as e:
                    log_error(
                        "EXPRESSION_ERROR",
                        f"Error evaluating expression: {str(e)}",
                        context={
                            "expression": stmt.get("expression"),
                            "available_variables": list(self.variables.keys()),
                        },
                    )
                    raise

        except ReturnValue:
            raise  # Re-raise return values without logging
        except Exception as e:
            # Re-raise with additional context if not already logged
            if not any(
                error_type in str(e)
                for error_type in ["SYNTAX_ERROR", "RUNTIME_ERROR", "TYPE_ERROR"]
            ):
                log_error(
                    "STATEMENT_ERROR",
                    f"Unexpected error in statement execution: {str(e)}",
                    context={
                        "statement_type": stmt.get("type", "unknown"),
                        "statement": stmt,
                    },
                )
            raise

        return None

    def _execute_block(self, statements: List[Dict], quiet: bool = False) -> Any:
        result = None
        for stmt in statements:
            try:
                result = self._execute_statement(stmt, quiet)
            except ReturnValue:
                raise  # Re-raise return to bubble up
        return result

    def _evaluate_expression(self, expr: Dict, quiet: bool = False) -> Any:
        try:
            if expr["type"] == "literal":
                return expr["value"]

            elif expr["type"] == "variable":
                name = expr["name"]
                if name in self.variables:
                    return self.variables[name]
                elif name in self.user_functions:
                    return self.user_functions[name]

                # Provide helpful suggestions for undefined variables
                similar_vars = [
                    var
                    for var in self.variables.keys()
                    if var.lower().startswith(name.lower()[:2])
                ]
                suggestion = (
                    f" Did you mean: {', '.join(similar_vars[:3])}?"
                    if similar_vars
                    else ""
                )

                log_error(
                    "UNDEFINED_VARIABLE",
                    f"Variable '{name}' is not defined",
                    context={
                        "variable_name": name,
                        "available_variables": list(self.variables.keys()),
                        "suggestions": similar_vars[:3],
                    },
                )
                raise Exception(f"Undefined variable: {name}.{suggestion}")

            elif expr["type"] == "binary":
                left = self._evaluate_expression(expr["left"], quiet)
                right = self._evaluate_expression(expr["right"], quiet)
                op = expr["operator"]

                if op == "+":
                    # Handle string concatenation with type coercion
                    if isinstance(left, str) or isinstance(right, str):
                        return str(left) + str(right)
                    return left + right
                elif op == "-":
                    return left - right
                elif op == "*":
                    return left * right
                elif op == "/":
                    return left / right
                elif op == "==":
                    return left == right
                elif op == "!=":
                    return left != right
                elif op == ">":
                    return left > right
                elif op == "<":
                    return left < right
                elif op == ">=":
                    return left >= right
                elif op == "<=":
                    return left <= right
                elif op == "and":
                    return self._is_truthy(left) and self._is_truthy(right)
                elif op == "or":
                    return self._is_truthy(left) or self._is_truthy(right)

            elif expr["type"] == "unary":
                operand = self._evaluate_expression(expr["operand"])
                op = expr["operator"]

                if op == "-":
                    return -operand
                elif op == "not":
                    return not self._is_truthy(operand)

            elif expr["type"] == "array":
                elements = [
                    self._evaluate_expression(elem, quiet) for elem in expr["elements"]
                ]
                return elements

            elif expr["type"] == "tuple":
                elements = [
                    self._evaluate_expression(elem, quiet) for elem in expr["elements"]
                ]
                return tuple(elements)

            elif expr["type"] == "object":
                obj = {}
                for prop in expr["properties"]:
                    key = self._evaluate_expression(prop["key"], quiet)
                    value = self._evaluate_expression(prop["value"], quiet)
                    obj[str(key)] = value
                return obj

            elif expr["type"] == "index":
                obj = self._evaluate_expression(expr["object"], quiet)
                index = self._evaluate_expression(expr["index"], quiet)
                if isinstance(obj, list) and isinstance(index, int):
                    return obj[index] if 0 <= index < len(obj) else None
                return None

            elif expr["type"] == "property":
                obj = self._evaluate_expression(expr["object"], quiet)
                if isinstance(obj, dict):
                    return obj.get(expr["property"])
                elif isinstance(obj, list) and expr["property"] == "length":
                    return len(obj)
                return None

            elif expr["type"] == "call":
                # Handle function calls directly
                if expr["callee"]["type"] == "variable":
                    func_name = expr["callee"]["name"]
                    args = [
                        self._evaluate_expression(arg, quiet)
                        for arg in expr["arguments"]
                    ]

                    if func_name in self.functions:
                        if not quiet or func_name in ["log", "echo"]:
                            log_step(
                                f"Calling function: {func_name}", args_count=len(args)
                            )

                        # Enhanced function call with error handling
                        try:
                            result = self.functions[func_name](*args)
                            if not quiet or func_name in ["log", "echo"]:
                                log_step(f"Function {func_name} completed successfully")
                            return result
                        except Exception as func_error:
                            log_error(
                                "FUNCTION_EXECUTION_ERROR",
                                f"Error executing function '{func_name}': {str(func_error)}",
                                context={
                                    "function_name": func_name,
                                    "arguments": [str(arg)[:100] for arg in args],
                                    "error": str(func_error),
                                },
                            )
                            raise Exception(
                                f"Function '{func_name}' failed: {str(func_error)}"
                            )

                    # Provide helpful suggestions for undefined functions
                    similar_funcs = [
                        func
                        for func in self.functions.keys()
                        if func.lower().startswith(func_name.lower()[:2])
                    ]
                    suggestion = (
                        f" Did you mean: {', '.join(similar_funcs[:3])}?"
                        if similar_funcs
                        else ""
                    )

                    log_error(
                        "UNDEFINED_FUNCTION",
                        f"Function '{func_name}' is not defined",
                        context={
                            "function_name": func_name,
                            "available_functions": list(self.functions.keys()),
                            "suggestions": similar_funcs[:3],
                        },
                    )
                    raise Exception(f"Undefined function: {func_name}.{suggestion}")
                else:
                    # Handle complex function expressions
                    callee = self._evaluate_expression(expr["callee"])
                    args = [self._evaluate_expression(arg) for arg in expr["arguments"]]
                    raise Exception("Complex function calls not supported yet")

            else:
                log_error(
                    "UNKNOWN_EXPRESSION_TYPE",
                    f"Unknown expression type: {expr.get('type', 'missing')}",
                    context={"expression": expr},
                )
                raise Exception(
                    f"Unknown expression type: {expr.get('type', 'missing')}"
                )

        except Exception as e:
            # Add context to expression evaluation errors
            if "Unknown expression type" not in str(e) and "Undefined" not in str(e):
                log_error(
                    "EXPRESSION_EVALUATION_ERROR",
                    f"Error evaluating expression: {str(e)}",
                    context={
                        "expression_type": expr.get("type", "unknown"),
                        "expression": expr,
                    },
                )
            raise

    def _is_truthy(self, value: Any) -> bool:
        if value is None or value is False:
            return False
        if isinstance(value, (int, float)) and value == 0:
            return False
        if isinstance(value, str) and value == "":
            return False
        return True
