# 1g. Fluidità dei controlli (requisito)

Dettaglio della skill `engine-integration`.

Il remaster non deve avere un mouse che scatta né tasti che si ripetono. Comandi del driver da
aggiungere: `inputlog <file>` (scrive eventi ricevuti, posizione del cursore a ogni fotogramma
presentato e azioni eseguite; formato in `tools/remaster_tools/controls.py`), `mousepath x0 y0 x1
y1 ms` (movimento rettilineo a velocità costante, eventi a 120 Hz), `keyhold <tasto> ms` (tasto
tenuto premuto con la ripetizione automatica del sistema). Poi `rstool.py engine controls
qa/input.log`. Controlla, in modalità originale e remaster, a 1x e a 3x, in 4:3 e 16:9:
- **cursore**: ridisegnato a ogni fotogramma (≥ 50 Hz) e non al passo della logica; nessuna
  pausa né salto oltre il passo tipico; nessuna inversione su un percorso dritto (arrotondamenti
  nella conversione schermo → gioco, `warpMouse` che riporta indietro); in HD si muove ai pixel
  dello schermo, non a multipli della scala; ritardo ≤ 2 fotogrammi;
- **tasti**: le azioni a scatto (toggle F8, menu, inventario, salta battuta, aiuti, salva)
  avvengono una volta per pressione: ignora gli eventi con `kbdRepeat`; le azioni continue
  (scorrimento, camminata con le frecce) possono ripetersi;
- **clic**: un tocco o un clic veloce (pressione e rilascio nello stesso frame) non si perde
  e non diventa un trascinamento (soglia in pixel di gioco); doppio clic non doppia l'azione;
- sul telefono e sul web: stesso controllo con eventi touch.
Confronta anche la sensazione con l'originale sull'emulatore di riferimento (§1b): accelerazione
del mouse e velocità del puntatore non devono cambiare più del necessario.
