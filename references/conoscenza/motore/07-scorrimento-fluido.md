# Scorrimento fluido

- **Problema**: l'originale sposta lo sfondo di 32 px (8 in verticale) per passo di gioco. Lo scorrimento veniva eseguito a ogni fotogramma, quindi a salti di 32 px. In HD questo significava una ricomposizione completa per fotogramma (~90 ms a 3x, cioè ~10 fps).
- **Soluzione**: la stessa distanza alla stessa velocità del DOS, ma suddivisa in pochi pixel per fotogramma, e 60 fps solo durante lo scorrimento. Il personaggio e lo sfondo sono interpolati entrambi nel tempo, in coordinate della stanza, così non tremolano l'uno rispetto all'altro.
- **Spostamento della finestra HD**: l'immagine composta, il frame 8 bit e gli id del frame precedente vengono spostati del delta. Si ricompongono solo:
  - la striscia scoperta;
  - i bordi (il filtro usa 2 px di vicinato);
  - le colonne fuori dallo sfondo;
  - i testi;
  - le tessere cambiate.

  Sono ~20k pixel invece di ~285k. Lo scorrimento è a pixel interi di gioco: a 10–20 px per fotogramma non serve un sotto-pixel, che il frame 8 bit non potrebbe comunque rappresentare.
- **Bug collaterali trovati**: un contatore senza segno mandava lo scorrimento a sinistra fino al bordo della stanza invece di fermarsi dopo la distanza chiesta. Uno scorrimento in corso non deve passare alla stanza successiva.
- **Verifica**: una modalità del driver ricompone da zero ogni fotogramma scorso e lo confronta con quello spostato (`differing=0` atteso).
