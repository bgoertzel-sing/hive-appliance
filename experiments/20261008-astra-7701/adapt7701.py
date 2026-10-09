"""Mechanical retained-witness adaptations; originals remain in pinned 7694 evidence."""
import pathlib,difflib,json
E=pathlib.Path(__file__).resolve().parent
P=pathlib.Path('/tmp/hive-astra-7701-source/experiments/20261008-astra-7694')
diff=[]
def edit(name,changes):
 old=(P/name).read_text();new=old
 for a,b in changes:
  assert a in new,(name,a);new=new.replace(a,b)
 (E/name).write_text(new)
 diff.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='7694/'+name,tofile='7701/'+name))
edit('review7694.py',[("entry=lines[0]","entry=lines[1]")])
edit('followup7694.py',[
 ("v4 protocol review","v5 protocol review"),
 ("len(records(p))==1","len(records(p))==2"),
 ("L=original.splitlines(keepends=True)","L=original.splitlines(keepends=True);H,L=L[0],L[1:]"),
 ("if mode=='lost_final_newline':bad=original[:-1]","if mode=='lost_final_newline':bad=b''.join(L)[:-1]"),
 ("elif mode=='duplicate_pair':bad=original+original","elif mode=='duplicate_pair':bad=b''.join(L+L)"),
 ("r=rs[1 if mode=='edited_commit_id' else 0]","r=rs[2 if mode=='edited_commit_id' else 1]"),
 ("bad=p.read_bytes()","bad=p.read_bytes()[len(H):]"),
 ("else:bad=original+{'bad_utf8'","else:bad=b''.join(L)+{'bad_utf8'"),
 ("p.write_bytes(bad);rs=restarts(p,s)","p.write_bytes(H+bad);bad=H+bad;rs=restarts(p,s)"),
 ("assert ok==(uncertain or mode in ['positive_short','close_after'])","assert bool(ok)==(mode in ['positive_short','close_after']) and (ok.status=='uncertain')==uncertain"),
 ("if not ok:\n    held(h)","if ok.status=='refused':\n    held(h)"),
 ("k.startswith('_journal')","k.startswith('_journal') or k in ['last_rebind_result','_rebind_op_id']"),
 ("if ok and mode not in ['truncate_after','rollback_fsync']","if ok.applied and mode not in ['truncate_after','rollback_fsync']"),
 ("returned=ok","returned=ok.as_dict()"),
 ("assert ok and h._plan_owner==","assert not ok and ok.status=='uncertain' and ok.applied and ok.durable is None and h._plan_owner=="),
 ("OPEN Medium F-applied-without-durable-commit: True means in-memory applied but cannot mean durable success; structured UNCERTAIN required for current production gate","CLOSED Medium F-applied-without-durable-commit: explicit falsy UNCERTAIN; live applied and two restarts held"),
 ("P0,C0=records(p)","H0,P0,C0=records(p)"),
 ("rs=copy.deepcopy([P0,C0])","rs=copy.deepcopy([H0,P0,C0])"),
 ("rs=[P0];r['prev']","rs=[H0,P0];r['prev']"),
 ("r=records(p)[0]","r=records(p)[1]")
])
# Run only the applicable adapted groups; replacement identity/startup/prefix groups are in new focused harness.
p=E/'followup7694.py';s=p.read_text();start=s.index("functions=[")
end=s.index("\n# Extra clearance",start)
s=s[:start]+"""functions=[('exact7678_archived_witnesses',historical_exact),('native_tails_order_edits',tails_and_order),('v5_fault_matrix',fault_matrix),('applied_no_commit',commit_absent),('crash_boundaries',crash_boundaries),('duplicate_commit',duplicates),('legacy_default',legacy_default),('old_markers',old_markers)]"""+s[end:]
p.write_text(s)
# capture final complete adaptation, including selected group list
diff=[]
for name in ['review7694.py','followup7694.py']:
 diff.extend(difflib.unified_diff((P/name).read_text().splitlines(True),(E/name).read_text().splitlines(True),fromfile='7694/'+name,tofile='7701/'+name))
(E/'adaptation-7701.diff').write_text(''.join(diff))
print('adapted retained scripts, recorded complete diff')
