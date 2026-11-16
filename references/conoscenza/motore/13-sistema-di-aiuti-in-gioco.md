# Sistema di aiuti in gioco (tasto H)

- **Finestra** disegnata dal motore con i font del tema: situazione e indizio, più un pulsante "Mostra la soluzione" che la aggiunge nella stessa finestra.
  - Se H arriva durante una battuta o un dialogo, resta in attesa e la finestra si apre appena il gioco torna interattivo.
  - Nel menu principale H viene ignorato. Sul web c'è un pulsante che manda H.
- **Formato** (`hint/<lingua>.txt`, UTF-8, ripiego sulla lingua base):
  ```
  @parte N
  obiettivo: <titolo>
  fatto: <condizione>
  situazione: <dove si è, cosa si vuole>
  indizio: <spinta senza spoiler, dice dove andare>
  soluzione: <passi precisi>
  ```
- **Scelta**: si mostra il **primo obiettivo, in ordine di gioco, la cui condizione `fatto` è falsa**. Se sono tutti fatti, un messaggio generico.
- **Condizioni**: termini separati da spazio sono in AND; alternative separate da `|` sono in OR, che lega più forte (`A | B C` = (A o B) e C); `!` nega. Termini disponibili:
  - flag globale della parte;
  - flag locale di una stanza (`LF:<stanza>:<flag>`): il motore conserva i flag locali per stanza, anche nei salvataggi, e risolve il nome rileggendo la dichiarazione dello script quando non si è nella stanza;
  - oggetto nell'inventario del personaggio attuale;
  - contatore `>`, `<`, `=`;
  - stanza attuale;
  - stanza già visitata (da un registro proprio: il flag "visitata" del motore valeva solo dal secondo ingresso);
  - `sempre` / `mai`.
- **Le condizioni devono essere monotone**: una volta vere, restano vere. Un oggetto che poi si consuma va messo in OR con ciò che si ottiene dopo, altrimenti l'aiuto "torna indietro".
- **Uno stato che lo script non riesce a salvare non si vede impostandolo a mano**. Impostare un flag col driver prova la catena degli aiuti, non che il gioco lo imposti davvero. Per i passi critici bisogna rifare le azioni vere e controllare lo stato.
  - Caso reale: un bit di marcatore ("questo comando agisce sui flag globali") stava nello stesso campo dei bit dei flag. Il flag con l'indice più alto coincideva col marcatore e non veniva mai memorizzato. Correzione: marcatore in un campo separato, con le condizioni degli script invariate. I vecchi salvataggi si coprono con un'alternativa su un flag locale impostato dallo stesso comando.
