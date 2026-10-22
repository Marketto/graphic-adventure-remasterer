"""Composite SoundFont from a JSON recipe ("orchestra" strategy for dynamic MIDI music).

The engine keeps playing the MIDI (jumps, loops, part volumes stay intact); the remaster changes
only the SoundFont: a free General MIDI base bank, orchestral sections taken from other free
banks, fixes in the GM slots that the engine's program conversion table picks wrongly, a gentler
velocity curve and credits for every source. Pure Python (RIFF/sfbk), no dependency.

Recipe (paths relative to the recipe file):
{
  "base": "base-gm.sf2",                         # sf2 or sf3
  "imports": [{"slot": [0, 56], "from": "brass.sf2", "preset": [0, 0],
               "attenuation_cb": 0, "transpose": 0}],   # preset of another sf2 into a GM slot
  "copies":  [{"slot": [0, 79], "from_slot": [0, 73]}], # a preset of the base into another slot
  "velocity_attenuation_cb": -480,   # preset modulator velocity->attenuation, added to the
                                     # default 960 cB: -480 = half as steep (period modules)
  "keep": [[0, 47], [128, 0]],       # optional: keep only these presets (+ slots and copies)
  "credits": [{"source": "brass.sf2", "author": "...", "license": "CC BY 3.0", "url": "..."}]
}
Imports need an sf2 base and sf2 sources (PCM samples); on an sf3 base only "copies"."""
import json
import os
import struct

GEN_INSTRUMENT, GEN_SAMPLEID, GEN_ATTEN, GEN_COARSE = 41, 53, 48, 51
# licenses that require an attribution in the credits of the release
ATTRIBUTION = ("cc by", "cc-by", "sampling plus", "cc sampling", "attribution")


def _chunks(d, p, end):
    while p + 8 <= end:
        cid, ln = d[p:p + 4], struct.unpack("<I", d[p + 4:p + 8])[0]
        yield cid, p + 8, min(ln, end - p - 8)
        # RIFF pads odd chunks with one zero byte, but some sf3 writers do not: skip it only if
        # it is there
        p += 8 + ln + (1 if ln & 1 and d[p + 8 + ln:p + 9 + ln] == b"\0" else 0)


def _recs(b, size):
    return [b[i:i + size] for i in range(0, len(b) - size + 1, size)]


class SoundFont:
    def __init__(self, path):
        with open(path, "rb") as f:
            d = f.read()
        if d[:4] != b"RIFF" or d[8:12] != b"sfbk":
            raise ValueError(f"{path}: non è un SoundFont (RIFF sfbk)")
        self.path, self.info, self.smpl, pd = path, b"", b"", {}
        for cid, p, ln in _chunks(d, 12, len(d)):
            if cid != b"LIST":
                continue
            kind = d[p:p + 4]
            for sid, q, sl in _chunks(d, p + 4, p + ln):
                if kind == b"INFO":
                    self.info += d[q - 8:q + sl] + (b"\0" if sl & 1 else b"")
                elif sid == b"smpl":
                    self.smpl = d[q:q + sl]
                elif kind == b"pdta":
                    pd[sid.decode("latin-1")] = d[q:q + sl]
        missing = {"phdr", "pbag", "pmod", "pgen", "inst", "ibag", "imod", "igen", "shdr"} - set(pd)
        if missing:
            raise ValueError(f"{path}: SoundFont incompleto (manca {', '.join(sorted(missing))})")
        self.version = struct.unpack("<HH", self.info[8:12]) if self.info[:4] == b"ifil" else (2, 1)
        gens = lambda b: [struct.unpack("<HH", r) for r in _recs(b, 4)]
        self.presets = self._zones(_recs(pd["phdr"], 38), 24, _recs(pd["pbag"], 4), gens(pd["pgen"]),
                                   _recs(pd["pmod"], 10))
        self.insts = self._zones(_recs(pd["inst"], 22), 20, _recs(pd["ibag"], 4), gens(pd["igen"]),
                                 _recs(pd["imod"], 10))
        self.shdr = _recs(pd["shdr"], 46)[:-1]

    @property
    def compressed(self):
        return self.version[0] >= 3

    @staticmethod
    def _zones(hdrs, off, bags, gens, mods):
        out = []
        for h, nx in zip(hdrs, hdrs[1:]):
            a, b = struct.unpack("<H", h[off:off + 2])[0], struct.unpack("<H", nx[off:off + 2])[0]
            zones = []
            for i in range(a, b):
                g0, m0 = struct.unpack("<HH", bags[i])
                g1, m1 = struct.unpack("<HH", bags[i + 1])
                zones.append([list(gens[g0:g1]), list(mods[m0:m1])])
            out.append({"hdr": h, "zones": zones})
        return out

    @staticmethod
    def key(p):
        return struct.unpack("<H", p["hdr"][22:24])[0], struct.unpack("<H", p["hdr"][20:22])[0]

    @staticmethod
    def name(p):
        return p["hdr"][:20].split(b"\0")[0].decode("latin-1")

    def find(self, bank, prog):
        for p in self.presets:
            if self.key(p) == (bank, prog):
                return p
        raise ValueError(f"{os.path.basename(self.path)}: nessun preset {bank}:{prog}")


