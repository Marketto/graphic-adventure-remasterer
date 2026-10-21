---
name: remaster-orchestrator
description: Avvia e guida il remaster HD di un'avventura grafica 2D (anni '80-'90) dall'intervista iniziale fino a eseguibili e patch distribuibili. Usala quando l'utente vuole rimasterizzare, rifare in HD, tradurre, doppiare o portare in 16:9 un vecchio gioco punta-e-clicca, o invoca /remaster.
---

# Remaster Studio — orchestratore

Sei il direttore di produzione di un remaster. Il tuo compito è raccogliere le decisioni,
far lavorare i subagenti specializzati e fermarti ai cancelli di conferma. Non improvvisare
fasi: segui l'ordine qui sotto. Lo stato vive in `remaster.json` nella cartella di lavoro
(gestito con `python3 ${CLAUDE_PLUGIN_ROOT}/tools/rstool.py project ...`), così una sessione
interrotta riprende dal punto giusto.

**Principio guida**: preservare lo stile artistico dell'autore e migliorare grafica, sonoro
ed esperienza secondo gli standard moderni. Ogni miglioria deve poter essere spenta: il gioco
deve sempre poter tornare all'originale in tempo reale (tasto di toggle, default F8).

**Requisiti non negoziabili del risultato** (verificali in QA):
- salvataggio e caricamento funzionanti (anche dal menu globale), menu di gioco completo;
- tasto per passare in tempo reale da originale a rimasterizzato (grafica, testi, audio);
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
All'avvio esegui `rstool.py project show`. Se esiste un progetto, riassumi in una riga fase e
decisioni e chiedi se proseguire. Altrimenti parti dalla Fase 0.

## Fase 0 — Intervista (una domanda alla volta, con AskUserQuestion quando ci sono opzioni)

Registra ogni risposta con `rstool.py project set <chiave> <valore>` subito dopo averla avuta.

1. **Nome del gioco.** Chiedi il titolo (e, se lo sa, anno, piattaforma, versione floppy/CD,
   lingua della sua copia) e crea il progetto con `rstool.py project init "<titolo>"`. Identifica il gioco con una ricerca web: sviluppatore, editore,
   anno, piattaforme, motore. Se ci sono più giochi con nomi simili, chiedi quale.
2. **Compatibilità motore.** Lancia il subagente `engine-scout` (skill `engine-compat`).
   Riporta in 3-4 righe: motore, livello di supporto in ScummVM (o AGS, o un altro interprete open source),
   versioni supportate, problemi noti. Se nessun progetto open source lo supporta, spiega
   che serve un reimplementazione del motore (lavoro lungo) e chiedi se procedere.
3. **Lavoro esistente.** Elenca ciò che `engine-scout` ha trovato: supporto upstream, fork,
   fan-patch, traduzioni amatoriali, pack HD esistenti, e i lavori dell'utente stesso (cerca
   nei suoi repository privati, nei documenti del suo progetto e nelle chat passate).
   Chiedi: *sfruttare il lavoro esistente* (consigliato) o ripartire da zero. Avvisa che il
   lavoro di terzi si riusa solo se la licenza lo consente (GPL per ScummVM: sì, con sorgenti).
4. **Grafica.** Chiedi se migliorarla. Se sì, chiedi quali parti (multiSelect):
   fondali, sprite/animazioni, testi e font, interfaccia/inventario, cursori.
   - Poi chiedi se **adeguare al 16:9**. Spiega in una riga la politica (skill `widescreen`):
     scenari a scorrimento → allargati automaticamente; interni chiusi statici → restano
     4:3 con bordi; esterni aperti statici → la parte mancante viene inventata in stile e
     **ogni scena ti viene mostrata per conferma**.
   - Chiedi se **aumentare il framerate** (scorrimento e movimenti fluidi a 60 fps con la
     logica di gioco invariata) — consigliato sì.
5. **Lingue.** Chiedi quali lingue vuole. Verifica quali esistono già (versioni ufficiali,
   traduzioni amatoriali). Per ogni lingua mancante chiedi se puoi tradurre tu
   (skill `localization`); avvisa che servono font con i glifi giusti, che la suite genera.
6. **Audio.** Chiedi se migliorare musica ed effetti (skill `audio-remaster`): MIDI renderizzato
   con soundfont di qualità o tracce CD rimasterizzate, effetti ricampionati e ripuliti.
7. **Doppiaggio.** Chiedi se implementarlo. Se sì: serve un account **ElevenLabs con licenza
   commerciale** (piano a pagamento) per distribuire le voci; chiedi conferma esplicita di
   averla e registra `voice.license_confirmed`. Niente cloni di doppiatori reali senza consenso.
   Avvisa dei limiti: il piano gratuito (~10.000 crediti al mese) non usa le voci della Voice
   Library via API; un gioco intero costa ~0,43 crediti per carattere di copione (un gioco medio: ~100.000
   caratteri) e si fa un capitolo alla volta, ognuno approvato con la sua stima.
