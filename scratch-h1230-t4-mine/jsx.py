import subprocess, sys, pathlib, time, os
R = pathlib.Path("/home/creaite/dev.env/clark/wt-h1230-t4")
F = R/"src/clark/page/src/edit/MsPicker.jsx"
orig = F.read_text()
M = [
 ("go filtered by have", "selection.filter((id) => have.has(id))", "selection"),
 ("submit needs go.length", "if (go.length && onAdd)", "if (onAdd)"),
 ("Escape stop", "e.stopPropagation(); if (onClose)", "if (onClose)"),
 ("row click ignore INPUT", 'e.target.tagName !== "INPUT"', 'true'),
 ("header select keeps others", "[...selection, ...ids.filter((id) => !selection.includes(id))]", "ids"),
 ("header uncheck only shown", "selection.filter((id) => !ids.includes(id))", "[]"),
 ("indeterminate", "k > 0 && k < ids.length", "k > 0"),
 ("header checked", "ids.length > 0 && k === ids.length", "k === ids.length"),
 ("progress dash", 'r.percent === null || r.percent === ""', 'r.percent === ""'),
 ("progress round", "Math.round(Number(r.percent))", "Math.floor(Number(r.percent))"),
 ("zero disabled", "disabled={!c && !has}", "disabled={false}"),
 ("Add disabled", "disabled={!n}", "disabled={false}"),
 ("badge hidden", "{nOn ? <i>{nOn}</i> : null}", "null"),
 ("panel toggle", "setPan(!pan)", "setPan(true)"),
 ("is-not set", "not: { ...filter.not, [field]: true }", "not: { ...filter.not, [field]: false }"),
 ("empty text", '"Everything is already on the page."', '"Nothing."'),
]
sel = sys.argv[1:]
def load(): return float(open("/proc/loadavg").read().split()[0])
try:
    for i,(n,a,b) in enumerate(M):
        if sel and str(i) not in sel: continue
        assert orig.count(a)==1, (n, orig.count(a))
        waited=0
        while load()>=60 and waited<1500: time.sleep(60); waited+=60
        F.write_text(orig.replace(a,b))
        p = subprocess.run(["python3","dev/run_tests.py","-j","1","test_ms_picker_1230.py"],cwd=R,capture_output=True,text=True)
        print(i, n, "KILLED" if p.returncode else "SURVIVED", "load", load(), flush=True)
        F.write_text(orig)
finally:
    F.write_text(orig)
