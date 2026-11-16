# Doppiaggio: impostazioni, regia, testo detto, pause, continuità
## Impostazioni

- Modello multilingue recente (`eleven_v3`/`eleven_v4`), `language_code` italiano, similarità 0,8 per tutti.
- I personaggi principali usano sempre il modello che recita i tag; un modello più economico solo per i secondari e solo se i crediti lo chiedono, con la scelta registrata nel progetto.
- Stabilità 0,25-0,3 e stile 0,6-0,85 per una recitazione espressiva.
- La velocità si imposta nella voce: 0,92 per il narratore e 0,95 per un personaggio enfatico, perché a 1,0 l'utente le trovava veloci.
- **Nessuna accelerazione o rallentamento dopo la generazione**: produce artefatti e un ritmo innaturale.
- Il cast è approvato con una data. Da lì le impostazioni non cambiano più.

## Audio tag e regia

- **Recitazione, non lettura.** Ogni battuta ha un'indicazione in inglese tra parentesi quadre, per personaggio o per battuta, scelta dal contesto della scena. Esempi: `[cocky, ironic]`, `[bored cashier, sing-song]`. Non si copia dal doppiaggio originale.
- **Regia per battuta, generata dal contesto.** Un tag fisso per personaggio appiattisce la recitazione: lo stesso tono su una battuta triste e su una ironica. Per ogni battuta si guarda testo, scena, battute vicine con chi parla, interlocutore e carattere; uno strumento prepara la scheda e propone un tag da punteggiatura e parole chiave (regole per lingua), poi chi dirige rivede. Al massimo un tag sobrio per battuta, spesso nessuno. Sulle voci gravi i tag che alzano energia (eccitato, urlato) spingono la voce in un registro che non è il suo: si evitano salvo scene che lo chiedono.
- **I tag si mandano solo ai modelli che li recitano (v3/v4).** I modelli precedenti li leggono ad alta voce. La trascrizione di controllo rileva i tag letti.
- **Niente sussurri né voci "inquietanti"**: anche le battute misteriose vanno a voce piena, perché i sussurri escono male e sotto la musica non si sentono.
- Accenti e parlate volute (es. un personaggio che dice "L" al posto di "R") si segnano nella regia. Il trascrittore poi "corregge" la parola, quindi in quei casi l'avviso del controllo non conta.

## Testo detto e sottotitolo

Ci sono tre livelli distinti:

1. **testo originale**, da cui si calcola la chiave del file (CRC32 senza spazi): la chiave non cambia mai;
2. **sottotitolo corretto** a schermo (vedi §2);
3. **testo recitato** (`recita`), cioè la forma che la sintesi pronuncia bene. Non cambia il sottotitolo.

Le correzioni di pronuncia sono una lista ordinata di (espressione regolare → testo detto):

- **Sigle**: "ONU" → "o enne u", "TV" → "tivù", "OK" → "okay". Le parole tutte maiuscole di 3 o più lettere (titoli, insegne) passano in minuscolo con l'iniziale maiuscola, altrimenti la sintesi le compita.
- **Simboli**: "Rossi & Figli" → "Rossi e Figli". *Problema:* la "&" veniva letta in modo strano; l'utente voleva "e".
- **Numeri e codici**: "007" → "zero zero sette", "XY12" → "ics ipsilon uno due", ore ("9:06" → "nove e zero sei"), numeri romani nei titoli ("II" → "secondo"), unità ("12 cm" → "dodici centimetri"), codici alfanumerici.
- **Nomi stranieri**: si scrivono come si pronunciano (grafia fonetica italiana).
- **Separatori di riga** del formato originale (es. `/`): sostituiti con punteggiatura adatta all'intonazione.
- **Correzioni per singola battuta dopo il controllo.** *Problema:* in una battuta brevissima ("Boh.") la sintesi aggiungeva parole; in un'altra ripeteva un gioco di parole. Si riscrive il testo detto solo per quella chiave.

## Pause e tempi

- I silenzi si tolgono a entrambi i capi (`silenceremove` a -45 dB, avanti e con `areverse`).
- Dopo una battuta che finisce con `. ! ? …` si aggiungono **0,6 s**. Se la frase continua nella battuta successiva, **0,15 s**. Tra i pezzi composti di una stessa frase, **0,05 s** (un respiro).
- **Tempi naturali.** Nelle scene animate il motore fa partire il comando successivo quando finisce il suono, così la scena segue la durata dell'audio italiano. Forzare la durata dell'originale inglese richiedeva accelerazioni fino a 1,25x, ed è stato scartato.
- **La durata deve stare nel tempo del testo a schermo.** Le battute nei fumetti restano finché si clicca, quindi non hanno vincoli. I sottotitoli a tempo hanno quello dello script: se la voce è troppo lunga si rigenera più lenta o si accorcia il testo detto.

## Continuità

- `previous_text` e `next_text` passano la battuta prima e quella dopo **dello stesso personaggio nella stessa scena**. Servono per le scene in sequenza e non si pagano.
- **Nei dialoghi non si usano.** *Problema:* le battute corte prendevano parole dalla battuta vicina passata come contesto. Ogni battuta di dialogo è autonoma.
- **Battute con un valore variabile** ("Ho solo N monete"). Si genera una volta la parte fissa, con i tag. Il numero si genera da solo, in cifre, con il resto della frase come contesto, così l'intonazione combacia. Poi si compone in locale, con la chiave del testo che contiene il numero, che il motore cerca per prima.
  *Risultato:* spesa circa 20 volte più bassa, ogni battuta verificata con la trascrizione.
