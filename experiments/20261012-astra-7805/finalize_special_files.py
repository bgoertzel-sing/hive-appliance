"""Preserve nonregular fixture metadata; Git cannot store FIFO objects."""
import os,stat,json
from pathlib import Path
E=Path(__file__).resolve().parent;special=[];links=[]
for base,dirs,files in os.walk(E,followlinks=False):
 for name in dirs+files:
  p=Path(base)/name;st=p.lstat();rel=str(p.relative_to(E))
  if stat.S_ISLNK(st.st_mode):links.append(dict(path=rel,target=os.readlink(p)))
  elif not stat.S_ISREG(st.st_mode) and not stat.S_ISDIR(st.st_mode):
   special.append(dict(path=rel,mode=st.st_mode,inode=st.st_ino,device=st.st_dev,disposition='review-created FIFO serialized then unlinked; Git cannot preserve FIFO'))
   assert stat.S_ISFIFO(st.st_mode);p.unlink()
(E/'special-fixtures.json').write_text(json.dumps(dict(serialized_special_entries=special,retained_symlinks=links),indent=2)+'\n');print('serialized FIFO entries',len(special),'retained symlinks',len(links))
