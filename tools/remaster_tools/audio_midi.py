"""Diagnosis of dynamic MIDI music ("why does it sound shrill/fake?") and program remapping for
listening tests.

Interactive MIDI music (jumps, loops, part volumes decided by the scripts) stays played by the
engine: these helpers do not produce game assets. They answer three questions:
  * are the notes the same in every version of a piece (no octave shifts, no missing parts)?
  * which instrument does each channel really get once the engine converts the programs of the
    period module to General MIDI (table given by the project or by the engine documentation)?
  * where is the energy (frequency bands) of a rendering or of a recording of the engine?
Pure Python for the MIDI part; numpy (optional) for the bands."""
import json
import math
import os
import shutil
import subprocess
import wave

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
GM_NAMES = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet", "Celesta", "Glockenspiel",
    "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ",
    "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica",
    "Tango Accordion", "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)",
    "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar",
    "Guitar Harmonics", "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)",
    "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin", "Viola",
    "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2", "Choir Aahs",
    "Voice Oohs", "Synth Choir", "Orchestra Hit", "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2", "Soprano Sax", "Alto Sax",
    "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet", "Piccolo", "Flute",
    "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina", "Lead 1 (square)",
    "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)",
    "Lead 7 (fifths)", "Lead 8 (bass + lead)", "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)",
    "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)",
    "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)", "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bagpipe", "Fiddle", "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal", "Guitar Fret Noise", "Breath Noise",
    "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter", "Applause", "Gunshot"]
# GM slots that conversion tables often pick as the "nearest" timbre of a period module but that
# change the character of an orchestral part (seen on the test bench: a muted trumpet instead
# of an open one, an ocarina instead of a flute). A warning to listen, not an error.
SUSPECT_GM = {59: "tromba con sordina: nasale, spesso al posto di una tromba aperta (56)",
              79: "ocarina: spesso al posto di un flauto (73)",
              55: "colpo d'orchestra: raro in una partitura, spesso un ripiego",
              80: "onda quadra: timbro sintetico al posto di un legno",
              81: "dente di sega: timbro sintetico al posto di ottoni/archi",
              62: "ottoni sintetici: al posto di una sezione di ottoni (61)",
              50: "archi sintetici: al posto degli archi (48)",
              112: "campanellino: spesso un ripiego per suoni che non hanno un posto GM"}
DRUM_CHANNEL = 9


def note_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"


# ------------------------------------------------------------------ standard MIDI files
def _vlq(b, i):
    v = 0
    while True:
        c = b[i]
        i += 1
        v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, i


def _enc_vlq(v):
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.insert(0, 0x80 | (v & 0x7F))
        v >>= 7
    return bytes(out)


def read_midi(path):
    """{format, division, tracks: [[(abs_tick, bytes_of_event)]]}: running status resolved,
    meta (FF) and sysex (F0/F7) events kept whole. Never reads past the end of the file."""
    with open(path, "rb") as f:
        b = f.read()
    if b[:4] != b"MThd":
        raise ValueError(f"{path}: non è un MIDI standard")
    fmt, ntrk, div = (int.from_bytes(b[k:k + 2], "big") for k in (8, 10, 12))
    i, tracks = 8 + int.from_bytes(b[4:8], "big"), []
    for _ in range(ntrk):
        if b[i:i + 4] != b"MTrk":
            break
        end = min(i + 8 + int.from_bytes(b[i + 4:i + 8], "big"), len(b))
        j, tick, status, evs = i + 8, 0, 0, []
        try:
            while j < end - 1:
                dt, j = _vlq(b, j)
                tick += dt
                c = b[j]
                if c == 0xFF:
                    n, k = _vlq(b, j + 2)
                    evs.append((tick, b[j:k + n]))
                    j = k + n
                    continue
                if c in (0xF0, 0xF7):
                    n, k = _vlq(b, j + 1)
                    evs.append((tick, b[j:k + n]))
                    j = k + n
                    continue
                if c & 0x80:
                    status, j = c, j + 1
                size = 1 if status & 0xF0 in (0xC0, 0xD0) else 2
                evs.append((tick, bytes([status]) + b[j:j + size]))
                j += size
        except IndexError:   # truncated last event
            pass
        tracks.append(evs)
        i = end
    return {"format": fmt, "division": div, "tracks": tracks}