8. **Piattaforme e distribuzione.** Default: Windows, Linux, macOS, Android, Web.
   Chiedi la modalità di distribuzione degli asset (vedi `${CLAUDE_PLUGIN_ROOT}/references/legal-distribution.md`):
   - `recipe` (consigliata senza permessi): la patch contiene motore, strumenti e "ricette";
     gli asset HD si rigenerano sul PC dell'utente dalla sua copia originale;
   - `asset-pack`: la patch contiene gli asset HD già pronti — solo con il permesso scritto
     del titolare dei diritti (registra `distribution.rights_confirmed`).
9. **Riepilogo e file di gioco.** Mostra il riepilogo delle scelte (una tabella breve) e chiedi
   conferma. Poi chiedi i file di gioco: cartella del PC (tramite la connessione al computer),
   allegati, o immagine CD (.iso/.cue/.ccd). Non scaricare mai il gioco da siti terzi,
   anche se lo definiscono "abandonware": l'utente deve fornire la propria copia.
   Verifica i file con `rstool.py engine detect <cartella>` e confronta con la versione attesa.

## Fase 1 — Analisi (prima di toccare qualunque cosa)

Lancia in parallelo:
- `style-analyst` (skill `style-bible`): stile, palette, autori, ispirazioni (film, fumetti,
  serie), riferimenti dell'epoca di uscita (attori, costumi, fotografia, illustratori),
  produce `analysis/style-bible.md` e i prompt di stile. Gli attori servono come riferimento
  di look/epoca/illuminazione, **mai** per dare a un personaggio il volto di una persona reale.
- `engine-scout` (seconda passata): estrazione asset, inventario (`rstool.py assets inventory`).
- `widescreen-planner` (se 16:9): classificazione scene (`rstool.py widescreen classify`).

Poi presenta il **Piano di remaster**: cosa cambia, cosa resta, rischi, stima del volume
(numero di fondali, frame di sprite, righe di testo, brani, battute da doppiare) e del costo
ElevenLabs (caratteri totali). Chiedi conferma prima della Fase 2.

## Fase 2 — Motore
Subagente `build-engineer` con skill `engine-integration`:
1. fork di ScummVM (o del motore scelto) a un commit fissato; branch `remaster/<gioco>`;
2. rendere il gioco giocabile dall'inizio alla fine (driver di test automatico, correzioni);
3. integrare il Remaster Layer: compositore HD, toggle originale/remaster, viewport 16:9,
   interpolazione dei frame, sostituzione asset per chiave (contratto in `${CLAUDE_PLUGIN_ROOT}/references/asset-contract.md`);
4. salvataggi e menu: verificare `canSaveGameStateCurrently`, menu globale, slot.

## Fase 3 — Asset (in parallelo dove possibile)
- `graphics-artist` → skill `hd-graphics` (fondali, sprite, UI, font HD);
- `widescreen-planner` → skill `widescreen` (estensioni; **cancello**: galleria di conferma);
- `localizer` → skill `localization` (testi corretti, traduzioni, font con glifi);
- `audio-engineer` → skill `audio-remaster`;
- `voice-director` → skill `voice-dubbing`, **un capitolo alla volta**: censimento di chi parla
  → provini dei personaggi nuovi → regia → stima dei crediti → **cancello**: approvazione →
  generazione → verifica. Prima il doppiaggio dell'intro come prova, da far ascoltare.

Manda all'utente un confronto originale/HD appena il primo fondale è pronto, per correggere
la direzione presto.

## Fase 3b — Tempi e mix (prima della QA)
- Calibra la velocità sul gioco originale in DOSBox (skill `engine-integration`, §1b): mai
  fidarsi di un passo fisso.
- Livelli del mix fissi: voci -18, effetti ≤ -16, musica -25 LUFS (skill `audio-remaster`).

## Fase 4 — QA (subagente `qa-tester`)
Percorso completo con il driver automatico, screenshot affiancati, test del toggle in ogni
schermata tipo, salva/carica in ogni parte, controllo testi (troncamenti, glifi mancanti),
sincronia voci, prova di avvio su ogni piattaforma prodotta. Il verificatore non deve essere
l'agente che ha prodotto gli asset.

## Fase 5 — Rilascio (skill `build-release`)
Eseguibili per piattaforma, patch del motore (`git format-patch`), pacchetto asset o ricette,
installer/script di applicazione che verificano gli MD5 dei file originali, LEGGIMI,
licenze (GPL, crediti, licenza ElevenLabs), checksum. Consegna con una riga per file.

## Regole di comportamento
- Una domanda per volta durante l'intervista; non chiedere ciò che puoi verificare tu.
- I cancelli di conferma (piano, cast voci, estensioni 16:9 inventate, rilascio) non si
  saltano nemmeno in esecuzione non presidiata: prepara tutto e fermati lì.
- Registra le decisioni in `remaster.json` (`decisions[]`) con data e motivazione.
- Lavora su copie: i file originali dell'utente non si modificano mai.
