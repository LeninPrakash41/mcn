"""
MCN Abstract Syntax Tree node definitions.

Pure data structures — no parsing or evaluation logic here.
Every node carries source location (line, col) for precise error messages
and IDE tooling (hover, go-to-definition, inline diagnostics).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


# ── Base ───────────────────────────────────────────────────────────────────────

@dataclass
class Node:
    """Base AST node. All nodes carry source location."""
    line: int = 0
    col: int = 0


# ── Statements ─────────────────────────────────────────────────────────────────

@dataclass
class VarDecl(Node):
    """var name [: type] = expr"""
    name:      str           = ""
    value:     "Expr"        = None
    type_hint: Optional[str] = None   # e.g. "int", "str", "bool", "list", "object"


@dataclass
class IfStmt(Node):
    """if condition\n    body\nelse\n    body"""
    condition: "Expr" = None
    then_body: List["Stmt"] = field(default_factory=list)
    else_body: List["Stmt"] = field(default_factory=list)


@dataclass
class ForStmt(Node):
    """for variable in iterable  OR  for index, variable in iterable"""
    variable:  str             = ""
    index_var: Optional[str]   = None   # set when 'for i, val in list'
    iterable:  "Expr"          = None
    body:      List["Stmt"]    = field(default_factory=list)


@dataclass
class WhileStmt(Node):
    """while condition\n    body"""
    condition: "Expr" = None
    body: List["Stmt"] = field(default_factory=list)


@dataclass
class TryStmt(Node):
    """try / catch [var] / finally"""
    try_body:     List["Stmt"]  = field(default_factory=list)
    catch_var:    Optional[str] = None   # e.g. 'catch e' → e.message, e.type
    catch_body:   List["Stmt"]  = field(default_factory=list)
    finally_body: List["Stmt"]  = field(default_factory=list)


@dataclass
class ThrowStmt(Node):
    """throw expr"""
    message: "Expr" = None


@dataclass
class TaskStmt(Node):
    """task name func_name [args...]"""
    name: "Expr" = None
    function: "Expr" = None
    arguments: List["Expr"] = field(default_factory=list)


@dataclass
class UseStmt(Node):
    """use package_name"""
    package: "Expr" = None


@dataclass
class FunctionDecl(Node):
    """function name(params)\n    body"""
    name:        str               = ""
    params:      List[str]         = field(default_factory=list)
    defaults:    Dict[str, "Expr"] = field(default_factory=dict)
    body:        List["Stmt"]      = field(default_factory=list)
    param_types: Dict[str, str]    = field(default_factory=dict)  # param → type hint
    return_type: Optional[str]     = None                          # return type hint


@dataclass
class ReturnStmt(Node):
    """return [expr]"""
    value: Optional["Expr"] = None


@dataclass
class AssignStmt(Node):
    """name = expr  — re-assign an existing variable (no 'var' keyword)"""
    name:  str    = ""
    value: "Expr" = None

@dataclass
class PropertyAssignStmt(Node):
    """obj.key = expr  — assign to an object property"""
    object: "Expr" = None
    prop:   str    = ""
    value:  "Expr" = None

@dataclass
class IndexAssignStmt(Node):
    """obj[idx] = expr  — assign to an array index or dict key"""
    object: "Expr" = None
    index:  "Expr" = None
    value:  "Expr" = None

@dataclass
class CompoundAssignStmt(Node):
    """name OP= expr  — shorthand: x += 1, x -= 1, x *= 2, x /= 2, x %= 3"""
    name:  str    = ""
    op:    str    = "+"   # "+", "-", "*", "/", "%"
    value: "Expr" = None

@dataclass
class BreakStmt(Node):
    """break  — exit the innermost loop"""

@dataclass
class ContinueStmt(Node):
    """continue  — skip to next iteration of the innermost loop"""

@dataclass
class AssertStmt(Node):
    """assert condition [, message]"""
    condition: "Expr" = None
    message:   Optional["Expr"] = None

@dataclass
class TestDecl(Node):
    """
    test "description"
        assert expr [, message]
        ...
    """
    description: str         = ""
    body:        List["Stmt"] = field(default_factory=list)

@dataclass
class ExprStmt(Node):
    """A statement that is just an expression (function call, assignment, etc.)"""
    expression: "Expr" = None


@dataclass
class Program(Node):
    """Root node of every MCN program."""
    body: List["Stmt"] = field(default_factory=list)


# ── Expressions ────────────────────────────────────────────────────────────────

@dataclass
class Literal(Node):
    """A literal value: number, string."""
    value: Any = None


@dataclass
class Variable(Node):
    """A name reference."""
    name: str = ""


@dataclass
class Binary(Node):
    """left op right"""
    left: "Expr" = None
    operator: str = ""
    right: "Expr" = None


@dataclass
class Unary(Node):
    """op operand  (e.g. -x, not x)"""
    operator: str = ""
    operand: "Expr" = None


@dataclass
class Call(Node):
    """callee(arguments)"""
    callee: "Expr" = None
    arguments: List["Expr"] = field(default_factory=list)


@dataclass
class Index(Node):
    """object[index]"""
    object: "Expr" = None
    index: "Expr" = None


@dataclass
class Property(Node):
    """object.name  or  object?.name (safe=True)"""
    object: "Expr" = None
    name:   str    = ""
    safe:   bool   = False   # True for ?. — returns None if object is None


@dataclass
class Array(Node):
    """[elements...]"""
    elements: List["Expr"] = field(default_factory=list)


@dataclass
class MCNObject(Node):
    """{key: value, ...}"""
    # Each entry is (key_expr, value_expr)
    properties: List[Tuple["Expr", "Expr"]] = field(default_factory=list)


@dataclass
class MCNTuple(Node):
    """(a, b, c)  — used as SQL parameter tuples, etc."""
    elements: List["Expr"] = field(default_factory=list)

@dataclass
class TernaryExpr(Node):
    """condition ? then_expr : else_expr"""
    condition: "Expr" = None
    then_expr: "Expr" = None
    else_expr: "Expr" = None

@dataclass
class ArrowFunc(Node):
    """(x, y) => expr   or   x => expr   (lambda / anonymous function)"""
    params: List[str]  = field(default_factory=list)
    body:   "Expr"     = None   # single-expression body; stmt body TBD


# ── 2030 Language Primitives ───────────────────────────────────────────────────

@dataclass
class ContractField(Node):
    """A single field in a contract: name: type"""
    name:      str = ""
    type_name: str = ""


@dataclass
class ContractDecl(Node):
    """
    contract User
        id:    int
        name:  str
        email: str
    """
    name:   str                 = ""
    fields: List[ContractField] = field(default_factory=list)


@dataclass
class StageDecl(Node):
    """A single stage inside a pipeline declaration."""
    name:     str               = ""
    params:   List[str]         = field(default_factory=list)
    defaults: Dict[str, "Expr"] = field(default_factory=dict)
    body:     List["Stmt"]      = field(default_factory=list)


@dataclass
class PipelineDecl(Node):
    """
    pipeline data_pipeline
        stage extract
            ...
        stage transform(data)
            ...
    """
    name:   str             = ""
    stages: List[StageDecl] = field(default_factory=list)


@dataclass
class EndpointDecl(Node):
    """A single endpoint inside a service declaration."""
    name:     str               = ""
    params:   List[str]         = field(default_factory=list)
    defaults: Dict[str, "Expr"] = field(default_factory=dict)
    body:     List["Stmt"]      = field(default_factory=list)


@dataclass
class ServiceDecl(Node):
    """
    service user_api
        port 8080
        endpoint get_user(id)
            ...
    """
    name:      str                = ""
    port:      Optional[int]      = None
    endpoints: List[EndpointDecl] = field(default_factory=list)


@dataclass
class StepDecl(Node):
    """A single step inside a workflow declaration."""
    name:     str               = ""
    params:   List[str]         = field(default_factory=list)
    defaults: Dict[str, "Expr"] = field(default_factory=dict)
    body:     List["Stmt"]      = field(default_factory=list)


@dataclass
class WorkflowDecl(Node):
    """
    workflow order_processing
        step validate(order_id)
            ...
        step process(order)
            ...
    """
    name:  str            = ""
    steps: List[StepDecl] = field(default_factory=list)


# ── AI / Intelligent Primitives ────────────────────────────────────────────────

@dataclass
class PromptDecl(Node):
    """
    prompt support_reply
        system "You are a helpful support agent."
        user   "Customer: {{message}}"
        format text

    `system`, `user`, and `format` are parsed as context-sensitive identifiers
    (not reserved keywords) so they remain usable as variable names.
    """
    name:    str = ""
    system:  str = ""       # system message template
    user:    str = ""       # user message template (supports {{var}} placeholders)
    format:  str = "text"   # "text" | "json"


@dataclass
class AgentTaskDecl(Node):
    """A callable task inside an agent declaration."""
    name:     str               = ""
    params:   List[str]         = field(default_factory=list)
    defaults: Dict[str, "Expr"] = field(default_factory=dict)
    body:     List["Stmt"]      = field(default_factory=list)


@dataclass
class AgentDecl(Node):
    """
    agent researcher
        model  "claude-3-5-sonnet"
        tools  fetch, query, ai
        memory session

        task analyze(topic)
            var data     = fetch("https://api.example.com?q=" + topic)
            var findings = ai("Key insights from: " + data)
            return findings

    `model`, `tools`, `memory` are context-sensitive identifiers (not keywords).
    """
    name:   str                 = ""
    model:  str                 = ""
    tools:  List[str]           = field(default_factory=list)
    memory: str                 = ""    # "session" | "persistent" | ""
    tasks:  List[AgentTaskDecl] = field(default_factory=list)


# ── UI / Frontend Primitives ───────────────────────────────────────────────────

@dataclass
class UIAttr(Node):
    """A single attribute on a UI element: key=value or key="string"."""
    key:   str    = ""
    value: "Expr" = None   # None means boolean flag (e.g. `disabled`)


@dataclass
class UIElement(Node):
    """
    A UI element inside a render block.

    Examples:
        button "Submit"              → tag="button", text=Literal("Submit")
        input bind=name label="Name" → tag="input", attrs=[UIAttr(bind, name), UIAttr(label, "Name")]
        card                         → tag="card", children=[...]
    """
    tag:      str             = ""
    attrs:    List[UIAttr]    = field(default_factory=list)
    text:     Optional["Expr"] = None       # inline text content
    children: List["UIElement"] = field(default_factory=list)


@dataclass
class RenderBlock(Node):
    """render\n    <ui elements>"""
    elements: List[UIElement] = field(default_factory=list)


@dataclass
class ComponentStateDecl(Node):
    """state name = default_value"""
    name:  str    = ""
    value: "Expr" = None


@dataclass
class OnHandler(Node):
    """on event_name\n    body"""
    event: str          = ""
    body:  List["Stmt"] = field(default_factory=list)


@dataclass
class ComponentDecl(Node):
    """
    component ClaimForm
        state claimant = ""
        state amount   = 0

        on submit
            var result = submit_claim(claimant, amount)

        render
            card
                input bind=claimant label="Your name"
                button "Submit"
    """
    name:     str                      = ""
    states:   List[ComponentStateDecl] = field(default_factory=list)
    handlers: List[OnHandler]          = field(default_factory=list)
    render:   Optional[RenderBlock]    = None


@dataclass
class NavItem(Node):
    """nav "Label" icon="home" → navigation sidebar item"""
    label:     str = ""
    icon:      str = ""
    component: str = ""   # component name to show when selected


@dataclass
class TabItem(Node):
    """tab "Label"\n    ComponentName"""
    label:     str  = ""
    component: str  = ""


@dataclass
class LayoutBlock(Node):
    """
    layout
        sidebar
            nav "Dashboard"   icon="home"
            nav "Claims"      icon="file-text"
        tabs
            tab "Submit"  → ClaimForm
            tab "History" → ClaimTable
        main
            ClaimForm
            ClaimTable
    """
    sidebar:    List[NavItem]  = field(default_factory=list)
    tabs:       List[TabItem]  = field(default_factory=list)
    main:       List[str]      = field(default_factory=list)   # component names
    routes:     List["RouteItem"] = field(default_factory=list)


@dataclass
class RouteItem(Node):
    """route "/" Dashboard — URL route binding a path to a component"""
    path:      str = ""
    component: str = ""


@dataclass
class IncludeStmt(Node):
    """include "path/to/file.mcn" — import another MCN file"""
    path: str = ""


@dataclass
class AppDecl(Node):
    """
    app InsuranceClaims
        title  "Claims Management"
        theme  "professional"
        layout
            sidebar
                nav "Dashboard" icon="home"
            main
                ClaimForm
    """
    name:       str                  = ""
    title:      str                  = ""
    theme:      str                  = "default"
    layout:     Optional[LayoutBlock] = None


# ── Type aliases ───────────────────────────────────────────────────────────────

Stmt = Union[
    VarDecl, AssignStmt, IfStmt, ForStmt, WhileStmt, TryStmt, ThrowStmt,
    TaskStmt, UseStmt, FunctionDecl, ReturnStmt, ExprStmt,
    BreakStmt, ContinueStmt, AssertStmt, TestDecl,
    PipelineDecl, ServiceDecl, WorkflowDecl, ContractDecl,
    PromptDecl, AgentDecl,
    ComponentDecl, AppDecl, IncludeStmt,
]

Expr = Union[
    Literal, Variable, Binary, Unary, Call, Index, Property,
    Array, MCNObject, MCNTuple,
]
