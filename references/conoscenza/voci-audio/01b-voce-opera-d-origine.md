# Doppiaggio: personaggi di un'opera d'origine
## Personaggi di un'opera d'origine (film, serie, cartoni)

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
