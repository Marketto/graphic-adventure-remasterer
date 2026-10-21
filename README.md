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
   (fondali, sprite, testi; 16:9; framerate) → lingue (verifica, traduzione) → audio →
   doppiaggio ElevenLabs (licenza) → piattaforme e distribuzione → file di gioco dell'utente.
2. **Analisi**: style bible, inventario degli asset, classificazione delle scene per il 16:9,
   piano con stime di tempo e costi → conferma.
3. **Motore**: fork di ScummVM + Remaster Layer, gioco completabile, tempi calibrati
   sull'originale in DOSBox, salvataggi, menu, aiuti in gioco.
4. **Asset**: grafica HD, bande 16:9 (fogli numerati da approvare), testi e traduzioni, audio,
   voci (censimento, provini, preventivo, approvazione, verifica).
5. **QA indipendente** e **rilascio**: build per Windows, Linux, macOS, Android, Web, pagina HTML
   unica per il telefono, patch e installer che verifica la copia del giocatore.

## Contenuto
| Cartella | Cosa |
|---|---|
| `skills/` | orchestratore + 9 skill (motore, style bible, grafica HD, 16:9, localizzazione, audio, doppiaggio, integrazione nel motore, rilascio) |
| `agents/` | 9 subagenti specializzati, tra cui un QA indipendente |
| `commands/remaster.md` | comando `/remaster` |
| `tools/rstool.py` | pipeline a riga di comando: progetto, rilevamento, chiavi degli asset, stile, grafica, font, 16:9, gallerie di revisione, testi, audio, voci, ricette, rilascio |
| `tools/ip_guard.py` | controllo che il repository resti privo di contenuti e riferimenti a giochi |
| `engine/scummvm-remaster-layer/` | patch per ScummVM (`engines/remaster/`) + guida di integrazione |
| `ci/` | workflow GitHub Actions multipiattaforma, librerie Android, build locale |
| `app/` | app standalone con Claude Agent SDK |
| `references/` | contratto degli asset (RAC v1), distribuzione lecita, modello di richiesta di permesso, `conoscenza/` (tecniche del banco di prova) |

## Conoscenza dal banco di prova
| Nota | Contenuto |
|---|---|
| `references/conoscenza/motore-e-test.md` | motore e contenuto separati, renderer HD, sprite via buffer di id, testo HD, 16:9 con sprite e zone nelle bande, scorrimento fluido, tempi misurati in DOSBox, input moderno, salvataggi con miniature, aiuti in gioco, driver di test e casi di regressione, pagina web che si aggiorna da sola, versioni |
| `references/conoscenza/grafica.md` | confronto degli upscaler (APISR, Real-ESRGAN...), pipeline dei fondali, bande 16:9 (LaMa a 1x, quilting, FLUX Fill via fal.ai, ricette locali), controlli e costi, insegne e firme inventate, sprite e font |
| `references/conoscenza/voci-testi-audio-flusso.md` | doppiaggio ElevenLabs (chi parla, cast, regia, testo detto, pause, crediti, lotti in CI, verifica), correzione dei testi, livelli audio, flusso con agenti (router, revisore, hook, PR, rilasci, spese) |

## Requisiti sul tuo PC
Python 3.10+ con `numpy` e `Pillow`; `ffmpeg`; `git` e toolchain C++ per ScummVM.
Opzionali: `torch` + `spandrel` per gli upscaler (APISR, Real-ESRGAN) e LaMa su CPU,
`fluidsynth` + soundfont, munt (MT-32) con le tue ROM, una GPU con ComfyUI, chiavi ElevenLabs e fal.ai.

## Stato delle verifiche
- `tools/`: test automatici su dati sintetici (`python -m pytest tools/tests`), tutti verdi.
- Remaster Layer: si applica su ScummVM `5d13ee16`, compila, collega, 410/410 test di `make test`
  verdi (4 nuovi: chiavi, composizione, 16:9/mouse, scorrimento sub-pixel).
- Build Linux in modalità release verificata; Windows, macOS, Web e Android da provare al primo
  giro di CI.
- Non ancora provati con questo codice su un gioco vero: generazione grafica, ElevenLabs via API,
  classificazione 16:9 (le soglie vanno tarate sul primo gioco). Le tecniche in
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
