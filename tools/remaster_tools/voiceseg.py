"""Stretches of speech in long reference files (trailers, clips): local transcription with word
times, then grouping of the speakers by voice prints, written as a TSV that `voice reference
--segments` measures without cutting the files first.

Everything runs locally and for free; the audio never leaves the machine. Optional
dependencies, each with a clear message when missing:
  faster-whisper  transcription (pip install faster-whisper). The audio is decoded by ffmpeg and
                  passed as an array: recent PyAV builds fail opening files inside faster-whisper.
  resemblyzer     voice prints (pip install resemblyzer "setuptools<81": it imports
                  pkg_resources, removed from setuptools 81). Without it a simple print is used
                  (median pitch + mean cepstrum of `voiceref`), weaker but free of dependencies.

Grouping: agglomerative clustering with average linkage, either to a fixed number of groups
(`speakers`, the most reliable when you know how many people talk) or up to a distance
threshold. Prints of resemblyzer separate little (two different voices can be only ~0.3 apart in
cosine distance), so the default threshold is low and `--speakers` is preferred. Each row gets a
confidence: how much closer the stretch is to its own group than to the nearest other group
(0 = on the border, 1 = clear-cut).

TSV columns: id, file (relative to the TSV), inizio, fine (seconds), gruppo (G1 = the group with
most speech; "-" = too short to attribute), sicurezza, logprob (of the transcription), testo.
"""
import math
import os

import numpy as np

from . import voiceref

SR = voiceref.SR
MIN_ATTRIB_S = 0.8          # shorter stretches are listed but not attributed
SPLIT_GAP_S = 0.5           # a silence this long between two words splits a segment
COLUMNS = ("id", "file", "inizio", "fine", "gruppo", "sicurezza", "logprob", "testo")


# ---------------------------------------------------------------------------- backends

def whisper_transcriber(model="small"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("manca faster-whisper per la trascrizione locale: pip install faster-whisper "
                           "(gratuito, gira sulla CPU; il modello si scarica alla prima esecuzione)")
    wm = WhisperModel(model, device="cpu", compute_type="int8")

    def run(x, lang):
        segs, _ = wm.transcribe(np.asarray(x, dtype=np.float32), language=lang, beam_size=5,
                                word_timestamps=True, vad_filter=True, condition_on_previous_text=False)
        out = []
        for s in segs:
            words = [{"start": w.start, "end": w.end, "word": w.word} for w in (s.words or [])]
            out.append({"start": s.start, "end": s.end, "text": s.text.strip(), "logprob": s.avg_logprob,
                        "words": words})
        return out
    return run


class ResemblyzerPrint:
    metric = "cosine"
    threshold = 0.25
    name = "resemblyzer"

    def __init__(self):
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav
        except ImportError as e:
            hint = (' e "setuptools<81" (resemblyzer importa pkg_resources)' if "pkg_resources" in str(e) else "")
            raise RuntimeError(f'manca resemblyzer per le impronte vocali: pip install resemblyzer "setuptools<81"'
                               f"{hint}; senza, usa --prints simple")
        self._enc = VoiceEncoder("cpu", verbose=False)
        self._pre = preprocess_wav

    def __call__(self, x):
        return self._enc.embed_utterance(self._pre(np.asarray(x, dtype=np.float32), source_sr=SR))


class SimplePrint:
    """Median pitch (semitones) and mean cepstrum, scaled like the distance of `voiceref`."""
    metric = "euclidean"
    threshold = 1.0
    name = "simple"

    def __call__(self, x):
        m = voiceref.measure_signal(x)
        f0s, mfs = voiceref.FEATURES["f0_st"][0], voiceref.FEATURES["mfcc"][0]
        v = np.concatenate([[12 * math.log2(m["f0_median_hz"]) / f0s],
                            np.array(m["mfcc"]) / mfs / math.sqrt(len(m["mfcc"]))])
        return v / math.sqrt(2.0)


def voice_prints(kind="auto"):
    if kind == "simple":
        return SimplePrint()
    if kind == "resemblyzer":
        return ResemblyzerPrint()
    try:
        return ResemblyzerPrint()
    except RuntimeError:
        return SimplePrint()


# ---------------------------------------------------------------------------- clustering

def _distances(E, metric):
    E = np.asarray(E, dtype=float)
    if metric == "cosine":
        n = E / np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-12)
        return np.clip(1.0 - n @ n.T, 0.0, 2.0)
    d = E[:, None, :] - E[None, :, :]
    return np.sqrt((d ** 2).sum(axis=2))


