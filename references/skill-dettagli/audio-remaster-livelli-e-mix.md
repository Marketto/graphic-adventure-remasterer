# Livelli: prima per gruppo, poi il mix tra i gruppi

Dettaglio della skill `audio-remaster`.

Le tracce si dividono in tre **gruppi**: `music` (bgm: CD, MIDI renderizzato, MOD), `sfx`
(effetti) e `voice` (parlato). Il lavoro ha due fasi distinte e si codifica **una volta sola**,
con la somma dei due guadagni (niente doppia compressione con perdita):

**Fase 1 — normalizzazione per gruppo** (`rstool.py audio normalize <gruppo> <file o cartelle>`):
ogni gruppo viene portato allo stesso livello di riferimento (-23 LUFS, EBU R128) con la regola
del gruppo, e il risultato va in `analysis/audio-norm.json` (solo misure e guadagni):
| Gruppo | Regola | Perché |
|---|---|---|
| `music` | **per file**: ogni brano al riferimento | tutte le tracce devono suonare allo stesso volume |
| `voice` | **per file**: ogni battuta al riferimento | nessun personaggio più forte di un altro |
| `sfx` | **per gruppo**: un solo guadagno per tutti, calcolato sugli effetti forti (90° percentile) | resta la differenza voluta dagli autori tra un sussurro e un'esplosione |
Clip più corte di 400 ms (la misura integrata le dà a -70 LUFS): `normalize` le misura insieme,
concatenate, e dà a tutte lo stesso guadagno (campo `short` nel piano).
Prima della fase 1: effetti puliti e ricampionati (`audio sfx --lossless`), MIDI renderizzato in
WAV/FLAC (`audio render-midi ... --out x.flac`), tracce CD estratte: tutto senza perdita.

**Fase 2 — mix** (`rstool.py audio mix analysis/audio-norm.json --mix audio/mix.json --out remaster`):
un livello per gruppo fissa il rapporto tra le tracce. Valori di partenza consigliati (la musica ~7 dB sotto il parlato):
| Gruppo | Livello nel mix | Note |
|---|---|---|
| Parlato | -18 LUFS | mono 44,1 kHz |
| Effetti | -16 LUFS gli effetti forti, nessun file oltre -16 (`cap`) | mai più forti dell'originale se l'originale era già forte |
| Musica | -25 LUFS | ~7 dB sotto il parlato: a livelli uguali la musica lo copre |
Guadagno statico (al massimo ±8 dB, la dinamica non cambia), `adeclip` solo sulle tracce già
saturate nell'originale, limitatore a 0,89, OGG Vorbis q6; i file limitati sono elencati.
I livelli stanno in `remaster.json` (`audio.mix`, usato quando non si passa `--mix`) o in un
`audio/mix.json` nel repository privato, per esempio `{"voice": -18, "sfx": -16, "music": -25,
"cap": {"sfx": -16}}`. **Si decide ascoltando**: `rstool.py audio mix-preview --music <brano>
--sfx <effetto> --voice <battuta> --music-offsets 0 -3 3` produce 2-3 prove (musica di sottofondo,
un effetto, una battuta) da far sentire all'utente; il valore scelto vale per tutto il gioco.
Se il gioco non viene doppiato, la musica può salire (es. -20): chiedilo con una prova
d'ascolto. Registra i livelli in `remaster.json` (`audio.mix`) e nelle decisioni, e rifai la
fase 2 (non la 1) quando cambiano. Gli slider musica/effetti/parlato di ScummVM restano al
giocatore: partono uguali, quindi il mix scelto è quello che sente.
