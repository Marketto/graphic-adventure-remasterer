# Nota tecnica: doppiaggio con ElevenLabs, testi, audio e flusso di lavoro con agenti

*Note generiche da un progetto di rimasterizzazione di un'avventura punta-e-clicca 2D degli anni '90 su un motore open source (GPL). Gli esempi sono inventati.*

---

## 1. Doppiaggio con ElevenLabs

### 1.1 Chi parla: attribuzione delle battute

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

### 1.2 Casting e provini

- **Una voce per personaggio, fissa per sempre**, coerente con età e genere. Voce e impostazioni stanno in un file di cast versionato (`cast.json`). La regia per battuta sta in un file separato.
- **Provini.** Per ogni nuovo personaggio si propongono 2-3 voci con una battuta di prova. Sceglie l'utente, all'orecchio.
- **Lista delle voci scartate**, con il motivo, da controllare prima di ogni proposta. I motivi tipici sono "stanza piccola", "riverbero da chiesa" e "non usabile via API".
- **Le misure automatiche del riverbero non sono affidabili.** Una voce con riverbero evidente era passata. È meglio preferire voci di studi professionali già approvati e far decidere l'orecchio dell'utente.
- **Limiti della piattaforma.**
  - Le voci della Voice Library non si usano via API con il piano gratuito (errore 402).
  - Una voce della libreria va prima aggiunta al proprio account (`/v1/voices/add/...`); il suo id può cambiare.
  - Voice Design non crea voci di bambino.
  - Per un ragazzo si è usata una voce femminile con un filtro ffmpeg (formanti -10%, altezza -15%).
- **Filtri a valle (ffmpeg) per voci "speciali"**: robot, telefono, televisore. Sono deterministici e ripetibili, e non costano crediti.
- **Nei provini una voce mancante salta le sue battute, non blocca il lotto.**

### 1.2b Personaggi di un'opera d'origine (film, serie, cartoni)

- **La verifica si fa sempre**, anche quando il gioco non sembra su licenza: scatola, manuale,
  crediti ("basato su"), schede dei database. Per ogni personaggio riconoscibile si annotano
  l'interprete originale e, per ogni lingua di destinazione, il doppiatore dell'edizione
  dell'epoca del gioco, con le fonti. "Non trovato" è una risposta, inventare no.
- **La domanda sulla voce simile arriva solo dopo che il doppiaggio è scelto**, una per
  personaggio: chiederla prima allunga la Fase 1b senza motivo.
- **Somiglianza senza clonazione.** Si misurano pochi secondi puliti del riferimento (trailer,
  spot, clip ufficiali dello stesso periodo) in locale: altezza mediana e variabilità in
  semitoni, centroide e pendenza dello spettro, rapporto armoniche/rumore come ruvidità,
  velocità d'eloquio dai picchi d'energia sillabici, quota di pause. Le stesse misure sulle
  anteprime delle voci della libreria danno una classifica; i frammenti si cancellano subito
  dopo e non vengono caricati da nessuna parte.
- **Pesare ciò che i parametri non cambiano.** Altezza e timbro pesano di più nella distanza,
  perché stabilità, stile e velocità non li spostano; velocità e pause pesano poco, perché si
  correggono con `speed` e con la regia (punteggiatura, pause, audio tag).
- **Le misure scelgono la rosa, l'orecchio sceglie la voce.** Le anteprime della libreria sono
  frasi diverse da quelle del riferimento e con un'altra recitazione: la classifica serve a
  passare da centinaia di voci a 3-5 provini, non a decidere.
- **Riferimenti d'epoca con banda stretta.** Le copie di trailer vecchi (VHS, TV) spesso tagliano
  sopra i 4-5 kHz: la pendenza dello spettro si misura solo fino a 4 kHz e il centroide va letto
  con prudenza.
- **Ambienti cloud bloccati dalle piattaforme video.** Le richieste da un ambiente cloud ricevono
  403, poi 429 e la verifica "non sono un bot": insistere peggiora il blocco. Due tentativi per
  piattaforma, poi altre fonti consentite, poi l'audio caricato dall'utente (anche registrato col
  telefono) o scaricato sul suo computer con un comando pronto. Mai cookie o credenziali
  dell'utente. `yt-dlp` recente vuole un runtime JS (`node` + `yt-dlp-ejs`), senza gli stream
  rispondono 403 anche se i metadati arrivano.
