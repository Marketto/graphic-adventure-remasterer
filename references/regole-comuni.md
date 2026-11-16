# Regole comuni (fonte unica)

Valgono per tutte le skill e gli agenti. Le skill le richiamano con una riga e non le ripetono.

1. **Prima l'uso, poi il lavoro.** Prima di elaborare o generare un media (immagine, sprite, effetto, voce, brano) si verifica che il gioco lo usi: `rstool.py usage scan`, poi `usage gate` sul lotto.
   - Priorità: usato, poi usabile (solo in righe commentate, per la versione extended), poi mai usato (non si fa).
   - Nel preventivo lo stato è indicato voce per voce.
2. **Spese solo con approvazione.** ElevenLabs, fal.ai, Gemini e simili: prima una stima gratuita, poi il preventivo, poi l'ok esplicito dell'utente.
   - Ogni chiamata a pagamento si fa una volta sola: su errore ci si ferma e si spiega, senza ritentare da soli.
   - Ogni spesa si registra con `project spend`.
3. **Motore e contenuto separati.** Nel motore vanno solo meccanismi generici: nessuna eccezione per una stanza, una battuta o un oggetto. Le correzioni stanno nei file della patch. I file originali non si toccano.
4. **Stile da preservare.** Alfabeti finti, accenti e parlate dei personaggi, gag nei testi e refusi voluti non si correggono.
5. **Scelte dell'utente su una pagina.** Tra più varianti l'utente sceglie da una pagina locale (`rstool.py review choose`, o la galleria specifica dell'area come `review gallery` per il 16:9): variante, "altro" o nota per ogni voce, poi incolla in chat il messaggio pronto.
   - Si propone senza sostituire: l'originale o la versione di prima restano tra le scelte.
6. **Chi parla davvero.** Ritratto mostrato, personaggi giocabili, genere ed età della voce: `voice speaker-audit` prima di ogni lotto.
7. **Repository.**
   - Rami e PR verso `main`, mai commit diretti.
   - Prima del commit: `git status` per i file cancellati non voluti (gli hook di `project hooks` bloccano le cancellazioni grandi).
   - La roadmap con emoji (`project roadmap`) si aggiorna nella stessa PR.
   - A "come va?" si risponde con una tabella: voce, stato, avanzamento, tempo stimato.
8. **Dati del gioco privati.** Originali e derivati (sprite, testi, voci, script) solo nel repository privato del gioco. Mai su pagine pubbliche, artifact pubblici, gist o release pubbliche.
9. **L'utente può essere al telefono.** Messaggi brevi, pagine leggere che si aprono su mobile, una domanda alla volta.
10. **Agenti.** Un agente per area indipendente, ciascuno con un budget di token (sotto i 200k). Chi coordina integra, documenta e chiude. Gli agenti non committano da soli.
