# Istruzioni per agenti AI — graphic-adventure-remasterer

Questo repository contiene la **suite agentica** (skill, agenti, strumenti, patch del motore) per
rimasterizzare avventure grafiche 2D. Lingua di lavoro: italiano.

## Regole fisse
- **Repository pubblico.** Mai nomi di giochi, personaggi, luoghi, sviluppatori, editori o motori
  proprietari; mai testi, immagini, suoni, script o dati di un gioco, neanche come esempio nei
  test o nella documentazione (usa esempi inventati). Si possono citare strumenti e servizi open
  source o commerciali (ScummVM, AGS, DOSBox, ffmpeg, ElevenLabs, fal.ai...).
- Prima di ogni commit: `python3 tools/ip_guard.py --staged` deve passare (hook in `.githooks/`,
  attivalo con `git config core.hooksPath .githooks`). Se lavorando su un gioco emergono nuovi nomi
  da proteggere, aggiungili con `python3 tools/ip_guard.py --add "<termine>"` (salvati come hash).
- Il lavoro su un gioco specifico vive in un **repository privato** del gioco, mai qui. Qui si
  portano solo tecniche e regole generalizzate (in `references/conoscenza/`, nelle skill, nel codice).
- Il codice del Remaster Layer è codice ScummVM (GPL-3.0-or-later): rispetta `AI-GUIDELINES.md`
  di ScummVM nei fork (trailer `Assisted-by:`, niente co-autorialità AI, nessuna PR upstream per
  conto dell'utente).
- Lavoro su rami e PR verso `main`; test (`python -m pytest -q tools/tests`) verdi prima della PR.

## Mappa
- `skills/remaster-orchestrator/` — il flusso completo; le altre skill sono le fasi.
- `references/conoscenza/` — tecniche del banco di prova (motore, grafica, voci/testi/audio/flusso).
- `references/asset-contract.md` — formati e chiavi degli asset (RAC v1).
- `engine/scummvm-remaster-layer/` — patch per ScummVM e guida di integrazione.
- `tools/` — `rstool.py` (pipeline), `ip_guard.py` (controllo del repository pubblico), test.
