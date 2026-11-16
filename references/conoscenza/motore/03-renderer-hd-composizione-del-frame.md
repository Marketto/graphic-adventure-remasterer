# Renderer HD: composizione del frame

- **Il gioco resta a bassa risoluzione**: la logica, gli script, le maschere e il clipping lavorano sempre sul frame originale a 8 bit. Il renderer HD produce a ogni frame un'immagine true color a scala intera (3x; 2x supportata).
- **Sfondo HD per corrispondenza**: un pixel prende lo sfondo HD solo se nel frame 8 bit coincide con il pixel dello sfondo originale. Tutto il resto (sprite, effetti, testo non catturato) passa da un filtro sugli indici (xBR 3x, oppure Scale3x).
  - Perché: è robusto a qualunque cosa il gioco disegni sopra lo sfondo, senza conoscere la semantica degli script.
- **Palette per indice**: per ogni colore si confronta la palette di riferimento con quella corrente. Il risultato è una delle quattro modalità che seguono.
  - Uguale.
  - Dissolvenza: fattore applicato all'HD.
  - Grigio: vista in bianco e nero, valida solo se il colore non diventa più chiaro.
  - Ciclo di colore: il pixel HD si sposta della differenza, con un alone morbido sulle accensioni.
  - Qualsiasi altro caso: si usa la bassa risoluzione.
  - Perché: le dissolvenze e i cicli di palette dell'originale continuano a funzionare in HD.
- **Ridisegno a tessere 16x16**: si ricompone solo dove il frame 8 bit **o** gli id degli sprite sono cambiati.
  - Perché gli id: due fotogrammi diversi possono avere gli stessi pixel in una tessera ma immagini HD diverse. Se si controllano solo i pixel, una testa che si gira lascia il collo del fotogramma precedente.
- **Commutazione classica/HD al volo** con un tasto. In modalità classica: frame ingrandito senza filtri, niente sprite né testi HD. I testi catturati conservano l'originale e vengono ridisegnati col font bitmap, salvando i pixel sotto. Anche la musica riprende dallo stesso punto (seek dell'OGG, ricerca del tick per il MIDI).
