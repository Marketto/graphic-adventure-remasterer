# 5a. Stima per parte e doppiaggio parziale

Dettaglio della skill `voice-dubbing`.

Il doppiaggio non è "tutto o niente": quando i crediti non bastano per l'intero gioco si propone
di doppiare **solo una o più parti** (capitoli, atti, dischi, percorsi), in ordine di gioco.

- **Trovare le parti** (fase di analisi, prima della stima), dalla fonte più affidabile:
  1. struttura degli script e delle stanze: cartelle o prefissi per capitolo, file di script
     caricati a blocchi, gruppi di stanze raggiungibili solo dopo un certo punto;
  2. salti di capitolo nel codice: istruzioni che cambiano capitolo/disco, variabili di
     avanzamento, richieste di cambio disco;
  3. titoli di parte mostrati nel gioco (schermate "Parte N", intertitoli, nomi dei salvataggi);
  4. guida agli indizi o soluzione divisa in parti (manuale, guida ufficiale): utile per i nomi,
     da verificare sugli script;
  5. percorsi alternativi (personaggi giocabili diversi, rami esclusivi): ogni percorso è una parte.
  Senza fonti certe le parti restano ignote: non inventarle, il piano spezza per lotti e lo dice.
- **Nei conti dell'analisi**: `"voice": {"parts": [{"id": "1", "label": "<titolo neutro>",
  "chars": <caratteri unici>, "lines": <battute>}, ...]}` in ordine di gioco. Una battuta ripetuta
  in più parti si conta solo nella prima in cui compare (lì si genera; le parti dopo la riusano).
  Il dettaglio riga → parte (chiave del testo e id della parte) resta nei dati privati del gioco e
  serve per comporre i lotti.
- **Stima**: `rstool.py plan table <conti>` mostra una riga per parte ("Doppiaggio parte 2/4")
  con i crediti della parte, i cumulati e, se `voice.credits_available` è nel progetto (crediti
  rimasti, letti con la modalità `verifica` gratuita), "✅ nei crediti" o "⏸️ oltre i crediti":
  stanno le prime parti in ordine di gioco finché i cumulati restano nei crediti (la prima sempre
  per prima, una parte economica dopo non scavalca una costosa prima).
- **Domanda all'utente** quando i cumulati superano i crediti, con il costo di ciascuna opzione:
  1. piano superiore del servizio (quanto costa in più, quanti crediti dà) → tutto il gioco;
  2. modello più economico per le comparse (battute dei personaggi minori), i protagonisti con il
     modello pieno: ricalcola e di' se così sta tutto;
  3. solo alcune parti: elenca le parti con crediti e cumulati, proponi quelle che stanno;
  4. rimandare il doppiaggio (si può aggiungere una parte dopo, con i crediti del mese dopo).
- **Scelta registrata**: `rstool.py project set voice.credits_available <n>` e
  `rstool.py project set voice.scope '{"mode": "parti", "parts": ["1", "2"]}'` (oppure
  `{"mode": "tutto"}`), e una riga in `decisions`. I pacchetti delle parti escluse non vengono
  generati: `plan packages --register` li segna `deferred`; quando l'utente le aggiunge allo
  scope tornano `pending`.
- **In gioco**: le righe senza voce nuova ricadono sul comportamento originale (clip originale o
  solo sottotitolo, vedi `engine/scummvm-remaster-layer/INTEGRAZIONE.md`, "Doppiaggio parziale").
  Nei crediti del remaster e nelle note di rilascio scrivi quali parti sono doppiate.

- **Registro delle spese**: per ogni esecuzione id del run, caratteri, crediti spesi, crediti
  rimasti sul totale del mese. Prima di rifare una battuta cerca una correzione gratuita (un file
  esistente equivalente); i rifacimenti si fanno con la lista `solo` delle battute indicate.
- Lotti via GitHub Action (`workflow_dispatch`) con modalità `verifica` (gratis), `genera`,
  `adatta` (solo tagli, pause e volume, senza chiave) e `controlla` (ritrascrive); limite
  `max_caratteri` per esecuzione, `concurrency` per evitare due generazioni insieme, risultato in
  un ramo privato per lotto con `rapporto.md` (crediti prima e dopo). Entra negli asset solo ciò
  che l'utente ha ascoltato e approvato.