def info(path):
    """Version (sf2/sf3), size of the samples and the list of presets."""
    sf = SoundFont(path)
    return {"file": os.path.basename(path), "version": "%d.%02d" % sf.version,
            "format": "sf3" if sf.compressed else "sf2", "samples_mb": round(len(sf.smpl) / 1e6, 1),
            "presets": [{"bank": b, "program": p, "name": SoundFont.name(x)}
                        for x in sorted(sf.presets, key=SoundFont.key) for b, p in [SoundFont.key(x)]]}


def _set_slot(p, bank, prog, name=None):
    h = bytearray(p["hdr"])
    if name:
        h[0:20] = name.encode("latin-1", "replace")[:19].ljust(20, b"\0")
    h[20:24] = struct.pack("<HH", prog, bank)
    return {"hdr": bytes(h), "zones": [[list(g), list(m)] for g, m in p["zones"]]}


def _tweak(p, atten=0, transpose=0):
    """Additive attenuation (cB) and transposition (semitones) on the global zone of a preset."""
    if not (atten or transpose):
        return p
    z = p["zones"]
    if not z or any(o == GEN_INSTRUMENT for o, _ in z[0][0]):
        z.insert(0, [[], []])
    if atten:
        z[0][0].append((GEN_ATTEN, int(atten) & 0xFFFF))
    if transpose:
        z[0][0].append((GEN_COARSE, int(transpose) & 0xFFFF))
    return p


def _pack(items, nameoff, size, term):
    hdr, bag, gen, mod = bytearray(), bytearray(), bytearray(), bytearray()
    nb = ng = nm = 0
    for it in items:
        h = bytearray(it["hdr"])
        h[nameoff:nameoff + 2] = struct.pack("<H", nb)
        hdr += h
        for g, m in it["zones"]:
            bag += struct.pack("<HH", ng, nm)
            nb += 1
            for o, a in g:
                gen += struct.pack("<HH", o, a)
                ng += 1
            for x in m:
                mod += x
                nm += 1
    t = bytearray(size)
    t[0:len(term)] = term
    t[nameoff:nameoff + 2] = struct.pack("<H", nb)
    hdr += t
    bag += struct.pack("<HH", ng, nm)
    return bytes(hdr), bytes(bag), bytes(mod + b"\0" * 10), bytes(gen + b"\0" * 4)


def _write(out, info_chunks, presets, insts, shdr, smpl):
    ph, pb, pm, pg = _pack(presets, 24, 38, b"EOP")
    ih, ib, imd, ig = _pack(insts, 20, 22, b"EOI")
    sh = b"".join(shdr) + b"EOS".ljust(46, b"\0")
    ck = lambda i, b: i + struct.pack("<I", len(b)) + b + (b"\0" if len(b) & 1 else b"")
    pdta = b"".join(ck(i, b) for i, b in [(b"phdr", ph), (b"pbag", pb), (b"pmod", pm), (b"pgen", pg),
                                          (b"inst", ih), (b"ibag", ib), (b"imod", imd), (b"igen", ig),
                                          (b"shdr", sh)])
    body = (b"sfbk" + ck(b"LIST", b"INFO" + info_chunks) + ck(b"LIST", b"sdta" + ck(b"smpl", smpl))
            + ck(b"LIST", b"pdta" + pdta))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(body)) + body)
    return out


def _credits_text(credits):
    lines = []
    for c in credits:
        lines.append(" — ".join(x for x in (c.get("source"), c.get("author"), c.get("license"), c.get("url")) if x))
    return "\n".join(lines) + ("\n" if lines else "")


