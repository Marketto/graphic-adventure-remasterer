# Patch del motore: generazione e normalizzazione

- Il motore è una **patch unica** su un commit base fissato. Uno script scarica quel commit e la applica come modifiche non committate. Le CI fanno lo stesso.
- **Rigenerazione**: `git add -A && git diff --cached <commit base>`. Un `git diff` semplice perde i file nuovi non tracciati (renderer HD, driver di test, aiuti).
- **Mai correggere a mano i conteggi delle righe degli hunk**. Le modifiche manuali al `.patch` hanno richiesto più commit di "normalizzazione" per riallineare conteggi e contesto. La patch si rigenera sempre dal sorgente.
- **Verifica**: applicazione da zero in una cartella pulita; deve stampare `applied …`.
- **Codice comune a più giochi dello stesso motore**: le modifiche si limitano al tipo di gioco interessato e gli altri restano invariati. Correzioni minime, commenti in inglese come il resto del motore.
- Se qualcosa "non funziona più", si cerca nella storia della patch (`git log -p -- engine/patches`) il commit che l'ha introdotto.
