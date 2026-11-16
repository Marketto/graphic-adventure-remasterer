---
name: hd-graphics
description: HD locale di fondali, sprite, oggetti, icone, puntatori, font e filmati nel rispetto della style bible, in asset conformi al contratto RAC. Usala nella fase asset del remaster.
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
Dettagli e misure: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/grafica/02-upscaler-modelli-provati-e-scelta.md` e `03-pipeline-degli-sfondi.md`.
`rstool.py gfx bg <dump>/bg --out remaster/gfx/bg --scale 3 --format jpg [--model ~/modelli/4x_APISR_RRDB_GAN_generator.pth] [--recipe analysis/style-recipes.json]`
1. Conversione dell'originale con **la stessa palette che usa il motore** (altrimenti il test
   "pixel uguale allo sfondo" del compositore fallisce).
2. **Scelta dell'upscaler su fogli numerati** (0 = originale, 1 = attuale, poi i candidati), con
   batterie separate per fondali e personaggi: il migliore per uno non lo è per l'altro.
   Scelta che ha funzionato in pratica: **APISR RRDB** per i fondali (linee nette), **APISR GRL** per gli
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
- Prima l'uso: solo i fotogrammi che il gioco carica (`usage scan` o `dumpall` del driver); spesso
  la maggior parte di quelli senza HD sta in file mai caricati.
- Pipeline (`gfx.remaster_sprite`), quella che ha funzionato meglio in pratica:
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
Come gli sprite (sono frame). Per i dettagli piccoli spesso è meglio il vettoriale ("doppio +
vettoriale"). Icone dell'inventario da un fotogramma unico pulito; puntatori HD RGBA con l'icona
dell'oggetto in mano (`ui/cursor/`). Sprite a tempo e a forma libera, fotogrammi uniformati,
varianti proposte accanto all'originale: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/grafica/11-oggetti-puntatori-icone.md`.

## 4. Font e testi
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/hd-graphics-font-e-testi.md` per i font e i testi HD.

## 5. Filmati
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/hd-graphics-filmati.md` per i filmati.

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
