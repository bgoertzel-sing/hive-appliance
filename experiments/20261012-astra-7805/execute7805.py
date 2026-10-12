import os,sys
from runner import E,S,run
os.environ['PIP_FIND_LINKS']='/tmp/hive-astra-7718/20261008-astra-7718/build-prerequisites'
run('pytest',[sys.executable,'-m','pytest','tests/','-q','-p','no:cacheprovider','--basetemp=/tmp/hive-astra-7805-pytest'],S)
for n in ['review7195','review7694','followup7694','focused7701','startup7708','startup_recovery_final7708','clearance7701','marker7701','recovery-final7750','reset7718','exact_restore_final7718','intent_final7727','extra_io7727','intent7734','metadata7734','focused7741']:
 run(n,[sys.executable,str(E/(n+'.py'))])
