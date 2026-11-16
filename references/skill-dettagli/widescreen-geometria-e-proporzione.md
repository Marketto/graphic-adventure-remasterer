# Geometria e proporzione dei pixel

Dettaglio della skill `widescreen`.

La logica resta nelle coordinate originali. Il Layer mostra una viewport più larga, con lo
stesso numero di pixel aggiunti per lato.

**Proporzione dei pixel: si corregge solo se il gioco era concepito per quel tipo di monitor.**
Non basta la risoluzione: decidi nell'analisi, prima di classificare, da
- **data di uscita** e **piattaforma di destinazione** (`game.year`, `game.platform`);
- **dispositivi dell'epoca**: monitor CRT 4:3 che allungavano i pixel (VGA 320x200, EGA, Amiga
  NTSC, Atari ST) o pixel quadrati (640x480, Windows, Mac, Amiga PAL lowres);
- **come è nata l'arte**: disegnata a mano su quel monitor (l'artista vedeva i pixel allungati)
  o digitalizzata/renderizzata a pixel quadrati (allora la versione fedele è quadrata).
**Il controllo è automatico; si chiede all'utente solo in caso di dubbio.**
`rstool.py widescreen aspect-auto --platform dos --w 320 --h 200 --year 1992 [--art pixel|digitized]
--evidence <dump>/bg <dump>/obj [--measure review/misura.json] --record` combina:
- il **candidato della tabella** (piattaforma, modo video, anno, monitor dell'epoca) con la sua
  confidenza (lo stesso di `rstool.py widescreen aspect`);
- le **prove misurate da sole** sul dump: cerca forme ellittiche piene o ad anello (rapporto
  d'inerzia, sovrapposizione con l'ellisse stimata) e archi di cerchi grandi tagliati dal bordo
  (per esempio un oggetto rotondo diviso tra due schermate) in oggetti, icone, sprite e fondali, e ne misura
  larghezza/altezza: un cerchio disegnato per pixel allungati di 1,2 misura ~1,2. Le forme più
  larghe di ogni candidato sono rotonde **in prospettiva** (tavoli, pozzi visti di sbieco) e si
  scartano, quelle più alte non sono rotonde; conta la distribuzione delle restanti (moda e
  sostegno attorno a 1,0, 1,2 o al candidato della tabella), non la singola forma;
- le eventuali **misure manuali** salvate da `aspect-measure` (vedi sotto).
Decide **da solo** (`decided_by: "auto"`) quando la tabella è sicura (confidenza alta) e le prove
non la contraddicono, o quando le prove concordano nettamente con il candidato della tabella;
con `--record` scrive `graphics.pixel_aspect` {stretch, decided_by, confidence, reasons, evidence}
e una decisione con la data. **Chiede** (`decided_by: "ask"`, `stretch` null, `proposed` e i motivi
in `reasons`, «dubbi: ...») quando la confidenza è media o bassa senza prove concordi, quando
prove e tabella (o le prove tra loro) si contraddicono, o con arte digitalizzata senza prove; allora
prepara il foglio di confronto (`--sheet`, default `review/aspect.png`) con le scene dove ha
trovato più forme, e `rstool.py project missing` elenca la domanda finché l'utente non risponde
(`rstool.py project set graphics.pixel_aspect.stretch 1.2 graphics.pixel_aspect.decided_by user`
e una decisione con `project decide`).

Nei casi dubbi aiutano: `rstool.py widescreen aspect-sheet <3-4 fondali con oggetti tondi, volti,
ruote, lune, testo disegnato> --out review/aspect.png` (scene a pixel quadrati e allungati
affiancate; la versione giusta li mostra rotondi; **non basta** su viste in prospettiva e
documenti) e la **misura** manuale di una forma rotonda nella realtà (disco o tavolo visto
dall'alto, ruota, luna, oblò), anche divisa tra più stanze:
`rstool.py widescreen aspect-measure <img...> [--compose 2x2] [--box x,y,w,h] [--color #rrggbb]
--out review/aspect-misura.png` dà larghezza/altezza sui pixel originali (riquadro e momenti,
quanto somiglia a un'ellisse piena) e il candidato più vicino; salvane il JSON e ripassalo ad
`aspect-auto --measure`. Se resta il dubbio guarda l'originale sull'emulatore di riferimento
(skill `engine-integration` §1b) con la correzione d'aspetto dell'epoca.
Default: **pixel quadrati** (`stretch` 1.0). Se l'allungamento serve, imposta
`Desc::pixelAspect`: il Layer scala in verticale con righe filtrate (320x200 a 3x con 1,2 →
960x720), allarga la viewport 16:9 di conseguenza e converte il mouse; `remaster_aspect=false`
lo spegne (vedi `INTEGRAZIONE.md`, "Pixel non quadrati").
Il pacchetto `pixel-aspect` del piano lo imposta nel motore del gioco e lo verifica.

Larghezza delle bande per lato (`rstool.py widescreen geometry --w W --h H [--par <stretch>]`):
- pixel quadrati: 640x400 → **+36 per lato** (712x400, a 3x 2136x1200), 320x200 → +18, 640x480 → +107;
- con allungamento 1,2 (320x200 pensato per un CRT 4:3): 320x200 → +54.
Le bande sono piccole (~11% dell'immagine): l'obiettivo è che non si notino.
