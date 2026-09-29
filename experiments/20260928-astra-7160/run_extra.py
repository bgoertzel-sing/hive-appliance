from run_review import *
for n in ["semantic_7133", "focused_witnesses", "correct_owner_traces"]:
 run(n,[sys.executable,str(E/(n+".py"))])
for n in ["semantic_probes", "legacy_information_loss", "expanded_probes", "followup_probes"]:
 run("a-"+n,[sys.executable,str(E/"review-a"/(n+".py"))],E/"review-a")
