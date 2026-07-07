import os, json, http.server, socketserver
from sentence_transformers import SentenceTransformer
TOKEN = os.environ.get("EMBED_API_KEY", "")
MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")
print("loading", MODEL, flush=True)
m = SentenceTransformer(MODEL, device="cuda")
print("READY", flush=True)
class Hd(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _s(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path in ("/health","/v1/models"): self._s(200, {"status":"ok","model":MODEL,"data":[{"id":MODEL}]})
        else: self._s(404, {"error":"nf"})
    def do_POST(self):
        if not self.path.endswith("/embeddings"): return self._s(404, {"error":"nf"})
        if TOKEN and self.headers.get("Authorization","") != "Bearer "+TOKEN: return self._s(401, {"error":"unauthorized"})
        n = int(self.headers.get("Content-Length", 0) or 0); d = json.loads(self.rfile.read(n) or b"{}")
        inp = d.get("input", [])
        if isinstance(inp, str): inp = [inp]
        try:
            vecs = m.encode(inp, normalize_embeddings=True).tolist()
            self._s(200, {"object":"list","model":MODEL,
                          "data":[{"object":"embedding","index":i,"embedding":v} for i,v in enumerate(vecs)]})
        except Exception as e:
            self._s(500, {"error": str(e)})
class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads=True
print("serving :8000", flush=True); TS(("0.0.0.0",8000), Hd).serve_forever()
