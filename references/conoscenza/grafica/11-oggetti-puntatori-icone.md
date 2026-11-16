# Oggetti, icone, puntatori e animazioni

- **Censimento prima dell'HD** (`rstool.py usage scan` sui file di sprite, oppure dump di tutti gli sprite dichiarati dalle stanze): si fa l'HD solo di ciò che il gioco carica. In un caso reale su 314 fotogrammi senza HD solo 14 erano usati; gli altri stavano in file mai caricati, cioè prove e copie.
- **Sprite "doppio + vettoriale"**:
  1. upscaler due volte;
  2. campo di distanza con segno dalla sagoma originale;
  3. tracciato potrace dei colori netti;
  4. riduzione Lanczos con alpha premoltiplicata.

  Contorni puliti e stabili tra fotogrammi. Per i dettagli piccoli (bocche, scintille, pioli) spesso il vettoriale da solo è meglio dell'upscaler.
- **Fotogrammi uniformati**: lo stesso oggetto in più fotogrammi deve avere la stessa HD dove i pixel originali coincidono, altrimenti tremola.
- **Icone dell'inventario**: un fotogramma unico "pulito" (il colore più frequente per pixel tra le occorrenze), poi l'oggetto in vettoriale. Il motore può copiare le icone senza passare dai blitter degli sprite: serve un aggancio apposito, altrimenti restano a bassa risoluzione.
- **Puntatori del mouse HD**: frecce vettoriali RGBA e l'icona HD dell'oggetto in mano sul puntatore. In modalità classica, nelle stanze in bianco e nero e nei menu resta l'originale.
- **Sprite a tempo** (un PNG HD che cambia con l'orologio, per esempio una bolla che respira) e **sprite a forma libera** (il PNG disegna oltre la sagoma originale dentro il rettangolo): meccanismi generici, dati in `gfx/spr/timed.tsv` e `freeform.tsv`.
- **Animazioni tagliate al bordo dagli autori**: in 16:9 si vede il taglio. Il motore lo segnala (`BANDCUT` nel log) e lo sprite si completa nella banda, con preventivo se serve la generazione.
- **Proporre senza sostituire**: una variante ridisegnata (più spessa, più dettagliata) va mostrata accanto all'originale nella pagina di scelta. L'utente può tenere quella di prima.
- **Insegne e scritte mancanti nelle bande**: si cercano lettere e firme inventate confrontando con l'originale 1x sulle colonne del centro, poi si fa un ritocco locale. Il testo giusto viene dagli script.
