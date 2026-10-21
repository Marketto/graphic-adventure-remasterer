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
  gfx/spr/index.dat        indice sprite (formato RSPR, sotto)
  gfx/spr/<key>.png|jpg    frame HD, key = frameKey
  fonts/<font>.dat|png     atlante font HD (formato RFNT, sotto)
  text/<lang>.tsv          testi corretti/tradotti: "<textKey>\t<testo UTF-8>"
  voice/<lang>/<textKey>.ogg   battute doppiate
  music/<nome>.ogg         sostituti digitali dei brani (MIDI, MOD, CD)        [hook per motore]
  sfx/<nome>[_<rate>].ogg  effetti rimasterizzati (rate = frequenza di riproduzione) [hook per motore]
  manual/<lang>.md         manuale ripulito/tradotto, letto in gioco dal menu     [hook per motore]
  manual/img/<file>.png    immagini del manuale
  manual/<lang>.html       stesso manuale come pagina unica (con img/ copiate accanto); il rilascio
                           ne mette una copia anche accanto all'eseguibile
  hint/<lang>.txt          aiuti in gioco (tasto H), formato in tools/remaster_tools/hints.py [hook per motore]
  theme/<gioco>.zip        tema GUI di ScummVM nello stile del gioco (stesso commit del fork)
  gfx/inbetween/<key>.png  frame intermedi delle animazioni                       [riservato]
  fonts/<font>.<lang>.dat  atlante per lingue oltre la codepage del gioco          [riservato]
```

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
  del Layer, gli strumenti e `AssetPack` usano la stessa regola.
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
PNG: canale R = copertura riempimento, canale G = copertura contorno.
Per alfabeti oltre i 256 codici è previsto `fonts/<font>.<lang>.dat` con la codepage della lingua (riservato).

## manifest.json
```json
{
  "rac": 1, "game": "<id>-dos-cd", "pack": "1.0.0", "scale": 3,
  "aspect": "16:9", "languages": ["it", "en"],
  "contents": ["bg", "spr", "fonts", "text", "music", "sfx", "voice"],
  "recipe": {"file": "recipe.json", "hash": "sha256:..."}
}
```
