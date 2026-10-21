"""Target platform of the original release: how its pixels were shown on the displays of the
time (pixel aspect) and which reliable emulator or VM reproduces it for the comparison tests.

The pixel aspect is corrected ONLY when the game was conceived for a display that stretched
its pixels: that depends on release date, target platform and the devices of the time, not on
the resolution alone. Here `stretch` is the vertical stretch factor the original display
applied to one pixel (1.2 = a 320x200 picture filling a 4:3 CRT); 1.0 = square pixels.
The table gives a candidate with reasons; the art decides (round objects, faces, text drawn
in the picture) with `aspect_sheet`, and the user confirms.
"""
import os

from PIL import Image

# (platform, width, height) -> (stretch, display of the time, how sure)
_MODES = [
    ("dos", 320, 200, 1.2, "VGA/MCGA 13h o EGA a 200 righe su monitor CRT 4:3", "alta"),
    ("dos", 640, 200, 2.4, "CGA/EGA ad alta risoluzione su CRT 4:3", "alta"),
    ("dos", 640, 350, 1.37, "EGA 640x350 su CRT 4:3", "alta"),
    ("dos", 640, 400, 1.2, "SVGA 640x400 su CRT 4:3 (ma spesso arte digitalizzata o renderizzata a pixel quadrati: verifica)", "media"),
    ("dos", 320, 240, 1.0, "Mode X 320x240: pixel quadrati su 4:3", "alta"),
    ("dos", 640, 480, 1.0, "VGA/SVGA 640x480: pixel quadrati", "alta"),
    ("windows", 640, 480, 1.0, "Windows a 640x480 o più: pixel quadrati", "alta"),
    ("windows", 800, 600, 1.0, "Windows SVGA: pixel quadrati", "alta"),
    ("mac", 512, 342, 1.0, "Mac compatti: pixel quadrati", "alta"),
    ("mac", 640, 480, 1.0, "Mac a colori: pixel quadrati", "alta"),
    ("amiga-pal", 320, 256, 1.0, "Amiga PAL lowres: pixel quasi quadrati", "media"),
    ("amiga-pal", 320, 200, 1.0, "gioco NTSC-safe su Amiga PAL: pixel quasi quadrati, bordo nero sotto", "media"),
    ("amiga-ntsc", 320, 200, 1.2, "Amiga NTSC: pixel alti come su un TV 4:3", "media"),
    ("amiga-pal", 640, 256, 0.5, "Amiga hires non interlacciato: pixel larghi la metà", "alta"),
    ("amiga-pal", 640, 512, 1.0, "Amiga hires interlacciato", "media"),
    ("atari-st", 320, 200, 1.2, "Atari ST lowres su monitor/TV 4:3", "alta"),
    ("atari-st", 640, 400, 1.0, "Atari ST monocromatico SM124: pixel quadrati", "alta"),
    ("pc-98", 640, 400, 1.2, "PC-98 640x400 su monitor 4:3", "media"),
    ("fm-towns", 640, 480, 1.0, "FM Towns 640x480: pixel quadrati", "alta"),
]

# reference to compare timings, input and look against the original
EMULATORS = {
    "dos": [("DOSBox Staging / DOSBox-X", "riferimento principale; ritracce VGA a 70 Hz, cicli fissi; Xvfb + ffmpeg x11grab + xdotool"),
            ("86Box / PCem", "PC d'epoca emulato a livello di hardware, quando i tempi dipendono dalla CPU o dalla scheda video")],
    "windows3": [("86Box / PCem con Windows 3.1", "macchina virtuale d'epoca: tempi più fedeli"),
                 ("DOSBox-X con Windows 3.1", "più semplice da automatizzare")],
    "windows": [("86Box / PCem o QEMU/VirtualBox con Windows 95/98", "macchina virtuale: tempi e driver DirectX/WinG dell'epoca"),
                ("Wine", "comodo e automatizzabile, ma i tempi dipendono dall'host: va bene per logica e testi, non per misurare la velocità")],
    "mac": [("Basilisk II / SheepShaver / Mini vMac", "richiede la ROM del Mac dell'utente")],
    "amiga-pal": [("WinUAE / FS-UAE (cycle-exact)", "richiede le ROM Kickstart dell'utente (o AROS per prove di sola logica)")],
    "amiga-ntsc": [("WinUAE / FS-UAE (cycle-exact, modo NTSC)", "richiede le ROM Kickstart dell'utente")],
    "atari-st": [("Hatari", "EmuTOS libero; TOS originale dall'utente se serve")],
    "pc-98": [("Neko Project II kai / np21w", "richiede le ROM dell'utente")],
    "fm-towns": [("MAME / Tsugaru", "richiede le ROM dell'utente")],
}
ALIASES = {"pc": "dos", "msdos": "dos", "ms-dos": "dos", "win": "windows", "win95": "windows", "win9x": "windows",
           "windows95": "windows", "win31": "windows3", "windows31": "windows3", "amiga": "amiga-pal",
           "st": "atari-st", "atari": "atari-st", "macintosh": "mac", "pc98": "pc-98"}


