# Sprite HD tramite buffer degli id

- **Chiave di un fotogramma**: CRC32 di larghezza, altezza e pixel decodificati. È indipendente dal file e dalla posizione.
- **Buffer degli id**: i blitter originali (senza maschera, con maschera, scalato) scrivono per ogni pixel `slot<<20 | sx<<10 | sy` in un buffer grande quanto il backbuffer. La composizione campiona lo sprite HD nel pixel sorgente corrispondente.
  - Perché: maschere di priorità, clipping, scala prospettica e occlusione si ereditano gratis dal blitter originale, senza reimplementarli.
- **Due livelli** (sprite in cima e sprite sotto): i bordi semitrasparenti di uno sprite HD si fondono con l'immagine HD dello sprite sotto, non col pixel ingrandito. Evita gli scalini tra testa e corpo che cambiano a ogni fotogramma.
- **Bordi**: l'alpha si ricava dalla maschera originale sfocata (gaussiana σ≈0,65 px), campionata bilineare, con soglia morbida stretta. Gli scalini diventano curve. Dove l'alpha HD è 0 si vede l'HD sottostante. L'alpha dei JPEG si ricostruisce dalla sagoma (bilineare + smoothstep 0,3–0,7).
- **Prospettiva**: uno sprite scalato si ricampiona bilineare nella posizione esatta, invece di ripetere o saltare righe come l'originale. Uno slot per disegno.
- **Ripiego**: se un colore del fotogramma non è mappabile sulla palette corrente, si usa lo sprite originale.
- **Cache** in memoria limitata (96 MB). Un'opzione da sviluppatore scarica i fotogrammi visti, per alimentare la pipeline di rimasterizzazione (vedi `fuzz` nel §13).
