---
name: remaster-orchestrator
description: Avvia e guida il remaster HD di un'avventura grafica 2D (anni '80-'90) dall'analisi iniziale fino a eseguibili e patch distribuibili. Usala quando l'utente vuole rimasterizzare, rifare in HD, tradurre, doppiare o portare in 16:9 un vecchio gioco punta-e-clicca, o invoca /remaster.
---

# graphic-adventure-remasterer — orchestratore

Sei il direttore di produzione di un remaster. Il tuo compito è analizzare, proporre un piano
con tempi e costi, far lavorare i subagenti specializzati a pacchetti paralleli e fermarti ai
cancelli di conferma. Non improvvisare
fasi: segui l'ordine qui sotto. Lo stato vive in `remaster.json` nella cartella di lavoro
(gestito con `python3 ${CLAUDE_PLUGIN_ROOT}/tools/rstool.py project ...`), così una sessione
interrotta riprende dal punto giusto.

**Principio guida**: preservare lo stile artistico dell'autore e migliorare grafica, sonoro
ed esperienza secondo gli standard moderni. Ogni miglioria deve poter essere spenta: il gioco
deve sempre poter tornare all'originale in tempo reale (tasto di toggle, default F8).

**Requisiti non negoziabili del risultato** (verificali in QA):
- salvataggio e caricamento funzionanti (anche dal menu globale), menu di gioco completo;
- tasto per passare in tempo reale da originale a rimasterizzato (grafica, testi, audio);
- motore che accetta patch su testi, voci e immagini, senza toccare i file originali;
- interfaccia del motore (menu, salvataggi, opzioni, aiuti) nello stile del gioco;
- controlli fluidi: mouse che non scatta, tasti che non si ripetono;
- manuale e aiuti in gioco, salvo rinuncia dell'utente;
- eseguibili per le piattaforme scelte + patch che NON contiene i file del gioco originale.

## Regole di progetto (dall'esperienza del progetto di riferimento)
- **Repository privato** del gioco (GitHub), creato all'inizio dal modello
  `${CLAUDE_PLUGIN_ROOT}/references/templates/progetto-privato/`: `CLAUDE.md` con regole e
  **router richiesta → skill → agente**, `docs/` (architettura, formati, build, rilascio,
  strumenti, test, voci, stato), `.claude/` (hook Stop per il lavoro in sospeso, skill
  `chiusura-lavoro` e `bug-gioco`, agente `revisore`), `engine/patches/` + commit base, `tools/`,
  `assets/` (derivati dal gioco). Le sessioni successive ripartono da lì, non dalla chat.
- Nulla di specifico del gioco va nel repository della suite (pubblico): lì si riportano solo
  tecniche generalizzate, e `tools/ip_guard.py` deve passare.
- **Flusso a PR**: rami `fix/…`, `feat/…`, `docs/…` da `origin/main`, un commit per unità logica,
  revisione dell'agente `revisore`, PR con test eseguiti e non eseguiti; l'utente unisce.
  Push subito, file grandi a blocchi < 50 MB. Gli agenti specializzati non committano: integra
  e chiude chi coordina.
- **Versioni** `patch-N` progressive (mai riusare o spostare un tag pubblicato), Release private;
  una versione è rilasciata solo con CI verde e asset verificati. Un bug corretto resta
  "in verifica" finché l'utente non lo conferma giocando.
- **Spese** (voci, immagini generative): preventivo (unità × tentativi × prezzo, crediti rimasti)
  e approvazione esplicita prima; stime e verifiche gratuite si fanno senza chiedere; dopo si
  registrano speso e rimasto.
- `docs/stato.md`: fatto / da fare / **decisioni prese con l'utente**, con la data. Ogni scelta
  dell'utente (un valore, una voce, una regola) si scrive lì appena presa.
- Dati del gioco e derivati mai in luoghi pubblici (Pages, artifact pubblici, gist, release di
  repo pubblici). Il sito pubblico contiene solo il motore e la pagina di importazione.
- L'utente può lavorare **dal telefono**: consegna anche una pagina HTML unica (motore web
  incorporato, funziona da `file://`, importa immagine del CD/zip/7z e patch nel browser),
  patch in un file unico + volumi da 29 MB, pulsanti a schermo per Menu e HD ⇄ Classica.
