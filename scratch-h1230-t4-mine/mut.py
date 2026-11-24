import subprocess, sys, pathlib, shutil
R = pathlib.Path("/home/creaite/dev.env/clark/wt-h1230-t4")
F = R/"src/clark/page/src/logic/msPicker.js"
orig = F.read_text()
M = [
 ("EYE text", 'EYE = "Taken off with the eye"', 'EYE = "Taken off with eye"'),
 ("hidden->NOT_ON swap", "hidden.has(r.id) ? EYE : NOT_ON", "hidden.has(r.id) ? NOT_ON : EYE"),
 ("leftOut default dropped", "new Set(leftOut || [])", "new Set(leftOut)"),
 ("d null guard", "(d && d.milestones) || []", "d.milestones || []"),
 ("closed Achieved", 'r.state === "Achieved" || r.state === CANCELLED', 'r.state === CANCELLED'),
 ("none guard dropped", "!r.baseline || dayNumber", "dayNumber"),
 ("overdue <=", "r.baseline < today", "r.baseline <= today"),
 ("soon 7->6", "<= 7 ?", "<= 6 ?"),
 ("soon 7->8", "<= 7 ?", "<= 8 ?"),
 ("soon <", "<= 7 ?", "< 7 ?"),
 ("client inverted", 'r.clientVisible ? "yes" : "no"', 'r.clientVisible ? "no" : "yes"'),
 ("status field->state off", "if (f === \"status\") return r.state;", "if (f === \"status\") return r.why;"),
 ("page field", 'if (f === "page") return r.why;', 'if (f === "page") return r.state;'),
 ("options due", 'f === "due" ? DUE', 'f === "due" ? PAGE'),
 ("skip ignored", "if (f === skip) return true;", ""),
 ("not flag ignored", "filter.not && filter.not[f] ? !has : has", "has"),
 ("includes->every-empty", "if (!c.length) return true;", ""),
 ("query trim dropped", "String(q || \"\").trim().toLowerCase()", "String(q || \"\").toLowerCase()"),
 ("query word dropped", "${r.name} ${r.id} ${r.word}", "${r.name} ${r.id}"),
 ("query id dropped", "${r.name} ${r.id} ${r.word}", "${r.name} ${r.word}"),
 ("resultWords", "`Result: ${shown} of ${total} shown`", "`Result: ${total} of ${shown} shown`"),
 ("toast plural", 'n === 1 ? "" : "s"', 'n <= 1 ? "" : "s"'),
 ("addWords", "`Add ${n}`", "`Add ${n + 0 || 1}`"),
 ("filtersOn counts MORE", "[...FIELDS, ...MORE].filter((f) => ((filter.sel", "[...FIELDS].filter((f) => ((filter.sel"),
 ("passes ignores MORE", "return [...FIELDS, ...MORE].every", "return [...FIELDS].every"),
 ("counts options order", "options(f).map(([v]) => [v, L.filter", "options(f).map(([v]) => [v, rows.filter"),
 ("selectedWords", '"None selected"', '"None"'),
 ("STATUS order", '"Slipped", "Overdue"', '"Overdue", "Slipped"'),
]
sel = sys.argv[1:]
try:
    for i,(n,a,b) in enumerate(M):
        if sel and str(i) not in sel: continue
        assert orig.count(a)==1, (n, orig.count(a))
        F.write_text(orig.replace(a,b))
        p = subprocess.run(["python3","dev/run_tests.py","test_ms_picker_1230_node"],cwd=R,capture_output=True,text=True)
        print(i, n, "KILLED" if p.returncode else "SURVIVED", flush=True)
finally:
    F.write_text(orig)
