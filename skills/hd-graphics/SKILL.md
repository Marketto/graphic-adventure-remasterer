---
name: hd-graphics
description: Pipeline locale per rifare in HD fondali, sprite, interfaccia, cursori e font di un'avventura 2D d'epoca nel rispetto della style bible (upscaling, LoRA di stile, img2img controllato, alfa degli sprite, atlanti font), producendo asset conformi al contratto RAC. Usala nella fase asset del remaster.
---

# Grafica HD

Prerequisiti: `analysis/style-bible.md` e `analysis/style-recipes.json` approvati.
Tutto gira in locale sul PC dell'utente con GPU (backend in ordine di preferenza):
1. ComfyUI in esecuzione (`COMFYUI_URL`, default `http://127.0.0.1:8188`): img2img e
   outpainting con soli nodi standard (checkpoint, LoRA di stile, ControlNet tile), costruiti
   da `tools/remaster_tools/comfy.py` a partire dalla ricetta (esempio in
   `references/style-recipes.example.json`);
2. `realesrgan-ncnn-vulkan` nel PATH: upscaling di base di qualità (Vulkan, anche senza CUDA);
3. senza GPU: solo upscaling deterministico Scale2x/3x — nessuna parte inventata.
`rstool.py gfx backends` dice cosa è disponibile.

## 0. Estrazione
Dal motore con l'opzione di dump del Remaster Layer (`remaster_dump=<cartella>`): fondali per scena + palette, ogni frame di sprite come
`.raw` (w, h, colore trasparente, palette, pixel) + `.png` di anteprima.
`rstool.py assets inventory <dump>` crea `analysis/assets.csv` (tipo, chiave, dimensioni,
scena, frequenza d'uso) per dare priorità ai frame più visti.

## 1. Fondali
Dettagli e misure: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/grafica.md`.
`rstool.py gfx bg <dump>/bg --out remaster/gfx/bg --scale 3 [--recipe analysis/style-recipes.json]`
1. Conversione dell'originale con **la stessa palette che usa il motore** (altrimenti il test
   "pixel uguale allo sfondo" del compositore fallisce).
2. **Scelta dell'upscaler su fogli numerati** (0 = originale, 1 = attuale, poi i candidati), con
   batterie separate per fondali e personaggi: il migliore per uno non lo è per l'altro.
   Nel progetto di riferimento: **APISR RRDB** per i fondali (linee nette, ~73 µs/pixel su CPU),
   **APISR GRL** per gli sprite; Real-ESRGAN anime 6B accettabile ma morbido; i modelli "Sharp"
   2x sfocati o cancellano i volti. Pesi caricati con `spandrel`.
3. Solo se la style bible lo chiede e c'è una GPU: img2img con LoRA di stile e ControlNet tile,
   denoise basso; poi **ricolorazione sulla palette originale** (`color_lock`).
4. 4x → 3x con LANCZOS (BOX per gli sprite), JPEG q90 **4:4:4** (il 4:2:0 sporca i bordi colorati).
5. Script ripartibile che salta ciò che è già fatto e tiene in cache le bande 16:9.
Controlli automatici (`rstool.py gfx check`): stessa composizione (SSIM sul ridotto ≥ 0.85),
nessuna deriva cromatica (ΔE medio ≤ 6), nessuna scritta inventata. Verifica sempre nel log del
motore che l'HD sia stato caricato: un'edizione con dimensioni diverse lo fa scartare in silenzio.

## 2. Sprite e animazioni
`rstool.py gfx sprites <dump>/spr --out remaster/gfx/spr --scale 3`
- **Coerenza prima di tutto.** Migliaia di fotogrammi non reggono la generazione AI fotogramma
  per fotogramma: solo trattamenti **deterministici** (stesso input → stesso output).
- Pipeline finale del progetto di riferimento: upscaler (APISR GRL) sul riquadro utile →
  **contorno smussato**: la sagoma è il livello 0,5 della maschera originale sfocata
  (σ = 0,65 px a 1x, lo stesso campo dell'alpha del motore); dove il bordo originale è scuro si
  ridipinge una fascia d'inchiostro spessa come il contorno originale, con antialiasing.
- Una resa "cinematografica" calcolata dalla sagoma (ombra cel-shading, luce di bordo) era stata
  approvata e poi **abbandonata**: creava ombre e macchie scure. Prima di cambiare modello,
  isola quale passo della pipeline causa il difetto.
- Nel JPEG riempi i colori fuori sagoma allargando quelli di bordo (box blur a raggi 2-16),
  altrimenti compaiono frange scure; l'alpha la ricostruisce il motore dalla sagoma originale.
- **Si decide guardando**: 3-4 personaggi affiancati per ogni variante; poi lo stesso valore per tutto.
- Sprite peggiorato dall'HD → toglilo dall'indice: il motore usa l'originale.
- Copertura: il dump vede solo i fotogrammi disegnati; ripeti `fuzz` su ogni parte finché i
  fotogrammi nuovi si azzerano.

## 3. Interfaccia, inventario, cursori
Come gli sprite (sono frame); i cursori a 2-3x con hotspot scalato.

## 4. Font e testi
`rstool.py font build <ttf> --name <font> --scale 3 --codepage cp850 --out remaster/fonts`
- scegli il TTF (licenza OFL) **confrontando i glifi con il font bitmap originale**
  (2-3 candidati affiancati);
- **preserva le stilizzazioni volute** dell'originale (alfabeti finti, maiuscolo, contorni,
  tratti tagliati intenzionali): genera l'atlante sostituendo i glifi con le forme dello stile;
- sottotitoli: un font più leggibile dello stesso stile, chiaro con contorno nero, in basso con
  fascia scura (posizione originale come opzione);
- includi tutti i glifi delle lingue scelte; prova anche con i font bitmap originali.

## 5. Framerate alto (opzionale, con conferma)
Il Layer interpola lo scorrimento senza asset nuovi. Per animazioni molto scattose
(camminate a 6-8 fotogrammi) si possono generare frame intermedi (`gfx/inbetween/`) con
interpolazione video (RIFE) sul livello fedele: proponilo su 2-3 animazioni di prova e
fallo approvare, perché può tradire il ritmo voluto dall'animatore.

## Consegna e revisione
Appena pronto il primo fondale: `rstool.py gfx compare <orig> <hd> --out review/<scena>.png` e manda
l'immagine affiancata all'utente. Ogni lotto di 20 fondali: galleria di revisione
(`rstool.py review compare <dump>/bg remaster/gfx/bg`) prima di proseguire.
