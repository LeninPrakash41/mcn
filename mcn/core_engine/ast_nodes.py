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
class NamedArg(Node):
    """name = value (keyword argument in function call)"""
    name: str = ""
    value: "Expr" = None


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
    """
    A single field in a contract:

        name:  str
        phone: str?                      optional
        value: float = 0                 default
        email: str unique                unique
        stage: choice("new", "won") = "new"
    """
    name:      str                  = ""
    type_name: str                  = ""
    optional:  bool                 = False
    default:   Optional["Expr"]     = None
    unique:    bool                 = False
    choices:   List[str]            = field(default_factory=list)
    ref:       str                  = ""        # company: ref Company
    read_roles:  List[str]          = field(default_factory=list)   # salary: float  read admin
    write_roles: List[str]          = field(default_factory=list)   #               write admin


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
    allow:    List[str]         = field(default_factory=list)  # endpoint x() allow admin
    public:   bool              = False                        # endpoint x() public


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
    cruds:     List["CrudDecl"]   = field(default_factory=list)
    triggers:  List["TriggerDecl"] = field(default_factory=list)
    jobs:      List["JobDecl"]    = field(default_factory=list)


@dataclass
class TriggerDecl(Node):
    """
    on update Lead                      (create | update | delete | approve | reject)
        if changed("stage") and record.stage == "won"
            send_email(...)
    """
    event:    str          = ""
    contract: str          = ""
    body:     List["Stmt"] = field(default_factory=list)


@dataclass
class JobDecl(Node):
    """
    job daily_digest every day at "09:00"
    job sync every 15 minutes
    job weekly_report every monday at "08:30"
    """
    name:  str          = ""
    every: int          = 1
    unit:  str          = "day"        # minute | hour | day | week | monday … sunday
    at:    str          = ""           # "HH:MM" (server local time)
    body:  List["Stmt"] = field(default_factory=list)


@dataclass
class ApprovalDecl(Node):
    """
    approval
        approvers admin, manager
        when record.amount > 10000
    """
    approvers: List[str]        = field(default_factory=list)
    when:      Optional["Expr"] = None


@dataclass
class CrudDecl(Node):
    """
    Inside a service — generates list/get/create/update/delete endpoints:

        crud Lead
            search    name, email
            sort      created_at desc
            page_size 25
    """
    contract:  str       = ""
    search:    List[str] = field(default_factory=list)
    sort:      str       = ""          # "field" or "field desc"
    page_size: int       = 25
    allow:     Dict[str, List[str]] = field(default_factory=dict)  # read/write/delete → roles
    audit:     bool      = False
    approval:  Optional[ApprovalDecl] = None
    csv_import: bool     = False
    csv_export: bool     = False


@dataclass
class AuthDecl(Node):
    """
    Login and roles for the app (usually in models.mcn, shared by backend + UI):

        auth
            roles         admin, sales, viewer     # first role = administrator
            session_hours 12
    """
    roles:         List[str] = field(default_factory=list)
    session_hours: int       = 12
    sso:           Optional["SSODecl"] = None


@dataclass
class SSODecl(Node):
    """
    sso
        issuer        "https://accounts.google.com"
        client_id     env("SSO_CLIENT_ID")
        client_secret env("SSO_CLIENT_SECRET")
        allow_domains "acme.in", "acme.com"
        default_role  staff
        label         "Google"
    """
    issuer:        Optional["Expr"] = None
    client_id:     Optional["Expr"] = None
    client_secret: Optional["Expr"] = None
    allow_domains: List["Expr"]     = field(default_factory=list)
    default_role:  str              = ""
    label:         Optional["Expr"] = None
    auto_create:   bool             = True


@dataclass
class ScheduleDecl(Node):
    """
    schedule my_job at "0 0 * * *"
        var data = query("...")
    """
    name:      str          = ""
    cron_expr: str          = ""
    body:      List["Stmt"] = field(default_factory=list)


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


@dataclass
class MCPToolDecl(Node):
    """A tool declaration inside an mcp server block."""
    name:   str       = ""
    params: List[str] = field(default_factory=list)


@dataclass
class MCPServerDecl(Node):
    """
    mcp filesystem_server
        transport "stdio"
        command   "npx"
        args      ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

        tool read_file(path)
        tool write_file(path, content)
    """
    name:      str              = ""
    transport: str              = "stdio"   # "stdio" | "sse" | "http"
    command:   str              = ""
    args:      List[str]        = field(default_factory=list)
    url:       str              = ""        # for sse/http transport
    tools:     List[MCPToolDecl] = field(default_factory=list)




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
        for j in jobs                → tag="for", for_var="j", for_iterable=Variable("jobs")
    """
    tag:           str               = ""
    attrs:         List[UIAttr]      = field(default_factory=list)
    text:          Optional["Expr"]  = None       # inline text content
    children:      List["UIElement"] = field(default_factory=list)
    for_var:       Optional[str]     = None       # loop var name (for 'for' elements)
    for_iterable:  Optional["Expr"]  = None       # loop iterable expr (for 'for' elements)


@dataclass
class UIIf(Node):
    """
    Conditional UI inside a render block:

        if loading
            p "Loading…"
        else if error
            alert text=error
        else
            p "Ready"

    `else if` is represented as a single UIIf inside else_children.
    tag / attrs / text / children mirror UIElement so tree walkers work.
    """
    condition:      "Expr"            = None
    then_children:  List["UIElement"] = field(default_factory=list)
    else_children:  List["UIElement"] = field(default_factory=list)
    tag:   str            = "if"
    attrs: List[UIAttr]   = field(default_factory=list)
    text:  Optional["Expr"] = None

    @property
    def children(self) -> List["UIElement"]:
        return self.then_children + self.else_children


@dataclass
class UIFor(Node):
    """
    Repeated UI inside a render block:

        for task in tasks          (or: for i, task in tasks)
            card_header "{task.title}"
        empty
            p "No tasks yet"

    `empty` (optional) renders when the list has no items.
    """
    variable:       str               = ""
    index_var:      Optional[str]     = None
    iterable:       "Expr"            = None
    body:           List["UIElement"] = field(default_factory=list)
    empty:          List["UIElement"] = field(default_factory=list)
    tag:   str            = "for"
    attrs: List[UIAttr]   = field(default_factory=list)
    text:  Optional["Expr"] = None

    @property
    def children(self) -> List["UIElement"]:
        return self.body + self.empty


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
    event:  str          = ""
    body:   List["Stmt"] = field(default_factory=list)
    params: List[str]    = field(default_factory=list)   # on remove(id)


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
    allow:     List[str] = field(default_factory=list)   # roles that see this item


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
    PromptDecl, AgentDecl, MCPServerDecl,
    ComponentDecl, AppDecl, IncludeStmt,
]

Expr = Union[
    Literal, Variable, Binary, Unary, Call, Index, Property,
    Array, MCNObject, MCNTuple,
]
