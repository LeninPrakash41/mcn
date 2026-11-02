"""
Core MCN semantics (Python-like, predictable for new developers) and the
friendly error output.
"""

import pytest

from mcn.core_engine.mcn_interpreter import MCNInterpreter, MCNScriptError


def run(src):
    interp = MCNInterpreter()
    interp.execute(src, quiet=True)
    return interp.variables


def out(src):
    return run(src)["out"]


# ── Truthiness ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("[]", "no"), ("{}", "no"), ('""', "no"), ("0", "no"), ("null", "no"),
    ("false", "no"), ("[0]", "yes"), ('{a: 1}', "yes"), ('"x"', "yes"), ("1", "yes"),
])
def test_truthiness(value, expected):
    assert out(f'var v = {value}\nvar out = v ? "yes" : "no"') == expected


# ── and / or ──────────────────────────────────────────────────────────────────

def test_and_or_short_circuit():
    v = run('var calls = 0\n'
            'function hit()\n    calls += 1\n    return true\n'
            'var a = false and hit()\nvar b = true or hit()\n')
    assert v["calls"] == 0


def test_and_or_return_values_and_guards():
    assert out('var u = {name: "a"}\n'
               'var out = [null and 1, u and u.name, null or "guest", [] or "x"]') \
        == [None, "a", "guest", "x"]
    assert out('var u = null\nvar out = u != null and u.name == "x"') is False


# ── Indexing ──────────────────────────────────────────────────────────────────

def test_negative_and_out_of_range_index():
    assert out('var out = [[1, 2, 3][-1], [1, 2, 3][-4], [1][5], "abc"[-1]]') \
        == [3, None, None, "c"]


def test_dict_int_and_string_keys():
    assert out('var d = {}\nd[1] = "x"\nd["k"] = 2\nvar out = [d[1], d["k"], d.k]') \
        == ["x", 2, 2]


# ── Loops and scoping ─────────────────────────────────────────────────────────

def test_for_key_value_over_dict():
    assert out('var out = []\nfor k, v in {a: 1, b: 2}\n    out = out + [k + "=" + v]') \
        == ["a=1", "b=2"]


def test_for_index_value_over_list():
    assert out('var out = []\nfor i, x in ["a", "b"]\n    out = out + [i + x]') \
        == ["0a", "1b"]


def test_vars_declared_in_blocks_stay_visible():
    v = run('for i in [1, 2]\n    var last = i * 10\n'
            'if true\n    var flag = "set"\n'
            'try\n    throw "boom"\ncatch e\n    var msg = e.message\n')
    assert (v["last"], v["i"], v["flag"], v["msg"]) == (20, 2, "set", "boom")


def test_catch_variable_does_not_clobber_outer_names():
    v = run('var e = "outer"\nvar error = "keep"\n'
            'try\n    throw "x"\ncatch e\n    var seen = e.message\n')
    assert (v["e"], v["error"], v["seen"]) == ("outer", "keep", "x")


def test_function_locals_stay_local():
    v = run('function f()\n    for j in [1]\n        var t = 9\n    return t\n'
            'var r = f()\n')
    assert v["r"] == 9 and "t" not in v and "j" not in v


# ── Friendly errors ───────────────────────────────────────────────────────────

def _pretty(src, name="app.mcn"):
    with pytest.raises(MCNScriptError) as exc:
        MCNInterpreter().execute(src, name, quiet=True)
    return exc.value.pretty()


def test_runtime_error_message():
    msg = _pretty("var total = 0\nlog(totl)\n")
    assert msg.splitlines() == [
        "error: Undefined variable 'totl'. Did you mean 'total'?",
        "  --> app.mcn:2:5",
        "  |",
        "2 | log(totl)",
        "  |     ^",
    ]


def test_syntax_errors_are_all_reported_without_cascades():
    msg = _pretty('var a = 1\nvar = 2\nif a == )\n    log("x")\n')
    assert "syntax error: Expected variable name after 'var', but found '='" in msg
    assert "syntax error: Unexpected ')'" in msg
    assert msg.count("syntax error") == 2           # no follow-on error for the block
    assert "Traceback" not in msg


def test_legacy_error_text_is_kept():
    with pytest.raises(Exception) as exc:
        MCNInterpreter().execute("log(nope)\n", quiet=True)
    assert str(exc.value).startswith("MCN REFERENCE_ERROR:")


def test_running_does_not_print_logs(capsys):
    MCNInterpreter().execute('var x = 1\n', "x.mcn", quiet=False)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
