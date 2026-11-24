import sys, subprocess, shutil, time, os, json
W = "/home/creaite/dev.env/clark/wt-row1230-pr2-clean"
S = W + "/scratch-m3860-stark"
M = "src/clark/page/src/logic/milestones.js"
C = "src/clark/page/shell.css"
J = "src/clark/page/src/components/MsTimeline.jsx"
# id, file, old, new, kind ("logic" runs node first; "ui" runs browser)
MUT = [
 ("T01", M, "for (let d = 12; d <= reach; d += 12)", "for (let d = 12; d <= reach; d += 6)"),
 ("T02", M, "l.w / 2 - 10), offs", "l.w / 2 - 12), offs"),
 ("T03", M, "if (l.x < cx - l.w / 2 + 6 ||", "if (l.x < cx - l.w / 2 + 3 ||"),
 ("T04", M, "l.x > cx + l.w / 2 - 6) continue", "l.x > cx + l.w / 2 - 8) continue"),
 ("T05", M, "Math.abs(o.cx - cx) >= (o.w + l.w) / 2 + gap", "Math.abs(o.cx - cx) > (o.w + l.w) / 2 + gap"),
 ("T06", M, "Math.abs(o.cx - cx) >= (o.w + l.w) / 2 + gap", "Math.abs(o.cx - cx) >= (o.w + l.w) / 2 + gap / 2"),
 ("T07", M, "offs.push(-d, d)", "offs.push(d, -d)"),
 ("T08", M, "const lo = l.w / 2, hi = Math.max(lo, width - l.w / 2);", "const lo = l.w / 2, hi = width - l.w / 2;"),
 ("T09", M, "o.lvl < lvl ? !(l.x > o.cx", "o.lvl <= lvl ? !(l.x > o.cx"),
 ("T10", M, "o.cx - o.w / 2 - 4 && l.x < o.cx + o.w / 2 + 4", "o.cx - o.w / 2 - 4 && l.x < o.cx + o.w / 2 + 1"),
 ("T11", M, "!(o.x > cx - l.w / 2 - 4 && o.x < cx + l.w / 2 + 4)", "!(o.x > cx - l.w / 2 - 4 && o.x < cx + l.w / 2 + 12)"),
 ("T12", M, "got = at(t, false);", "got = at(t, true);"),
 ("T13", M, "for (let t = 0; t < TIER_MAX && !got; t++) got = at(t, true);", "for (let t = 0; t < TIER_MAX - 1 && !got; t++) got = at(t, true);"),
 ("T14", M, "if (o.dir !== dir || !strict) return true;", "if (o.dir !== dir) return true;"),
 ("H01", C, "padding-right: 212px; }", "padding-right: 190px; }"),
 ("H02", C, ".mv-cap { position: absolute; left: var(--space-3);", ".mv-cap { position: absolute; left: var(--space-1);"),
 ("H03", J, "const LH = 38, TGAP = 10,", "const LH = 38, TGAP = 14,"),
 ("H04", J, "SIDE = 24, CAPROOM = 30;", "SIDE = 24, CAPROOM = 12;"),
 ("H05", C, ".msv[data-place^=\"sec-\"] .mv-today b { top: 20px;", ".msv[data-place^=\"sec-\"] .mv-today b { top: 26px;"),
 ("H06", C, "padding: 0 var(--space-2); border-radius: var(--radius-pill); background: var(--brand-navy)", "padding: 0 var(--space-2); border-radius: var(--radius-sm); background: var(--brand-navy)"),
 ("H07", C, "z-index: 4; font-size: var(--size-caption); color: var(--text-muted); pointer-events: none; }", "z-index: 4; font-size: var(--size-caption); color: var(--text-muted); pointer-events: auto; }"),
 ("H08", J, "const LY = R2 ? 44 + (nA", "const LY = R2 ? 36 + (nA"),
 ("H09", C, ".mv-lead { position: absolute; width: 1px;", ".mv-lead { position: absolute; width: 3px;"),
 ("H10", C, ".mv-lab2:hover { background: var(--grey-100); }", ".mv-lab2:hover { background: var(--grey-50); }"),
 ("H11", C, ".mv-txt button[aria-current=\"true\"] { color: var(--heading); font-weight: var(--weight-medium); border-bottom-color: var(--brand-blue); }", ".mv-txt button[aria-current=\"true\"] { color: var(--heading); font-weight: var(--weight-medium); border-bottom-color: transparent; }"),
]
def load1(): return float(open("/proc/loadavg").read().split()[0])
def wait_load():
    for i in range(26):
        if load1() < 60: return True
        time.sleep(60)
    return False
def run(args, log):
    r = subprocess.run(args, cwd=W, capture_output=True, text=True)
    open(log, "w").write(r.stdout + r.stderr)
    return r.returncode
def main(ids, mode):
    for mid, f, old, new in MUT:
        if mid not in ids: continue
        p = W + "/" + f
        src = open(p).read()
        n = src.count(old)
        if n != 1:
            print(mid, "NOT-UNIQUE", n); continue
        bak = S + "/orig." + os.path.basename(f)
        shutil.copy(p, bak)
        try:
            open(p, "w").write(src.replace(old, new))
            res = {}
            if mode in ("node", "both"):
                res["node"] = run(["python3", "dev/run_tests.py", "-j", "1", "test_tier_labels_node"], f"{S}/{mid}.node.out")
            if mode in ("browser", "both") and (mode == "browser" or res.get("node") == 0):
                if not wait_load(): res["browser"] = "SKIPPED-LOAD"
                else:
                    l = load1()
                    res["browser"] = run(["python3", "dev/run_tests.py", "-j", "1", "test_ms_header_1230"], f"{S}/{mid}.hdr.out")
                    res["load1"] = l
        finally:
            shutil.copy(bak, p)
        print(mid, json.dumps(res), flush=True)
        open(S + "/summary.txt", "a").write(f"{mid} {mode} {json.dumps(res)} {time.strftime('%T')}\n")
if __name__ == "__main__":
    main(sys.argv[2].split(","), sys.argv[1])
