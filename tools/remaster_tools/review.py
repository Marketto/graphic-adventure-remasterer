"""Self-contained HTML review pages (images embedded as JPEG thumbnails)."""
import base64
import html
import io
import json
import os

from PIL import Image

from . import rawframe


def _thumb(path_or_img, width=960):
    img = path_or_img if isinstance(path_or_img, Image.Image) else (
        rawframe.read_raw(path_or_img).rgb() if str(path_or_img).endswith(".raw") else Image.open(path_or_img))
    img = img.convert("RGB")
    if img.width > width:
        img = img.resize((width, max(1, img.height * width // img.width)), Image.LANCZOS)
    elif img.width < width // 2:
        k = max(1, (width // 2) // img.width)
        img = img.resize((img.width * k, img.height * k), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


CSS = """
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1b18;--mute:#6b665d;--line:#e2ddd3;--acc:#b2361f}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15130f;--card:#1f1c17;--ink:#eee8dc;--mute:#a39b8c;--line:#353027;--acc:#e0644a}}
:root[data-theme=dark]{--bg:#15130f;--card:#1f1c17;--ink:#eee8dc;--mute:#a39b8c;--line:#353027;--acc:#e0644a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}
header{padding:20px 16px;max-width:1200px;margin:auto}h1{font-size:22px;margin:0 0 6px}
p.sub{color:var(--mute);margin:0}main{max-width:1200px;margin:auto;padding:0 16px 96px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:14px 0}
.head{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;justify-content:space-between}
.tag{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--mute)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px;margin-top:10px}
figure{margin:0}figure img{width:100%;border-radius:6px;display:block;image-rendering:auto}
figcaption{font-size:13px;color:var(--mute);margin-top:4px}label{display:flex;gap:6px;align-items:center;cursor:pointer}
.why{color:var(--mute);font-size:13px}footer{position:fixed;bottom:0;left:0;right:0;background:var(--card);
border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;justify-content:center;align-items:center}
button{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:9px 16px;font-size:15px;cursor:pointer}
#count{color:var(--mute)}
"""

JS = """
const KEY='rs-review-'+document.title;function load(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return{}}}
function save(d){try{localStorage.setItem(KEY,JSON.stringify(d))}catch(e){}}
const d=load();document.querySelectorAll('input[type=radio]').forEach(r=>{if(d[r.name]===r.value)r.checked=true;
r.addEventListener('change',()=>{const x=load();x[r.name]=r.value;save(x);count()})});
function collect(){const o={};document.querySelectorAll('input[type=radio]:checked').forEach(r=>o[r.name]=r.value);return o}
function count(){const n=Object.keys(collect()).length,t=document.querySelectorAll('.card').length;document.getElementById('count').textContent=n+' / '+t+' scene decise'}
document.getElementById('export').onclick=()=>{const b=new Blob([JSON.stringify(collect(),null,2)],{type:'application/json'});
const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='decisions.json';a.click()};
document.getElementById('copy').onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(JSON.stringify(collect(),null,2))};count();
"""


def widescreen_gallery(plan_path, variants_dir, out_path, title="Revisione 16:9"):
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    cards = []
    for s in plan["scenes"]:
        if not s.get("variants") and s["class"] != "scroll-wide":
            continue
        num = len(cards) + 1   # numbered sheets: the user can answer "scarta 4, 17, 23"
        sc = html.escape(s["scene"])
        figs = [f'<figure><img alt="originale {sc}" src="{_thumb(s["source"])}"><figcaption>Originale</figcaption></figure>']
        opts = []
        for v in s.get("variants", []):
            val = v["file"].rsplit(".", 2)[-2]
            label = {"borders": "Bordi (4:3 decorato)", "inpaint": f"Estensione {val.upper()} (ricostruita, nitida)"}.get(
                v["kind"], f"Estensione {val.upper()} (generativa, seed {v['seed']})")
            figs.append(f'<figure><img alt="{label}" src="{_thumb(os.path.join(variants_dir, v["file"]))}">'
                        f'<figcaption><label><input type="radio" name="{sc}" value="{val}"> {label}</label></figcaption></figure>')
        if s["class"] == "scroll-wide":
            opts.append(f'<label><input type="radio" name="{sc}" value="auto" checked> Allargamento automatico (scorrimento)</label>')
        opts.append(f'<label><input type="radio" name="{sc}" value="4:3"> Lascia 4:3 con bande nere</label>')
        opts.append(f'<label><input type="radio" name="{sc}" value="redo"> Da rifare</label>')
        cards.append(f'<section class="card" id="s{num}"><div class="head"><strong>{num}. {sc}</strong>'
                     f'<span class="tag">{html.escape(s["class"])} · {s.get("confidence", "")}</span></div>'
                     f'<div class="why">{html.escape(s.get("why", ""))}</div><div class="grid">{"".join(figs)}</div>'
                     f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px">{"".join(opts)}</div></section>')
    page = f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body><header><h1>{html.escape(title)}</h1>
<p class="sub">Scegli per ogni scena. Le parti estese sono inventate: entrano nel remaster solo se le approvi.
I pixel originali non sono mai modificati.</p></header><main>{''.join(cards)}</main>
<footer><span id="count"></span><button id="copy" type="button">Copia scelte</button><button id="export" type="button">Esporta decisions.json</button></footer>
<script>{JS}</script></body></html>"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return {"scenes": len(cards), "path": out_path}


def compare_gallery(pairs, out_path, title="Originale vs HD"):
    """pairs: list of (label, original_path, hd_path)."""
    cards = []
    for label, a, b in pairs:
        cards.append(f'<section class="card"><strong>{html.escape(label)}</strong><div class="grid">'
                     f'<figure><img alt="originale" src="{_thumb(a)}"><figcaption>Originale</figcaption></figure>'
                     f'<figure><img alt="HD" src="{_thumb(b)}"><figcaption>Rimasterizzato</figcaption></figure></div>'
                     f'<div style="display:flex;gap:16px;margin-top:8px"><label><input type="radio" name="{html.escape(label)}" value="ok"> Approvato</label>'
                     f'<label><input type="radio" name="{html.escape(label)}" value="redo"> Da rifare</label></div></section>')
    page = f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body><header><h1>{html.escape(title)}</h1>
<p class="sub">Approva o rimanda indietro ogni asset.</p></header><main>{''.join(cards)}</main>
<footer><span id="count"></span><button id="copy" type="button">Copia scelte</button><button id="export" type="button">Esporta decisions.json</button></footer>
<script>{JS}</script></body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return {"items": len(cards), "path": out_path}
