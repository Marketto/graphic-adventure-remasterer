---
name: hd-graphics
description: Pipeline locale per rifare in HD fondali, sprite, interfaccia, cursori, font e filmati di un'avventura 2D d'epoca nel rispetto della style bible (upscaler APISR/Real-ESRGAN su CPU, contorno smussato e inchiostro degli sprite, img2img opzionale, atlanti font, filmati ricodificati), producendo asset conformi al contratto RAC. Usala nella fase asset del remaster.
---

# Grafica HD

Prerequisiti: `analysis/style-bible.md` approvata; `analysis/style-recipes.json` solo se si userà
l'img2img (esempio commentato in `${CLAUDE_PLUGIN_ROOT}/references/style-recipes.example.json`).
Nessuna GPU richiesta: la pipeline collaudata gira su CPU (2 core, 7 GB di RAM bastano).

## Backend (`rstool.py gfx backends` dice cosa c'è e quali modelli sono configurati)
1. **spandrel + PyTorch su CPU (pipeline collaudata).** Pesi `.pth`/`.safetensors` caricati con
   `spandrel`, inferenza a tessere sovrapposte (256 px + 16 di contesto: memoria limitata,
   senza cuciture visibili: il risultato è identico all'immagine intera solo se la portata del
   modello sta nei 16 px). Installazione:
   `pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install spandrel`.
   Modelli dalle release GitHub dei progetti, scaricati **fuori dal repository** (es. `~/modelli`):
   - fondali, bande 16:9 e filmati: **APISR RRDB** (`4x_APISR_RRDB_GAN_generator.pth`);
   - sprite: **APISR GRL** (`4x_APISR_GRL_GAN_generator.pth`).
   Scelta del modello: `--model <file>` oppure le variabili `REMASTER_MODEL_BG` (fondali, bande,
   filmati) e `REMASTER_MODEL_SPR` (sprite). Un modello configurato deve funzionare: se mancano
   torch/spandrel il comando si ferma con le istruzioni, non ripiega in silenzio.
   Tempi misurati (CPU 2 core): ~80 µs per pixel d'ingresso per tessera (RRDB e GRL), ~110 µs
   con le sovrapposizioni: un fondale 320x200 ~7 s, 640x400 ~30 s; 100 fondali ~1 h.
2. **`realesrgan-ncnn-vulkan`** nel PATH: alternativa (Vulkan, anche senza CUDA); `--model` col
   nome del modello ncnn (es. `realesrgan-x4plus-anime`). Più morbido di APISR.
3. **Scale2x/3x** sugli indici di palette: sempre disponibile, deterministico, nulla di inventato.
4. **ComfyUI (opzionale, GPU)** solo per l'img2img con LoRA di stile e ControlNet tile
   (`COMFYUI_URL`, default `http://127.0.0.1:8188`), costruito da `tools/remaster_tools/comfy.py`
   dalla ricetta. Mai necessario per l'HD di base.
La riduzione finale da 4x alla scala del pacchetto usa LANCZOS per fondali e filmati e BOX per
gli sprite (niente aloni sui contorni).

