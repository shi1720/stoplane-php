"""Controlled HTTP/SSE workload. Work ticks are synthetic, never model tokens."""
import http.server, json, os, select, socket, time, urllib.parse
from pathlib import Path

class Provider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        args = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        ident, shape = args['id'][0], args['shape'][0]
        path = Path(os.environ['STOPLANE_STATE']) / (ident + '.provider')
        def log(kind, **extra):
            with path.open('a') as f: f.write(json.dumps(dict(t=time.time(), event=kind, **extra))+'\n')
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
        begin=time.monotonic(); log('provider_start', shape=shape)
        ticks=0; sent=0; disconnected=False; next_emit=0 if shape=='regular' else .9
        while time.monotonic()-begin < 1.4:
            elapsed=time.monotonic()-begin
            if not disconnected and select.select([self.connection],[],[],0)[0]:
                try: disconnected = self.connection.recv(1, socket.MSG_PEEK) == b''
                except OSError: disconnected=True
                if disconnected: log('peer_closed', ticks=ticks)
            if disconnected and shape!='uncooperative': break
            if not disconnected and elapsed>=next_emit:
                try:
                    self.wfile.write(('data: '+json.dumps({'delta':'x'*64})+'\n\n').encode()); self.wfile.flush(); sent+=1
                except OSError:
                    disconnected=True; log('peer_closed', ticks=ticks)
                    if shape!='uncooperative': break
                next_emit=elapsed+.02
            ticks+=1; time.sleep(.01)
        log('provider_end', ticks=ticks, frames=sent, disconnected=disconnected)

if __name__=='__main__':
    http.server.ThreadingHTTPServer(('127.0.0.1', int(os.environ['STOPLANE_PROVIDER_PORT'])), Provider).serve_forever()
