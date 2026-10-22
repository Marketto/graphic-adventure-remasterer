---
name: engine-compat
description: Identifica il motore di un'avventura grafica d'epoca e verifica se è supportato da ScummVM o da altri interpreti open source (es. AGS), con livello di supporto, versioni, problemi noti e lavori esistenti riutilizzabili (fork, patch amatoriali, traduzioni, pacchetti HD). Usala nella fase di analisi del remaster.
---

# Compatibilità del motore e lavoro esistente

La suite non contiene elenchi di giochi o di motori: ogni informazione su un titolo si cerca
al momento, sul web e nei file dell'utente, e resta nella cartella privata del progetto.

## 1. Identificare il gioco e il motore
- Ricerca web: sviluppatore, anno, piattaforme, edizioni (floppy, CD, versione parlata, demo),
  motore usato. Annota le fonti.
- File dell'utente: `python3 ${CLAUDE_PLUGIN_ROOT}/tools/rstool.py engine detect <cartella>`
  restituisce un inventario neutro (estensioni, file più grandi, eseguibili, immagini disco,
  stringhe di copyright/versione negli eseguibili) e, se `scummvm` è installato, l'esito di
  `scummvm --detect`, la fonte più affidabile perché confronta gli MD5 con le tabelle di
  rilevamento di ScummVM. Le stringhe degli eseguibili servono a cercare il motore online.

## 2. Livello di supporto (verificalo sempre online: cambia nel tempo)
- ScummVM: elenco di compatibilità sul sito ufficiale e pagina del gioco; wiki (formati dei
  file, stato del motore); tracker dei bug; sorgenti (`engines/<id>/detection*.cpp`: flag
  `ADGF_TESTING` = in test, `ADGF_UNSTABLE` = instabile, spesso esclusi dalle build ufficiali).
- AGS: interprete open source `adventuregamestudio/ags` (giochi creati con AGS).
- Altri interpreti open source: cerca "<titolo> open source engine reimplementation".

Classifica in: **A** supportato e completabile → si lavora sul fork; **B** supportato in parte
→ prima lo si rende completabile (vedi `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/motore-e-test.md`);
**C** non supportato → serve un nuovo interprete (settimane-mesi, vedi §2b). L'emulatore o la VM
della piattaforma originale (`rstool.py engine reference --platform <piattaforma>`: DOSBox, VM
Windows d'epoca, Wine, emulatori Amiga/Atari/Mac...) serve solo come riferimento per tempi,
aspetto e controlli, non come base del remaster.

## 2b. Classe C: come impostare un nuovo interprete
Non promettere tempi: proponi all'utente uno studio di fattibilità di qualche giorno.
1. **Formati**: archivi e risorse (indice, compressione, palette, sprite, fondali, testi,
   suoni) dai file dell'utente; cerca documentazione pubblica e strumenti di estrazione open
   source esistenti. Un estrattore che produce il dump RAC (`bg/`, `spr/`, `text.jsonl`) serve
   subito alla pipeline grafica e ai testi, anche prima dell'interprete.
2. **Script**: disassemblatore degli script del gioco (opcode, parametri, salti); confronto col
   comportamento sull'emulatore di riferimento.
3. **Interprete dentro ScummVM** (nuovo motore in `engines/<id>/`): ScummVM fornisce già
   rilevamento, salvataggi, audio, input, piattaforme e il Remaster Layer. Partire da un motore
   esistente di struttura simile (fondali + sprite + script a opcode).
4. **Tappe verificabili**: mostrare la prima stanza → camminare e cliccare → primo enigma →
   prima parte completa → tutto il gioco; il driver di test e i casi di regressione dal giorno uno.
5. Rispetta la licenza e le regole di ScummVM (codice GPL, nessun asset del gioco nel fork);
   l'estrazione dagli eseguibili si fa solo dalla copia dell'utente.

## 3. Lavoro esistente da cercare
- Codice upstream e fork (GitHub), rami di sviluppatori, issue aperte sul motore.
- Patch amatoriali, correzioni dei testi, traduzioni amatoriali: controlla licenza e autori,
  si riusano solo con permesso e citandoli nei crediti.
- Remaster o pacchetti HD esistenti, per non duplicare lavoro.
- Lavori precedenti dell'utente: repository privati, documenti del suo progetto, chat passate.

## 4. Output (solo nella cartella privata del progetto)
Scrivi `analysis/engine-report.md` e aggiorna il progetto:
```
rstool.py project set engine.id <id>
rstool.py project set engine.runtime scummvm|ags|custom
rstool.py project set engine.support A|B|C
rstool.py project set engine.notes "<una riga>"
rstool.py project set existing_work '<json array di {tipo, url, licenza, riusabile}>'
```
All'orchestratore restituisci 3-4 righe: motore, supporto, versioni, lavoro riutilizzabile.
Cita le fonti (URL) nel report. Non copiare nulla di tutto ciò nel repository della suite.