def norm_platform(p):
    p = (p or "").strip().lower()
    return ALIASES.get(p, p)


def pixel_aspect(platform, width, height, year=None, art=None):
    """Candidate vertical stretch for (platform, resolution, year) with the reasons.
    art: "pixel" (drawn by hand on the target display), "digitized" (scans, photos, 3D renders
    made at square pixels), or None when unknown."""
    plat = norm_platform(platform)
    reasons = []
    hit = next((m for m in _MODES if m[0] == plat and m[1] == width and m[2] == height), None)
    if hit is None and plat in ("windows3", "windows", "mac", "fm-towns"):
        hit = (plat, width, height, 1.0, "piattaforma con pixel quadrati", "alta")
    if hit is None:
        stretch = round((width / height) / (4 / 3), 3)
        reasons.append(f"modo {width}x{height} su {plat or '?'} non in tabella: se riempiva un 4:3, "
                       f"il pixel era allungato di {stretch}; verificare sui documenti dell'epoca")
        sure = "bassa"
    else:
        stretch, why, sure = hit[3], hit[4], hit[5]
        reasons.append(why)
    if year:
        if year >= 1997 and plat == "dos" and stretch != 1.0:
            reasons.append("uscita tarda: molti giochi DOS di fine decennio erano pensati per 640x480 o per "
                           "arte a pixel quadrati")
            sure = "bassa" if sure != "alta" else "media"
        if year < 1987 and plat == "dos":
            reasons.append("prima della VGA: CGA/EGA, controlla il modo grafico effettivo")
    if art == "digitized" and stretch != 1.0:
        reasons.append("arte digitalizzata o renderizzata: se fu acquisita a pixel quadrati e mostrata così, "
                       "la versione fedele è quadrata; se fu schiacciata apposta per il monitor 4:3, va "
                       "allungata. Non si deduce dal tipo di arte: decide il foglio di confronto")
        sure = "bassa"
    elif art == "pixel" and stretch != 1.0:
        reasons.append("disegnata a mano sul monitor dell'epoca: l'artista vedeva i pixel allungati")
    return {"platform": plat, "mode": [width, height], "stretch": stretch, "confidence": sure,
            "correct": stretch != 1.0, "reasons": reasons,
            "check": "confronta `aspect_sheet` su 3-4 scene con oggetti tondi, volti, ruote, orologi, lune "
                     "o testo disegnato: la versione giusta li mostra rotondi e proporzionati"}


def reference_emulators(platform):
    plat = norm_platform(platform)
    rows = EMULATORS.get(plat)
    if not rows:
        return {"platform": plat, "emulators": [],
                "note": "piattaforma non in tabella: cerca l'emulatore più accurato e mantenuto (MAME copre molte "
                        "macchine), con le ROM/BIOS fornite dall'utente"}
    return {"platform": plat, "emulators": [{"name": n, "note": t} for n, t in rows],
            "rules": ["stessa versione del gioco che si rimasterizza (lingua, floppy/CD)",
                      "prima scelta: l'emulatore più fedele ai tempi della macchina; una VM o un livello di "
                      "compatibilità (Wine) solo per ciò che non dipende dai tempi",
                      "registrazione sotto Xvfb con ffmpeg x11grab a 60 fps; input con xdotool; poi "
                      "`rstool.py engine timing <video>`",
                      "ROM, BIOS e sistemi operativi d'epoca li fornisce l'utente: non si scaricano"]}


def aspect_sheet(images, out_path, stretches=(1.0, 1.2), height=360):
    """Same scenes at each candidate stretch, side by side, to choose by eye."""
    rows = []
    for p in images:
        im = Image.open(p).convert("RGB")
        cells = []
        for s in stretches:
            h = height
            w = int(round(im.width * height / (im.height * s)))
            cells.append(im.resize((w, h), Image.LANCZOS))
        rows.append(cells)
    W = max(sum(c.width for c in r) + 16 * (len(r) - 1) for r in rows)
    H = sum(height + 28 for _ in rows)
    from PIL import ImageDraw
    sheet = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    y = 0
    for r, p in zip(rows, images):
        x = 0
        for c, s in zip(r, stretches):
            d.text((x + 4, y + 6), f"{os.path.basename(p)} — allungamento {s}", fill=(230, 230, 230))
            sheet.paste(c, (x, y + 24))
            x += c.width + 16
        y += height + 28
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)
    return {"sheet": out_path, "stretches": list(stretches), "scenes": len(images)}