def write_midi(path, midi):
    out = bytearray(b"MThd" + (6).to_bytes(4, "big") + midi["format"].to_bytes(2, "big")
                    + len(midi["tracks"]).to_bytes(2, "big") + midi["division"].to_bytes(2, "big"))
    for evs in midi["tracks"]:
        body, prev = bytearray(), 0
        for t, ev in sorted(evs, key=lambda e: e[0]):   # stable: same-tick order kept
            body += _enc_vlq(t - prev) + ev
            prev = t
        if not evs or evs[-1][1][:2] != b"\xff\x2f":
            body += b"\x00\xff\x2f\x00"
        out += b"MTrk" + len(body).to_bytes(4, "big") + body
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(bytes(out))
    return path


def _seconds_of(midi):
    """tick -> seconds function (tempo map from every track)."""
    div = midi["division"]
    if div & 0x8000:
        rate = (256 - (div >> 8)) * (div & 0xFF)
        return lambda t: t / rate
    tempos = sorted((t, int.from_bytes(ev[3:6], "big")) for evs in midi["tracks"] for t, ev in evs
                    if ev[:2] == b"\xff\x51" and len(ev) >= 6)
    marks, acc, prev, tempo = [], 0.0, 0, 500000
    for t, v in tempos:
        acc += (t - prev) * tempo / (div * 1e6)
        marks.append((t, acc, v))
        prev, tempo = t, v

    def conv(t):
        base_t, base_s, tp = 0, 0.0, 500000
        for mt, ms, v in marks:
            if mt > t:
                break
            base_t, base_s, tp = mt, ms, v
        return base_s + (t - base_t) * tp / (div * 1e6)
    return conv


def _load_table(table):
    """Program conversion table: list of 128 numbers or {"src": dst}; a path to a JSON file."""
    if table is None:
        return None
    if isinstance(table, str):
        with open(table, encoding="utf-8") as f:
            table = json.load(f)
    if isinstance(table, dict) and "table" in table:
        table = table["table"]
    if isinstance(table, list):
        if len(table) != 128:
            raise ValueError(f"la tabella dei programmi deve avere 128 voci (ne ha {len(table)})")
        return {i: int(v) for i, v in enumerate(table)}
    return {int(k): int(v) for k, v in table.items()}


def _velocity_db(v, law):
    """Level of a note-on velocity relative to velocity 127: 'gm' = squared law of General MIDI
    synthesizers (40·log10), 'linear' = gentler law of many period modules (20·log10)."""
    v = max(1, v)
    return (40 if law == "gm" else 20) * math.log10(v / 127)


