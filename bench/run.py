"""Run real nginx -> PHP-FPM -> controlled provider trials on loopback.
Usage: python3 bench/run.py --repeats 10
Requires php, php-fpm and nginx binaries; override using environment variables.
"""
import argparse, concurrent.futures as cf, hashlib, itertools, json, os, platform
import random, shutil, socket, subprocess, tempfile, time, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def binary(env, name, homebrew):
    value=os.environ.get(env) or shutil.which(name) or homebrew
    if not Path(value).exists(): raise RuntimeError(f'Missing {name}; set {env}')
    return value
def port():
    with socket.socket() as s: s.bind(('127.0.0.1',0)); return s.getsockname()[1]
def read_events(path):
    return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
def wait_for(fn, seconds=6):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if fn(): return
        time.sleep(.005)
    raise TimeoutError('Readiness barrier failed')

class Stack:
    def __enter__(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='stoplane-')
        self.path=Path(self.tmp.name); (self.path/'sessions').mkdir()
        self.http,self.upstream,self.shared,self.data,self.control=[port() for _ in range(5)]
        php=binary('PHP_BIN','php','/opt/homebrew/opt/php@8.4/bin/php')
        fpm=binary('FPM_BIN','php-fpm','/opt/homebrew/opt/php@8.4/sbin/php-fpm')
        nginx=binary('NGINX_BIN','nginx','/opt/homebrew/opt/nginx/bin/nginx')
        self.versions={'php':subprocess.check_output([php,'-v'],text=True).splitlines()[0],
          'nginx':subprocess.run([nginx,'-v'],capture_output=True,text=True).stderr.strip(),
          'python':platform.python_version(),'platform':platform.platform(),
          'curl':subprocess.check_output([php,'-r','echo json_encode(curl_version());'],text=True),
          'cpu':subprocess.run(['sysctl','-n','machdep.cpu.brand_string'],capture_output=True,text=True).stdout.strip()}
        config=f'[global]\nerror_log = {self.path}/fpm.log\ndaemonize = no\n'
        for name,addr,workers in [('shared',self.shared,3),('data',self.data,2),('control',self.control,1)]:
            config+=f'''[{name}]
listen = 127.0.0.1:{addr}
pm = static
pm.max_children = {workers}
catch_workers_output = yes
clear_env = no
php_admin_value[session.save_path] = {self.path}/sessions
php_admin_value[session.gc_probability] = 0
php_admin_value[output_buffering] = 0
php_admin_value[max_execution_time] = 10
'''
        (self.path/'fpm.conf').write_text(config)
        config=f'''worker_processes 1;
error_log {self.path}/nginx.log;
pid {self.path}/nginx.pid;
events {{ worker_connections 256; }}
http {{
  access_log off;
  fastcgi_temp_path {self.path}/fastcgi;
  map $arg_action $split_backend {{ default 127.0.0.1:{self.data}; cancel 127.0.0.1:{self.control}; }}
  server {{
    listen 127.0.0.1:{self.http};
    location / {{
      fastcgi_pass 127.0.0.1:{self.shared};
      fastcgi_buffering off;
      fastcgi_read_timeout 8s;
      fastcgi_param SCRIPT_FILENAME {ROOT}/src/gateway.php;
      fastcgi_param QUERY_STRING $query_string;
      fastcgi_param REQUEST_METHOD $request_method;
      fastcgi_param HTTP_COOKIE $http_cookie;
      fastcgi_param HTTP_X_CSRF_TOKEN $http_x_csrf_token;
      fastcgi_param CONTENT_LENGTH $content_length;
    }}
    location /split {{
      fastcgi_pass $split_backend;
      fastcgi_buffering off;
      fastcgi_read_timeout 8s;
      fastcgi_param SCRIPT_FILENAME {ROOT}/src/gateway.php;
      fastcgi_param QUERY_STRING $query_string;
      fastcgi_param REQUEST_METHOD $request_method;
      fastcgi_param HTTP_COOKIE $http_cookie;
      fastcgi_param HTTP_X_CSRF_TOKEN $http_x_csrf_token;
      fastcgi_param CONTENT_LENGTH $content_length;
    }}
  }}
}}
'''
        (self.path/'nginx.conf').write_text(config)
        env=dict(os.environ,STOPLANE_STATE=str(self.path),STOPLANE_UPSTREAM=f'http://127.0.0.1:{self.upstream}/',STOPLANE_PROVIDER_PORT=str(self.upstream))
        self.procs=[]; self.logs=[]
        for name,cmd in [('provider',[os.sys.executable,str(ROOT/'bench/provider.py')]),('fpm',[fpm,'-F','-y',str(self.path/'fpm.conf')]),('nginx',[nginx,'-c',str(self.path/'nginx.conf'),'-p',str(self.path),'-g','daemon off;'])]:
            log=(self.path/(name+'.stdout')).open('w'); self.logs.append(log)
            self.procs.append(subprocess.Popen(cmd,env=env,stdout=log,stderr=log))
        def ready():
            if any(p.poll() is not None for p in self.procs):
                raise RuntimeError('\n'.join(p.read_text() for p in self.path.glob('*.log'))+'\n'+'\n'.join(p.read_text() for p in self.path.glob('*.stdout')))
            try: self.request('shared',{'action':'init'}); return True
            except OSError: return False
        wait_for(ready)
        return self
    def __exit__(self,*args):
        for p in self.procs: p.terminate()
        for p in self.procs:
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
        for f in self.logs: f.close()
        self.tmp.cleanup()
    def request(self,lane,params,creds=None,post=False):
        url=f'http://127.0.0.1:{self.http}/{lane}?'+urllib.parse.urlencode(params)
        headers={} if creds is None else {'Cookie':creds['cookie'],'X-CSRF-Token':creds['csrf']}
        req=urllib.request.Request(url,data=b'' if post else None,headers=headers)
        with urllib.request.urlopen(req,timeout=8) as r: return r.read().decode(), dict(r.headers)
    def actor(self,lane):
        body,headers=self.request(lane,{'action':'init'})
        return {'csrf':json.loads(body)['csrf'],'cookie':headers['Set-Cookie'].split(';')[0]}
    def trial(self, spec):
        lane='split' if spec['reserve'] else 'shared'
        ids=[hashlib.sha256(f"{spec['trial']}:{i}".encode()).hexdigest()[:32] for i in range(spec['load'])]
        actors=[self.actor(lane) for _ in ids]
        def launch(i):
            return self.request(lane,dict(action='stream',id=ids[i],release=int(spec['release']),timer=int(spec['timer']),shape=spec['shape'],poll=spec.get('poll',.02)),actors[i],True)[0]
        with cf.ThreadPoolExecutor(max_workers=5) as pool:
            streams=[]
            # Target starts before fillers; pool overload cannot queue the target itself.
            streams.append(pool.submit(launch,0))
            wait_for(lambda:(self.path/(ids[0]+'.provider')).exists())
            for i in range(1,len(ids)): streams.append(pool.submit(launch,i))
            active=min(len(ids),2 if spec['reserve'] else 3)
            wait_for(lambda:sum((self.path/(j+'.provider')).exists() for j in ids)>=active)
            time.sleep(.12)
            requested=time.time()
            response,headers=self.request(lane,dict(action='cancel',id=ids[0]),actors[0],True)
            acknowledged=time.time()
            bodies=[f.result() for f in streams]
        for j in ids: wait_for(lambda j=j:any(e['event']=='provider_end' for e in read_events(self.path/(j+'.provider'))))
        jobs={j:{'gateway':read_events(self.path/(j+'.events')),'provider':read_events(self.path/(j+'.provider'))} for j in ids}
        target=jobs[ids[0]]
        end=next(e for e in target['gateway'] if e['event']=='gateway_end')
        publish=next(e for e in target['gateway'] if e['event']=='cancel_published')
        provider_end=next(e for e in target['provider'] if e['event']=='provider_end')
        observed=[e for e in target['gateway'] if e['event']=='cancel_observed']
        return dict(spec,id=ids[0],requested=requested,acknowledged=acknowledged,
          admission_ms=1000*(publish['t']-requested),ack_ms=1000*(acknowledged-requested),
          gateway_ms=1000*(end['t']-requested),provider_ms=1000*(provider_end['t']-requested),
          cancelled=end['cancelled'],observed_ms=1000*(observed[0]['t']-requested) if observed else None,
          ticks=provider_end['ticks'],checks=end['checks'],bytes=end['bytes'],jobs=jobs)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--repeats',type=int,default=10); parser.add_argument('--out',default='results/raw.jsonl'); args=parser.parse_args()
    rng=random.Random(1720406); specs=[]
    for repeat in range(args.repeats):
        block=[dict(repeat=repeat,release=a,reserve=b,timer=c,load=d,shape=e,experiment='factorial') for a,b,c,d,e in itertools.product([False,True],[False,True],[False,True],[2,3],['regular','silent'])]
        rng.shuffle(block); specs.extend(block)
    specs.extend(dict(repeat=i,release=True,reserve=True,timer=True,load=3,shape='uncooperative',experiment='upstream_limit') for i in range(10))
    specs.extend(dict(repeat=i,release=True,reserve=True,timer=True,load=3,shape='silent',poll=p,experiment='poll_sweep') for p in [.005,.01,.02,.05,.1] for i in range(10))
    out=ROOT/args.out; out.parent.mkdir(exist_ok=True)
    with Stack() as stack, out.open('w') as f:
        (out.parent/'environment.json').write_text(json.dumps(stack.versions,indent=2))
        for n,spec in enumerate(specs):
            spec['trial']=f'{args.out}-{n:04d}'
            row=stack.trial(spec); f.write(json.dumps(row)+'\n'); f.flush()
            if n%16==0: print(f'{n+1}/{len(specs)}: '+json.dumps({k:row[k] for k in ['release','reserve','timer','load','shape','gateway_ms','provider_ms','cancelled']}),flush=True)
    print(f'Saved {len(specs)} trials to {out}',flush=True)
if __name__=='__main__': main()
