"""Row 1366: the one reviewed exception to the 'only store.py writes or opens a database' pins.

ask_index.py writes only its own rebuildable index file, <data folder>/ask-index/<project>.db, never clark.db. The exception
is by file AND by what that file opens: every sqlite3.connect in it must take a variable that is assigned, in the same
function, from path_for(...), and path_for must build its path under 'ask-index' and end in '.db'. The file may not import
store (so it has no connection to clark.db) and may not name clark.db outside its docstrings. Any other shape is not
excused, so a second writer to clark.db added to that file still fails the pins."""
import ast

ASK_INDEX = "clark/ask_index.py"


def _is_connect(n):
    return isinstance(n, ast.Attribute) and n.attr == "connect" and isinstance(n.value, ast.Name) and n.value.id == "sqlite3"


def _docstrings(tree):
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            out.add(id(n.body[0].value))
    return out


def _consts(node):
    return [c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str)]


def problems(tree):
    """Why ask_index.py is NOT excused (empty list = it opens and writes only its own index file)."""
    out = []
    docs = _docstrings(tree)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[-1] == "store" for a in n.names):
            out.append(f"{n.lineno}: imports store")
        if isinstance(n, ast.ImportFrom) and ((n.module or "").split(".")[-1] == "store" or any(a.name == "store" for a in n.names)):
            out.append(f"{n.lineno}: imports store")
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and "clark.db" in n.value:
            out.append(f"{n.lineno}: names clark.db")
        if isinstance(n, ast.Name) and n.id in ("open_store", "store_module"):
            out.append(f"{n.lineno}: uses the store connection")
    connects = 0
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for c in [n for n in ast.walk(fn) if isinstance(n, ast.Call) and _is_connect(n.func)]:
            connects += 1
            arg = c.args[0] if len(c.args) == 1 and not c.keywords else None
            if not isinstance(arg, ast.Name):
                out.append(f"{c.lineno}: connect does not take a plain variable")
                continue
            sources = [a.value for a in ast.walk(fn) if isinstance(a, ast.Assign) and len(a.targets) == 1
                       and isinstance(a.targets[0], ast.Name) and a.targets[0].id == arg.id]
            if len(sources) != 1 or not (isinstance(sources[0], ast.Call) and isinstance(sources[0].func, ast.Name)
                                         and sources[0].func.id == "path_for"):
                out.append(f"{c.lineno}: connect path is not path_for(...)")
    if sum(1 for n in ast.walk(tree) if _is_connect(n)) != connects:
        out.append("a sqlite3.connect outside a function")
    if connects != 1:
        out.append(f"{connects} connects (the reviewed shape has exactly one)")
    pf = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "path_for"]
    if len(pf) != 1:
        out.append("no single path_for")
    else:
        text = _consts(pf[0])
        if "ask-index" not in text or not any(t.endswith(".db") for t in text):
            out.append("path_for does not build <data>/ask-index/<project>.db")
    return out
