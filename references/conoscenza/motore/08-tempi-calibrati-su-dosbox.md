# Tempi calibrati su DOSBox

Regola generalizzata: il confronto si fa sulla **piattaforma di destinazione** dell'originale,
con la soluzione affidabile più vicina (DOSBox per DOS, macchina virtuale d'epoca o Wine per
Windows, emulatori cycle-exact per Amiga, Atari ST, Mac...). Le misure sotto
valgono come metodo per qualunque piattaforma.

- **Il gioco DOS non ha un timer**: ogni passo disegna e poi aspetta due ritracce verticali. La durata di un passo è quindi 2 ritracce + il tempo di disegno, limitato dalle porte VGA e non dalla CPU (identico a 40k e a 120k cicli in DOSBox).
- **Misura**: si registra DOSBox su Xvfb con `ffmpeg -f x11grab -framerate 60` e si contano i fotogrammi tra due cambi (7–8 fotogrammi a 60 fps = ~128 ms). Il mouse si pilota con `xdotool` (`autolock=false`). Valori trovati: da ~43 ms senza animazioni fino a ~160 ms con molte figure grandi.
- **Modello**: la durata del passo si stima dall'area dei fotogrammi animati a schermo, interpolando i punti misurati e arrotondando a ritracce intere (70 Hz). Un'opzione forza un valore fisso.
  - Problema risolto: a 33 ms fissi il gioco andava fino a 4 volte più veloce dell'originale.
  - Confronto ottenuto: durata di una sequenza animata entro il 2% dell'originale.
- **Logica e disegno separati**: la logica avanza ogni passo; lo schermo e l'input vanno a 30 fps (60 a scelta).
  - Nei fotogrammi intermedi gli sprite vanno rimessi nella lista di disegno, altrimenti sfarfallano.
- **Movimento fluido**: tra due passi ogni animazione si disegna a metà strada tra la posizione precedente e la nuova (un passo di ritardo; il fotogramma cambia come prima). I salti grandi (>48x32 px) non si ammorbidiscono, perché sono teletrasporti.
- **Cursore a ~120 Hz**: mentre aspetta il fotogramma il motore legge gli eventi, li rimette in coda nello stesso ordine e ridisegna solo il puntatore.
- **Suoni che comandano gli script**: i comandi legati a una zona sonora partono **quando il suono finisce**, come nell'originale. Gli effetti in loop si fermano allo scaricamento della stanza.
- **Attese bloccate**: se uno script aspetta la fine di una voce e il backend audio non la segnala, un clic o un tasto la interrompe e lo script prosegue.
