# Contratto degli asset rimasterizzati (RAC v1)

Il motore e gli strumenti si parlano solo attraverso questo contratto. Il motore non sa
come un asset è stato prodotto; gli strumenti non sanno come il motore lo disegna. Così ogni
asset può essere rigenerato, sostituito o spento senza toccare il codice.

Derivato da un remaster completo usato come banco di prova
(`references/conoscenza/`).

## Radice
Tutto sta in `<cartella del gioco>/remaster/`. Se la cartella manca, il gioco parte originale.

```
remaster/
  manifest.json            id gioco, versione pack, scala, aspetto, contenuti, hash ricetta
  gfx/bg/<scene>.png|jpg   fondali HD (multiplo intero dell'originale)
  gfx/bg/<scene>.wide.json 16:9: {"left","right" (px a scala originale), "camera": "clamp"|"center"}
  gfx/bg/<scene>.wide.png  fondale esteso (stessa scala del fondale HD); senza: bande nere
  gfx/bg/<scene>.<lang>.png|jpg       fondale localizzato (testi dipinti tradotti): per la
                           lingua del Layer vince su <scene>.png; se manca si usa quello normale
  gfx/bg/<scene>.<lang>.wide.png|jpg  idem per il fondale esteso (la geometria resta in
                           <scene>.wide.json, unica per tutte le lingue)
  gfx/spr/index.dat        indice sprite (formato RSPR, sotto)
  gfx/spr/<key>.png|jpg    frame HD, key = frameKey (PNG con alpha; un JPEG è opaco nei blocchi originali)
  fonts/<font>.dat|png     atlante font HD (formato RFNT, sotto)
  fonts/charmap.tsv        mappa carattere Unicode -> codice del glifo per tutti i font (sotto)
  fonts/<font>.charmap.tsv override della mappa per un solo font (alias propri)
  ui/verbs.<lang>.tsv      etichette dei verbi dell'interfaccia: posizione e larghezza massima (sotto)
  text/<lang>.tsv          testi corretti/tradotti: "<textKey>\t<testo UTF-8>"
  voice/<lang>/<textKey>.ogg   battute doppiate; possono coprire solo alcune parti del gioco
                           (doppiaggio parziale, voice.scope): una riga senza file ricade sul
                           comportamento originale (clip originale o solo sottotitolo)
  voice/<lang>/<textKey>.lip.json  sincronia labiale della voce nuova: {"fps": 60, "frames": [indici
                           della bocca]}, generata dall'audio; senza file il motore guida la bocca
                           dall'ampiezza o la lascia ferma (le voci nuove perdono i dati
                           originali di movimento della bocca)                   [hook per motore]
  music/<nome>.ogg         sostituti digitali dei brani (MIDI, MOD, CD)        [hook per motore]
  sfx/<nome>[_<rate>].ogg  effetti rimasterizzati (rate = frequenza di riproduzione) [hook per motore]
  manual/<lang>.md         manuale ripulito/tradotto, letto in gioco dal menu     [hook per motore]
  manual/img/<file>.png    immagini del manuale
  manual/<lang>.html       stesso manuale come pagina unica (con img/ copiate accanto); il rilascio
                           ne mette una copia anche accanto all'eseguibile
  hint/<lang>.txt          aiuti in gioco (tasto H), formato in tools/remaster_tools/hints.py [hook per motore]
  theme/<gioco>.zip        tema GUI di ScummVM nello stile del gioco (stesso commit del fork)
  video/<nome>.mkv         filmato rimasterizzato (H.264, fps e durata originali, audio originale);
                           <nome> = file originale in minuscolo senza estensione; `.ogv` (Theora)
                           se il fork usa il decoder Theora di ScummVM; senza file: originale [hook per motore]
  gfx/inbetween/<key>.png  frame intermedi delle animazioni                       [riservato]
  fonts/<font>.<lang>.dat  atlante per lingue oltre la codepage del gioco          [riservato]
```

## Dump (ingresso degli strumenti)
Il dump è ciò che gli strumenti leggono dell'originale: lo scrive il Layer (`remaster_dump=`,
frame `.raw`) oppure, finché il Layer non è agganciato al motore, un **adattatore** del
repository privato (`rstool.py engine extract --adapter <script> --game <dir> --out <dump>`, PNG
ammessi). Stesso formato in entrambi i casi, controllato da `rstool.py engine validate-dump`:
```
<dump>/bg/<scene>.png|raw     fondali a misura originale     bg/names.json  {scena: nome della stanza}
<dump>/spr/<key>.png|raw      sprite (PNG RGBA)              spr/index.json elenco dei fotogrammi
<dump>/obj/<nome>.png         oggetti disegnati sui fondali
<dump>/text.jsonl             {"hex", "kind", "location", "speaker", "voice", ...} una riga per occorrenza
<dump>/voice-index.json       {id voce: {"file", "hex", "speaker", "seconds", "lipsync"}}
<dump>/midi/<nome>.mid        musica come MIDI standard (variante più vicina al General MIDI)
<dump>/meta.json              {"screen": [w, h], "playfield_h", "engine", "extractor"}
```
Dettagli e tipi di battuta ammessi: `tools/remaster_tools/extract.py`. `lipsync` vero vuol dire
che la clip originale porta dati di movimento della bocca: le voci nuove ne richiedono di nuovi.

## Chiavi
- **frameKey** (sprite, UI, cursori): CRC32 zlib di `w` (LE16), `h` (LE16), poi i pixel
  indicizzati del frame decompresso, riga per riga. Esadecimale minuscolo a 8 cifre.
  Indipendente da nome file e posizione: lo stesso frame riusato in più animazioni è
  rimasterizzato una volta sola.
