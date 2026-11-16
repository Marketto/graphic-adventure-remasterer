# Testo HD

- La funzione di disegno del font, per i font con un sostituto HD, **registra la stringa** per superficie invece di disegnarla. Quando la superficie finisce nel backbuffer, le stringhe passano al renderer. Il renderer le disegna da atlanti HD centrate nel riquadro della riga originale (i menu allineati a sinistra) e le comprime fino al 70% se più larghe.
- I colori vengono dalla palette corrente, così le dissolvenze funzionano anche sul testo. La riga evidenziata dei menu, ottenuta con uno XOR nell'originale, viene ricostruita.
- I caratteri che il font originale rende vuoti diventano spazi.
- **Prestazioni**: un testo che compare, sparisce o si muove (l'etichetta che segue il puntatore) ridisegna solo le tessere sotto la vecchia e la nuova posizione.
  - Problema risolto: prima ogni movimento del mouse con l'etichetta visibile ricomponeva la scena e il puntatore rallentava.
- **Sottotitoli**: spostati in basso, con una fascia scura semitrasparente in HD. Un'opzione ripristina la posizione originale.
- **Font**: atlanti generati da font liberi vicini allo stile originale. Gli alfabeti stilizzati dell'originale vanno preservati, non "corretti".
