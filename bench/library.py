"""Separately specified, pinned-library replication of the cancellation contract."""
import json, os, random, subprocess
from pathlib import Path
from run import ROOT, Stack, wait_for

def switch_script(stack, library):
    proc=stack.procs[-1];proc.terminate();proc.wait(timeout=5)
    path=stack.path/'nginx.conf'
    text=path.read_text().replace('src/symfony_gateway.php','src/gateway.php')
    if library: text=text.replace('src/gateway.php','src/symfony_gateway.php')
    path.write_text(text)
    stack.procs[-1]=subprocess.Popen(proc.args,stdout=stack.logs[-1],stderr=stack.logs[-1])
    def ready():
        try: stack.request('shared',{'action':'init'});return True
        except OSError:return False
    wait_for(ready)

def main():
    rng=random.Random(271828)
    out=ROOT/'results/library.jsonl'
    with out.open('w') as f:
        for repeat in range(10):
            cases=[('symfony',True,True),('symfony',False,True),('symfony',True,False),('curl',True,True)]
            rng.shuffle(cases)
            with Stack() as stack:
                for driver,release,reserve in cases:
                    switch_script(stack,driver=='symfony')
                    spec=dict(driver=driver,repeat=repeat,release=release,reserve=reserve,timer=True,load=3,shape='silent',experiment='library',trial=f'library-{repeat}-{driver}-{release}-{reserve}')
                    row=stack.trial(spec);f.write(json.dumps(row)+'\n');f.flush()
                print(f'Library block {repeat+1}/10 complete',flush=True)
if __name__=='__main__':main()
