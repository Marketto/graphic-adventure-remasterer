# Input

Regola generalizzata: la **fluidità dei controlli** si verifica sempre, con un log degli eventi e
dei fotogrammi del driver: cursore ridisegnato a ogni fotogramma e non al passo della logica,
nessun salto o inversione, in HD ai pixel dello schermo; azioni a scatto (toggle, menu,
inventario) una volta per pressione, ignorando la ripetizione automatica dei tasti.

- **Clic destro breve per l'inventario**: il gesto originale è "tieni premuto, spostati, rilascia". Il gesto agevolato: rilascio entro 350 ms senza spostamento, e l'inventario resta aperto. Poi un sinistro su un oggetto lo prende, un sinistro fuori chiude, il destro chiude.
- **Soglia di trascinamento in pixel di gioco** (6 px), non in pixel dello schermo.
  - Problema risolto: in HD 3x 16:9 su una finestra o su un telefono il tremolio di un tocco valeva decine di pixel schermo e veniva preso per un trascinamento.
  - La distanza si misura tra pressione e rilascio, non sui movimenti intermedi.
- **Pressione e rilascio nello stesso frame** (tap del trackpad, touch): si usa la pressione e si rimette il rilascio in coda per il frame dopo. Altrimenti il solo rilascio non apriva nulla.
- **Combinare dall'inventario**, con un oggetto in mano:
  - il sinistro su un altro oggetto lo **prende**;
  - il destro su un secondo oggetto **tenta la combinazione**: con una coppia valida va in mano il risultato e l'inventario si chiude; con una coppia non valida l'inventario resta aperto e l'oggetto resta in mano.
  - L'oggetto in mano si identifica dal suo id, non da un indice valido solo in certi percorsi di apertura.
- **Clic durante la camminata**: cambiano la destinazione. Un'azione in sospeso aspetta l'arrivo o si annulla col nuovo clic. Una sorveglianza chiude una camminata ferma da 15 passi.
- **Esc/F5** aprono il menu di ScummVM.
- **Robustezza**: un cambio di personaggio verso una figura senza inventario mantiene l'inventario corrente. Prima il renderer dell'inventario restava scollegato e il clic destro chiudeva il gioco.
