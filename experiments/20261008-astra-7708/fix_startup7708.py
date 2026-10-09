from pathlib import Path
import difflib
E=Path('/tmp/hive-astra-7708/20261008-astra-7708')
s=(E/'startup7701.py').read_text();s=s.replace("p=T/('initial7701-'", "stream=history();p=T/('initial7708-'").replace('hfeed(hnew(p),history())','hfeed(hnew(p),stream)').replace("'startup7701.json'","'startup7708.json'")
(E/'startup7708.py').write_text(s)
(E/'startup-adaptation-7708.diff').write_text(''.join(difflib.unified_diff((E/'startup7701.py').read_text().splitlines(True),s.splitlines(True),fromfile='initial/startup7701.py',tofile='corrected/startup7708.py')))
s=(E/'startup_recovery7708.py').read_text().replace("'startup7701.json'","'startup7708.json'").replace("'initial7701-'","'initial7708-'").replace("h=ns['hfeed'](ns['hnew'](p),ns['history']())","stream=ns['history']();h=ns['hfeed'](ns['hnew'](p),stream)").replace("ns['hfeed'](ns['hnew'](p),ns['history']())","ns['hfeed'](ns['hnew'](p),stream)")
(E/'startup_recovery_final7708.py').write_text(s)
