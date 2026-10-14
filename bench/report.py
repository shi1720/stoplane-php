"""Generate remaining manuscript includes without manually transcribing results."""
import csv, hashlib, json, statistics
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
paper=ROOT/'paper';results=ROOT/'results'
env=json.loads((results/'environment.json').read_text())
curl=json.loads(env['curl'])
cpu=env['cpu'] or env['platform']
text=(r'\paragraph{Recorded environment.} The main run used '+env['php'].replace('(cli)','').replace('(built:','(build:')+r'; '+env['nginx'].replace('nginx version: ','')+r'; libcurl '+curl['version']+r'; Python '+env['python']+r'; and '+cpu+r'. All measured services ran locally on '+env['platform'].replace('_',r'\_')+r'. '+'Exact libcurl features and dependency values are retained in the machine-readable environment file.\n')
(paper/'environment.tex').write_text(text)
contrasts=json.loads((results/'contrasts.json').read_text())
d=contrasts['000'];lo,hi=d['bootstrap95']
(paper/'contrasts.tex').write_text(f"The paired median reduction from the fully disabled row to the fully enabled row is {d['median_difference_ms']:.1f} ms, with a descriptive paired-bootstrap interval of [{lo:.1f}, {hi:.1f}] ms. This contrast combines all three controls; the ablation rows identify the distinct failure boundaries rather than attributing the total reduction to one primitive.\n")
cells=list(csv.DictReader((results/'cells.csv').open()))
for c in cells:
    for k in ['n','cancelled','load']:c[k]=int(c[k])
    for k in ['admission_ms_median','gateway_ms_median','gateway_ms_min','gateway_ms_max']:c[k]=float(c[k])
text=''
for load in [2,3]:
    text+=r'\begin{table}[ht]\centering\small\begin{tabular}{@{}lccc r r r@{}}'+'\n'+r'\toprule Output & Release & Reserve & Timer & Observed & Publish (ms) & Gateway (ms)\\\midrule'+'\n'
    for c in sorted([c for c in cells if c['load']==load],key=lambda c:(c['shape'],c['release'],c['reserve'],c['timer'])):
        text+=' & '.join([c['shape'],*(str(int(c[k]=='True')) for k in ['release','reserve','timer']),f"{c['cancelled']}/10",f"{c['admission_ms_median']:.1f}",f"{c['gateway_ms_median']:.1f}"])+r' \\'+'\n'
    text+=r'\bottomrule\end{tabular}'+f'\\caption{{Complete factorial cells with {load} offered streams. Latencies are cell medians; each row contains ten trials. The full CSV additionally reports ranges, provider termination, work ticks and check counts.}}\\end{{table}}\n'
(paper/'all_cells.tex').write_text(text)
secondary=list(csv.DictReader((results/'secondary.csv').open()))
sweep=[r for r in secondary if r['experiment']=='poll_sweep']
text=r'\begin{table}[ht]\centering\small\begin{tabular}{@{}rrrr@{}}\toprule Wait (ms) & Gateway median (ms) & Gateway range (ms) & Checks, median\\\midrule'+'\n'
for r in sweep:
    text+=f"{float(r['poll_ms']):.0f} & {float(r['gateway_median_ms']):.1f} & {float(r['gateway_min_ms']):.1f}--{float(r['gateway_max_ms']):.1f} & {float(r['checks_median']):.1f}"+r' \\'+'\n'
text+=r'\bottomrule\end{tabular}\caption{Secondary polling sweep: ten saturated-silent trials per setting with release and reservation enabled. Check counts include timer and body-callback checks, not measured CPU utilization.}\label{tab:poll}\end{table}'+'\n'
text+='The timer sweep in Table~\\ref{tab:poll} exposes the observation-latency tradeoff without treating the configured wait as a strict deadline. Cancellation occurs at a fixed offset after readiness; phase alignment means median latency need not increase monotonically with the wait. Check counts describe application observation frequency, not CPU overhead or an optimal production interval.\n'
(paper/'poll_results.tex').write_text(text)
rs=[json.loads(l) for l in (results/'library.jsonl').read_text().splitlines()]
assert len(rs)==40
groups={}
for driver,release,reserve in [('symfony',True,True),('symfony',False,True),('symfony',True,False),('curl',True,True)]:
    vals=sorted([r for r in rs if (r['driver'],r['release'],r['reserve'])==(driver,release,reserve)],key=lambda r:r['repeat'])
    assert len(vals)==10
    groups[(driver,release,reserve)]=vals
good=groups[('symfony',True,True)];baseline=groups[('curl',True,True)]
delta=np.array([r['gateway_ms']-s['gateway_ms'] for r,s in zip(good,baseline)])
rng=np.random.default_rng(314159);boot=np.median(delta[rng.integers(0,10,size=(10000,10))],axis=1)
interval=np.quantile(boot,[.025,.975])
text=r'\begin{table}[ht]\centering\small\begin{tabular}{@{}lccrrr@{}}\toprule Client & Release & Reserve & Observed & Gateway (ms) & Range (ms)\\\midrule'+'\n'
report=[]
for k,vals in groups.items():
    d={'driver':k[0],'release':k[1],'reserve':k[2],'n':10,'cancelled':sum(r['cancelled'] for r in vals),'median_ms':statistics.median(r['gateway_ms'] for r in vals),'min_ms':min(r['gateway_ms'] for r in vals),'max_ms':max(r['gateway_ms'] for r in vals)}
    report.append(d)
    text+=f"{k[0]} & {int(k[1])} & {int(k[2])} & {d['cancelled']}/10 & {d['median_ms']:.1f} & {d['min_ms']:.1f}--{d['max_ms']:.1f}"+r' \\'+'\n'
text+=r'\bottomrule\end{tabular}\caption{Separate Symfony v8.1.9 extension: three offered streams, silent provider and 20 ms timed observation; ten randomized blocks.}\label{tab:library}\end{table}'+'\n'
text+=f"Symfony's documented timeout-aware stream and response cancellation satisfy the same observation contract when release and reservation are enabled: {sum(r['cancelled'] for r in good)}/10 trials observe cancellation, with median termination {statistics.median(r['gateway_ms'] for r in good):.1f} ms. Without release, no trial records observation. Without reservation, one of ten trials records a late observation after the provider has already ended naturally; all ten gateway lifetimes remain above one second. Thus an observed marker can also arrive too late to interrupt work. This completion race reinforces the need to inspect provider events as well as the gateway flag. The paired median Symfony-minus-direct-cURL difference is {np.median(delta):.1f} ms, with descriptive bootstrap interval [{interval[0]:.1f}, {interval[1]:.1f}] ms. This small integration comparison provides no basis for claiming that StopLane's direct client is superior to Symfony. It supports the broader interpretation: a mature client solves observation opportunities, while deployment controls must also solve admission.\n"
(paper/'library_results.tex').write_text(text)
(results/'library_summary.json').write_text(json.dumps({'cells':report,'symfony_minus_curl_median_ms':float(np.median(delta)),'bootstrap95':list(map(float,interval))},indent=2)+'\n')
manifest=json.loads((results/'manifest.json').read_text())
manifest['files_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [results/'raw.jsonl',results/'library.jsonl',results/'authorization.json',ROOT/'composer.lock',ROOT/'src/gateway.php',ROOT/'src/symfony_gateway.php']}
manifest['library_trials']=len(rs)
(results/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(report,indent=2))
