---
name: chiusura-lavoro
description: Chiudere ogni lavoro completato - aggiornare la documentazione pertinente, verificare, committare, fare push e aprire o aggiornare la PR. Da usare alla fine di ogni modifica e quando l'hook Stop segnala lavoro in sospeso.
---
1. Documentazione, secondo cosa è cambiato:
   | Cambiato | Aggiorna |
   |---|---|
   | motore | `docs/architettura.md`, `docs/test.md` (caso di regressione) |
   | formati o file della patch | `docs/formati.md` |
   | strumenti | `docs/strumenti.md` |
   | voci / testi | `docs/voci.md`, rapporto del capitolo |
   | build / CI / rilascio | `docs/build.md`, `docs/rilascio.md` |
   | sempre | `docs/stato.md`: bug corretto → "In verifica" finché l'utente non lo conferma giocando; decisioni con data assoluta (gg/mm/aaaa) |
2. Verifiche: la patch del motore si applica da zero; nessun dato privato o segreto in posti
   pubblici; file < 50 MB per push (evita HTTP 413); test eseguiti davvero (un test non eseguito
   si dichiara come tale).
3. Ramo `fix/…`, `feat/…` o `docs/…` da `origin/main` aggiornato; un commit per unità logica.
4. Fai rileggere il diff all'agente `revisore` prima della PR.
5. Push e PR: cosa cambia, come provarlo, test eseguiti e **non** eseguiti. L'utente unisce.
