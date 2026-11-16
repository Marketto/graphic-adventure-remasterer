# Driver di test automatico e casi di regressione

- **Driver nel motore**, attivo solo con una variabile d'ambiente che punta a un file di comandi.

  | Gruppo | Comandi | Note |
  |---|---|---|
  | Mouse | `move/click/rclick/rhold/rtap x y` | coordinate di gioco, anche negative o >639 per le bande; `rtap` = pressione e rilascio nello stesso frame |
  | Tempo, tastiera, catture | `wait N` (frame), `key`, `shot file.png`, `time`, `quit` | |
  | Spostamenti | `loc <stanza> [parte]`, `ingame` | `ingame` clicca finché il gioco torna interattivo |
  | Ispezione | `poke [doors]`, `zones`, `zoneon/zoneoff`, `scene` | `poke` clicca tutte le zone; `scene` dà l'ordine di disegno con Z |
  | Stato | `state`, `flag`, `item`, `flags`, `hintlog`, `save n` / `load n` | `state`: modo input, oggetto in mano, personaggio, stanza, scroll, zona sotto il puntatore; `flag`/`item` impostano lo stato, `flags` lo legge; `hintlog`: aiuto che H mostrerebbe |
  | Configurazione e menu | `conf chiave valore`, `gui w:<ms> k:<tasto> shot:<file>` | `gui` pilota e cattura i menu di ScummVM; l'ultimo passo deve chiudere il menu |
  | Prestazioni | `framelog on/off`, `verifyscroll on/all/off`, `fullredraw` | `framelog`: ms di disegno, pixel ricomposti, frame spostato |
  | Mouse dopo un salto | `mouseon` | riattiva il mouse spento da una scena interrotta |

- **Trappola trovata**: in ScummVM `warpMouse` cancella gli eventi del mouse ancora in coda. Il driver deve muovere il puntatore solo col primo evento di ogni comando. Prima i clic simulati perdevano la pressione e i test dell'inventario non potevano funzionare.
- **Script di supporto**:
  - `at.sh`: esegue un file di comandi e riassume warning ed errori. Lavora su una copia della configurazione (ScummVM la riscrive all'uscita) e su una cartella di salvataggi isolata.
  - `atgdb.sh`: come sopra, con backtrace in caso di crash.
  - `sweep.sh`: visita tutte le stanze di una parte.
  - `fuzz.sh`: visita le stanze e clicca tutte le zone; serve anche a estrarre gli sprite.
- **Entrare a metà**: prima si salta alla prima stanza della parte, che imposta personaggio e inventario, poi alla stanza voluta. Un salto diretto lascia lo stato incoerente.
- **Due configurazioni sempre**: originale e HD. Ogni correzione si prova in entrambe.
- **Casi di regressione**: per ogni bug corretto, un file di comandi in `tools/test/casi/` con l'atteso scritto nella documentazione. L'atteso è un valore nel log (`state mode 3`, `hover <zona>`, `SHIFTCHECK differing=0`, `HINT #i`) o uno screenshot da confrontare. A questi si aggiunge una checklist manuale per ciò che richiede occhio o mani (trackpad, telefono).
- **Finestre modali**: il driver video `dummy` non le cattura. Su Linux si usa `ffmpeg -f x11grab` sul display Xvfb.
