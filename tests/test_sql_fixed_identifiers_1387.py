"""Row 1387 (bandit B608): every SQL string in src/ that is put together by formatting, joining or adding text interpolates
only FIXED identifiers: a table name that went through store._table, a key clause from where_key, a run of '?' marks, or a
name that is a constant of the module. Values always travel as ? parameters. A new formatted statement that takes any other
expression fails here until it is looked at."""
import ast
import re
import unittest

from _paths import SRC
from clark import store as store_module
from _demo import DemoStore
from clark.store import Invalid, _table

SQL = re.compile(r"\b(SELECT\s.+\sFROM|INSERT\s+(OR\s+\w+\s+)?INTO|UPDATE\s.*\sSET\b|DELETE\s+FROM|ALTER\s+TABLE|"
                 r"CREATE\s+(TABLE|INDEX|TRIGGER|VIEW)|DROP\s+(TABLE|INDEX)|PRAGMA\s)", re.S)      # the statements in src/ are upper case (checked)

# Plain names allowed in a formatted statement, per file, each with the reason it is fixed (looked at one by one, row 1387).
FIXED_NAMES = {
    ("activity_read.py", "table"): "loop over TABLES, a tuple of constants",
    ("history.py", "table"): "_has_column is called with the literal 'applies'",
    ("history.py", "where"): "built from literal clauses and '?' marks at every call site",
    ("history.py", "SORT_KEY"): "module constant",
    ("store.py", "BRAND_COLUMN"): "module constant",
    ("store.py", "THEME_COLUMN"): "module constant",
    ("store.py", "COLUMN_ORDERS_COLUMN"): "module constant (migrate_column_orders, row 1534)",
    ("store.py", "name"): "name of GANTT_PROJECT_COLUMNS, a constant tuple",
    ("store.py", "definition"): "text of GANTT_PROJECT_COLUMNS, a constant tuple",
    ("store.py", "text"): "item of OWNER_COLUMNS, a constant tuple",
    ("store.py", "column"): "item of ASK_FILES_COLUMNS, a constant tuple of fixed column text (migrate_ask_files)",
    ("store.py", "where"): "literal clauses joined with AND; values are ? parameters",
    ("store.py", "col"): "column of REVERT_REFS (constants) or a literal column name in the same function",
    ("store.py", "f"): "a column name taken from the table's own columns (cols) before the statement is made",
    ("store.py", "picked_columns"): "pick(): every name is checked against the table's own columns",
    ("store.py", "values"): "_insert_sql: every key is checked against the table's columns first",
    ("update_helper.py", "name"): "only ever passed through _ident (quoted), read from the file's own catalogue",
}
FIXED_CALLS = {"_table", "where_key", "_ident"}


def _literal_text(node):
    return "".join(c.value for c in ast.walk(node) if isinstance(c, ast.Constant) and isinstance(c.value, str))


def _is_marks(node):
    """', '.join('?' * n)"""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "join"
            and len(node.args) == 1 and isinstance(node.args[0], ast.BinOp) and isinstance(node.args[0].op, ast.Mult)
            and isinstance(node.args[0].left, ast.Constant) and node.args[0].left.value == "?")


def _parts(node):
    """The non-constant expressions a composed string takes in, or None when `node` is not a composed string."""
    if isinstance(node, ast.JoinedStr):
        got = [v.value for v in node.values if isinstance(v, ast.FormattedValue)]
        return got or None
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return [n for n in (node.left, node.right) if not (isinstance(n, ast.Constant) and isinstance(n.value, str))]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format" \
            and isinstance(node.func.value, ast.Constant):
        return list(node.args) + [k.value for k in node.keywords]
    return None


def _fixed(expr, fname):
    if isinstance(expr, ast.Constant):
        return True
    if isinstance(expr, ast.Name):
        return (fname, expr.id) in FIXED_NAMES
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in FIXED_CALLS:
        return True
    if _is_marks(expr):
        return True
    if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Name) and expr.value.id == "PUBLISH_ORDER":
        return True
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "join" \
            and isinstance(expr.func.value, ast.Constant):                # " AND ".join(where): the pieces are checked as `where`
        if expr.args and isinstance(expr.args[0], ast.GeneratorExp):
            return _fixed(expr.args[0].elt, fname)
        return all(isinstance(a, ast.Name) and (fname, a.id) in FIXED_NAMES for a in expr.args)
    if isinstance(expr, ast.JoinedStr):
        return all(_fixed(v.value, fname) for v in expr.values if isinstance(v, ast.FormattedValue))
    if isinstance(expr, ast.IfExp):                                       # (" WHERE " + ...) if where else ""
        return all(_fixed(n, fname) for n in (expr.body, expr.orelse))
    if isinstance(expr, (ast.BinOp,)):
        return all(_fixed(n, fname) for n in (expr.left, expr.right))
    return False


def composed_sql(tree, fname):
    """[(line, [expressions that are not fixed])] for every composed SQL-looking string of the tree."""
    out, seen = [], set()
    for n in ast.walk(tree):
        parts = _parts(n)
        if parts is None or not SQL.search(_literal_text(n)) or n.lineno in seen:
            continue
        seen.add(n.lineno)
        out.append((n.lineno, [ast.unparse(p) for p in parts if not _fixed(p, fname)]))
    return out


class FixedIdentifiers(unittest.TestCase):
    def test_every_composed_statement_takes_only_fixed_identifiers(self):
        total, bad = 0, []
        for path in sorted((SRC / "clark").rglob("*.py")):
            found = composed_sql(ast.parse(path.read_text(encoding="utf-8")), path.name)
            total += len(found)
            bad += [f"{path.name}:{line}: {parts}" for line, parts in found if parts]
        self.assertEqual(bad, [])
        self.assertGreaterEqual(total, 30, "the scan found the composed statements bandit flags (36 on 19-11)")

    def test_the_checker_finds_a_value_put_into_a_statement(self):
        for src in ('con.execute("SELECT * FROM t WHERE a = \'" + value + "\'")',
                    'con.execute(f"SELECT * FROM t WHERE a = {value}")',
                    'con.execute("DELETE FROM t WHERE a = %s" % value)',
                    'con.execute("DELETE FROM {} WHERE a = 1".format(request))',
                    'con.execute(f"UPDATE {_table(t)} SET {field} = ?")'):
            with self.subTest(src=src):
                (line, parts), = composed_sql(ast.parse(src), "x.py")
                self.assertTrue(parts)
        (line, parts), = composed_sql(ast.parse('con.execute(f"SELECT * FROM {_table(t)} WHERE {where_key(t)}")'), "x.py")
        self.assertEqual(parts, [])

    def test_the_names_that_reach_a_statement_are_refused_when_unknown(self):
        for name in ("actions; DROP TABLE actions", "nope", "", "actions --"):
            with self.subTest(name=name):
                with self.assertRaises(Invalid):
                    _table(name)
        for table in store_module.TABLES:
            self.assertEqual(_table(table), table)

    def test_a_field_name_that_is_not_a_column_never_reaches_the_insert(self):
        with DemoStore() as store:
            with self.assertRaises(Invalid):
                store_module._insert_sql(store.con, "actions", {"id) VALUES (1); --": "x"})


if __name__ == "__main__":
    unittest.main()
