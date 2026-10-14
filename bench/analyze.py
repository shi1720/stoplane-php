"""Regenerate paper tables, macros and vector figures from saved trials."""
import collections, csv, hashlib, json, statistics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
ROOT=Path(__file__).resolve().parents[1]
raw=ROOT/'results/raw.jsonl'; rows=[json.loads(s) for s in raw.read_text().splitlines()]
primary=[r for r in rows if r['experiment']=='factorial']
groups=collections.defaultdict(list)
for r in primary: groups[(r['release'],r['reserve'],r['timer'],r['load'],r['shape'])].append(r)
summary=[]
for key,rs in sorted(groups.items()):
    d=dict(zip(['release','reserve','timer','load','shape'],key)); d['n']=len(rs)
    d['cancelled']=sum(r['cancelled'] for r in rs)
    for k in ['admission_ms','gateway_ms','provider_ms','ticks','checks']:
        d[k+'_median']=statistics.median(r[k] for r in rs)
        d[k+'_min']=min(r[k] for r in rs); d[k+'_max']=max(r[k] for r in rs)
    summary.append(d)
with (ROOT/'results/cells.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
full=[r for r in primary if r['load']==3 and r['shape']=='silent']
def group(a,b,c): return sorted([r for r in full if (r['release'],r['reserve'],r['timer'])==(a,b,c)],key=lambda r:r['repeat'])
good=group(True,True,True)
stats={}
rng=np.random.default_rng(20406)
for key in [(False,False,False),(True,False,False),(True,True,False),(False,True,True),(True,False,True)]:
    base=group(*key); delta=np.array([r['gateway_ms']-s['gateway_ms'] for r,s in zip(base,good)])
    samples=np.median(delta[rng.integers(0,10,size=(10000,10))],axis=1)
    stats[''.join(str(int(x)) for x in key)]={'median_difference_ms':float(np.median(delta)),'bootstrap95':list(map(float,np.quantile(samples,[.025,.975])))}
(ROOT/'results/contrasts.json').write_text(json.dumps(stats,indent=2)+'\n')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
blue='#24516b';orange='#b96b27';grey='#707b82'
def save(name):
    plt.savefig(ROOT/f'figures/{name}.pdf',bbox_inches='tight');plt.savefig(ROOT/f'figures/{name}.png',dpi=180,bbox_inches='tight');plt.close()
fig,ax=plt.subplots(figsize=(8.5,2.7));ax.set_xlim(0,10);ax.set_ylim(0,3);ax.axis('off')
labels=[('Stop request',.1),('Worker admission',2.1),('Session access',4.1),('Poll opportunity',6.1),('Upstream stop',8.1)]
for text,x in labels:
    ax.add_patch(FancyBboxPatch((x,1.5),1.7,.7,boxstyle='round,pad=0.08',facecolor='#edf4f7',edgecolor=blue))
    ax.text(x+.85,1.85,text,ha='center',va='center',fontsize=9)
    if x<8:ax.annotate('',xy=(x+1.98,1.85),xytext=(x+1.8,1.85),arrowprops={'arrowstyle':'->','color':blue})
ax.text(2.95,.9,'Reserve capacity',ha='center',color=blue);ax.text(4.95,.9,'Release lock early',ha='center',color=blue)
ax.text(6.95,.9,'Poll while idle',ha='center',color=blue);ax.text(8.95,.9,'Verify cooperation',ha='center',color=blue)
ax.text(5,.25,'An HTTP acknowledgement certifies publication; it does not certify upstream termination.',ha='center',fontsize=9,color=grey)
save('architecture')
fig,ax=plt.subplots(figsize=(8,4.3));keys=list(__import__('itertools').product([False,True],repeat=3))
for i,k in enumerate(keys):
    vals=[r['gateway_ms'] for r in group(*k)];color=blue if k==(True,True,True) else orange
    ax.scatter(vals,[i+(.035*(j-4.5)) for j in range(len(vals))],color=color,s=19,alpha=.65)
    ax.plot([statistics.median(vals)]*2,[i-.23,i+.23],color='black',lw=2)
ax.set_yticks(range(8));ax.set_yticklabels([' '.join(str(int(x)) for x in k) for k in keys]);ax.set_ylabel('Release / reserve / timer (1 = enabled)')
ax.set_xlabel('Request to gateway end (ms)');ax.set_xlim(-35,1400);ax.grid(axis='x',alpha=.18);ax.invert_yaxis()
ax.set_title('Saturated pool, silent upstream: ten trials per configuration',fontsize=11)
save('ablation')
fig,axes=plt.subplots(1,2,figsize=(8.4,3.4))
for i,rs in enumerate([good,[r for r in rows if r['experiment']=='upstream_limit']]):
    for j,field in enumerate(['gateway_ms','provider_ms']):
        vals=[r[field] for r in rs];axes[0].scatter([i+(j-.5)*.15]*len(vals),vals,color=[blue,orange][j],s=18,alpha=.7,label=['Gateway','Provider'][j] if i==0 else None)
axes[0].set_xticks([0,1]);axes[0].set_xticklabels(['Cooperative','Uncooperative']);axes[0].set_ylabel('Request to end (ms)');axes[0].legend(frameon=False,fontsize=8);axes[0].grid(axis='y',alpha=.18)
for p in [.005,.01,.02,.05,.1]:
    rs=[r for r in rows if r['experiment']=='poll_sweep' and r['poll']==p]
    axes[1].scatter([p*1000]*len(rs),[r['gateway_ms'] for r in rs],s=18,color=blue,alpha=.65)
axes[1].set_xlabel('Configured curl_multi_select wait (ms)');axes[1].set_ylabel('Request to gateway end (ms)');axes[1].grid(alpha=.18)
fig.tight_layout(w_pad=2);save('limits')
macros={
 'GoodGateway':statistics.median(r['gateway_ms'] for r in good),
 'GoodGatewayMax':max(r['gateway_ms'] for r in good),
 'GoodProvider':statistics.median(r['provider_ms'] for r in good),
 'GoodAdmission':statistics.median(r['admission_ms'] for r in good),
 'BaselineGateway':statistics.median(r['gateway_ms'] for r in group(False,False,False)),
 'CallbackGateway':statistics.median(r['gateway_ms'] for r in group(True,True,False)),
 'UncoopProvider':statistics.median(r['provider_ms'] for r in rows if r['experiment']=='upstream_limit'),
 'UncoopGateway':statistics.median(r['gateway_ms'] for r in rows if r['experiment']=='upstream_limit'),
 'SavedTicks':100*(1-statistics.median(r['ticks'] for r in good)/statistics.median(r['ticks'] for r in group(False,False,False))),
}
(ROOT/'paper/results.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+f'{v:.1f}'+'}' for k,v in macros.items())+'\n')
table=''
for k in keys:
    rs=group(*k); gs=[r['gateway_ms'] for r in rs]
    table+=' & '.join([*(str(int(x)) for x in k),f"{sum(r['cancelled'] for r in rs)}/10",f"{statistics.median(r['admission_ms'] for r in rs):.1f}",f'{statistics.median(gs):.1f}',f'{min(gs):.1f}--{max(gs):.1f}'])+' \\\\'+'\n'
(ROOT/'paper/ablation.tex').write_text(r'\begin{tabular}{@{}ccc r r r r@{}}\toprule Release & Reserve & Timer & Observed & Publish & Gateway & Gateway range\\ & & & cancellation & (ms) & (ms) & (ms)\\\midrule'+'\n'+table+r'\bottomrule\end{tabular}'+'\n')
with (ROOT/'results/secondary.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['experiment','poll_ms','n','gateway_median_ms','gateway_min_ms','gateway_max_ms','provider_median_ms','checks_median'])
    for experiment,poll in [('upstream_limit',.02)]+[('poll_sweep',p) for p in [.005,.01,.02,.05,.1]]:
        rs=[r for r in rows if r['experiment']==experiment and r.get('poll',.02)==poll]
        w.writerow([experiment,poll*1000,len(rs),statistics.median(r['gateway_ms'] for r in rs),min(r['gateway_ms'] for r in rs),max(r['gateway_ms'] for r in rs),statistics.median(r['provider_ms'] for r in rs),statistics.median(r['checks'] for r in rs)])
(ROOT/'results/manifest.json').write_text(json.dumps({'raw_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'primary_source_commit':'b685e41','trials':len(rows),'primary_trials':len(primary),'seed':1720406,'bootstrap_seed':20406,'macros':macros},indent=2)+'\n')
print(json.dumps(macros,indent=2))
