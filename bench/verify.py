"""Independent raw-trace checks. No import from runner or analysis implementation."""
import collections, itertools, json, math
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=[json.loads(s) for s in (root/'results/raw.jsonl').read_text().splitlines()]
assert len(rows)==380, len(rows)
assert len({r['trial'] for r in rows})==380
primary=[r for r in rows if r['experiment']=='factorial']
cells=collections.Counter((r['release'],r['reserve'],r['timer'],r['load'],r['shape']) for r in primary)
assert len(primary)==320 and len(cells)==32 and set(cells.values())=={10}
assert set(cells)==set(itertools.product([False,True],[False,True],[False,True],[2,3],['regular','silent']))
library=[json.loads(s) for s in (root/'results/library.jsonl').read_text().splitlines()]
assert len(library)==40
library_cells=collections.Counter((r['driver'],r['release'],r['reserve']) for r in library)
assert library_cells=={('symfony',True,True):10,('symfony',False,True):10,
                      ('symfony',True,False):10,('curl',True,True):10}
rows+=library
assert len({r['trial'] for r in rows})==420
counts=collections.Counter()
for r in rows:
    assert all(math.isfinite(r[k]) and r[k]>=0 for k in ['admission_ms','ack_ms','gateway_ms','provider_ms'])
    for ident,job in r['jobs'].items():
        for channel in ['gateway','provider']:
            es=job[channel]
            assert es and all(es[i]['t']<=es[i+1]['t'] for i in range(len(es)-1))
        ge=[e for e in job['gateway'] if e['event']=='gateway_end']
        pe=[e for e in job['provider'] if e['event']=='provider_end']
        assert len(ge)==len(pe)==1
        assert ge[0]['bytes']>=0 and ge[0]['checks']>0 and pe[0]['ticks']>0
        counts['jobs']+=1
    target=r['jobs'][r['id']]
    g=target['gateway']; p=target['provider']
    end=next(e for e in g if e['event']=='gateway_end')
    publish=next(e for e in g if e['event']=='cancel_published')
    pe=next(e for e in p if e['event']=='provider_end')
    for field,t in [('admission_ms',publish['t']),('gateway_ms',end['t']),('provider_ms',pe['t'])]:
        assert abs(r[field]-1000*(t-r['requested']))<1e-8
    obs=[e for e in g if e['event']=='cancel_observed']
    assert bool(obs)==r['cancelled']==end['cancelled']
    if obs: assert publish['t']<=obs[0]['t']<=end['t']
    # No observation does not imply publication happened after end: natural
    # completion can race with publication after the last callback/check.
    # Retain the cancellation-observed flag rather than inferring it from order.
    if r['experiment']=='factorial':
        predicted=r['release'] and (r['reserve'] or r['load']==2)
        assert r['cancelled']==predicted, r['trial']
        counts['prediction_matches']+=1
        if r['shape']=='silent' and predicted and not r['timer']:
            assert r['observed_ms']>600, r['trial']
    if r['experiment']=='upstream_limit':
        assert r['cancelled'] and r['gateway_ms']<200 and r['provider_ms']>1000
    if r['experiment']=='library':
        if r['release'] and r['reserve']:
            assert r['cancelled'] and r['gateway_ms']<200, r['trial']
        else:
            assert r['gateway_ms']>1000, r['trial']
            # A late marker can be observed during completion processing.
            if obs: assert pe['t']<=obs[0]['t'], r['trial']
        counts['library_control_checks']+=1
    counts['trials']+=1
print(json.dumps(dict(counts),indent=2))
(root/'results/verification.json').write_text(json.dumps(dict(counts),indent=2)+'\n')
