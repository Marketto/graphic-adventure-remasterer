# Flusso di lavoro con agenti

### 4.1 Router in CLAUDE.md

- Una tabella **richiesta → skill → agente**, per esempio: bug in gioco → skill bug, poi modifica del motore, con l'agente del motore; voci e testi → agente voci-testi; fine di qualunque lavoro → skill di chiusura e revisore.
- Una mappa dei documenti (architettura, formati, build, strumenti, test, voci, stato).
- Le regole fisse: lingua, privacy dei dati, stile da preservare, spese, separazione tra motore e contenuto.
- *Problema risolto:* senza router ogni sessione ripartiva da zero e saltava procedure già decise.

### 4.2 Agenti specializzati

- Un agente per area (motore, grafica, voci e testi). Ognuno legge i suoi documenti e le sue skill e restituisce file cambiati, causa, correzione e come verificarla.
- **Gli agenti non committano**: integra, documenta e chiude solo il coordinatore.
- Problemi indipendenti nella stessa richiesta: un agente per area, in parallelo.
- **Revisore in sola lettura** (soli strumenti di lettura, modello più economico), da usare prima della PR, sul diff rispetto a `origin/main` e sui file non committati. Controlla:
  - che la documentazione sia aggiornata secondo la tabella della chiusura;
  - che la patch del motore si applichi da zero;
  - che non ci siano dati privati o segreti in posti pubblici;
  - che le regole siano rispettate;
  - che skill e router citino file e azioni che esistono davvero.

### 4.3 Skill di chiusura e skill per i bug

- **Chiusura del lavoro**: una tabella "cosa è cambiato → quale documento aggiornare", poi verifiche (patch applicabile, privacy, file sotto i 50 MB per push per evitare l'errore HTTP 413), commit, push e PR.
  - Si usano date assolute (gg/mm/aaaa).
  - Un bug segnalato va in "In verifica" e passa a "Fatto" solo dopo la conferma in gioco.
  - Le decisioni dell'utente si registrano con la data.
- **Bug in gioco**: dalla stanza agli script originali, poi al codice del motore. Si riproduce con un driver di test automatico e si aggiunge un caso di regressione. Si cerca il commit che ha introdotto il problema.
- **Un test non eseguito si dichiara come tale.** Non si scrive "verde" senza un output verificabile.

### 4.4 Hook Stop per il lavoro in sospeso

Logica generica dell'hook:

1. Se l'input contiene `stop_hook_active: true`, esce subito: blocca una sola volta per turno, così non entra in un ciclo.
2. Se non è un repository git, esce.
3. Le modifiche non committate si leggono con `git status --porcelain`.
4. I commit non inviati:
   - se il ramo ha un upstream, sono `git log @{u}..HEAD`;
   - se non ce l'ha, contano solo i commit **che non sono su nessun ramo remoto** (`git log HEAD --not --remotes`). Un ramo appena creato da `origin/main`, senza commit propri, **non è lavoro in sospeso**. *Problema risolto:* falsi allarmi a ogni ramo nuovo.
   - HEAD staccato: si ignora.
5. Se trova qualcosa, risponde `{"decision":"block","reason":...}` con l'elenco e il rimando alla skill di chiusura. Se il lavoro non è finito, l'agente lo dice all'utente invece di committare.

### 4.5 Flusso basato sulle PR

- Mai commit su `main`. Si apre un ramo `fix/…`, `feat/…` o `docs/…` da `origin/main` aggiornato.
- Un commit per unità logica. La PR descrive cosa cambia, come provarlo, i test eseguiti e quelli **non** eseguiti. **L'utente unisce.**
- Se l'utente vuole provare, si avvia la build sul ramo e si riporta il link.

### 4.6 Versioni di rilascio

- Tag progressivi `patch-N`, non SemVer. **Non si riutilizza né si sposta mai un tag pubblicato.** Se una versione pubblicata è sbagliata, se ne fa una nuova.
- Il workflow di rilascio riceve **solo il numero** e crea `patch-N` con lo zip e i checksum. Un secondo workflow allega la build web autonoma.
- Le Release sono private, perché contengono dati derivati. Nessun token negli artefatti.
- Il rilascio non è completato finché Actions non è verde e gli asset (checksum, accesso) non sono verificati.
- Se l'agente non può avviare un workflow, non simula l'operazione: dà i passaggi esatti all'operatore.

### 4.7 Spese

- Ogni servizio a pagamento (sintesi vocale, immagini generative) parte **solo dopo un'approvazione esplicita**, con un preventivo: unità × tentativi × prezzo, crediti rimasti e tempo di revisione.
- **Le stime gratuite e le verifiche a costo zero si possono fare senza chiedere.**
- Dopo la spesa si registrano speso e rimasto.

---
