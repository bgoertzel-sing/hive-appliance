"""Bounded near-cap full-file verification/write measurements; padded fixture excluded."""
import os,json,time,hashlib,statistics
from pathlib import Path
E=Path(__file__).resolve().parent
ns={'__file__':str(E/'focused7701.py'),'__name__':'defs'};src=(E/'focused7701.py').read_text();exec(compile(src[:src.index('\nout={}\n')],str(E/'focused7701.py'),'exec'),ns)
fresh,two,hb,bindq,hnew,hfeed,hr=[ns[k] for k in ['fresh','two','hb','bindq','hnew','hfeed','hr']]
rows=[]
for size in [0,1<<20,16<<20,63<<20]:
 p,s,h=fresh('perf7701-'+str(size),two())
 if size:
  # Valid JSON header contains an ignored padding field, hash recomputed by ordinary format helper.
  header=json.loads(p.read_text());header['review_padding']='x'*size;header['rec_hash']=hr.HiveReducer._rec_hash(header)
  data=(json.dumps(header,sort_keys=True)+'\n').encode();p.write_bytes(data)
  t=time.perf_counter();h=hfeed(hnew(p),s);startup=time.perf_counter()-t
 else:startup=None
 assert h.journal_status()['healthy']
 times=[]
 for _ in range(5):
  t=time.perf_counter();assert h.verify_journal();times.append(time.perf_counter()-t)
 writes=[];orig=h._journal_write
 def timed(rec):
  t=time.perf_counter();orig(rec);writes.append(dict(op=rec['op'],seconds=time.perf_counter()-t))
 h._journal_write=timed
 t=time.perf_counter();r=hb(h);rebind=time.perf_counter()-t
 assert r and r.durable
 t=time.perf_counter();r2=bindq(h);second=time.perf_counter()-t;assert r2
 rows.append(dict(padding_bytes=size,file_bytes=p.stat().st_size,file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),startup_seconds=startup,verify_seconds=times,verify_median=statistics.median(times),first_rebind_seconds=rebind,second_rebind_seconds=second,per_record_writes=writes))
 # Large content not published; exact construction and hash retained.
 if size:p.unlink()
(E/'performance7701.json').write_text(json.dumps(dict(cases=rows,cap=hr.MAX_HIVE_JOURNAL_BYTES,method='Warm OS page cache on this host, five verifies and two rebinds per size; no throughput SLA claimed. Padding is valid hash-covered header JSON; no bypass of verification. Two whole-file scans per rebind.'),indent=2)+'\n')
print(json.dumps(rows,indent=2))