def channel_report(path, table=None, fixes=None):
    """Per channel: notes, range, velocity, volume (CC7), reverb send (CC91), programs heard
    (with the GM slot after the conversion table and the fixes) and warnings."""
    midi = read_midi(path)
    sec = _seconds_of(midi)
    tab, fixes = _load_table(table), {int(k): int(v) for k, v in (fixes or {}).items()}
    events = sorted(((t, ev) for evs in midi["tracks"] for t, ev in evs), key=lambda e: e[0])
    ch = {}
    prog = {}
    sysex = 0
    for t, ev in events:
        if ev[0] in (0xF0, 0xF7):
            sysex += 1
            continue
        if ev[0] == 0xFF:
            continue
        c, hi = ev[0] & 0x0F, ev[0] & 0xF0
        d = ch.setdefault(c, {"notes": [], "vel": [], "cc7": [], "cc11": [], "cc91": [], "programs": {}, "first": None})
        if hi == 0xC0:
            prog[c] = ev[1]
        elif hi == 0xB0 and ev[1] in (7, 11, 91):
            d["cc%d" % ev[1]].append(ev[2])
        elif hi == 0x90 and ev[2] > 0:
            d["notes"].append(ev[1])
            d["vel"].append(ev[2])
            p = prog.get(c, 0)
            d["programs"][p] = d["programs"].get(p, 0) + 1
            if d["first"] is None:
                d["first"] = round(sec(t), 2)
    out = {}
    for c, d in sorted(ch.items()):
        if not d["notes"]:
            continue
        n, v = d["notes"], sorted(d["vel"])
        cc7 = d["cc7"][-1] if d["cc7"] else 100
        eff_vel = v[len(v) // 2]
        level_gm = _velocity_db(eff_vel, "gm") + 40 * math.log10(max(1, cc7) / 127)
        level_old = _velocity_db(eff_vel, "linear") + 40 * math.log10(max(1, cc7) / 127)
        row = {"notes": len(n), "low": note_name(min(n)), "high": note_name(max(n)),
               "mean": note_name(round(sum(n) / len(n))), "first_s": d["first"],
               "velocity": {"min": v[0], "median": eff_vel, "max": v[-1],
                            "below_64": round(sum(1 for x in v if x < 64) / len(v), 2)},
               "cc7": cc7, "cc91": d["cc91"][-1] if d["cc91"] else None,
               "level_db": {"gm": round(level_gm, 1), "linear": round(level_old, 1)},
               "drums": c == DRUM_CHANNEL, "programs": [], "warnings": []}
        for p, cnt in sorted(d["programs"].items(), key=lambda kv: -kv[1]):
            e = {"program": p, "notes": cnt}
            if c != DRUM_CHANNEL:
                gm = tab.get(p, p) if tab else p
                gm2 = fixes.get(gm, gm)
                e.update({"gm": gm2, "gm_name": GM_NAMES[gm2 % 128]})
                if gm2 != gm:
                    e["fixed_from"] = gm
                if gm2 in SUSPECT_GM:
                    row["warnings"].append(f"prog {p} -> GM {gm2} ({GM_NAMES[gm2]}): {SUSPECT_GM[gm2]}")
            row["programs"].append(e)
        out[str(c + 1)] = row
    # accompaniment that a GM synthesizer pushes far below the loudest part
    if out:
        top = max(r["level_db"]["gm"] for r in out.values())
        for r in out.values():
            gap = top - r["level_db"]["gm"]
            if gap >= 10:
                r["warnings"].append(f"{gap:.0f} dB sotto la parte più forte con la curva GM "
                                     f"({top - r['level_db']['linear']:.0f} dB con una curva lineare): "
                                     "l'accompagnamento rischia di sparire")
    return {"file": os.path.basename(path), "channels": out, "sysex": sysex,
            "seconds": round(sec(max((t for t, _ in events), default=0)), 1)}


def compare_notes(paths):
    """Notes per channel between versions of the same piece (e.g. the variants for two devices
    in one engine block): same count, same pitches in order, octave shift."""
    reps = []
    for p in paths:
        midi = read_midi(p)
        per = {}
        for t, ev in sorted(((t, ev) for evs in midi["tracks"] for t, ev in evs), key=lambda e: e[0]):
            if ev[0] & 0xF0 == 0x90 and ev[0] < 0xF0 and ev[2] > 0:
                per.setdefault(ev[0] & 0x0F, []).append(ev[1])
        reps.append(per)
    base, out = reps[0], {}
    for other, path in zip(reps[1:], paths[1:]):
        rows = {}
        for c in sorted(set(base) | set(other)):
            a, b = base.get(c, []), other.get(c, [])
            pairs = list(zip(a, b))
            diffs = sorted(y - x for x, y in pairs)
            med = diffs[len(diffs) // 2] if diffs else None
            rows[str(c + 1)] = {"notes": [len(a), len(b)],
                                "same_pitch": round(sum(1 for x, y in pairs if x == y) / len(pairs), 2) if pairs else 0,
                                "median_shift": med,
                                "octave_shift": bool(med) and med % 12 == 0}
        out[os.path.basename(path)] = rows
    flags = [f"{f} canale {c}: spostamento di {r['median_shift']} semitoni" for f, rows in out.items()
             for c, r in rows.items() if r["median_shift"]]
    flags += [f"{f} canale {c}: note {r['notes'][0]} contro {r['notes'][1]}" for f, rows in out.items()
              for c, r in rows.items() if r["notes"][0] != r["notes"][1]]
    return {"reference": os.path.basename(paths[0]), "versions": out, "differences": flags}


def remap(src, dst, table, fixes=None, strip_sysex=True, reverb_send=None, drums=DRUM_CHANNEL):
    """Rewrite a MIDI file as the engine plays it on a GM synthesizer (for listening tests only):
    program changes through the conversion table, then the fixes {gm: gm}; sysex of the period
    module removed (strip_sysex); optional CC91 (reverb send) on every channel at the start, when
    the engine sends it from its own data. The drum channel is left untouched."""
    midi = read_midi(src)
    tab, fixes = _load_table(table) or {}, {int(k): int(v) for k, v in (fixes or {}).items()}
    used, seen = {}, set()
    for k, evs in enumerate(midi["tracks"]):
        new = []
        for t, ev in evs:
            if ev[0] in (0xF0, 0xF7) and strip_sysex:
                continue
            if ev[0] < 0xF0 and ev[0] & 0xF0 == 0xC0 and (ev[0] & 0x0F) != drums:
                gm = fixes.get(tab.get(ev[1], ev[1]), tab.get(ev[1], ev[1]))
                used[str(ev[1])] = gm
                ev = bytes([ev[0], gm & 0x7F])
            if ev[0] < 0xF0:
                seen.add(ev[0] & 0x0F)
            new.append((t, ev))
        midi["tracks"][k] = new
    if reverb_send is not None and midi["tracks"]:
        lead = [(0, bytes([0xB0 | c, 91, max(0, min(127, int(reverb_send)))])) for c in sorted(seen)]
        midi["tracks"][0] = lead + midi["tracks"][0]
    write_midi(dst, midi)
    return {"written": dst, "programs": dict(sorted(used.items(), key=lambda kv: int(kv[0])))}


# ------------------------------------------------------------------ energy per band
BANDS = ((0, 250), (250, 2000), (2000, 4000), (4000, None))


def _numpy():
    try:
        import numpy as np
    except ImportError:
        raise RuntimeError("serve numpy per la distribuzione per bande (pip install numpy)") from None
    return np


def _samples(path, rate=22050, start=0.0, duration=None):
    np = _numpy()
    if path.lower().endswith(".wav"):
        try:
            with wave.open(path) as w:
                if w.getsampwidth() == 2:
                    r, nch = w.getframerate(), w.getnchannels()
                    w.setpos(min(w.getnframes(), int(start * r)))
                    n = w.getnframes() if duration is None else int(duration * r)
                    x = np.frombuffer(w.readframes(n), "<i2").astype(np.float32) / 32768
                    return x.reshape(-1, nch).mean(axis=1), r
        except wave.Error:
            pass
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg non trovato (serve per leggere file diversi da WAV a 16 bit)")
    args = [exe, "-hide_banner", "-loglevel", "error", "-ss", str(start)]
    if duration:
        args += ["-t", str(duration)]
    res = subprocess.run(args + ["-i", path, "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"],
                         capture_output=True, check=True)
    return np.frombuffer(res.stdout, "<f4"), rate


def bands(path, start=0.0, duration=30.0):
    """Spectral centroid, share of energy per band (<250 Hz, 250-2k, 2k-4k, >4k), share of the
    octaves C1-B3 (the low register of an orchestra) and dominant note of a recording: the
    measure of "too shrill" (energy above 2 kHz, nothing in the lows) and of what an orchestral
    reference has."""
    np = _numpy()
    x, rate = _samples(path, start=start, duration=duration)
    if len(x) < 4096:
        raise ValueError(f"{path}: troppo corto per la misura")
    n = 4096
    win = np.hanning(n)
    frames = [x[i:i + n] * win for i in range(0, len(x) - n, n // 2)]
    spec = np.mean([np.abs(np.fft.rfft(f)) ** 2 for f in frames], axis=0)
    freqs = np.fft.rfftfreq(n, 1 / rate)
    total = float(spec[1:].sum()) or 1.0
    share = {}
    for lo, hi in BANDS:
        m = (freqs >= lo) & ((freqs < hi) if hi else True)
        share[f"{lo}-{hi}" if hi else f">{lo}"] = round(float(spec[m].sum()) / total, 3)
    centroid = float((freqs * spec).sum() / spec.sum()) if spec.sum() else 0.0
    valid = freqs >= 27.5
    midi_n = np.round(69 + 12 * np.log2(freqs[valid] / 440)).astype(int)
    per_note = np.bincount(np.clip(midi_n, 0, 127), weights=spec[valid], minlength=128)
    low = float(per_note[24:60].sum() / (per_note.sum() or 1))
    return {"file": os.path.basename(path), "centroid_hz": round(centroid), "bands": share,
            "octaves_C1_B3": round(low, 3), "dominant_note": note_name(int(per_note.argmax())),
            "window_s": [start, duration]}


def diagnose(midis=(), table=None, fixes=None, audio=(), compare=False, start=0.0, duration=30.0):
    """Everything at once: channels of every MIDI, notes compared between versions (compare=True
    and at least two MIDI), bands of the recordings/renderings."""
    out = {"midi": [channel_report(m, table, fixes) for m in midis]}
    if compare and len(midis) >= 2:
        out["compare"] = compare_notes(list(midis))
    if audio:
        out["bands"] = [bands(a, start, duration) for a in audio]
    out["warnings"] = [f"{r['file']} canale {c}: {w}" for r in out["midi"] for c, row in r["channels"].items()
                       for w in row["warnings"]]
    return out
