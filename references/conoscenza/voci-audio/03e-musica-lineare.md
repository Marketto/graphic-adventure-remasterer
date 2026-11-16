# Musica lineare: riorchestrazione e ibrido con il CD

Vale per brani suonati per intero o in ciclo (tracce CD, MIDI lineari). Per la musica MIDI dinamica
(il motore salta, ripete, cambia i volumi) vale la strategia "orchestra" (`03b`); la tabella in fondo
dice cosa si riusa.

- **Inventario prima di tutto**: brani citati dagli script (usati davvero, `usage scan`), solo CD, solo MIDI o tutti e due, varianti con lo stesso nome in parti diverse. Il MIDI è spesso un arrangiamento 2-8 volte più lungo del CD.
- **Strade che di solito non convincono**:
  - render General MIDI semplice;
  - filtri sul CD finito (EQ, exciter, riverbero, stereo allargato);
  - campioni senza loop, che lasciano mancare le note lunghe;
  - tappeto aggiunto sotto il CD senza la stessa sala.

  La lezione: si lavora sulle note del MIDI, non sullo stereo finito.
- **Riorchestrazione con campioni veri** (librerie libere, per esempio VSCO-2 CE in CC0, rese con sfizz):
  - strati di dinamica e CC1/CC11;
  - inizio del campione dove l'inviluppo raggiunge ~30% del picco;
  - note legate su una traccia separata;
  - altezze verificate con l'autocorrelazione, perché alcune librerie nominano il Do centrale un'ottava sotto.
- **Ruoli dei canali**:
  - la melodia è il canale che sta più spesso sopra gli altri, poi il più forte e il più denso (non il più acuto in media: quello sceglie i controcanti);
  - un canale di pianoforte si divide per registro;
  - il metro si ricava dalle ripetizioni.
- **Non inventare note**:
  - ogni nota aggiunta è una nota del brano nello stesso istante, al massimo spostata di ottava, e lo spostamento vale per tutta la frase;
  - una riserva raccoglie le note che nessuno strato usa.
- **Strumenti di stile solo come raddoppi**:
  - coro sulle note lunghe dei passaggi densi;
  - tremolo di uno strumento popolare a pizzico sulla melodia;
  - percussioni a inizio frase;
  - sempre una variante "misurata" e una "piena".

  Campioni rari ritagliati da registrazioni di accordi solo se tutte le loro note suonano già nel brano.
- **Equilibrio preso dall'originale**:
  - livello di ogni traccia rispetto alla melodia misurato su un render GM traccia per traccia;
  - variazione nel tempo entro ±6 dB, lisciata;
  - intervalli per ruolo (melodia +3/+6 dB, basso e controcanti −9/−3).

  Il problema che risolve: "sembrano due melodie sovrapposte".
- **Melodia in primo piano**: mediana melodia − accompagnamento ≥ +3 dB. Altrimenti EQ −3 dB a ~2,4 kHz e ducking leggero dell'accompagnamento. Se la soglia non è raggiunta, la verifica fallisce.
- **Ibrido con il CD** (spesso la scelta finale):
  1. CD separato con Demucs (~2× il tempo reale su CPU);
  2. il CD fa da corpo, l'orchestra va sotto a ~−6 dB;
  3. stessa sala a convoluzione (risposte all'impulso libere, crediti CC BY).
- **Allineamento CD ↔ MIDI**:
  - rapporto di tempo contro un render GM: sotto un punteggio minimo l'arrangiamento è diverso e il CD non si usa;
  - ritardo dai picchi del flusso spettrale (±6 s), deciso dal cromagramma;
  - copie del CD in fila se il MIDI è più lungo, cercate attorno alla fine della musica e non della traccia.
  - Errori tipici: segno del ritardo invertito, copia agganciata a una frase ripetuta.
- **Ciclo senza salti**: la coda dopo la fine del giro (sala, rilasci) si somma all'inizio.
- **Brani che sono effetti** (sirene, allarmi): si rifanno come l'effetto vero, seguendo nota e pitch bend.
- **Verifiche per brano**, con numeri:
  - note originali senza corrispondenza: 0;
  - note aggiunte fuori dal brano: 0;
  - nessun buco;
  - note tenute che non si spengono;
  - nessuna saturazione;
  - livello e true peak;
  - somma mono.

  Calcoli a blocchi e in float32, per contenere la memoria.
- **Confronto d'ascolto**:
  - versioni sullo stesso passaggio forte, 15-40 s, allo stesso LUFS, ognuna annunciata da una voce di sintesi ("Versione C");
  - una tabella spiega le versioni a parole;
  - lettere nuove a ogni serie e un diario delle bocciature.
- **Lotti** nell'ordine del gioco, raggruppati per carattere. Stima: 0,5-1 h per brano.
- **Interruttore nel motore**: Remastered (brano rimasterizzato → CD → MIDI) / Originale (CD → MIDI), con effetto immediato.
- **Licenze**: ogni campione CC BY va nei crediti del pacchetto.

| Tecnica | Lineare | MIDI dinamica |
|---|---|---|
| inventario, non inventare note, verifica dei timbri, confronto annunciato, licenze, brani-effetto | sì | sì |
| ibrido con il CD, allineamento, rendering in file, equilibrio nel tempo, coda del ciclo | sì | no (il MIDI resta al motore) |