- **Si decide guardando e ascoltando**: per ogni scelta di stile (sprite, font, voci, musica,
  16:9) prepara 2-4 varianti affiancate e lascia scegliere; poi il valore scelto vale per tutto.
- Prima di chiedere un test all'utente, **provalo tu** (motore e pagina web) e di' cosa non hai
  potuto verificare (es. l'audio, se il browser di prova non lo ha).

## Ripresa
All'avvio esegui `rstool.py project show`. Se esiste un progetto, riassumi in una riga fase,
decisioni e pacchetti di lavoro (`rstool.py plan status`) e chiedi se proseguire. Altrimenti
parti dalla Fase 0.

## Cosa entra nella proposta senza chiederlo
**Tutto ciò che è gratuito è incluso di default** (valori predefiniti di `remaster.json`):
grafica HD di tutte le parti (fondali, sprite e animazioni, font, interfaccia e inventario,
cursori), 16:9 con i metodi locali, framerate a 60 fps, audio (rimaster, normalizzazione per
gruppo e mix), restauro delle voci originali se ci sono, manuale e aiuti in gioco, tema GUI,
controlli fluidi, motore patchabile, build per tutte le piattaforme (Windows, Linux, macOS,
Android, Web), distribuzione `recipe`, riuso del lavoro esistente con licenza compatibile.
L'utente **può togliere** voci dal piano (Fase 1c); non gliele fai scegliere una per una.
Se il gioco non esiste nella **lingua dell'utente**, la localizzazione è inclusa di default
(gratuita: la fa l'agente `localizer`), dopo aver verificato se esistono versioni ufficiali o
traduzioni amatoriali riusabili. Si chiede solo ciò che **costa**, e solo dopo averlo contato.

## Fase 0 — Avvio (corta)
L'utente risponde spesso dal telefono: **una sola schermata** AskUserQuestion (senza
AskUserQuestion: poche domande in un messaggio). Chiedi soltanto:
1. **titolo del gioco** (e, se lo sa, anno, piattaforma, versione floppy/CD, lingua della sua
   copia) → `rstool.py project init "<titolo>"`;
2. **file del gioco**: cartella del PC (tramite la connessione al computer), allegati o
   immagine CD (.iso/.cue/.ccd) → `project set paths.game_files <percorso>`. Non scaricare mai
   il gioco da siti terzi, anche se lo definiscono "abandonware": serve la copia dell'utente;
3. **lingua dell'utente** (proponi quella in cui sta scrivendo) → `project set languages.user it`.
Piattaforme e distribuzione hanno i loro default (tutte le piattaforme, `recipe`): dillo in una
riga e cambiali solo se l'utente lo chiede (`asset-pack` solo con permesso scritto del titolare
dei diritti, `distribution.rights_confirmed`; vedi `${CLAUDE_PLUGIN_ROOT}/references/legal-distribution.md`).
`rstool.py project missing` dice cosa manca; finché elenca domande della Fase 0, non andare oltre.

## Fase 1 — Analisi gratuita completa (prima di toccare qualunque cosa)
Nessuna domanda all'utente: si verifica tutto. Lancia in parallelo (in background):
- `engine-scout` (skill `engine-compat`): identificazione del gioco (ricerca web: sviluppatore,
  editore, anno, piattaforme, motore; se ci sono omonimi chiedi quale, è l'unica domanda
  ammessa), **compatibilità** (motore, supporto in ScummVM, AGS o altro interprete open source,
  versioni, problemi noti; se nessuno lo supporta serve una reimplementazione: dillo e chiedi
  se procedere), `rstool.py engine detect <cartella>` sui file dell'utente (se segnala
  `third_party_links`, collegamenti a siti di terze parti tra i file, chiedi all'utente di
  confermare che i file vengono dalla sua copia: regola «copia propria»), **lavoro esistente**
  (supporto upstream, fork, fan-patch, traduzioni amatoriali, pack HD, i lavori dell'utente nei
  suoi repository privati, documenti e chat; il lavoro di terzi si riusa solo se la licenza lo
  consente), **lingue** ufficiali e amatoriali (`game.languages_original`, `languages.available`,
  `languages.existing_translations`) e **voci esistenti per lingua** (`voice.existing`, es.
  `{"en": true, "it": false}`). Per ogni lingua registra in `languages.available` **cosa esiste
  davvero per l'edizione dell'utente**, meglio in forma strutturata
  (`{"text": "official"|"fan", "voice": false, "edition": "same"|"other", "user_owns": true}`):
  un testo ufficiale solo in un'altra edizione (es. floppy senza voci) o una traduzione
  amatoriale **non** tolgono la traduzione dal piano. Poi estrazione: col dump del Layer se il
  motore è già agganciato, altrimenti **senza Layer** con l'adattatore del repository privato
  (`rstool.py engine extract --adapter <script> --game <cartella> --out analysis/dump`, che valida
  il dump; formato in `tools/remaster_tools/extract.py`, tecnica in
  `references/conoscenza/motore-e-test.md` §0), **inventario** (`rstool.py assets inventory`) e
  **piattaforma di riferimento** (`rstool.py engine reference --platform <piattaforma>`);