- **Tratti da file lunghi.** Trascrizione locale con i tempi delle parole e impronte vocali
  danno un TSV di tratti per parlante da misurare senza tagliare i file. faster-whisper con PyAV
  recente fallisce aprendo i file: si decodifica con ffmpeg e si passa l'array. I tempi delle
  parole scavalcano le pause, quindi i segmenti si tagliano anche sui silenzi veri del segnale.
  Le impronte di resemblyzer separano poco (circa 0,3 di distanza coseno tra due voci diverse):
  con un numero noto di parlanti si fissa il numero di gruppi, e l'ascolto conferma.
- **Anteprime con musica.** Molte anteprime della libreria hanno un letto musicale: quota di pause
  a zero, dinamica bassa e rapporto armoniche/rumore basso. Pause e ruvidità di quelle anteprime
  non dicono nulla della voce e si pesano meno.
- **Errori d'ottava.** Il tracciamento dell'altezza può dimezzare o raddoppiare: un'altezza fuori
  dall'intervallo plausibile per genere ed età dichiarati si segnala, con l'ottava alternativa.
- **Timbro oltre due numeri.** Centroide e pendenza riassumono lo spettro in due valori; due
  voci con stessa altezza e brillantezza possono avere formanti diverse. I 12 coefficienti
  cepstrali medi dello spettro di lungo periodo (fino a 4 kHz, per le copie a banda stretta)
  aggiungono la forma.
- **Misure riusabili.** Le anteprime si misurano una volta e si riusano tra personaggi e sessioni;
  il riferimento conserva fonti e intervalli (non il testo) per rifare la misura dopo aver
  cancellato l'audio.
- **Toni interpretativi**: dal modo di recitare nei riferimenti (ritmo, ironia, pause, attacchi)
  si ricavano gli audio tag e le note di regia, scritti senza citare la persona.

### 1.3 Impostazioni

- Modello multilingue recente (`eleven_v3`/`eleven_v4`), `language_code` italiano, similarità 0,8 per tutti.
- Stabilità 0,25-0,3 e stile 0,6-0,85 per una recitazione espressiva.
- La velocità si imposta nella voce: 0,92 per il narratore e 0,95 per un personaggio enfatico, perché a 1,0 l'utente le trovava veloci.
- **Nessuna accelerazione o rallentamento dopo la generazione**: produce artefatti e un ritmo innaturale.
- Il cast è approvato con una data. Da lì le impostazioni non cambiano più.

### 1.4 Audio tag e regia

- **Recitazione, non lettura.** Ogni battuta ha un'indicazione in inglese tra parentesi quadre, per personaggio o per battuta, scelta dal contesto della scena. Esempi: `[cocky, ironic]`, `[bored cashier, sing-song]`. Non si copia dal doppiaggio originale.
- **I tag si mandano solo ai modelli che li recitano (v3/v4).** I modelli precedenti li leggono ad alta voce. La trascrizione di controllo rileva i tag letti.
- **Niente sussurri né voci "inquietanti"**: anche le battute misteriose vanno a voce piena, perché i sussurri escono male e sotto la musica non si sentono.
- Accenti e parlate volute (es. un personaggio che dice "L" al posto di "R") si segnano nella regia. Il trascrittore poi "corregge" la parola, quindi in quei casi l'avviso del controllo non conta.

### 1.5 Testo detto e sottotitolo

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

### 1.6 Pause e tempi

- I silenzi si tolgono a entrambi i capi (`silenceremove` a -45 dB, avanti e con `areverse`).
- Dopo una battuta che finisce con `. ! ? …` si aggiungono **0,6 s**. Se la frase continua nella battuta successiva, **0,15 s**. Tra i pezzi composti di una stessa frase, **0,05 s** (un respiro).
- **Tempi naturali.** Nelle scene animate il motore fa partire il comando successivo quando finisce il suono, così la scena segue la durata dell'audio italiano. Forzare la durata dell'originale inglese richiedeva accelerazioni fino a 1,25x, ed è stato scartato.
- **La durata deve stare nel tempo del testo a schermo.** Le battute nei fumetti restano finché si clicca, quindi non hanno vincoli. I sottotitoli a tempo hanno quello dello script: se la voce è troppo lunga si rigenera più lenta o si accorcia il testo detto.