def cluster(E, metric="cosine", n_clusters=None, threshold=0.25):
    """Average-linkage agglomerative clustering. Returns labels 0..k-1 and the pair distances."""
    D0 = _distances(E, metric)
    n = len(D0)
    if n == 0:
        return np.array([], dtype=int), D0
    D = D0.copy()
    np.fill_diagonal(D, np.inf)
    size = np.ones(n)
    alive = np.ones(n, dtype=bool)
    lab = np.arange(n)
    k = n
    target = max(1, n_clusters) if n_clusters else 1
    while k > target:
        i, j = np.unravel_index(np.argmin(D), D.shape)
        if not n_clusters and D[i, j] > threshold:
            break
        new = (size[i] * D[i] + size[j] * D[j]) / (size[i] + size[j])
        D[i], D[:, i] = new, new
        D[i, i] = np.inf
        D[j], D[:, j] = np.inf, np.inf
        size[i] += size[j]
        alive[j] = False
        lab[lab == j] = i
        k -= 1
    _, lab = np.unique(lab, return_inverse=True)
    return lab, D0


def _confidence(D0, lab):
    """(nearest other group - own group) / max of the two, mean distances; 1.0 with one group."""
    out = np.ones(len(lab))
    groups = np.unique(lab)
    if len(groups) < 2:
        return out
    for i in range(len(lab)):
        own = [D0[i, j] for j in np.nonzero(lab == lab[i])[0] if j != i]
        a = float(np.mean(own)) if own else 0.0
        b = min(float(D0[i, lab == g].mean()) for g in groups if g != lab[i])
        out[i] = (b - a) / max(a, b, 1e-9)
    return np.clip(out, 0.0, 1.0)


# ---------------------------------------------------------------------------- main