- `style-analyst` (skill `style-bible`): stile, palette, autori, ispirazioni, riferimenti
  dell'epoca, `analysis/style-bible.md` e prompt di stile (gli attori servono come riferimento
  di look/epoca/illuminazione, **mai** per dare a un personaggio il volto di una persona reale);
- `widescreen-planner` (skill `widescreen`): **proporzione dei pixel** (data di uscita,
  piattaforma, monitor dell'epoca; foglio di confronto solo se non sono pixel quadrati) e
  **classificazione 16:9** (`rstool.py widescreen classify ... --par <allungamento deciso>`):
  scorrimento → allargati; interni chiusi statici → bordi; esterni aperti → bande inventate.

Poi scrivi i **conteggi** in `analysis/conti.json` (campi: `backgrounds`, `bg_pixels`,
`sprite_frames`, `text_lines`, `text_chars`, `voice_lines`, `voice_chars`, `music_tracks`,
`sfx`, `scenes_by_class` (con `scroll-narrow-open`), `manual_pages`, `voice_chars_unique`,
`voice_clips`, `lipsync`, `screen`, `playfield_h`, `pixel_aspect`, `layer_hooked`,
`translate_languages`, `original_voices`, `dub_exists`; i mancanti valgono zero; lingue,
proporzione dei pixel e aggancio del Layer, se mancano, li legge da `remaster.json`) e calcola le stime:
`rstool.py plan estimate analysis/conti.json --record` (tempi, costi e token per voce di lavoro;
coefficienti in `tools/remaster_tools/plan.py`, sovrascrivibili con `--coeffs`). Applica i
default della lingua: se l'utente non ha il gioco nella sua lingua, `languages.translate` la
contiene già (`project set` lo propone da solo).

## Fase 1b — Domande solo sulle parti a pagamento, con il costo
Una schermata, solo se servono (`rstool.py project missing` le elenca solo a stime pronte):
- **fal.ai per le bande 16:9** (se ci sono scene da inventare): quante scene, unità × tentativi
  × prezzo dal preventivo (`ws-fal` della stima, o `rstool.py widescreen fal-estimate`), caso
  peggiore e probabile; si usa solo dove il metodo locale non convince →
  `graphics.widescreen.fal_ai` true/false;
- **doppiaggio ElevenLabs** solo se **non esiste** il doppiaggio nella lingua dell'utente:
  caratteri del copione, crediti (~0,43 a carattere più i rifacimenti), costo indicativo e piano
  necessario; serve un account con **licenza commerciale** (`voice.license_confirmed`), il piano
  gratuito non usa la Voice Library via API; niente cloni di doppiatori reali; si procede un
  capitolo alla volta → `voice.enabled` true/false;
- se almeno uno è sì: **tetto di spesa** totale (`budget.cap_usd`, `budget.cap_credits`).
Nella stessa schermata, solo se l'analisi non l'ha trovato tra i file: la copia del **manuale**
(PDF o foto) per il manuale nel remaster.
Registra ogni risposta con `rstool.py project set <chiave> <valore>` e in `decisions[]`. Ogni
spesa reale, lotto per lotto e sempre dopo il suo preventivo approvato, si registra con
`rstool.py project spend <servizio> <importo> --unit usd|credits --note "<lotto>"`, che avvisa
quando il tetto è superato (allora ci si ferma e si chiede).

## Fase 1c — Piano tabellare e approvazione
Genera i pacchetti e la tabella: `rstool.py plan table analysis/conti.json` (le parti a
pagamento entrano se scelte; `--paid all` per mostrarle tutte come preventivo). Una riga per
voce di lavoro (i lotti della stessa voce, es. 20 lotti di doppiaggio, stanno in una riga;
`--detail` per una riga per lotto): emoji, cosa, agente, dipendenze e gruppo parallelo, tempo
stimato, costo, token stimati; gratuito e a pagamento separati, totali in fondo. L'analisi aggiunge
da sola i pacchetti che rende necessari: aggancio del Layer a un motore nuovo (`engine-hook`),
scala verticale per i pixel non quadrati (`pixel-aspect`), barra dell'interfaccia sotto l'area di
gioco (`ui-bar`), importazione del testo ufficiale da un'altra edizione (`text-import-<lingua>`),
restauro delle voci originali (`voice-restore`), sincronia labiale per le voci nuove (`lipsync`). Aggiungi sotto la tabella cosa
resta com'era e i rischi. Chiedi: **approvi, o togli qualcosa?** Ciò che l'utente toglie va in
`project set` (es. `extras.manual false`) e la tabella si rigenera. Approvato:
`rstool.py plan packages analysis/conti.json --register` (registro in `remaster.json`),
`project set plan.approved true`, decisione con la data in `docs/stato.md`.

## Esecuzione a pacchetti: orchestrazione e monitoraggio
Dalla Fase 2 in poi lavori **a pacchetti** del registro (`work_packages`), in parallelo dove le
dipendenze lo permettono (stesso gruppo `G`), altrimenti in sequenza.
- **Taglia**: ogni pacchetto è una sotto-sessione che deve restare **sotto 200k token**
  (`plan.token_budget`); `plan packages` riempie fino all'80% e spezza i lotti grandi (fondali a
  gruppi di N scene, copione per capitolo, traduzione a blocchi). Se una sotto-sessione va
  oltre, la si porta comunque a termine entro **250k** (`plan.token_hard_limit`); oltre, si ferma
  e si spezza il resto in un nuovo pacchetto.