- **textKey** (testi, voci): CRC32 zlib dei byte del testo originale (codepage del gioco)
  saltando spazio, tab, CR, LF, VT, FF e backslash. Così gli a-capo del motore non cambiano
  la chiave. Esadecimale minuscolo a 8 cifre.
- **scene** (fondali): definita dal motore, di solito `<parte>/<nome risorsa>`. Nei nomi
  dei file `/` e `\\` diventano `_` (`part1/bg/room` → `gfx/bg/part1_bg_room.png`): il dump
  del Layer, gli strumenti e `AssetPack` usano la stessa regola. Il fondale localizzato aggiunge
  la lingua dopo il nome (`gfx/bg/part1_bg_room.it.png`, `gfx/bg/part1_bg_room.it.wide.png`);
  la lingua è quella del Layer (`remaster_language`, altrimenti la lingua di ScummVM).
- Le voci marcate `[hook per motore]` le legge il codice del singolo motore,
  non il Layer comune; quelle `[riservato]` non sono ancora implementate.

`rstool.py key frame|text` calcola le chiavi; i test in `tools/tests` ne fissano i valori.

## Regole di composizione
1. La logica gira sempre alla risoluzione e al framerate originali. L'HD è solo resa.
2. Un pixel del fondale HD si usa solo se il pixel 8 bit corrispondente nel back buffer è
   ancora quello del fondale originale; altrimenti si usa l'upscaling del frame (Scale2x/3x nel
   Layer comune, xBR come alternativa) o lo
   sprite HD che lo ha disegnato (buffer di id per pixel).
3. Effetti di palette: dissolvenze e grigi si applicano ai pixel HD; effetti esotici (color
   cycling) ricadono sull'upscaling solo per i colori coinvolti.
4. Il toggle originale/remaster ricompone il frame corrente senza ricaricare la scena.

## Formato RSPR (`gfx/spr/index.dat`), little endian salvo il tag
```
char[4]  "RSPR"
u16      versione = 1
u16      scala dei PNG (2, 3, 4)
u16      numero palette di riferimento N
u8[N][768] palette RGB 8 bit con cui i frame sono stati dipinti
u32      numero voci M
M x { u32 frameKey; u16 palette; u16 w; u16 h }
```

## Formato RFNT (`fonts/<font>.dat` + `.png`)
```
char[4] "RFNT"
u16 versione = 1, u16 scala, u16 altezza riga, u16 ascendente, u16 spessore contorno
256 x { u16 ax, ay, w, h; s16 bx, by; u16 avanzamento }   (per codice della codepage)
```
PNG: canale R = copertura del riempimento, canale G = copertura della **sagoma completa**
(riempimento + contorno/ombra; 0 nei font a 1 bpp). Il contorno disegnato è G senza R.
Per alfabeti oltre i 256 codici è previsto `fonts/<font>.<lang>.dat` con la codepage della lingua (riservato).

Atlanti da font bitmap originali (`rstool.py font from-bitmap`): scala 3, altezza riga =
ascendente = altezza del font × 3, spessore contorno 3 (font con contorno) o 0; ogni glifo ha 1 px
originale di margine nell'atlante, quindi `bx = (ox − 1)·3`, `by = (oy − 1)·3` dalla penna (angolo
in alto a sinistra) e `avanzamento = adv·3`. Ridotto a 1x (centro di ogni blocco 3×3) il glifo
coincide con quello originale o costruito: è il modo in cui il motore disegna in modalità
originale i glifi che il font originale non ha.

**Maiuscole accentate**: lettera maiuscola intera (piena altezza) + accento sopra, anche oltre la
cima della riga (`by` negativo, `oy` < 0). Mai il corpo accorciato per far stare l'accento nella
cella: accanto alle minuscole si legge minuscola. Il motore non taglia ciò che sporge dalla cella.

### `fonts/charmap.tsv`
Testo UTF-8, una voce per riga, `#` commento:
```
U+00E8<TAB>8A
```
Colonna 1 punto di codice (`U+` + 4–6 cifre esadecimali), colonna 2 codice del glifo (00–FF,
esadecimale) valido in tutti gli atlanti `fonts/*.dat`. Più caratteri possono puntare allo stesso
codice (alias). `fonts/<font>.charmap.tsv`, stesso formato, sostituisce le voci della mappa generale
per quel font. Contenuto tipico: ASCII identico, 0x80–0xFF secondo la codepage dei byte del gioco,
più i caratteri aggiunti in codici liberi (di preferenza la loro posizione CP850, mai un codice che
il motore usa per scopi propri). Carattere assente o glifo vuoto: il motore disegna `?` e lo
registra nel log. Controllo: `rstool.py font coverage remaster/fonts --texts remaster/text/*.tsv`
(tutti i caratteri dei testi di tutte le lingue in ogni font).

### `ui/verbs.<lang>.tsv`
Etichette dell'interfaccia (verbi) che nella lingua tradotta sbordano o vanno spostate:
```
# id verbo<TAB>x<TAB>y[<TAB>larghezza massima]   (pixel del gioco)
11	53	159	43
```
Senza riga il verbo resta dove lo mette il gioco. Oltre la larghezza massima il motore riduce la
spaziatura tra le lettere (1–2 px, stessa resa in classico e in HD); se non basta, si accorcia il
testo in `text/<lang>.tsv`. Se esiste un'edizione tradotta ufficiale, le posizioni si prendono da lì.

## manifest.json
```json
{
  "rac": 1, "game": "<id>-dos-cd", "pack": "1.0.0", "scale": 3,
  "aspect": "16:9", "languages": ["it", "en"],
  "contents": ["bg", "spr", "fonts", "text", "music", "sfx", "voice", "video"],
  "recipe": {"file": "recipe.json", "hash": "sha256:..."}
}
```
