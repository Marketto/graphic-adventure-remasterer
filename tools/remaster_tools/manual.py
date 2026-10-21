"""Game manual: a cleaned, translated text (`manual/<lang>.md`) shown in game by the engine and
a self-contained HTML page, styled like the game, shipped with the release.

The source is ALWAYS the user's own copy (printed manual scanned or photographed, or the
manual file on the game disc). The manual is a protected work like the game: it goes in the
private repository and in the pack only under the same distribution rules as the other
derived assets (see references/legal-distribution.md).

Markdown subset understood here and by the engine's reader:
  # / ## / ### headings, paragraphs, blank line between blocks, "- " lists, **bold**, *italic*,
  ![caption](images/file.png) on a line of its own, "| a | b |" tables, `> ` boxed notes.
"""
import html
import os
import re

BLOCK_IMG = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")


def _inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    return s


def blocks(md):
    out, para, lst, table = [], [], [], []

    def flush():
        nonlocal para, lst, table
        if para:
            out.append(("p", " ".join(para)))
        if lst:
            out.append(("ul", lst))
        if table:
            out.append(("table", table))
        para, lst, table = [], [], []
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            flush()
            out.append((f"h{len(m.group(1))}", m.group(2).strip()))
            continue
        m = BLOCK_IMG.match(line.strip())
        if m:
            flush()
            out.append(("img", (m.group(1), m.group(2))))
            continue
        if line.lstrip().startswith("- "):
            if para or table:
                flush()
            lst.append(line.lstrip()[2:].strip())
            continue
        if line.lstrip().startswith("|"):
            if para or lst:
                flush()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                table.append(cells)
            continue
        if line.startswith("> "):
            flush()
            out.append(("note", line[2:].strip()))
            continue
        if lst or table:
            flush()
        para.append(line.strip())
    flush()
    return out


def check(md_path, codepage=None, base_dir=None):
    """Structure, images that exist, characters the game font may lack (with `codepage`)."""
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    base_dir = base_dir or os.path.dirname(os.path.abspath(md_path))
    bl = blocks(md)
    problems, warnings = [], []
    if not any(k == "h1" for k, _v in bl):
        warnings.append("nessun titolo di primo livello (#)")
    for k, v in bl:
        if k == "img" and not os.path.exists(os.path.join(base_dir, v[1])):
            problems.append(f"immagine mancante: {v[1]}")
    if codepage:
        bad = sorted({c for c in md if ord(c) > 127 and not _encodable(c, codepage)})
        if bad:
            warnings.append("caratteri fuori dalla codepage %s (servono glifi nel font del menu): %s" % (codepage, "".join(bad)))
    words = len(re.findall(r"\w+", md))
    return {"blocks": len(bl), "words": words, "headings": [v for k, v in bl if k in ("h1", "h2")],
            "problems": problems, "warnings": warnings}


def _encodable(c, cp):
    try:
        c.encode(cp)
        return True
    except UnicodeEncodeError:
        return False


def to_html(md_path, out_path, title=None, colors=None, font_css=None, lang="it"):
    """One self-contained page (images stay next to it). colors: {"bg", "panel", "text", "accent"}
    or directly the roles of the GUI theme (analysis/ui-palette.json): same colours as the menus."""
    c = {"bg": "#1d1b19", "panel": "#f4ecd8", "text": "#2a241f", "accent": "#8a2a12"}
    colors = dict(colors or {})
    for role, key in (("fondo", "bg"), ("pannello", "panel"), ("testo", "text"), ("pulsante", "accent")):
        if role in colors:  # roles of the GUI theme (rstool.py ui palette)
            colors.setdefault(key, colors.pop(role))
    c.update({k: v for k, v in colors.items() if k in c})
    with open(md_path, encoding="utf-8") as f:
        bl = blocks(f.read())
    title = title or next((v for k, v in bl if k == "h1"), "Manuale")
    body = []
    toc = []
    for i, (k, v) in enumerate(bl):
        if k in ("h1", "h2", "h3"):
            anchor = f"s{i}"
            if k == "h2":
                toc.append(f'<li><a href="#{anchor}">{_inline(v)}</a></li>')
            body.append(f'<{k} id="{anchor}">{_inline(v)}</{k}>')
        elif k == "p":
            body.append(f"<p>{_inline(v)}</p>")
        elif k == "ul":
            body.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in v) + "</ul>")
        elif k == "table":
            rows = ["<tr>" + "".join(f"<td>{_inline(x)}</td>" for x in r) + "</tr>" for r in v]
            body.append("<table>" + "".join(rows) + "</table>")
        elif k == "img":
            body.append(f'<figure><img src="{html.escape(v[1])}" alt="{html.escape(v[0])}">'
                        f"<figcaption>{_inline(v[0])}</figcaption></figure>")
        elif k == "note":
            body.append(f'<aside>{_inline(v)}</aside>')
    css = f"""
:root{{--bg:{c['bg']};--panel:{c['panel']};--text:{c['text']};--accent:{c['accent']}}}
body{{margin:0;background:var(--bg);color:var(--text);font:17px/1.55 Georgia,serif}}
main{{max-width:46rem;margin:0 auto;background:var(--panel);padding:2rem 1.25rem 4rem}}
h1,h2,h3{{color:var(--accent);line-height:1.2}} h1{{font-size:2rem}}
img{{max-width:100%;height:auto;image-rendering:auto}} figure{{margin:1.5rem 0;text-align:center}}
figcaption{{font-size:.9rem;opacity:.8}} table{{border-collapse:collapse;width:100%}}
td{{border:1px solid color-mix(in srgb,var(--text) 30%,transparent);padding:.3rem .5rem}}
aside{{border-left:4px solid var(--accent);padding:.5rem 1rem;margin:1rem 0;background:color-mix(in srgb,var(--accent) 8%,transparent)}}
nav ul{{columns:2;padding-left:1.2rem}} a{{color:var(--accent)}}
{font_css or ''}"""
    page = (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f"<style>{css}</style></head><body><main>"
            + (f"<nav><ul>{''.join(toc)}</ul></nav>" if len(toc) > 2 else "")
            + "".join(body) + "</main></body></html>")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return {"html": out_path, "sections": len(toc)}
