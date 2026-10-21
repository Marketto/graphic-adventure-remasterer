# graphic-adventure-remasterer

Suite agentica (plugin per Claude Code + app con Claude Agent SDK) per il remaster HD delle
avventure grafiche 2D uscite fino alla fine degli anni '90. Ti intervista, verifica il supporto
del motore in ScummVM o in altri interpreti open source, ricava lo stile del gioco, rifà
grafica, testi, audio e voci, e produce eseguibili e una patch distribuibile che richiede la
copia originale del giocatore. Un tasto (F8) passa in ogni momento dalla versione originale a
quella rimasterizzata.

Le regole e le tecniche vengono da un remaster completo usato come banco di prova; qui sono
riportate in forma generica in `references/conoscenza/`.

> Questo repository è **pubblico** e non contiene giochi, dati di gioco, riferimenti a opere
> protette né asset derivati. Ogni remaster vive in un repository **privato** a parte.
> `tools/ip_guard.py` lo verifica a ogni commit (vedi sotto).

## Come si usa
**In Claude Code** (consigliato: serve accesso a GPU/CPU, compilatori e ai file del gioco)
```
claude --plugin-dir /percorso/graphic-adventure-remasterer
> /remaster <titolo del gioco>
```
**App standalone** (stesso plugin, interfaccia a terminale)
```
cd app && pip install -r requirements.txt
python remaster_studio.py --project ~/remaster/mio-gioco "<titolo del gioco>"
```
Variabili: `ANTHROPIC_API_KEY` (o login del CLI), `ELEVENLABS_API_KEY` per il doppiaggio,
`FAL_KEY` per l'outpainting a pagamento, `COMFYUI_URL` se usi ComfyUI in locale.

## Il flusso
1. **Intervista**: titolo → compatibilità del motore → riuso del lavoro esistente → grafica
   (fondali, sprite, testi; 16:9 con tecniche locali, fal.ai solo se lo scegli; framerate) →
   lingue (verifica, traduzione) → audio → doppiaggio ElevenLabs (licenza) → manuale e aiuti →
   piattaforme e distribuzione → file di gioco dell'utente.
2. **Analisi**: style bible, inventario degli asset, piattaforma di riferimento e proporzione
   dei pixel (solo se il gioco era pensato per pixel non quadrati), classificazione delle scene
   per il 16:9, piano con stime di tempo e costi → conferma.