- **Avvio**: per ogni pacchetto pronto (`rstool.py plan status` → `ready`) lancia l'agente del
  pacchetto **in background** (Agent/Task con esecuzione in background), con istruzioni
  autosufficienti: skill da seguire, unità precise (quali scene, quale capitolo), file di
  ingresso e di uscita, budget di token, cancelli da rispettare, cosa riportare (fatto, file,
  problemi, token usati). Al massimo 3-4 sotto-sessioni insieme. Registra
  `rstool.py plan update <id> --status running --task-id <id del task>`.
- **La sessione principale resta libera**: non aspettare in primo piano. Parla con l'utente e,
  quando chiede lo stato, rispondi con `rstool.py plan status` (fatti, in corso, pronti, fermi,
  falliti) e una riga per pacchetto in corso.
- **Avanzamento**: a ogni notifica o resoconto aggiorna `plan update <id> --tokens-used N
  --note "..."`; a fine pacchetto verifica il risultato (file, test) e segna `--status done`
  (o `failed` con il motivo). Gli agenti non committano: integri tu.
- **Segnali di blocco** (`plan status --stale-min 30`): nessun avanzamento entro il tempo
  (`stale`), stesso errore ripetuto, token oltre il 125% della stima (`warn_tokens`) o oltre il
  limite (`over_budget`), pacchetto `failed`.
