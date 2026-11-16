# Esecuzione a pacchetti: orchestrazione e monitoraggio

Dettaglio della skill `remaster-orchestrator`.

Dalla Fase 2 in poi lavori **a pacchetti** del registro (`work_packages`), in parallelo dove le
dipendenze lo permettono (stesso gruppo `G`), altrimenti in sequenza.
- **Taglia**: ogni pacchetto è una sotto-sessione che deve restare **sotto 200k token**
  (`plan.token_budget`); `plan packages` riempie fino all'80% e spezza i lotti grandi (fondali a
  gruppi di N scene, copione per capitolo, traduzione a blocchi). Se una sotto-sessione va
  oltre, la si porta comunque a termine entro **250k** (`plan.token_hard_limit`); oltre, si ferma
  e si spezza il resto in un nuovo pacchetto.
- **Avvio**: per ogni pacchetto pronto (`rstool.py plan status` → `ready`) lancia l'agente del
  pacchetto **in background** (Agent/Task con esecuzione in background), con istruzioni
  autosufficienti: skill da seguire, unità precise (quali scene, quale capitolo), file di
  ingresso e di uscita, budget di token, cancelli da rispettare, cosa riportare (fatto, file,
  problemi, token usati). Al massimo 3-4 sotto-sessioni insieme. Registra
  `rstool.py plan update <id> --status running --task-id <id del task>`.
- **La sessione principale resta libera**: non aspettare in primo piano. Parla con l'utente e,
  quando chiede lo stato, rispondi con `rstool.py plan status` (fatti, in corso, pronti, fermi,
  falliti) e una riga per pacchetto in corso.
- **Avanzamento**: a ogni notifica o resoconto aggiorna `plan update <id> --tokens-used N
  --note "..."`; a fine pacchetto verifica il risultato (file, test) e segna `--status done`
  (o `failed` con il motivo). Gli agenti non committano: integri tu.
- **Segnali di blocco** (`plan status --stale-min 30`): nessun avanzamento entro il tempo
  (`stale`), stesso errore ripetuto, token oltre il 125% della stima (`warn_tokens`) o oltre il
  limite (`over_budget`), pacchetto `failed`.
- **Cosa fare**: `to_restart` → ferma il task se è ancora vivo, correggi le istruzioni (causa
  dell'errore, unità già fatte da saltare, pacchetto più piccolo) e rilancialo; `to_stop`
  (tentativi esauriti, limite di token superato) → fermalo, segna `stopped`, spezza o rimanda e
  **dillo all'utente** con il motivo. Ogni riavvio o arresto si scrive nella nota del pacchetto.
- I **cancelli** (galleria 16:9, cast voci, preventivo di ogni lotto a pagamento, rilascio)
  restano: un pacchetto che arriva a un cancello si ferma, prepara il materiale e lo riporta;
  chiedi tu all'utente e lanci il seguito solo dopo il sì.