3. **Motore**: fork di ScummVM + Remaster Layer, gioco completabile, motore che accetta patch su
   testi, voci e immagini, tempi calibrati sull'originale nell'emulatore o nella VM della sua
   piattaforma (DOSBox, VM Windows d'epoca, Wine...), controlli fluidi, interfaccia nello stile
   del gioco, salvataggi, menu, manuale e aiuti in gioco.
4. **Asset**: grafica HD, bande 16:9 (fogli numerati da approvare), testi e traduzioni, audio
   (normalizzazione per gruppo e poi mix), voci (censimento, provini, preventivo, approvazione,
   verifica), manuale e aiuti.
5. **QA indipendente** e **rilascio**: build per Windows, Linux, macOS, Android, Web, pagina HTML
   unica per il telefono, patch e installer che verifica la copia del giocatore.

## Contenuto
| Cartella | Cosa |
|---|---|
| `skills/` | orchestratore + 10 skill (motore, style bible, grafica HD, 16:9, localizzazione, audio, doppiaggio, integrazione nel motore, manuale e aiuti, rilascio) |
| `agents/` | 10 subagenti specializzati, tra cui un QA indipendente e un revisore |
| `commands/remaster.md` | comando `/remaster` |
| `tools/rstool.py` | pipeline a riga di comando: progetto (con tetto e registro delle spese), rilevamento, emulatore di riferimento, misura dei tempi, fluidità dei controlli, chiavi e copertura degli asset, pacchetto canary, stile, grafica, font, proporzione dei pixel, 16:9 (LaMa, quilting, ricette, controlli, fal.ai opzionale), gallerie di revisione e regressione visiva, testi, audio (gruppi e mix, restauro del parlato originale), voci (trascrizione locale), tema GUI, aiuti, manuale, ricette (esempio in `references/recipe.example.json`), rilascio e peso del pacchetto |
| `tools/ip_guard.py` | controllo che il repository resti privo di contenuti e riferimenti a giochi |
| `engine/scummvm-remaster-layer/` | patch per ScummVM (`engines/remaster/`) + guida di integrazione |
| `ci/` | workflow GitHub Actions multipiattaforma, librerie Android, build locale |
| `app/` | app standalone con Claude Agent SDK |
| `references/` | contratto degli asset (RAC v1), distribuzione lecita, modello di richiesta di permesso, `conoscenza/` (tecniche del banco di prova) |

## Conoscenza dal banco di prova
| Nota | Contenuto |
|---|---|
| `references/conoscenza/motore-e-test.md` | motore e contenuto separati, renderer HD, sprite via buffer di id, testo HD, 16:9 con sprite e zone nelle bande, scorrimento fluido, tempi misurati sull'emulatore della piattaforma (DOSBox nel banco di prova), input moderno e fluidità dei controlli, salvataggi con miniature, aiuti in gioco, driver di test e casi di regressione, pagina web che si aggiorna da sola, versioni |
| `references/conoscenza/grafica.md` | confronto degli upscaler (APISR, Real-ESRGAN...), pipeline dei fondali, bande 16:9 (LaMa a 1x, quilting, FLUX Fill via fal.ai, ricette locali), controlli e costi, insegne e firme inventate, sprite e font |
| `references/conoscenza/voci-testi-audio-flusso.md` | doppiaggio ElevenLabs (chi parla, cast, regia, testo detto, pause, crediti, lotti in CI, verifica), correzione dei testi, normalizzazione per gruppo e mix, flusso con agenti (router, revisore, hook, PR, rilasci, spese) |

## Requisiti sul tuo PC
Python 3.10+ con `numpy` e `Pillow`; `ffmpeg`; `git` e toolchain C++ per ScummVM.
Opzionali: `torch` + `spandrel` per gli upscaler (APISR, Real-ESRGAN) e LaMa su CPU,
`fluidsynth` + soundfont, munt (MT-32) con le tue ROM, una GPU con ComfyUI, chiavi ElevenLabs e
fal.ai (solo se scegli l'outpainting a pagamento), l'emulatore o la VM della piattaforma
originale (DOSBox, 86Box/PCem, QEMU, Wine, WinUAE/FS-UAE, Hatari...) con ROM e sistemi tuoi,
Xvfb + `xdotool` per le misure automatiche, `faster-whisper` per la trascrizione locale delle
voci, DeepFilterNet per il restauro del parlato originale.

## Stato delle verifiche
- `tools/`: test automatici su dati sintetici (`python -m pytest tools/tests`), tutti verdi; un
  test controlla anche che skill, agenti e documenti citino solo comandi, opzioni e file esistenti.
- Remaster Layer: si applica su ScummVM `5d13ee16`, compila, collega, 411/411 test di `make test`
  verdi (5 nuovi: chiavi, composizione, 16:9/mouse, scorrimento sub-pixel, fondali localizzati).
- Build Linux in modalità release verificata; Windows, macOS, Web e Android da provare al primo
  giro di CI.
- Non ancora provati con questo codice su un gioco vero: generazione grafica, ElevenLabs via API,
  fal.ai via API (il client è provato solo con un servizio finto), classificazione 16:9 (le
  soglie vanno tarate sul primo gioco).
- Tema GUI: generato dal tema di ScummVM dello stesso commit e caricato nel ScummVM compilato
  sotto Xvfb, con colori, font e logo sostituiti (schermata verificata).
- Da implementare nel Layer comune: la scala verticale per i giochi pensati per pixel non
  quadrati (oggi `pixelAspect` cambia solo la geometria 16:9) e i comandi `inputlog`,
  `mousepath`, `keyhold` del driver di test, che vanno scritti nel motore di ogni gioco. Le tecniche in
  `references/conoscenza/` invece sono state usate in produzione sul banco di prova.

## Repository pubblico: regole
- Nessun nome di giochi, personaggi, luoghi, sviluppatori o motori proprietari; nessun testo,
  immagine, suono o dato di gioco, neanche come esempio nei test. Strumenti open source citabili.
- Prima di ogni commit: `python3 tools/ip_guard.py --staged` (installa l'hook con
  `git config core.hooksPath .githooks`). La lista dei termini vietati è salvata solo come hash
  SHA-256 (`.ipguard/denylist.sha256`); nuovi termini: `python3 tools/ip_guard.py --add "termine"`.
  In locale si può aggiungere `--private-texts <testi del gioco>` per trovare frasi copiate.
- Lo stesso controllo gira in CI (`.github/workflows/ip-guard.yml`).

## Regole da sapere
- I file del gioco originale non si distribuiscono mai; l'installer verifica la copia del giocatore.
- Asset HD, traduzioni e voci sono opere derivate: per pubblicarli serve il permesso del titolare
  dei diritti, altrimenti si usa la modalità `recipe` (vedi `references/legal-distribution.md`).
- ScummVM vieta la co-autorialità AI e gli asset generati con AI nel progetto ufficiale: il fork usa
  `Assisted-by:` e nulla viene proposto upstream senza la tua revisione.

## Licenza
GPL-3.0-or-later (vedi `LICENSE`), come ScummVM a cui si integra il Remaster Layer.
