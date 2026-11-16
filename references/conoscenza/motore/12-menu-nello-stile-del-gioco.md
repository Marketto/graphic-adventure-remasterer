# Menu nello stile del gioco

Regola generalizzata: tutta l'interfaccia che il motore aggiunge (menu, salvataggi, opzioni,
aiuti, manuale) prende colori e font dall'interfaccia originale del gioco.

- **Tema GUI dedicato** (archivio zip del tema): colori, pulsanti e font ricavati dallo stile del gioco, generati da uno script. Il logo è rimpicciolito con un filtro.
  - Un'etichetta più larga del pulsante passa al font normale invece di essere tagliata.
- **FreeType nella build web**: con i soli font bitmap, alla scala del telefono (~2,5x) il menu era a blocchi.
- **Senza FreeType**: si preferisce il `.bdf` alla sua cache `.fcc`, che non ha dimensioni né nomi. Ingrandire la cache faceva cadere l'avvio successivo.
- **Niente "Torna a elenco giochi"**: la capacità corrispondente non viene dichiarata e il pulsante sparisce, invece di restare disattivato.
- **Versione della patch** nel menu principale, letta da un `VERSIONE.txt` nel pacchetto (assente: niente). Non c'è più bisogno di chiedere al giocatore quale versione usa.