### 1.7 Continuità

- `previous_text` e `next_text` passano la battuta prima e quella dopo **dello stesso personaggio nella stessa scena**. Servono per le scene in sequenza e non si pagano.
- **Nei dialoghi non si usano.** *Problema:* le battute corte prendevano parole dalla battuta vicina passata come contesto. Ogni battuta di dialogo è autonoma.
- **Battute con un valore variabile** ("Ho solo N monete"). Si genera una volta la parte fissa, con i tag. Il numero si genera da solo, in cifre, con il resto della frase come contesto, così l'intonazione combacia. Poi si compone in locale, con la chiave del testo che contiene il numero, che il motore cerca per prima.
  *Risultato:* 390 caratteri invece di 5.956, 131 crediti invece di ~2.600, 98 battute tutte verificate con la trascrizione.

### 1.8 Controllo dopo la generazione

- Ogni battuta nuova viene trascritta (speech-to-text, lingua italiana, senza tag degli eventi audio) e confrontata con il testo detto. Se il WER supera il **20%** viene segnalata.
- Il controllo trova parole mancanti, tag letti ad alta voce e pronunce sbagliate.
- Falsi positivi noti: nomi propri trascritti con un'altra grafia e parlate volute.
- Una modalità "controlla" ritrascrive le registrazioni esistenti senza generare nulla.

### 1.9 Battute da non registrare

- Messaggi per chi prova il gioco (debug, tester) e righe senza lettere.
- Righe con un valore variabile, che si fanno con il metodo dei pezzi (§1.7).
- Suoni senza sottotitolo (versi, folla): sono effetti, non parlato.
- Personaggi senza voce nel cast: il rapporto li elenca e li salta.
- Le battute escluse si elencano in un documento per capitolo, con il motivo.

### 1.10 Crediti, preventivi, rifacimenti

- **Costo reale: circa 0,4 crediti a carattere**, tag compresi. Per esempio, 45.000 caratteri sono costati ~19.200 crediti; un rifacimento di 232 caratteri ne è costato 92. Il preventivo si fa con (caratteri + tag) × ~0,43. Il "1 carattere = 1 credito" della documentazione generale sovrastima.
- **Effetti sonori: ~10 crediti al secondo.**
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

### 1.11 Lotti con GitHub Actions

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

### 1.12 Attese delle voci negli script: sempre interrompibili

Se uno script aspetta la fine della voce prima di proseguire, **un clic o un tasto deve sbloccarlo**.
*Problema:* su alcuni backend audio la fine del suono non viene segnalata, e lo script di una scena restava fermo per sempre.

---

### 1.13 Seconda prova: stime, tipi di battuta, sincronia labiale
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

## 2. Correzione dei testi

- **I file originali non si toccano.** Le correzioni stanno in un file di testi della patch, indicizzato per chiave del testo originale, che il motore carica sopra l'originale.
- **Base e correzioni separate.** C'è un JSON base (battute ed etichette) e più file di correzioni manuali `(indice, vecchio, nuovo)`, applicate in ordine.
  - Se il "vecchio" non si trova, la correzione viene **segnalata** e non applicata in silenzio.
  - Una lista di refusi globali vale ovunque, anche nelle etichette.
  - Una tabella sostituisce le etichette intere.