- **Cosa fare**: `to_restart` → ferma il task se è ancora vivo, correggi le istruzioni (causa
  dell'errore, unità già fatte da saltare, pacchetto più piccolo) e rilancialo; `to_stop`
  (tentativi esauriti, limite di token superato) → fermalo, segna `stopped`, spezza o rimanda e
  **dillo all'utente** con il motivo. Ogni riavvio o arresto si scrive nella nota del pacchetto.
- I **cancelli** (galleria 16:9, cast voci, preventivo di ogni lotto a pagamento, rilascio)
  restano: un pacchetto che arriva a un cancello si ferma, prepara il materiale e lo riporta;
  chiedi tu all'utente e lanci il seguito solo dopo il sì.

## Fase 2 — Motore (pacchetti `engine-*`, `framerate`)
Subagente `build-engineer` con skill `engine-integration`, un pacchetto alla volta per area:
1. fork di ScummVM (o del motore scelto) a un commit fissato; branch `remaster/<gioco>`;
2. rendere il gioco giocabile dall'inizio alla fine (driver di test automatico, correzioni);
3. integrare il Remaster Layer: compositore HD, toggle originale/remaster, viewport 16:9,
   interpolazione dei frame, sostituzione asset per chiave (contratto in `${CLAUDE_PLUGIN_ROOT}/references/asset-contract.md`);
4. **motore patchabile**: ogni testo, voce e immagine passa da un punto sostituibile dalla
   patch (pacchetto `canary` + `assets coverage`, skill `engine-integration` §1f);
5. **controlli fluidi** (§1g): cursore a ogni fotogramma, nessun salto, azioni a scatto una volta
   per pressione;
6. salvataggi e menu: verificare `canSaveGameStateCurrently`, menu globale, slot;
7. **interfaccia nello stile del gioco** (§6b): tema GUI dai colori e dai font dell'interfaccia
   originale, 2-3 varianti da far scegliere.

## Fase 3 — Asset (pacchetti paralleli, anche insieme alla Fase 2)
- `graphics-artist` → skill `hd-graphics` (fondali, sprite, UI, font HD, filmati);
- `widescreen-planner` → skill `widescreen` (estensioni; **cancello**: galleria di conferma);
- `localizer` → skill `localization` (testi corretti, traduzioni, font con glifi);
- `audio-engineer` → skill `audio-remaster` (fase 1: normalizzazione per gruppo; fase 2: mix);
- `localizer` → skill `manual-hints` (manuale e aiuti, se scelti);
- `voice-director` → skill `voice-dubbing`, **un capitolo alla volta**: censimento di chi parla
  → provini dei personaggi nuovi → regia → stima dei crediti → **cancello**: approvazione →
  generazione → verifica. Prima il doppiaggio dell'intro come prova, da far ascoltare.

Manda all'utente un confronto originale/HD appena il primo fondale è pronto, per correggere
la direzione presto.

## Fase 3b — Tempi e mix (prima della QA)
- Calibra la velocità sul gioco originale nell'emulatore o nella VM di riferimento della sua
  piattaforma (skill `engine-integration`, §1b): mai fidarsi di un passo fisso.
- Mix: dopo la normalizzazione per gruppo, livelli tra i gruppi (partenza: parlato -18,
  effetti fino a -16, musica -25 LUFS) scelti con le prove d'ascolto `audio mix-preview`, poi
  `audio mix` su tutto (skill `audio-remaster`).

## Fase 4 — QA (subagente `qa-tester`)
Regressione visiva tra una passata e l'altra (`review diff`) e peso del pacchetto per telefono e
web (`release budget`) fanno parte della QA.
Percorso completo con il driver automatico, screenshot affiancati, test del toggle in ogni
schermata tipo, salva/carica in ogni parte, controllo testi (troncamenti, glifi mancanti),
sincronia voci, fluidità di mouse e tasti (`engine controls`), menu nel tema del gioco, manuale
e aiuti (H avanza e non torna indietro), prova di avvio su ogni piattaforma prodotta. Il verificatore non deve essere
l'agente che ha prodotto gli asset.

## Fase 5 — Rilascio (skill `build-release`)
Eseguibili per piattaforma, patch del motore (`git format-patch`), pacchetto asset o ricette,
installer/script di applicazione che verificano gli MD5 dei file originali, LEGGIMI,
licenze (GPL, crediti, licenza ElevenLabs), checksum. Consegna con una riga per file.

## Regole di comportamento
- Chiedi poco: in Fase 0 titolo, file e lingua; dopo l'analisi solo le parti a pagamento, con
  il costo; non chiedere ciò che puoi verificare tu né ciò che è gratuito (è già incluso).
- I cancelli di conferma (piano, scelte a pagamento, cast voci, estensioni 16:9 inventate, spese fal.ai/ElevenLabs,
  rilascio) non si saltano nemmeno in esecuzione non presidiata: prepara tutto e fermati lì.
- Registra le decisioni in `remaster.json` (`decisions[]`) con data e motivazione.
- Lavora su copie: i file originali dell'utente non si modificano mai.
