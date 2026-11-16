# Camera, veicoli e navigazione

- **Camera che segue il personaggio** (opzione, accesa di predefinito; spenta = comportamento originale).
  Molti motori d'epoca scorrono a scatti di mezzo schermo quando i piedi arrivano a pochi pixel dal bordo.
  - Al loro posto: zona morta al centro (circa ±10% della larghezza; in verticale la fascia dove stanno i piedi) e inseguimento morbido esponenziale (costante ~150 ms), sempre dentro i bordi della stanza, alla frequenza dello scorrimento fluido.
  - Si seguono i piedi **disegnati** (interpolati tra due passi), non quelli logici, così personaggio e sfondo si muovono insieme.
- **Gli scorrimenti decisi dagli script passano per primi**, per esempio un salto tra due vagoni. Per il resto di quella camminata la zona morta torna ai limiti originali, così la camera non annulla la scelta dello script.
- **Ingresso nella stanza.** Se la regola originale lascia il personaggio a bordo schermo o fuori, la vista parte centrata su di lui. Capita entrando da destra in una stanza larga.
- **Paesaggio che scorre dietro un veicolo** (finestrini, tetto, vagoni visti da fuori). Gli originali lo ottengono quasi sempre con un ciclo di colori.
  - Il fondale HD si ricava **dal ciclo originale, non si inventa**: ogni fase del ciclo è un disegno a sé (con ciclo a 3 colori e 4 fasi: colore = cifra k in base 3 della voce di palette).
  - Si separano i piani che si muovono a velocità diverse (alberi lontani, binari vicini) e si misura lo spostamento tra le fasi.
  - Le parti sempre coperte dal veicolo si riempiono con le colonne visibili a tutta altezza, scelte con programmazione dinamica e cucite dove la giunta si vede meno (quilting).
  - Con pochi colori netti: vettoriale (ogni colore 8x, sfocato, soglia, potrace, Lanczos), niente upscaler.
- **Verso e velocità**: dichiarare una convenzione (positivo = verso destra) e verificarla a occhio in ogni stanza. Un verso invertito è l'errore più frequente.
- **Prestazioni sui veicoli.** Le voci di palette coperte dal paesaggio HD vanno congelate: se almeno l'80% dei loro pixel di sfondo sta nel vetro, sono ferme come con `freeze`. Altrimenti un ciclo che cambia molte voci a ogni passo ricompone tutta l'immagine e il personaggio rallenta.
- **Passi di gioco arretrati.** Se un fotogramma dura più di un passo di gioco, si eseguono subito i passi scaduti (fino a 3 per fotogramma), finché stanza e modo di input non cambiano. Senza, camminata e animazioni rallentano con il disegno. Dopo una pausa lunga si riparte da adesso.
- **Zone trappola** (eseguono comandi quando i piedi entrano o escono):
  - controllare che ENTER ed EXIT non siano scambiati nel motore, confrontandoli con il senso logico degli script e con il motore gemello;
  - azzerare la trappola al cambio di stanza, perché i comandi d'uscita della stanza lasciata non devono partire nella nuova.
- **Porte strette e ultimo passo.** Verso un punto più vicino di un passo intero va fatto l'ultimo passo corto, controllando il punto d'arrivo vero e non quello del passo intero. Altrimenti il personaggio si ferma davanti a una porta larga pochi pixel.
- **Diagnosi di un blocco**:
  1. log della camminata (piedi, nodo, ostacolo);
  2. maschera di camminata e zone sovrapposte;
  3. trappole attive;
  4. caso di prova con un clic dentro la porta e uno di ritorno.

  Se i nodi originali non collegano due zone, un percorso alternativo esplora la maschera; se i piedi finiscono dentro un ostacolo, un passo di sblocco li riporta fuori.
