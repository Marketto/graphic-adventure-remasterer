---
name: manual-hints
description: Inserisce nel remaster il manuale di gioco (dalla copia dell'utente, ripulito, tradotto, leggibile dal menu e come pagina HTML nello stile del gioco) e gli aiuti in gioco (tasto H, obiettivi in ordine con condizioni monotone, indizio e soluzione a richiesta). Usala quando l'utente vuole manuale e aiuti, cioè di default in ogni remaster.
---

# Manuale e aiuti in gioco

Entrambi sono **dati della patch** letti da meccanismi generici del motore (regola "motore e
contenuto separati", skill `engine-integration` §1d): nessun testo del manuale o degli aiuti
dentro il codice. Tutto ciò che deriva dal gioco sta nel repository **privato** del gioco.

## 1. Manuale
**Fonte**: solo la copia dell'utente: manuale stampato (scansione o foto delle pagine),
file sul disco del gioco (`.txt`, `.doc`, `.pdf`, `readme`), schede di riferimento, mappe e
ruote/codici della protezione anticopia. Non si scarica da siti terzi.
1. **Estrazione**: `rstool.py manual ocr <file.pdf> --out analysis/manual-ocr/manuale --lang eng`
   prova prima lo strato di testo (`pdftotext`); i PDF fatti **solo di immagini** (0 caratteri,
   il caso comune delle scansioni) passano a tesseract a 250 dpi (`--dpi`), che su pagine stampate
   dà un testo quasi pulito; un file per pagina più `all.txt`. Per foto o file non PDF: skill
   `pdf-reading` o tesseract direttamente. Le immagini
   utili (mappe, schermate, tabelle dei comandi) ritagliate e ripulite in `manual/img/`.
   Rileggi l'OCR contro le pagine: numeri, nomi e comandi sbagliati sono i difetti tipici.
2. **Ripulitura** in `manual/<lingua originale>.md` (formato in
   `tools/remaster_tools/manual.py`: titoli, paragrafi, elenchi, tabelle, immagini, note):
   stessa struttura e stesso tono dell'originale; nessuna riscrittura dei contenuti.
3. **Aggiornamento** in una sezione separata "Edizione rimasterizzata" (scritta da te, non
   dentro il testo originale): installazione della patch, tasti nuovi (F8 originale/remaster,
   H aiuti, menu, tocco sul telefono), opzioni remaster, piattaforme. Le istruzioni d'epoca
   superate (driver audio, memoria, dischetti) restano ma marcate come storiche.
4. **Protezione anticopia**: se il motore la salta (molti interpreti lo fanno) annotalo nella
   sezione nuova; se resta, il manuale deve contenere ciò che serve per superarla.
5. **Traduzione** nelle lingue scelte (skill `localization`: glossario e nomi uguali a quelli
   del gioco tradotto, larghezze non rilevanti qui).
6. Controllo e consegna:
   - `rstool.py manual check manual/<lang>.md --codepage <codepage del gioco>`: immagini
     mancanti, caratteri che il font del menu non ha;
   - `rstool.py manual html manual/<lang>.md --out remaster/manual/<lang>.html --colors
     analysis/ui-palette.json` (gli stessi colori del tema GUI, skill `engine-integration` §6b):
     pagina unica leggibile sul telefono, inclusa nel pacchetto accanto all'eseguibile;
   - in gioco: voce "Manuale" nel menu globale e nella pagina web, che mostra
     `manual/<lang>.md` con i font del tema (lettore generico nel motore, paginato, con
     immagini ridotte allo schermo).
Il manuale è un'opera protetta come il gioco: nel pacchetto solo con le stesse regole degli
altri asset derivati (`${CLAUDE_PLUGIN_ROOT}/references/legal-distribution.md`); in modalità
`recipe` si rigenera dalla copia dell'utente o si consegna solo la sezione nuova.

## 2. Aiuti in gioco (tasto H)
Formato, condizioni ed esempi: `tools/remaster_tools/hints.py` e la nota
`${CLAUDE_PLUGIN_ROOT}/references/conoscenza/motore-e-test.md` §12.
1. **Obiettivi** in ordine di gioco, per parte, ricavati dalla soluzione verificata
   (`qa/walkthrough.txt`) e dagli script. Se l'utente ha una **guida agli indizi a domande
   progressive** (libretto ufficiale: domanda → indizio → soluzione), è la fonte migliore della
   struttura: è già a livelli come gli aiuti in gioco; estraila con `rstool.py manual ocr` e usala
   per scegliere gli obiettivi e la gradazione, riscrivendo sempre il testo con parole tue: un obiettivo per ogni blocco che un giocatore può
   non capire (non per ogni clic). Le soluzioni pubbliche servono solo da riferimento: gli
   aiuti si scrivono con parole tue.
2. **Condizione `fatto`** per ogni obiettivo su flag globali, flag locali di una scena,
   oggetti, contatori, scene viste. Deve essere **monotona**: una volta vera resta vera; un
   oggetto che poi si consuma va in OR con ciò che si ottiene dopo. Usa i nomi degli script
   del gioco e scrivili in `analysis/vocabolario.json` (`{flags, items, scenes, counters,
   local_flags: {scena: [...]}}`): li ricavi dal parser degli script o dai comandi `flags`/`item`/
   `zones` del driver di test (skill `engine-integration` §1); nessuno strumento della suite lo
   genera da solo.
3. **Testi**: `situazione` (dove sei, cosa vuoi), `indizio` (spinta senza spoiler, dice dove
   guardare), `soluzione` (passi precisi). Tono del gioco; i nomi come nel gioco tradotto.
4. **Lingue**: un file per lingua (`hint/<lang>.txt`) con gli stessi obiettivi, nello stesso
   ordine, con le stesse condizioni; si traduce solo il testo.
5. Controllo: `rstool.py hint check hint/*.txt --vocab analysis/vocabolario.json` (sintassi,
   campi, termini sconosciuti, lingue allineate, avvisi di non monotonia). Poi col driver:
   percorri `qa/walkthrough.txt` premendo H dopo ogni obiettivo e verifica che l'aiuto mostrato
   avanzi e non torni mai indietro; per i passi critici rifai le azioni vere, non impostare i
   flag a mano (un flag che lo script non riesce a salvare non si vede impostandolo col driver).
6. Nel motore (generico): finestra con i font del tema, apertura rimandata se H arriva durante
   una battuta, ignorato nel menu principale, pulsante "Mostra la soluzione", pulsante H sul web
   e sul telefono; ripiego sulla lingua base se manca il file della lingua.

## 3. Consegna
`manual/` e `hint/` nel pacchetto (contratto `${CLAUDE_PLUGIN_ROOT}/references/asset-contract.md`),
la pagina HTML del manuale accanto all'eseguibile, una riga nel LEGGIMI. Decisioni dell'utente
(aiuti sì/no, manuale tradotto sì/no) in `remaster.json` (`extras.manual`, `extras.hints`).
