"""Executable ownership, CSRF, idempotency and generation-isolation checks."""
import concurrent.futures as cf, hashlib, json, time, urllib.error
from run import ROOT, Stack, wait_for, read_events

def main():
    checked=[]
    with Stack() as stack:
        owner=stack.actor('split');other=stack.actor('split')
        def ident(label):return hashlib.sha256(('auth-'+label).encode()).hexdigest()[:32]
        def call(action,ident,actor):return stack.request('split',dict(action=action,id=ident),actor,True)
        def expect_error(code,action,ident,actor,label):
            try:call(action,ident,actor)
            except urllib.error.HTTPError as e:assert e.code==code,(label,e.code)
            else:raise AssertionError(label)
            checked.append(label)
        expect_error(400,'cancel','../state',owner,'malformed ID rejected')
        expect_error(403,'cancel',ident('absent'),other,'unknown ID rejected')
        target=ident('target')
        with cf.ThreadPoolExecutor(max_workers=3) as pool:
            stream=pool.submit(stack.request,'split',dict(action='stream',id=target,release=1,timer=1,shape='silent'),owner,True)
            wait_for(lambda:(stack.path/(target+'.owner')).exists() and len((stack.path/(target+'.owner')).read_text())==32)
            expect_error(403,'cancel',target,other,'cross-session cancellation rejected')
            expect_error(403,'cancel',target,dict(owner,csrf='wrong'),'wrong CSRF rejected')
            expect_error(403,'cancel',target,dict(owner,csrf=''),'missing CSRF rejected')
            assert not (stack.path/(target+'.cancel')).exists();checked.append('rejections do not publish marker')
            (stack.path/(target+'.cancel')).mkdir()
            expect_error(503,'cancel',target,owner,'publication failure is not acknowledged')
            (stack.path/(target+'.cancel')).rmdir()
            call('cancel',target,owner);call('cancel',target,owner);checked.append('repeated cancellation accepted')
            stream.result()
        es=read_events(stack.path/(target+'.events'))
        assert next(e for e in es if e['event']=='gateway_end')['cancelled'];checked.append('authorized cancellation observed')
        expect_error(409,'stream',target,owner,'duplicate generation rejected')
        fresh=ident('fresh')
        with cf.ThreadPoolExecutor(max_workers=2) as pool:
            stream=pool.submit(stack.request,'split',dict(action='stream',id=fresh,release=1,timer=1,shape='regular'),owner,True)
            wait_for(lambda:(stack.path/(fresh+'.owner')).exists() and len((stack.path/(fresh+'.owner')).read_text())==32)
            call('cancel',target,owner);stream.result()
        assert not (stack.path/(fresh+'.cancel')).exists();checked.append('late old-generation cancel does not mark new generation')
        es=read_events(stack.path/(fresh+'.events'))
        assert not next(e for e in es if e['event']=='gateway_end')['cancelled'];checked.append('new generation completes independently')
    report={'assertions':len(checked),'checks':checked,'passed':True}
    (ROOT/'results/authorization.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
