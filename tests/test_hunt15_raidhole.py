"""RAID card put past the end of a shrunk body leaves no hole; the Add panel's title is looked for on each frame until drawn."""
import json
import shutil
import subprocess
import unittest

from _paths import SRC

LOGIC = SRC / "clark" / "page" / "src" / "logic"


def node(file, code):
    if not shutil.which("node"):
        raise unittest.SkipTest("no node")
    src = f"const m = await import({json.dumps((LOGIC / file).as_uri())}); {code}"
    done = subprocess.run(["node", "--input-type=module", "-e", src], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


class PutCard(unittest.TestCase):
    def test_a_slot_past_the_shrunk_body_is_pushed_not_left_as_a_hole(self):
        out = node("putCard.js", 'console.log(JSON.stringify(m.putCard([{id:"A"}], 2, {id:"C"})));')
        self.assertEqual(out, [{"id": "A"}, {"id": "C"}])

    def test_replace_and_remove_are_as_before(self):
        self.assertEqual(node("putCard.js", 'console.log(JSON.stringify(m.putCard([{id:"A"},{id:"B"}], 1, {id:"C"})));'), [{"id": "A"}, {"id": "C"}])
        self.assertEqual(node("putCard.js", 'console.log(JSON.stringify(m.putCard([{id:"A"},{id:"B"}], 0, null)));'), [{"id": "B"}])


class Focus(unittest.TestCase):
    def test_it_polls_by_frames_until_found_and_is_bounded(self):
        code = ('let q=[],n=0; const raf=(f)=>q.push(f); const find=()=>(++n>=4?"el":null);'
                'let got=m.whenFound(find,raf,30); while(q.length&&!got){got=m.whenFound===0?0:q.shift()();}'
                'let k=0; const q2=[]; m.whenFound(()=>{k++;return null;},(f)=>q2.push(f),5); while(q2.length) q2.shift()();'
                'console.log(JSON.stringify({got,n,k}));')
        out = node("whenFound.js", code)
        self.assertEqual(out, {"got": "el", "n": 4, "k": 5})


if __name__ == "__main__":
    unittest.main()