def compose(recipe, out, root=None):
    """Build the SoundFont of a recipe (dict or JSON path). Writes `out` and `<out>.crediti.txt`
    (sources, authors, licenses: the release must cite those under attribution licenses).
    Returns a summary with the slots changed and the warnings."""
    if isinstance(recipe, str):
        root = root or os.path.dirname(os.path.abspath(recipe))
        with open(recipe, encoding="utf-8") as f:
            recipe = json.load(f)
    root = root or os.getcwd()
    path = lambda f: f if os.path.isabs(f) else os.path.join(root, f)
    base = SoundFont(path(recipe["base"]))
    presets = {base.key(p): p for p in base.presets}
    keep = recipe.get("keep")
    if keep is not None:
        keep = {tuple(k) for k in keep} | {tuple(c["from_slot"]) for c in recipe.get("copies", [])}
        presets = {k: v for k, v in presets.items() if k in keep}
    insts, shdr, smpl = list(base.insts), list(base.shdr), bytearray(base.smpl)
    changed, warnings = [], []
    for c in recipe.get("copies", []):
        src = base.find(*c["from_slot"])
        presets[tuple(c["slot"])] = _tweak(_set_slot(src, *c["slot"]), c.get("attenuation_cb", 0),
                                           c.get("transpose", 0))
        changed.append({"slot": c["slot"], "from": "base", "preset": c["from_slot"], "name": SoundFont.name(src)})
    credits = list(recipe.get("credits", []))
    credited = {os.path.basename(c.get("source", "")) for c in credits}
    for im in recipe.get("imports", []):
        if base.compressed:
            raise ValueError("import da altri banchi non ammesso su una base sf3: usa una base sf2 "
                             "e comprimi alla fine (sf3convert), oppure solo 'copies'")
        src = SoundFont(path(im["from"]))
        if src.compressed:
            raise ValueError(f"{im['from']}: banco sf3, gli import vogliono campioni PCM (sf2)")
        ioff, soff, poff = len(insts), len(shdr), len(smpl) // 2
        for i in src.insts:
            insts.append({"hdr": i["hdr"], "zones": [[[(o, a + soff if o == GEN_SAMPLEID else a) for o, a in g], m]
                                                     for g, m in i["zones"]]})
        for s in src.shdr:
            s = bytearray(s)
            st, en, ls, le = struct.unpack("<IIII", s[20:36])
            s[20:36] = struct.pack("<IIII", st + poff, en + poff, ls + poff, le + poff)
            link, typ = struct.unpack("<HH", s[42:46])
            if typ & 0x6:   # stereo sample: index of its twin
                s[42:44] = struct.pack("<H", link + soff)
            shdr.append(bytes(s))
        smpl += src.smpl
        p = src.find(*im.get("preset", [0, 0]))
        p = {"hdr": p["hdr"], "zones": [[[(o, a + ioff if o == GEN_INSTRUMENT else a) for o, a in g], m]
                                        for g, m in p["zones"]]}
        presets[tuple(im["slot"])] = _tweak(_set_slot(p, *im["slot"]), im.get("attenuation_cb", 0),
                                            im.get("transpose", 0))
        changed.append({"slot": im["slot"], "from": os.path.basename(im["from"]),
                        "preset": im.get("preset", [0, 0]), "name": SoundFont.name(p)})
        if os.path.basename(im["from"]) not in credited:
            warnings.append(f"{im['from']}: manca nei crediti (fonte, autore, licenza)")
    vel = recipe.get("velocity_attenuation_cb", 0)
    if vel:   # additive preset modulator: velocity, concave, unipolar, negative -> attenuation
        vm = struct.pack("<HHhHH", 0x0502, GEN_ATTEN, int(vel), 0, 0)
        for p in presets.values():
            for z in p["zones"]:
                if any(o == GEN_INSTRUMENT for o, _ in z[0]):
                    z[1] = [m for m in z[1] if m[:4] != vm[:4]] + [vm]
    if len(smpl) // 2 > 0xFFFFFFFF:
        raise ValueError("campioni oltre il limite del formato sf2")
    _write(out, base.info, sorted(presets.values(), key=SoundFont.key), insts, shdr, bytes(smpl))
    for c in credits:
        if any(k in str(c.get("license", "")).lower() for k in ATTRIBUTION) and not c.get("author"):
            warnings.append(f"{c.get('source')}: licenza con attribuzione ({c.get('license')}) senza autore")
    with open(out + ".crediti.txt", "w", encoding="utf-8") as f:
        f.write(_credits_text(credits))
    return {"written": out, "format": "sf3" if base.compressed else "sf2", "presets": len(presets),
            "size_mb": round(os.path.getsize(out) / 1e6, 1), "changed": changed,
            "attribution_required": [c.get("source") for c in credits
                                     if any(k in str(c.get("license", "")).lower() for k in ATTRIBUTION)],
            "warnings": warnings}
