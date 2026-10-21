---
name: bug-gioco
description: Analizzare e correggere un problema segnalato giocando (crash, input, grafica, audio, script bloccati) - dalla stanza agli script originali, al codice del motore, alla riproduzione con il driver di test e a un caso di regressione.
---
1. Riproduci: stanza e azioni dell'utente → file di comandi per il driver di test (entra prima
   nella stanza iniziale della parte, poi salta a quella voluta); log e screenshot in configurazione
   originale **e** remaster.
2. Leggi gli script originali della stanza (lo stato atteso), poi il codice del motore.
3. Cerca se è una regressione: storia della patch (`git log -p -- engine/patches`).
4. Correggi nel motore solo il meccanismo; se il problema è di contenuto, il dato va nei file della
   patch. Regola d'ordine o di tempo: ricavala dall'originale (DOSBox), non inventarla.
5. Aggiungi un caso in `tools/test/casi/` con l'atteso (valore nel log o screenshot).
6. Rigenera la patch dal sorgente (`git add -A && git diff --cached <commit base>`), mai a mano;
   verifica che si applichi da zero. Chiudi con `chiusura-lavoro`.