## 0. Estrazione
Dal motore con l'opzione di dump del Remaster Layer (`remaster_dump=<cartella>`): fondali per scena + palette, ogni frame di sprite come
`.raw` (w, h, colore trasparente, palette, pixel) + `.png` di anteprima.
`rstool.py assets inventory <dump>` crea `analysis/assets.csv` (tipo, chiave, dimensioni,
scena, frequenza d'uso) per dare priorità ai frame più visti.

## 1. Fondali
Dettagli e misure: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/grafica.md` (§2-3).
`rstool.py gfx bg <dump>/bg --out remaster/gfx/bg --scale 3 --format jpg [--model ~/modelli/4x_APISR_RRDB_GAN_generator.pth] [--recipe analysis/style-recipes.json]`
1. Conversione dell'originale con **la stessa palette che usa il motore** (altrimenti il test
   "pixel uguale allo sfondo" del compositore fallisce).
2. **Scelta dell'upscaler su fogli numerati** (0 = originale, 1 = attuale, poi i candidati), con
   batterie separate per fondali e personaggi: il migliore per uno non lo è per l'altro.
   Nel progetto di riferimento: **APISR RRDB** per i fondali (linee nette), **APISR GRL** per gli
   sprite; Real-ESRGAN anime 6B accettabile ma morbido; i modelli "Sharp" 2x sfocano o
   cancellano i volti; APISR DAT è 7 volte più lento senza vantaggi visibili.
3. Solo se la style bible lo chiede e c'è una GPU con ComfyUI: img2img con LoRA di stile e
   ControlNet tile, denoise basso; poi **ricolorazione sulla palette originale** (`color_lock`,
   applicata in automatico dopo l'img2img). `--no-ai` lo esclude.
4. 4x → 3x con LANCZOS, JPEG q90 **4:4:4** (`--format jpg`; il 4:2:0 sporca i bordi colorati).
5. **Ripartibile**: una scena già fatta con stessa scala, modello e ricetta si salta
   (`--no-resume` per rifarla); il modello usato è scritto in `<scena>.jpg.json`.
6. Le bande 16:9 si ingrandiscono **con lo stesso modello** dei fondali:
   `rstool.py widescreen extend ... --model <stesso file>` (o la stessa `REMASTER_MODEL_BG`).
Controlli automatici (`rstool.py gfx check`): stessa composizione (SSIM sul ridotto ≥ 0.85),
nessuna deriva cromatica (ΔE medio ≤ 6), nessuna scritta inventata. Verifica sempre nel log del
motore che l'HD sia stato caricato: un'edizione con dimensioni diverse lo fa scartare in silenzio.

## 2. Sprite e animazioni
`rstool.py gfx sprites <dump>/spr --out remaster/gfx/spr --scale 3 [--model ~/modelli/4x_APISR_GRL_GAN_generator.pth] [--format jpg] [--no-ink]`
- **Coerenza prima di tutto.** Migliaia di fotogrammi non reggono la generazione AI fotogramma
  per fotogramma: solo trattamenti **deterministici** (stesso input → stesso output; i test lo
  verificano). `--ai` (img2img per fotogramma) solo per pochi fotogrammi statici approvati.
- Pipeline (`gfx.remaster_sprite`), quella finale del progetto di riferimento:
  1. riquadro utile; i colori fuori sagoma si allargano da quelli di bordo, così il colore
     trasparente non entra nell'upscaler;
  2. upscaler (APISR GRL) a 4x e riduzione BOX; senza modello, Scale2x/3x sugli indici;
  3. **contorno smussato**: la sagoma è il livello 0,5 della maschera originale sfocata
     (σ = 0,65 px a 1x, lo stesso campo dell'alpha del motore), con antialiasing;
  4. **inchiostro**: dove il bordo originale è scuro (luminanza sotto ~0,6 volte l'interno) si
     ridipinge lungo il bordo smussato una fascia spessa come il contorno originale (misurato in
     px a 1x, di solito ~1, × scala), con antialiasing e nel colore del contorno originale;
     linee interne e colori restano quelli dell'upscaler. `--no-ink` per confrontare;
  5. **colori fuori sagoma riempiti** allargando quelli di bordo (box blur a raggi 2-16): niente
     frange scure dove l'alpha sfuma.
  Formato: **PNG** con l'alpha, l'unico che il Layer comune usa per gli sprite. Limite del Layer
  comune: disegna i pixel HD di uno sprite solo dentro i blocchi dei pixel originali dello
  sprite, quindi la sfumatura che esce dalla sagoma originale viene tagliata e un JPEG (senza
  alpha) torna a scalini. Per contorni pienamente morbidi serve un aggancio nel motore che
  ricostruisca l'alpha dalla maschera originale anche nei blocchi vicini (come nel progetto di
  riferimento); solo allora `--format jpg` ha senso.
- Una resa "cinematografica" calcolata dalla sagoma (ombra cel-shading, luce di bordo) era stata
  approvata e poi **abbandonata**: creava ombre e macchie scure. Prima di cambiare modello,
  isola quale passo della pipeline causa il difetto (prova `--no-ink`, poi senza `--model`).
- **Si decide guardando**: 3-4 personaggi affiancati per ogni variante; poi lo stesso valore per tutto.
- **Personaggi riconoscibili** (opera d'origine in `remaster.json` → `source_work.characters`,
  vedi `style-bible` §1b): per i lineamenti il riferimento è l'**artwork ufficiale dello stesso
  gioco** (copertina, scatola, manuale, primi piani e ritratti dei dialoghi), mai fotografie o
  fotogrammi della persona reale, né come immagine guida né come LoRA. Gli attori restano un
  riferimento d'epoca (costumi, luce), mai un modello per i volti.
- Sprite peggiorato dall'HD → toglilo dall'indice: il motore usa l'originale.
- Copertura: il dump vede solo i fotogrammi disegnati; ripeti `fuzz` su ogni parte finché i
  fotogrammi nuovi si azzerano.

## 3. Interfaccia, inventario, cursori
Come gli sprite (sono frame); i cursori a 2-3x con hotspot scalato.

## 4. Font e testi
**Strada preferita per i testi in gioco: l'HD dei font bitmap originali**, fedele al disegno.
```
rstool.py font from-bitmap <dump del font> --name <font> --scale 3 --out remaster/fonts \
    [--extra-edition <dump dello stesso font di un'altra edizione>] [--compose-accents] \
    [--texts remaster/text/*.tsv] [--reserve 08,12,7F]
rstool.py font coverage remaster/fonts --texts remaster/text/*.tsv
```
Dump del font: JSON (`height`, `bpp`, glifi con `w h ox oy adv px`) o cartella di PNG indicizzati
`<hex>.png` + `font.json`; valori 0 vuoto, 1 riempimento, 2 contorno/ombra, 3 secondo colore. Lo
scrive il Layer o l'adattatore del repository privato.
1. **Ingrandimento 3x con angoli vivi** (`crisp3x`): blocchi 3×3 esatti, smussatura solo dei gradini
   delle diagonali vere; angoli retti convessi e concavi restano vivi e il centro di ogni blocco è il
   pixel originale. **Mai Scale3x doppio, media o upscaler IA sui glifi**: arrotondano gli angoli e
   una D si legge O. Contorno/ombra restano quelli dell'originale (stessa matrice indicizzata);
   atlante RFNT con R = riempimento, G = sagoma (contratto RAC).
2. **Verifica automatica**: il comando riduce ogni glifo dell'atlante a 1x (centri dei blocchi,
   come il motore in modalità originale) e lo confronta con l'originale/costruito
   (`verify_mismatch` deve essere vuoto, altrimenti esce con errore).
3. **Glifi mancanti per la lingua**, in quest'ordine: (a) dall'**altra edizione dell'utente** dello
   stesso gioco (`--extra-edition`, stesso disegno; se la lettera base ha peso diverso si mette
   l'accento dell'altra edizione sulla base di questa); (b) **costruiti** (`--compose-accents`):
   lettera base dello stesso font + accento della minuscola accentata dello stesso font (acuto ↔
   grave specchiato se manca), stessa distanza dal corpo, centrato, contorno rifatto con il nocciolo
   misurato sul font. I codici nuovi vanno in posizioni libere (di preferenza CP850, mai i codici
   del motore: `--reserve`) e nella **charmap** `fonts/charmap.tsv` (override per font).
4. **Maiuscole accentate a piena altezza** con l'accento sopra la riga: `--compose-accents` rifà
   anche quelle che l'originale accorcia per far stare l'accento nella cella (si leggono minuscole).
   Controlla `outside_line` nel risultato e, in gioco, che il motore non tagli l'accento (fumetti su
   più righe: l'accento può coprire 1–2 righe di contorno della riga sopra, di solito accettabile).
   Prova le varianti in un fumetto vero (HD e classico) e falle scegliere all'utente con un foglio.
5. **Copertura**: `font coverage` deve dare `ok` per tutti i testi di tutte le lingue; i glifi
   mancanti nel font originale il motore li disegna anche in modalità originale riducendo l'atlante.
6. **Stilizzazioni volute** dell'originale (alfabeti finti, maiuscoletto, tratti tagliati) restano:
   si costruisce solo ciò che manca, nello stesso stile.

**TTF come alternativa** (sottotitoli, filmati, font originale inservibile):
`rstool.py font build <ttf> --name <font> --scale 3 --codepage cp850 --out remaster/fonts`, TTF
OFL scelto confrontando 2–3 candidati con il font bitmap; sottotitoli più leggibili dello stesso
stile, chiari con contorno nero, in basso con fascia scura (posizione originale come opzione).

**Menu, tema GUI e finestra degli aiuti**: il font del gioco solo per titoli e pulsanti; per i testi
lunghi un font leggibile con tutti gli accenti delle lingue; dimensione minima che segue la scala
della GUI (mai più piccola del font del tema a quella scala).

## 5. Filmati
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

## 6. Framerate alto delle animazioni (opzionale, con conferma)
Il Layer interpola lo scorrimento senza asset nuovi. Per animazioni molto scattose
(camminate a 6-8 fotogrammi) si possono generare frame intermedi (`gfx/inbetween/`) con
interpolazione video (RIFE) sul livello fedele: proponilo su 2-3 animazioni di prova e
fallo approvare, perché può tradire il ritmo voluto dall'animatore.

## Consegna e revisione
Appena pronto il primo fondale: `rstool.py gfx compare <orig> <hd> --out review/<scena>.png` e manda
l'immagine affiancata all'utente. Ogni lotto di 20 fondali: galleria di revisione
(`rstool.py review compare <dump>/bg remaster/gfx/bg`) prima di proseguire. Per i filmati:
2-3 secondi di prova (`--max-frames`) prima della passata intera.
