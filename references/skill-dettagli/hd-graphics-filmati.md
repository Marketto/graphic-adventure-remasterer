# 5. Filmati

Dettaglio della skill `hd-graphics`.

Intro, intermezzi e finali in FMV o animazioni precalcolate.
1. **Analisi**: `rstool.py video probe <file>` → formato, risoluzione, fps (anche frazionari),
   durata, fotogrammi, tracce audio e stima dei minuti di CPU con il modello. ffmpeg legge molti
   formati d'epoca (Smacker, FLIC, AVI/QuickTime con codec storici). Se non lo legge, si fa
   fare il dump al motore (PNG numerati per fotogramma) e si passa la cartella con `--fps`.
2. **Upscale**: `rstool.py video upscale <file|cartella> --out remaster/video/<nome>.mkv --scale 3 [--model ...] [--fps 15] [--audio <file>]`
   - fotogrammi estratti 1:1 (nessuno perso o duplicato), fps originale conservato;
   - ogni fotogramma ingrandito in modo deterministico con **lo stesso backend dei fondali**;
     i fotogrammi identici (inquadrature ferme, pause) si riconoscono dall'hash dei pixel e si
     calcolano una volta sola: niente tempo sprecato e niente sfarfallio sui fermi;
   - cartella di lavoro `<out>.work` (fotogrammi HD per hash): un'esecuzione interrotta
     riparte da dove era arrivata; `--max-frames N` per una prova veloce, `--clean` alla fine;
   - ricodifica: MKV/MP4 H.264 a CRF 12 (`--crf`), **4:2:0 di default** (lo leggono anche telefoni,
     browser e decoder hardware; `--pix-fmt yuv444p` solo per archivio o desktop), oppure `.ogv`
     Theora + Vorbis (sempre 4:2:0, il formato che ScummVM sa già decodificare); l'audio originale si copia se il
     contenitore lo accetta, altrimenti FLAC (MKV), AAC (MP4) o Vorbis (OGV).
3. **Sottotitoli e voci**: se il motore disegna i sottotitoli dei filmati come testo, passano
   per `text/<lang>.tsv` e le voci per `voice/<lang>/<textKey>.ogg` come le altre battute
   (skill `localization` e `voice-dubbing`). Il parlato già mixato nella traccia del filmato non
   si separa: un doppiaggio del filmato richiede una traccia audio sostitutiva, da proporre.
4. **Aggancio nel motore** (`[hook per motore]` in `references/asset-contract.md`): il pacchetto
   contiene `video/<nome>.mkv` (`<nome>` = nome del file originale del filmato, minuscolo e senza
   estensione). Il lettore del motore, quando apre il filmato originale, cerca il sostituto e lo
   riproduce alla risoluzione HD con la stessa durata; se manca o non è decodificabile usa
   l'originale. Il formato lo decide il decoder disponibile nel fork: ScummVM ha già un decoder
   Theora (con libtheora) per `.ogv`; H.264 richiede un decoder esterno da aggiungere alla build.
   La logica (salti con Esc, sincronia con gli script) resta quella originale.
5. **Interpolazione (RIFE): non implementata, solo proposta.** Raddoppiare i fotogrammi con
   interpolazione video può tradire il ritmo voluto dall'animatore e inventare forme nei
   movimenti rapidi: si propone su 2-3 filmati di prova affiancati all'originale, con stima dei
   tempi, e si applica solo dopo approvazione esplicita (`--interpolate` oggi si rifiuta).
