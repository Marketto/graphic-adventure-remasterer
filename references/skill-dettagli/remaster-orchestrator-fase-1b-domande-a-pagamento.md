# Fase 1b — Domande solo sulle parti a pagamento, con il costo

Dettaglio della skill `remaster-orchestrator`.

Una schermata, solo se servono (`rstool.py project missing` le elenca solo a stime pronte):
- **fal.ai per le bande 16:9** (se ci sono scene da inventare): quante scene, unità × tentativi
  × prezzo dal preventivo (`ws-fal` della stima, o `rstool.py widescreen fal-estimate`), caso
  peggiore e probabile; si usa solo dove il metodo locale non convince →
  `graphics.widescreen.fal_ai` true/false;
- **barra fissa in 16:9** (insieme alle altre scelte del 16:9, se l'analisi trova verbi,
  inventario o pannelli che restano 4:3 con bande nere): opzioni A riempitivo / B barra allargata /
  C B + icone dei verbi, ognuna con esito della verifica di fattibilità, mockup gratuiti su 2 scene
  reali e stima (C con il preventivo delle icone se generate) → `graphics.widescreen.ui_bar`
  `{option, notes, icons}` (skill widescreen, «Barre fisse in 16:9»);
- **doppiaggio ElevenLabs** solo se **non esiste** il doppiaggio nella lingua dell'utente:
  caratteri del copione, crediti (~0,43 a carattere più i rifacimenti), costo indicativo e piano
  necessario; serve un account con **licenza commerciale** (`voice.license_confirmed`), il piano
  gratuito non usa la Voice Library via API; niente cloni di doppiatori reali; si procede una
  parte alla volta → `voice.enabled` true/false. **Sempre anche l'opzione per parti**: se
  l'analisi conosce le parti del gioco (`voice.parts` nei conti: capitoli, atti, dischi,
  percorsi; come trovarle in `voice-dubbing` §5a) mostra il costo di **ciascuna parte** e i
  cumulati; chiedi i crediti disponibili (`voice.credits_available`, letti con la modalità
  `verifica` gratuita) e, se non bastano per tutto, proponi: piano superiore, modello economico per
  le comparse, oppure solo le prime parti che stanno nei crediti (in ordine di gioco) → scelta in
  `voice.scope` (`{"mode": "tutto"}` o `{"mode": "parti", "parts": [...]}`). Le righe delle parti
  escluse restano originali in gioco (clip originale o sottotitolo). Parti ignote: si dice che il
  doppiaggio si spezza per lotti e che per doppiarne solo una parte va prima fatta la ricerca;
- **proporzione dei pixel** solo se `aspect-auto` ha lasciato un dubbio (`decided_by: "ask"`:
  `project missing` la elenca con la proposta, i dubbi e il foglio `review/aspect.png` da mostrare);
  se ha deciso da solo non si chiede;
- se almeno uno è sì: **tetto di spesa** totale (`budget.cap_usd`, `budget.cap_credits`);
- solo se il doppiaggio è sì e `source_work.characters` non è vuoto: per **ogni personaggio
  riconoscibile**, «voce il più simile possibile a quella dell'opera d'origine?» (nella lingua
  originale l'interprete, nelle altre il doppiatore dell'epoca) → `imitate_voice` true/false
  (`project missing` lo chiede finché è null). Il sì significa: si scelgono e regolano voci
  **esistenti** della libreria ElevenLabs, nessuna clonazione (`voice-dubbing` §2b).
Nella stessa schermata, solo se l'analisi non l'ha trovato tra i file: la copia del **manuale**
(PDF o foto) per il manuale nel remaster.
Registra ogni risposta con `rstool.py project set <chiave> <valore>` e in `decisions[]`. Ogni
spesa reale, lotto per lotto e sempre dopo il suo preventivo approvato, si registra con
`rstool.py project spend <servizio> <importo> --unit usd|credits --note "<lotto>"`, che avvisa
quando il tetto è superato (allora ci si ferma e si chiede).
