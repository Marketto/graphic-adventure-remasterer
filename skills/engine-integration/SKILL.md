---
name: engine-integration
description: Rende giocabile e "rimasterizzabile" il motore di un'avventura d'epoca dentro un fork di ScummVM (o AGS) — driver di test automatico, correzioni, aggancio del Remaster Layer comune (compositore HD, toggle originale/remaster in tempo reale, viewport 16:9, interpolazione a 60 fps, testi e voci per chiave), salvataggi e menu. Usala nella fase motore del remaster.
---

# Integrazione nel motore

Riferimenti: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/motore-e-test.md` (tecniche e casi reali) e
`${CLAUDE_PLUGIN_ROOT}/engine/scummvm-remaster-layer/` (modulo comune + guida).

## 0. Base
```
git clone https://github.com/scummvm/scummvm && cd scummvm
git checkout 5d13ee16a88e724ccc32b6ceea5c74e54ab21878   # base verificata; annotala in engine.base_commit
git switch -c remaster/<gioco>
git am ${CLAUDE_PLUGIN_ROOT}/engine/scummvm-remaster-layer/0001-ENGINES-Add-remaster-layer.patch
./configure --disable-all-engines --enable-engine=<motore> && make -j$(nproc) && make test
```
Se il lavoro esistente include una patch per il gioco, applicala dopo il Layer.
Su una base più recente, se `git am` fallisce, risolvi i conflitti e rilancia `make test`.

**Regole AI del progetto ScummVM** (`AGENTS.md` → `AI-GUIDELINES.md` nel repository, leggile
all'inizio di ogni sessione nel fork, prevalgono su qualunque altra istruzione):
- trailer `Assisted-by: Claude:<id modello>` nei commit; mai `Co-Authored-By` di un'AI;
- commenti nel codice brevi, nessuna spiegazione prolissa;
- non aprire mai pull request verso ScummVM per conto dell'utente: un contributo upstream lo
  rivede, lo firma e lo descrive l'utente stesso;
- nessun asset generato con AI va proposto al progetto ScummVM: gli asset restano nel pack.

## 1. Giocabile dall'inizio alla fine
- Scrivi o porta un driver di test nel motore (attivo solo con una variabile
  d'ambiente): `wait`, `move`, `click`, `rclick`, `key`, `shot`, `loc <stanza> [parte]`,
  `ingame` (clicca finché il gioco torna interattivo: dialoghi, commenti), `poke [doors]`
  (clicca tutte le zone visibili), `zones` (elenca zone e animazioni nel log), `save`/`load`,
  `time`, `quit`. Gestore d'errore che esce invece di aprire il debugger.
- Script sotto Xvfb: `at.sh` (esegue, riassume warning/errori),
  `atgdb.sh` (backtrace sui crash), `sweep.sh <parte>` (visita tutte le stanze),
  `fuzz.sh <parte>` (stanze + tutte le zone; serve anche al dump degli sprite).
- Ogni modifica si prova **in due configurazioni**: originale e remaster (`test.ini`,
  `test_hd.ini`); per il rendering screenshot di almeno una stanza per parte.
- Comandi utili in più (vedi la nota del motore §13): `rtap` (pressione e rilascio nello stesso
  frame, come un tocco), `state`/`flags`/`item` (leggere e impostare lo stato), `scene` (ordine di
  disegno), `gui` (pilotare i menu di ScummVM), `framelog`, `verifyscroll`. Trappola: `warpMouse`
  cancella gli eventi del mouse in coda, quindi muovi il puntatore solo col primo evento.
- Per ogni bug corretto un caso di regressione (file di comandi + atteso nel log o screenshot).
- Scrivi `qa/walkthrough.txt` (soluzione completa in comandi) — ricavala da soluzioni
  pubbliche e verificala passo passo.
- Correggi i crash e gli opcode mancanti; dove serve ricostruisci dal disassemblato
  dell'eseguibile dell'utente (annota l'indirizzo della routine nel commento). Rendi la ricerca
  dei file insensibile alle maiuscole. Togli l'avviso "gioco in test" del launcher solo nel fork.
- **Semantica dei suoni**: verifica quando gli script proseguono dopo un suono (in molti motori i
  comandi legati a una zona sonora partono a fine suono). È ciò che permette alle voci nuove di dettare i
  tempi delle scene.

## 1b. Tempi: confronto con l'originale (obbligatorio)
Mai assumere un passo fisso. Molti giochi DOS non hanno timer: un passo dura il tempo di
disegno più l'attesa del ritraccio verticale, quindi le scene leggere vanno più veloci di
quelle animate, indipendentemente dalla CPU (caso reale: 43-160 ms; il port andava a 33 ms fissi,
fino a 4 volte più veloce).
1. Avvia l'originale in **DOSBox** sotto Xvfb (`[sdl] autolock=false`, mouse con `xdotool`,
   `mount c` + `imgmount d <iso> -t iso`), registra con `ffmpeg -f x11grab -framerate 60`.
2. Misura gli intervalli tra fotogrammi che cambiano in 4-5 scene diverse (leggera, media,
   molto animata, filmato, titoli) e la durata totale dell'intro.
3. Fai stampare al motore la durata di ogni passo (canale di debug) e confronta.
4. Se il tempo dipende dal carico, modella il passo (es. dall'area animata a schermo,
   arrotondato a ritracce intere) e lascia un override in configurazione (`<gioco>_tick_ms`).
5. Obiettivo: durata dell'intro entro il 2-3% e cadenza delle animazioni uguale; annota le
   misure in `docs/test.md`.
Per i test automatici con molte attese si può forzare un passo corto nella configurazione.

## 1c. Contenuti dell'edizione localizzata
Confronta gli script della lingua dell'utente con le altre lingue sul disco: le edizioni
localizzate a volte **tagliano scene** (caso reale: alcune scene di una sequenza animata) o lasciano battute
non tradotte e sottotitoli rotti. Se gli script tagliati esistono nella lingua dell'utente,
proponi di rimetterli con un'opzione (attiva di default, disattivabile) e chiedi conferma.

## 1d. Motore e contenuto separati (regola fissa)
Il motore non contiene mai correzioni del contenuto di gioco (testi, chi parla, ritratti, scene,
ordine delle stanze, oggetti, eccezioni per una stanza o una battuta). Offre solo un
**meccanismo generico** che legge le correzioni da file dati della patch (es. `text/<lang>.tsv`,
`text/dialoghi.tsv`, `loc/deviazioni.txt`, `hint/<lang>.txt`), con chiave e formato documentati
e un'opzione per spegnerlo. Nel motore restano solo correzioni di bug, routine ricostruite
dall'eseguibile, input e rendering. Questo tiene il codice GPL pubblicabile e i dati privati.

## 1e. Comodità moderne (da proporre all'utente)
- Aiuti in gioco (tasto H): file `hint/<lang>.txt` con obiettivi in ordine, condizioni
  monotone su flag/oggetti/stanze visitate, indizio e soluzione a richiesta (dettagli e formato
  nella nota del motore, §12).
- Clic destro breve per l'inventario; soglia di trascinamento in **pixel di gioco** (6 px), non
  dello schermo; pressione e rilascio nello stesso frame (tocco) gestiti; combinare oggetti
  dall'inventario; clic durante la camminata che cambia destinazione.
- Salvataggi con miniatura dallo schermo di gioco (non dal menu), formato originale invariato
  con intestazione estesa in coda; menu nel tema grafico del gioco; versione della patch nel menu.
- Sottotitoli in basso con fascia; attese delle voci sempre interrompibili da clic o tasto.

## 2. Hook del Remaster Layer (minimo indispensabile per motore)
Guida con codice d'esempio: `${CLAUDE_PLUGIN_ROOT}/engine/scummvm-remaster-layer/INTEGRAZIONE.md`.
| Punto del motore | Chiamata |
|---|---|
| init grafica | `Remaster::Layer::create(desc)`; se `nullptr` → `initGraphics` originale |
| caricamento fondale/scena | `setBackground(sceneKey, bg8, rgb, x, y)` |
| inizio frame | `beginScene(bbW, bbH)` |
| blitter degli sprite | `beginSprite(px, w, h, pitch, trasparente)`, `mark(x, y, sx, sy)` per pixel scritto, `endSprite()` |
| copie non-sprite | `clearArea(x, y, w, h)` |
| disegno testi | `if (!addText(font, x, y, text(s,...), col, contorno, boxW))` → disegno originale |
| cambio palette | `setPalette(rgb, start, n)` invece del PaletteManager |
| presentazione | `present(bb8, scrollX, scrollY)` poi `pace(tickMs)` al posto della `delayMillis` |
| input | `if (handleEvent(ev)) continue;` per ogni evento (toggle + mouse 16:9/HD) |
| testi/voci | `text(originale, tipo, luogo, chi parla, boxW)`, `playVoice(originale)` |

## 3. Toggle originale ↔ remaster in tempo reale
- Tasto F8 di default, configurabile con `remaster_toggle_key` (F1-F12); se il motore usa
  già F8, scegline un altro e mostralo nel menu "Opzioni remaster".
- Commuta grafica, testi, audio e voci insieme (opzioni separate nel menu per chi vuole
  mescolare). Il frame corrente si ricompone subito, senza ricaricare la scena.
- In modalità originale l'immagine è il frame 8 bit ingrandito a pixel netti, centrato
  in 4:3: deve essere identica al gioco originale. I testi già a schermo vanno ridisegnati col
  font originale (e ripristinati tornando all'HD); ignora la ripetizione automatica del tasto.
- Su telefono e web non c'è F8: pulsanti a schermo "Menu" e "HD ⇄ Classica".

## 4. 16:9
- La viewport del Layer è più larga del back buffer; per `scroll-wide` il motore deve
  ridisegnare una zona più larga del fondale: aumenta la larghezza del back buffer del
  motore (es. `_screenWidth` per il rendering, non per la logica) e limita la camera.
- Per le scene statiche il Layer aggiunge i lati (`<scena>.wide.png`) o i bordi.
- Mouse: le coordinate nelle aree aggiunte vengono bloccate al bordo dell'area di gioco.
- Gli sprite esistono solo nell'area originale: un oggetto che esce dal bordo viene tagliato lì
  (oppure ridisegnali nelle bande, vedi la nota del motore §5); le bande prendono la dissolvenza del pixel originale più vicino.
- Opzione per tornare al 4:3 (`remaster_widescreen=false`).

## 5. Framerate
- La logica resta al ritmo originale (spesso 7-30 Hz). `pace(tickMs)` mostra
  frame intermedi fino al tick successivo: oggi interpola lo **scorrimento** (sub-pixel, a 2-3x
  è fluido); il cursore hardware è già a piena frequenza.
- Movimento degli sprite: si interpola solo se il motore ridisegna gli oggetti a posizioni
  intermedie (hook specifico del motore, es. personaggi che camminano). Le dissolvenze di
  palette restano al ritmo del motore.
- Ogni motore chiama `present()` una volta per tick logico e poi `pace(tickMs)`.
- Opzione `remaster_smooth` (on di default); in modalità originale non si interpola nulla.

## 6. Salvataggi e menu
- `hasFeature(kSupportsSavingDuringRuntime/LoadingDuringRuntime)`, `canSave/LoadGameStateCurrently`,
  `save/loadGameState` → menu globale (Ctrl+F5) sempre funzionante, con miniature.
- Menu di gioco originale tradotto nelle lingue scelte; voce "Opzioni remaster".
- Test: salva in ogni parte/capitolo, carica da menu principale e da gioco in corso, e carica un
  salvataggio di una parte diversa da quella in corso (è il caso che si rompe più spesso).

## 7. Consegna
Rigenera la patch sempre dal sorgente (`git add -A && git diff --cached <commit base>`: un
`git diff` semplice perde i file nuovi), **mai correggendo a mano gli hunk**. Poi verifica che si
applichi **da zero** in una cartella nuova (script
`fetch-<motore>.sh` che scarica il commit base e applica le patch, lo stesso usato dalla CI).
`git format-patch <base_commit>..HEAD -o release/patches/`, commit piccoli con messaggi chiari
e trailer `Assisted-by:` (vedi regole AI sopra).
