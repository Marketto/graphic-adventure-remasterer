# Doppiaggio: controllo, battute da saltare, crediti, lotti
## Controllo dopo la generazione

- Ogni battuta nuova viene trascritta (speech-to-text, lingua italiana, senza tag degli eventi audio) e confrontata con il testo detto. Se il WER supera il **20%** viene segnalata.
- Il controllo trova parole mancanti, tag letti ad alta voce e pronunce sbagliate.
- Falsi positivi noti: nomi propri trascritti con un'altra grafia e parlate volute.
- Una modalità "controlla" ritrascrive le registrazioni esistenti senza generare nulla.

## Battute da non registrare

- Messaggi per chi prova il gioco (debug, tester) e righe senza lettere.
- Righe con un valore variabile, che si fanno con il metodo dei pezzi (skill `voice-dubbing` §5b).
- Suoni senza sottotitolo (versi, folla): sono effetti, non parlato.
- Personaggi senza voce nel cast: il rapporto li elenca e li salta.
- Le battute escluse si elencano in un documento per capitolo, con il motivo.

## Crediti, preventivi, rifacimenti

- **Costo reale: circa 0,43 crediti a carattere** (valore del codice, `voice.credits_per_char` nel progetto per cambiarlo), tag compresi. Per esempio, 45.000 caratteri sono costati ~19.200 crediti; un rifacimento di 232 caratteri ne è costato 92. Il preventivo si fa con (caratteri + tag) × ~0,43. Il "1 carattere = 1 credito" della documentazione generale sovrastima.
- **Effetti sonori: ~11 crediti al secondo.**
- **Crediti che non bastano: doppiaggio per parti.** Invece di "tutto o niente" si doppiano solo
  le prime parti del gioco (capitoli, atti, dischi, percorsi) che stanno nei crediti, in ordine di
  gioco; le altre restano con il comportamento originale (clip originale o sottotitolo), perché il
  motore sceglie riga per riga dalla presenza del file della voce nuova. Le parti si ricavano dalla
  struttura degli script e delle stanze, dai salti di capitolo, dai titoli di parte e dalla guida
  agli indizi; una battuta ripetuta si conta nella prima parte in cui compare.
- **Preventivo prima di spendere, approvazione esplicita dell'utente.** Le stime e i controlli gratuiti si possono fare senza chiedere.
- **Ogni spesa si registra**: id del run, caratteri, crediti spesi, crediti rimasti su quelli totali del mese.
  *Problema:* senza un registro non si sa quanto resta prima del capitolo successivo.
- **Rifacimenti:** si rigenerano solo le battute indicate (lista `solo`); quelle già fatte si riusano.
- **Prima di rifare, si cerca la correzione a costo zero.** Esempio: una frase che differisce da un file esistente solo per un simbolo si copia dal file esistente. Poi la si rifà solo se l'utente lo chiede.
- **Le chiamate a pagamento non si ripetono mai automaticamente.** Al primo errore lo script si ferma, dice perché e tiene le battute già fatte. Non passa mai a un'altra voce da solo.

## Lotti con GitHub Actions

Un workflow `workflow_dispatch` legge un **lotto** JSON (battuta, chiave, personaggio, stanza, testo, testo detto, tag, durata dell'originale) e ha queste modalità:

| Modalità | Costo | Cosa fa |
|---|---|---|
| `verifica` | gratis | chiave, piano, crediti rimasti, modello, presenza delle voci del cast |
| `genera` | crediti | solo le battute nuove o quelle elencate in `solo`, poi rifinitura e trascrizione |
| `adatta` | gratis, senza chiave | rifà solo tagli, pause e volume dalle registrazioni salvate |
| `controlla` | trascrizione | ricontrolla le registrazioni esistenti |

Protezioni e organizzazione:

- `max_caratteri` è un limite di sicurezza per esecuzione (es. 8.000): se il lotto lo supera non si genera nulla. Si blocca anche se i crediti rimasti non bastano.
- La chiave API sta in un secret.
- Un gruppo di `concurrency` impedisce due generazioni insieme. Il timeout è lungo (3 h).
- **Il risultato va in un ramo privato per lotto** (`voci-<lotto>`, sovrascritto a ogni esecuzione), con gli MP3 originali, gli OGG rifiniti e un `rapporto.md` che riporta i crediti prima e dopo. All'esecuzione successiva il ramo si rilegge per riusare le registrazioni.
- Le voci entrano negli asset solo dopo che l'utente le ha ascoltate e approvate.

## Attese delle voci negli script: sempre interrompibili

Se uno script aspetta la fine della voce prima di proseguire, **un clic o un tasto deve sbloccarlo**.
*Problema:* su alcuni backend audio la fine del suono non viene segnalata, e lo script di una scena restava fermo per sempre.

---

## Seconda prova: stime, tipi di battuta, sincronia labiale
- **Stime sui testi unici e nella lingua di arrivo**: le clip originali ripetevano la stessa
  frase (+15% di clip rispetto ai testi unici) e l'italiano è più lungo dell'inglese del 10-15%:
  `rstool.py voice estimate <dump>/text.jsonl --expand 1.12`; il piano usa `voice_chars_unique` e
  il coefficiente `eleven_expand`.
- **Tipi di battuta**: dove le scelte di dialogo hanno il codice della voce nella stringa, sono
  parlato del protagonista (`question`); quelle senza voce sono `choice` e non si recitano.
- **Chi parla**: con l'attore indicato da un numero riassegnato da scena a scena, la mappa statica
  attore → nome sbagliava in parte; la conferma viene dal driver di test che registra l'attore
  nel momento della battuta.
- **Sincronia labiale**: ogni clip originale aveva i suoi dati di movimento della bocca; le voci
  nuove li perdono. Servono dati rigenerati dall'audio (`voice/<lang>/<textKey>.lip.json`) o la
  bocca guidata dall'ampiezza (pacchetto `lipsync` del piano).