- **Correzione automatica degli accenti**: l'apostrofo al posto dell'accento diventa una lettera accentata (`e'` → `è`; `perche'` → `perché`, con l'acuto). Restano esclusi `po'`, `be'`, `di'`, `da'` e i passaggi tra virgolette semplici.
- Si correggono refusi, punteggiatura e spazi (`..` → `...`, ` ?` → `?`, virgole dei vocativi) e si traducono le battute rimaste in inglese.
- **Si preservano** giochi di parole, nomi storpiati, parlate e accenti voluti dei personaggi, e il lettering stilizzato del gioco. Non sono refusi.
- **Non si toccano segnaposto e separatori** del formato (`%valore`, `/`).
- **Set di caratteri**: i caratteri fuori dalla codepage del gioco (CP850/CP437) non si vedono.
- **Le chiavi restano quelle del testo originale**, che servono anche per le voci.
- Si genera un elenco leggibile di tutte le correzioni, perché l'utente possa rivederle.
- I testi degli script che non sono nel JSON base si correggono con coppie `(testo originale esatto, testo corretto)`. Lo stesso vale per le differenze tra edizioni.
- **Le correzioni che non sono solo testo** (ritratto di chi parla, battuta attribuita al personaggio sbagliato, scene tagliate) diventano file di dati della patch, mai eccezioni nel codice del motore.
- Si prova con i font HD e con quelli bitmap originali.

---

## 3. Normalizzazione di audio e musica

Regola generalizzata (21/10/2026): le tracce si **normalizzano per gruppo** (musica, effetti,
parlato: musica e parlato file per file, effetti con un guadagno unico per il gruppo, così resta
la differenza voluta tra un effetto piano e uno forte) e **poi** si fissa il **livello di mix**
tra i gruppi, scelto ascoltando prove con musica, effetto e battuta insieme. I valori sotto sono
quelli scelti nel banco di prova.

| Tipo | Livello | Dettagli |
|---|---|---|
| Voci | **-18 LUFS** | `loudnorm=I=-18:TP=-1.5:LRA=11`, mono 44,1 kHz, OGG Vorbis |
| Effetti | **massimo -16 LUFS** | stesso livello dell'originale ma mai sopra; `alimiter=limit=0.89` |
| Musica (CD e MIDI) | **-25 LUFS** | guadagno limitato a ±8 dB; `adeclip` sulle tracce che saturano; limiter; Vorbis q6 |

- *Problema risolto:* la musica copriva il parlato. Con circa 7 dB di distanza dalle voci il parlato resta intelligibile.
- **Effetti rifatti con ElevenLabs Sound Effects**: stessa durata e loudness dell'originale, eventuale `loop`, descrizione in inglese.
  - La descrizione si scrive da ciò che succede nella scena e da ciò che si sente, **non dal nome del file**. *Problema:* un file chiamato "sparo" era in realtà un'esplosione.
- **Rimasterizzazione dei campioni PCM a 8 bit originali**:
  - offset DC tolto;
  - riduzione del fruscio di quantizzazione (denoiser FFT con la soglia al livello di rumore degli 8 bit);
  - ricampionamento polifase a 44,1 kHz, senza immagini oltre la banda originale;
  - limiter morbido.

  La frequenza di riproduzione non è nel file ma nello script che lo suona, quindi si produce un file per ogni coppia (suono, frequenza) usata. Il motore usa il file nuovo se esiste e altrimenti torna all'originale.
- Musica MIDI **lineare** convertita in WAV con FluidSynth e una soundfont, poi normalizzata come le tracce CD (quella a comando dinamico resta al motore: §3.1b).

---

### 3.1 Musica in blocchi con più varianti
Nella seconda prova ogni suono del motore conteneva più versioni (MT-32/General MIDI, AdLib,
altoparlante, a volte campioni digitali) e non c'erano tracce CD: si estrae la variante più vicina
al General MIDI come .mid standard e `rstool.py audio midi-classify` separa brani ed effetti
(brano: ≥ 20 s e ≥ 80 note). Alcuni estrattori scrivono una lunghezza di traccia sbagliata: il
parser non legge oltre la fine del file. Con la musica interattiva (punti di ripetizione) la
durata dei file sovrastima l'ascolto: i minuti sono un limite superiore.

### 3.1b Musica MIDI dinamica: strategia "orchestra"
Regola (decisione dell'utente, 22/10/2026): quando la musica è MIDI **a comando dinamico** (salti,
cicli, volumi e trasposizioni delle parti decisi dagli script, effetti MIDI sullo stesso
sintetizzatore) il MIDI **resta al motore** e si rifà il **SoundFont**: niente rendering in file,
niente generatori di musica. Nel banco di prova un brano di 36 s come file suonava 149 s di fila
nel motore.
- *Problema:* con FluidSynth e un banco GM la musica suonava "acuta e finta". Diagnosi, in
  ordine: (1) note uguali per canale tra le versioni del brano (nessun errore d'ottava, nessuna
  trasposizione delle parti); (2) la tabella di conversione dei programmi del motore manda due
  timbri al posto sbagliato (tromba con sordina per una tromba aperta, sul canale più forte;
  ocarina per un flauto); (3) la curva di velocità GM attenua le note piano molto più del modulo
  d'epoca: corni, archi e batteria d'accompagnamento scendono 10-15 dB e sotto 250 Hz resta il
  4% dell'energia (35% nell'originale, 28% nel riferimento orchestrale); (4) la prova offline non
  aveva la mandata di riverbero che il motore manda davvero.
