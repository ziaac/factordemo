import os, io, json, base64, http.server, socketserver
import torch
from diffusers import AutoPipelineForText2Image
TOKEN = os.environ.get("IMG_API_KEY", "")
MODEL = os.environ.get("IMG_MODEL", "stabilityai/sdxl-turbo")
print("loading", MODEL, "cuda?", torch.cuda.is_available(), flush=True)
pipe = AutoPipelineForText2Image.from_pretrained(MODEL, torch_dtype=torch.float16, variant="fp16").to("cuda")
print("READY", flush=True)
class Hd(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _s(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        self._s(200, {"status":"ok","model":MODEL}) if self.path=="/health" else self._s(404,{"error":"nf"})
    def do_POST(self):
        if self.path != "/generate": return self._s(404, {"error":"nf"})
        if TOKEN and self.headers.get("Authorization","") != "Bearer "+TOKEN: return self._s(401, {"error":"unauthorized"})
        n = int(self.headers.get("Content-Length", 0) or 0)
        d = json.loads(self.rfile.read(n) or b"{}")
        try:
            img = pipe(prompt=d.get("prompt","abstract editorial illustration"),
                       num_inference_steps=int(d.get("steps",3)), guidance_scale=0.0,
                       width=int(d.get("width",1024)), height=int(d.get("height",576))).images[0]
            buf = io.BytesIO(); img.save(buf, format="PNG")
            self._s(200, {"image_base64": base64.b64encode(buf.getvalue()).decode(), "model": MODEL})
        except Exception as e:
            self._s(500, {"error": str(e)})
class TS(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads=True
print("serving :8000", flush=True); TS(("0.0.0.0",8000), Hd).serve_forever()
