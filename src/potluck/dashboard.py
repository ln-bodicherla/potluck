"""A tiny local web dashboard: pool machines + a live route/split plan.

Stdlib http.server only. `render_page()` is pure (takes data, returns HTML) so it can
be tested without binding a socket; the handler just wires request → render.

    potluck dashboard --port 8777
    open http://localhost:8777/            (defaults)
    open http://localhost:8777/?model=llama-3.3-70b&quant=q3&link=ethernet
"""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from . import config, engine, models, planner
from .devices import Device

_STYLE = """
body{font:15px/1.5 -apple-system,system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h1{font-size:1.5rem}h2{font-size:1.05rem;margin-top:1.8rem;color:#444}
table{border-collapse:collapse;width:100%;margin:.5rem 0}
th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #eee}
th{color:#888;font-weight:600;font-size:.8rem;text-transform:uppercase;letter-spacing:.03em}
.yes{color:#0a7d2c;font-weight:600}.no{color:#c0392b;font-weight:600}
.tps{font-variant-numeric:tabular-nums;font-weight:600}
.pill{display:inline-block;background:#f0f0f3;border-radius:999px;padding:.1rem .6rem;font-size:.8rem;margin-right:.3rem}
form{margin:.5rem 0}input,select{font:inherit;padding:.25rem .4rem;margin-right:.4rem}
.note{color:#777;font-size:.85rem}.dot{color:#c0392b}.dot.on{color:#0a7d2c}
"""


def _load_devices() -> list[Device]:
    return [Device(**d) for d in config.load_devices()]


def render_page(devices: list[Device], model_key: str, quant: str, link: str,
                api_reachable: bool = False) -> str:
    esc = html.escape
    online = '<span class="dot on">●</span> engine reachable' if api_reachable \
        else '<span class="dot">●</span> engine offline'

    dev_rows = "".join(
        f"<tr><td>{esc(d.name)}</td><td>{d.ram_gb:.0f} GB</td>"
        f"<td>{esc(d.backend)}</td><td>{d.usable_gb():.1f} GB</td></tr>"
        for d in devices
    ) or '<tr><td colspan="4" class="note">No machines registered yet.</td></tr>'
    total = sum(d.usable_gb() for d in devices)

    plan_html = ""
    try:
        model = models.resolve(model_key)
        need = models.footprint_gb(model, quant)
        strategies = planner.plan(devices, model, quant=quant, link=link)
        rows = ""
        for s in strategies:
            fits = '<span class="yes">yes</span>' if s.fits else '<span class="no">NO</span>'
            tps = f'{s.tokens_per_sec:.1f}' if s.fits else "—"
            rows += (f"<tr><td>{esc(s.kind)}</td><td>{esc(s.device_label())}</td>"
                     f"<td>{fits}</td><td class='tps'>{tps}</td><td class='note'>{esc(s.note)}</td></tr>")
        plan_html = (
            f"<p class='note'>{esc(model.name)} @ {esc(quant)} needs ~{need:.1f} GB · link {esc(link)}</p>"
            "<table><tr><th>Strategy</th><th>Machines</th><th>Fits</th><th>~tok/s</th><th>Note</th></tr>"
            f"{rows}</table>"
        )
    except ValueError as e:
        plan_html = f"<p class='no'>{esc(str(e))}</p>"

    opts = "".join(
        f'<option value="{k}"{" selected" if k == model_key else ""}>{esc(v.name)}</option>'
        for k, v in models.CATALOG.items()
    )
    quant_opts = "".join(
        f'<option{" selected" if q == quant else ""}>{q}</option>' for q in models.QUANT_GB_PER_B
    )
    link_opts = "".join(
        f'<option{" selected" if l == link else ""}>{l}</option>' for l in ("wifi", "ethernet", "thunderbolt")
    )

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Potluck</title><style>{_STYLE}</style></head><body>
<h1>🍲 Potluck</h1>
<p>{online} · <span class="pill">{len(devices)} machine{"s" if len(devices) != 1 else ""}</span>
<span class="pill">{total:.0f} GB usable</span></p>

<h2>Machines</h2>
<table><tr><th>Name</th><th>RAM</th><th>Backend</th><th>Usable</th></tr>{dev_rows}</table>

<h2>Plan a model — you decide route vs split</h2>
<form method="get">
  <select name="model">{opts}</select>
  <select name="quant">{quant_opts}</select>
  <select name="link">{link_opts}</select>
  <button type="submit">Plan</button>
</form>
{plan_html}
<p class="note">Speeds are rough estimates to compare options — run <code>potluck bench</code> to calibrate.</p>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        q = parse_qs(urlparse(self.path).query)
        devices = _load_devices()
        model_key = q.get("model", ["qwen2.5-32b"])[0]
        quant = q.get("quant", ["q4"])[0]
        link = q.get("link", ["wifi"])[0]
        reachable = engine.probe_api("http://localhost:8000/v1")
        page = render_page(devices, model_key, quant, link, api_reachable=reachable)
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # silence per-request logging
        pass


def serve(host: str = "127.0.0.1", port: int = 8777) -> None:
    httpd = HTTPServer((host, port), _Handler)
    print(f"Potluck dashboard → http://{host}:{port}/   (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
