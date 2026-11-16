# Doppiaggio: chi parla, casting e provini
## Chi parla: attribuzione delle battute

- **Il personaggio non si ricava mai dal nome della stanza o del file.**
  *Problema:* le battute di una stanza chiamata come un personaggio erano state date a lui, ma le diceva un altro (una comparsa). Un doppiaggio intero sarebbe stato sbagliato.
- **L'attribuzione viene dalla struttura del copione.** Le domande di un dialogo appartengono al personaggio non giocante del file di dialogo. Le risposte, gli esami degli oggetti e i commenti appartengono al personaggio giocante della stanza. I commenti di stanza vanno al narratore. Nelle scene animate parla chi muove la bocca dopo il comando di testo (si guardano gli intervalli di fotogrammi). Un travestimento si riconduce al personaggio vero con una tabella di alias.
- **File di dialogo con due persone: si dividono per fotogramma del ritratto.**
  *Problema:* uno script cercava il file con un nome normalizzato male, senza il simbolo "&". Così decine di battute sarebbero finite a un personaggio inesistente e senza voce. Si decodificano i ritratti, si guarda quali fotogrammi mostrano quale persona e si divide in base al fotogramma.
- **Le eccezioni manuali valgono solo per la riga indicata.**
  *Problema:* un'eccezione "questa domanda la dice X" veniva applicata anche alla risposta del protagonista con lo stesso id di domanda, che quindi usciva con la voce sbagliata.
- **Il copione si estrae dall'edizione del gioco che ha l'utente.**
  *Problema:* il testo base veniva da un'altra edizione. Alcune frasi erano scritte diversamente, quindi avevano un'altra chiave, e restavano senza voce e senza correzione.
- **Dove esiste l'audio originale, lo si usa come controllo.** Per ogni battuta si confrontano l'altezza media (Hz) e il timbro (MFCC o embedding del parlante) con quelli dei personaggi già noti. Le battute che non somigliano a nessuno vengono segnalate. Le fasce di altezza misurate (es. 95-110 Hz, 240-300 Hz, ~350 Hz) distinguono bene voci diverse. Due voci maschili giovani a ~165 e ~175 Hz invece si confondono all'ascolto: questo spiega le segnalazioni "hanno tutti la stessa voce".
- **Revisione indipendente prima di ogni capitolo.** Un secondo agente, che non ha preparato il lotto, rilegge attribuzioni e indicazioni di regia. All'utente arrivano solo i casi dubbi, con l'audio originale da confrontare.
- **Collisioni di chiave.** La chiave del file voce è il CRC del testo, quindi lo stesso testo detto da due personaggi ("Grazie...", "Buongiorno...") ha un solo file. Bisogna segnalarlo nel rapporto. La soluzione proposta è un suffisso facoltativo `<chiave>_<personaggio>`, cercato prima della chiave semplice e compatibile con i file esistenti.
- **Verifica dopo l'integrazione, gratis e in locale.** Per ogni personaggio si confronta l'altezza della voce dei file integrati con chi parla a schermo. Una battuta del protagonista uscita a ~102 Hz invece di 150-190 Hz ha rivelato la voce sbagliata.

## Casting e provini

- **Una voce per personaggio, fissa per sempre**, coerente con età e genere. Voce e impostazioni stanno in un file di cast versionato (`cast.json`). La regia per battuta sta in un file separato.
- **Provini.** Per ogni nuovo personaggio si propongono 2-3 voci con **una sola battuta vera** del gioco, la stessa per tutte, nel registro tipico del personaggio (ironica per un ironico), non frasi inventate: una frase neutra non dice se la voce regge il ruolo. Sceglie l'utente, all'orecchio; se resta in dubbio su una o più voci si propone una battuta addizionale solo per quelle, con il costo.
- **Altezza.** Si sceglie una voce che sta già nel registro giusto e si controlla con la regia (tag che non alzano il tono). Niente correzione di tono a posteriori: sia i vocoder tipo WORLD sia un pitch-shift di 2 semitoni con formanti preservate (rubberband) sono risultati metallici all'ascolto.
- **Connettore e API.** Il connettore MCP può non esporre stabilità, stile e velocità: serve per esplorare; provini definitivi e lotti si fanno con l'API diretta, con la chiave nei segreti d'ambiente.
- **Lista delle voci scartate**, con il motivo, da controllare prima di ogni proposta. I motivi tipici sono "stanza piccola", "riverbero da chiesa" e "non usabile via API".
- **Le misure automatiche del riverbero non sono affidabili.** Una voce con riverbero evidente era passata. È meglio preferire voci di studi professionali già approvati e far decidere l'orecchio dell'utente.
- **Limiti della piattaforma.**
  - Le voci della Voice Library non si usano via API con il piano gratuito (errore 402).
  - Una voce della libreria va prima aggiunta al proprio account (`/v1/voices/add/...`); il suo id può cambiare.
  - Voice Design non crea voci di bambino.
  - Per un ragazzo si è usata una voce femminile con un filtro ffmpeg (formanti -10%, altezza -15%).
- **Filtri a valle (ffmpeg) per voci "speciali"**: robot, telefono, televisore. Sono deterministici e ripetibili, e non costano crediti.
- **Nei provini una voce mancante salta le sue battute, non blocca il lotto.**
