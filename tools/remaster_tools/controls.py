"""Smoothness of the controls, from the input log of the engine's test driver.

The driver (command `inputlog <file>`, see skill engine-integration) writes one line per event:
    <t_ms> in mouse <x> <y>               mouse event received (window/screen pixels)
    <t_ms> draw cursor <x> <y>            cursor position in a presented frame
    <t_ms> in key <name> down|up [repeat] key event; `repeat` = auto-repeat of the OS
    <t_ms> act <name>                     action executed by the game/engine (toggle, menu...)
Synthetic input comes from the driver commands `mousepath` (straight line at constant speed)
and `keyhold` (key held down long enough to auto-repeat).
"""
import statistics


def parse(path_or_lines):
    lines = path_or_lines
    if isinstance(path_or_lines, str):
        with open(path_or_lines, encoding="utf-8") as f:
            lines = f.read().splitlines()
    ev = []
    for ln in lines:
        p = ln.split()
        if len(p) < 3 or p[0].startswith("#"):
            continue
        try:
            t = float(p[0])
        except ValueError:
            continue
        if p[1] == "in" and p[2] == "mouse" and len(p) >= 5:
            ev.append(("mouse", t, int(p[3]), int(p[4])))
        elif p[1] == "draw" and p[2] == "cursor" and len(p) >= 5:
            ev.append(("draw", t, int(p[3]), int(p[4])))
        elif p[1] == "in" and p[2] == "key" and len(p) >= 5:
            ev.append(("key", t, p[3], p[4], len(p) > 5 and p[5] == "repeat"))
        elif p[1] == "act":
            ev.append(("act", t, p[2]))
    return ev


def analyze_cursor(ev, min_hz=50.0, max_latency_ms=34.0, jump_factor=3.0):
    draws = [e for e in ev if e[0] == "draw"]
    moves = [e for e in ev if e[0] == "mouse"]
    res = {"draws": len(draws), "moves": len(moves), "problems": []}
    if len(draws) < 3:
        res["problems"].append("troppo pochi fotogrammi col cursore nel log")
        return res
    dt = [b[1] - a[1] for a, b in zip(draws, draws[1:]) if b[1] > a[1]]
    med = statistics.median(dt)
    hz = 1000.0 / med if med else 0
    res["cursor_hz"] = round(hz, 1)
    gaps = [d for d in dt if d > 2.5 * med]
    res["frame_gaps"] = len(gaps)
    if hz < min_hz:
        res["problems"].append(f"cursore aggiornato a {hz:.0f} Hz (< {min_hz:.0f}): segue il passo della logica, "
                               "va ridisegnato a ogni fotogramma o col cursore hardware")
    if gaps:
        res["problems"].append(f"{len(gaps)} pause nel ridisegno (> {2.5 * med:.0f} ms): scatti visibili")
    # path while the input moves: steps and direction
    steps = [(b[2] - a[2], b[3] - a[3]) for a, b in zip(draws, draws[1:]) if (b[2], b[3]) != (a[2], a[3])]
    if steps:
        mags = [abs(sx) + abs(sy) for sx, sy in steps]
        mmed = statistics.median(mags)
        big = [m for m in mags if m > jump_factor * max(1, mmed)]
        res["step_median_px"] = mmed
        res["jumps"] = len(big)
        if big:
            res["problems"].append(f"{len(big)} salti del cursore oltre {jump_factor}x il passo tipico ({mmed} px)")
        back = 0
        for (ax, ay), (bx, by) in zip(steps, steps[1:]):
            if ax * bx + ay * by < 0:
                back += 1
        res["reversals"] = back
        if moves and back > max(1, len(steps) // 20):
            res["problems"].append(f"{back} inversioni di direzione su un percorso rettilineo: tremolio "
                                   "(arrotondamenti nella conversione schermo → gioco o warp del mouse)")
        xs = sorted({d[2] for d in draws})
        ins = sorted({m[2] for m in moves})
        for k in (4, 3, 2):
            if len(xs) > 8 and all((x - xs[0]) % k == 0 for x in xs) and any((x - xs[0]) % k for x in ins):
                res["problems"].append(f"il mouse si muove di 1 px ma il cursore solo a multipli di {k} px: "
                                       "scatta a pixel di gioco; in modalità remaster disegnalo alla risoluzione "
                                       "dello schermo")
                break
    # latency: first draw at (or past) the position of each input event
    lat = []
    j = 0
    for m in moves:
        while j < len(draws) and draws[j][1] < m[1]:
            j += 1
        for d in draws[j:j + 12]:
            if abs(d[2] - m[2]) <= 2 and abs(d[3] - m[3]) <= 2:
                lat.append(d[1] - m[1])
                break
    if lat:
        res["latency_ms_median"] = round(statistics.median(lat), 1)
        res["latency_ms_max"] = round(max(lat), 1)
        if statistics.median(lat) > max_latency_ms:
            res["problems"].append(f"ritardo mediano del cursore {statistics.median(lat):.0f} ms (> {max_latency_ms:.0f})")
    return res


CONTINUOUS = ("scroll", "walk", "move", "cammina", "scorri")


def analyze_keys(ev, continuous=CONTINUOUS):
    """Every physical press (down without `repeat` ... up) must trigger each action at most once,
    unless the action is meant to repeat (scrolling, walking): those are listed, not flagged."""
    res = {"presses": 0, "problems": [], "repeated_actions": []}
    press = None
    for e in ev:
        if e[0] == "key":
            _k, t, name, state, rep = e
            if state == "down" and not rep:
                press = {"key": name, "t": t, "acts": {}, "repeats": 0}
                res["presses"] += 1
            elif state == "down" and rep and press:
                press["repeats"] += 1
            elif state == "up" and press and press["key"] == name:
                for act, n in press["acts"].items():
                    if n > 1:
                        res["repeated_actions"].append({"key": name, "action": act, "times": n,
                                                        "os_repeats": press["repeats"]})
                press = None
        elif e[0] == "act" and press:
            press["acts"][e[2]] = press["acts"].get(e[2], 0) + 1
    for r in res["repeated_actions"]:
        if r["action"] in continuous:
            continue  # meant to repeat while the key is held
        res["problems"].append(f"tasto {r['key']} tenuto premuto: «{r['action']}» eseguita {r['times']} volte "
                               f"({r['os_repeats']} ripetizioni del sistema). Per azioni a scatto (toggle, menu, "
                               "inventario, salta battuta) ignora gli eventi con kbdRepeat")
    return res


def analyze(path, continuous=CONTINUOUS):
    """continuous: actions that may repeat while a key is held (listed, not flagged)."""
    ev = parse(path)
    cur = analyze_cursor(ev)
    keys = analyze_keys(ev, continuous)
    return {"cursor": cur, "keys": keys, "ok": not cur["problems"] and not keys["problems"]}