- *Soluzione:* SoundFont composito da ricetta (`rstool.py audio sf2-compose`): base GM libera
  (licenza MIT) + ottoni e timpani da un banco orchestrale libero (CC Sampling Plus / CC BY:
  autore nei crediti), slot 59 e 79 corretti (usati nel gioco solo dai programmi sbagliati),
  modulatore velocità→attenuazione -480 cB, sala con coda ~3 s nelle impostazioni del motore.
  Risultato: sotto 250 Hz dal 4% al 21%, nota dominante scesa di due ottave come nel
  riferimento. Variante leggera sf3 (~40 MB) per web/telefono con le sole correzioni.
- Misure con `audio midi-diagnose` (canali, programmi, curva) e `audio bands` (bande, baricentro,
  ottave gravi); livello vero misurato registrando il motore (driver audio su disco), poi
  `midi_gain` per stare ~7 dB sotto il parlato. Una curva più dolce alza il livello di 4-11 dB a
  pari guadagno. In ScummVM la larghezza del riverbero FluidSynth è divisa per 10 (gli altri
  parametri per 100).
- Bug corretti negli strumenti: clip < 400 ms misurate a -70 LUFS (ora guadagno unico misurato
  sulla concatenazione), `--rates` con un numero semplice, FluidSynth dato per assente quando
  c'era solo la libreria.

### 3.2 Manuale, guida agli indizi e provenienza dei file
- I PDF del manuale e della guida erano **solo immagini** (`pdftotext` 0 caratteri); tesseract a
  250 dpi dava un testo quasi pulito: `rstool.py manual ocr <pdf> --out <cartella>`. Una guida agli
  indizi a domande progressive è la fonte migliore per la struttura a livelli degli aiuti.
- Tra i file forniti c'era un collegamento a un sito di redistribuzione: `engine detect` ora
  segnala i collegamenti a siti di terze parti, e l'orchestratore chiede all'utente di confermare
  la provenienza dalla sua copia.

## 4. Flusso di lavoro con agenti

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

## Errori da non ripetere

- Dedurre chi parla dal nome della stanza o del file.
- Applicare un'eccezione di attribuzione anche alle risposte che condividono l'id della domanda.
- Estrarre il copione da un'edizione diversa da quella dell'utente: le chiavi non combaciano.
- Normalizzare male i nomi dei file con simboli (`&`): un personaggio senza voce passa inosservato.
- Passare le battute vicine come contesto nei dialoghi: le battute corte ne copiano parole.
- Mandare audio tag a modelli che li leggono ad alta voce.
- Accelerare o rallentare l'audio dopo la generazione invece di impostare la velocità nella voce.
- Usare sussurri o voci "misteriose" sotto la musica.
- Fidarsi della misura automatica del riverbero per scegliere una voce.
- Stimare i crediti con 1 carattere = 1 credito (in pratica ~0,4), o non registrare spesa e rimanenze.
- Riprovare in automatico una chiamata a pagamento fallita.
- Generare un capitolo intero prima che l'utente abbia approvato cast e preventivo.
- Pagare un rifacimento quando esiste una copia gratuita equivalente.
- Generare ogni variante di una battuta con un numero invece di comporla dai pezzi.
- Descrivere un effetto sonoro dal nome del file invece che dalla scena.
- Lasciare la musica allo stesso livello delle voci.
- Attese delle voci non interrompibili negli script.
- Correggere contenuto di gioco (testi, ritratti, scene) nel codice del motore invece che nei dati della patch.
- Correzioni di testo che falliscono in silenzio quando il testo da sostituire non c'è.
- Commit diretti su `main`, tag riusati o spostati, rilasci dichiarati prima della verifica degli asset.
- Un hook che segnala come "in sospeso" un ramo nuovo senza commit propri, o che blocca in ciclo.
- Push di file grandi in un unico blocco (errore HTTP 413).