def _silences(x, a, b):
    """Midpoints (s) of the silences of at least SPLIT_GAP_S between a and b: word times of the
    transcription often run over a pause, the signal does not."""
    seg = np.asarray(x[int(a * SR):int(b * SR)], dtype=float)
    hop = SR // 100
    n = len(seg) // hop
    if n < 3:
        return []
    db = 20 * np.log10(np.sqrt((seg[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-9)
    quiet = db < np.percentile(db, 95) - 35.0
    cuts, run = [], 0
    for i, q in enumerate(list(quiet) + [False]):
        if q:
            run += 1
            continue
        if run * hop / SR >= SPLIT_GAP_S and run < i:          # a pause, not the edges
            if i - run > 0:
                cuts.append(a + (i - run / 2) * hop / SR)
        run = 0
    return cuts


def _split(seg, x=None):
    """Split a transcribed segment at long gaps between words and at real silences of the
    signal (often a change of speaker). Text and times follow the words when there are any."""
    a, b = float(seg["start"]), float(seg["end"])
    words = seg.get("words") or []
    cuts = [] if x is None else _silences(x, a, b)
    for w0, w1 in zip(words, words[1:]):
        if w1["start"] - w0["end"] >= SPLIT_GAP_S:
            cuts.append((w0["end"] + w1["start"]) / 2)
    if not cuts:
        return [seg]
    edges = [a] + sorted(set(round(c, 3) for c in cuts)) + [b]
    parts = []
    for lo, hi in zip(edges, edges[1:]):
        ws = [w for w in words if lo <= (w["start"] + w["end"]) / 2 < hi]
        if words and not ws:
            continue
        p = {"start": max(lo, ws[0]["start"]) if ws else lo, "end": min(hi, ws[-1]["end"]) if ws else hi,
             "logprob": seg.get("logprob"),
             "text": "".join(w["word"] for w in ws).strip() if ws else seg.get("text", "")}
        parts.append(p)
    return parts or [seg]


def segments(paths, out_tsv, lang="it", model="small", speakers=None, threshold=None, prints="auto",
             transcriber=None, printer=None):
    """Transcribe and group the speakers of the audio files; write the TSV, return a summary."""
    files = voiceref._expand(paths)
    if not files:
        raise ValueError("nessun file audio")
    transcriber = transcriber or whisper_transcriber(model)
    printer = printer or voice_prints(prints)
    base = os.path.dirname(os.path.abspath(out_tsv))
    rows, embs = [], []
    for p in files:
        x = voiceref.load(p)
        rel = os.path.relpath(os.path.abspath(p), base)
        for seg in transcriber(x, lang):
            for s in _split(seg, x):
                a, b = max(0.0, float(s["start"])), min(len(x) / SR, float(s["end"]))
                if b <= a:
                    continue
                r = {"file": rel, "inizio": round(a, 2), "fine": round(b, 2), "testo": s.get("text", ""),
                     "logprob": "" if s.get("logprob") is None else round(float(s["logprob"]), 2),
                     "gruppo": "-", "sicurezza": ""}
                if b - a >= MIN_ATTRIB_S:
                    try:
                        e = printer(x[int(a * SR):int(b * SR)])
                        r["_e"] = len(embs)
                        embs.append(np.asarray(e, dtype=float))
                    except ValueError:
                        pass            # no voiced speech in the stretch: not attributed
                rows.append(r)
    thr = printer.threshold if threshold is None else threshold
    lab, D0 = cluster(np.array(embs), printer.metric, speakers, thr) if embs else (np.array([], int), None)
    conf = _confidence(D0, lab) if embs else []
    # name the groups by amount of speech: G1 speaks most
    dur = {}
    for r in rows:
        if "_e" in r:
            dur[lab[r["_e"]]] = dur.get(lab[r["_e"]], 0.0) + r["fine"] - r["inizio"]
    names = {g: f"G{i + 1}" for i, g in enumerate(sorted(dur, key=lambda g: -dur[g]))}
    for i, r in enumerate(rows, 1):
        r["id"] = i
        if "_e" in r:
            r["gruppo"] = names[lab[r["_e"]]]
            r["sicurezza"] = round(float(conf[r["_e"]]), 2)
    _write_tsv(out_tsv, rows)
    groups = []
    for g in sorted(names.values(), key=lambda n: int(n[1:])):
        rs = [r for r in rows if r["gruppo"] == g]
        groups.append({"group": g, "stretches": len(rs), "seconds": round(sum(r["fine"] - r["inizio"] for r in rs), 1),
                       "low_confidence": sum(1 for r in rs if r["sicurezza"] != "" and r["sicurezza"] < 0.15),
                       "ids": [r["id"] for r in rs][:20]})
    res = {"kind": "voice-segments", "file": out_tsv, "files": len(files), "stretches": len(rows),
           "unattributed": sum(1 for r in rows if r["gruppo"] == "-"), "prints": printer.name,
           "grouping": f"{speakers} gruppi" if speakers else f"soglia {thr}", "groups": groups,
           "next": f"ascolta qualche tratto per gruppo, poi: rstool.py voice reference --segments {out_tsv} "
                   "--group G1 --out voice/ref/<personaggio>-<lingua>.json"}
    if printer.name == "simple":
        res["note"] = ("impronte semplici (altezza e timbro medio): senza resemblyzer i gruppi vanno "
                       "controllati a orecchio; con un numero noto di parlanti usa --speakers")
    return res


def _clean(v):
    return str(v).replace("\t", " ").replace("\n", " ").replace("\r", " ")


def _write_tsv(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            f.write("\t".join(_clean(r[c]) for c in COLUMNS) + "\n")
