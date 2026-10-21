---
name: localization
description: Gestisce testi e lingue di un'avventura d'epoca da rimasterizzare — verifica le lingue esistenti, estrae il copione, corregge refusi e accenti, traduce nelle lingue richieste mantenendo tono, giochi di parole e vincoli di spazio, e prepara i glifi per i font HD. Usala quando l'utente chiede lingue particolari o una correzione dei testi.
---

# Localizzazione

## 1. Lingue disponibili
- Ufficiali: tabelle di rilevamento del motore (es. flag `GF_LANG_*` in ScummVM), cartelle
  lingua nei dati (cartelle per lingua), basi dati pubbliche delle edizioni pubblicate.
- Amatoriali: siti e forum di traduzioni (verifica licenza e autori; si riusano solo con
  permesso, citandoli nei crediti).
Riporta all'orchestratore: per ogni lingua richiesta → ufficiale / amatoriale / assente.

## 2. Estrazione del copione
Dal Remaster Layer: con `remaster_dump=<cartella>` ogni stringa passata a `text()` finisce in
`<cartella>/text.jsonl` con il contesto (luogo, personaggio, tipo: fumetto, risposta, etichetta,
menu) — insieme al passaggio del driver automatico che "tocca" tutte le zone. In alternativa
un parser dei file di script del motore che scriva lo stesso JSONL.
`rstool.py text catalog <dump>/text.jsonl --lang it --out text/catalog-it.tsv` crea il catalogo:
`chiave · lingua sorgente · testo · contesto · personaggio · larghezza max (px) · stato`.

## 3. Correzione della lingua originale
**Prima di correggere**, compila `text/gag.tsv`: parlate e storpiature **volute** che non sono
refusi (accenti stranieri imitati, la parlata impastata di un ubriaco, nomi parodia di
persone o marchi, scritte in un alfabeto finto). Falla confermare all'utente: quelle righe non si
toccano, e il doppiaggio le recita così.
Poi: refusi, accenti scritti come apostrofi (`e'` → `è`, con le eccezioni `po'`, `be'`, `di'`,
`da'` e le citazioni tra apici),
punteggiatura (`rstool.py text accents` per gli apostrofi). Mai riscrivere battute: solo errori
evidenti, nella colonna `text` del catalogo. Correggi anche:
- battute **rimaste in un'altra lingua** nell'edizione dell'utente → traducile nello stesso registro;
- sottotitoli rotti negli script (es. una riga che mostra solo la prima parola);
- non cambiare i codici del motore (`/` a capo forzato, segnaposto `%nome` e simili).
Una correzione il cui testo "vecchio" non si trova va **segnalata**, mai saltata in silenzio.
Il copione si estrae dall'**edizione dell'utente**: un'altra edizione ha frasi diverse e quindi
chiavi diverse. Nel progetto di riferimento le correzioni sono state circa un migliaio: preparale come elenco leggibile (`correzioni.txt`:
vecchio → nuovo) perché l'utente possa scorrerle. Poi
`rstool.py text export text/catalog-<lang>.tsv --out remaster/text/<lang>.tsv` (con
`--source-if-empty` per la lingua originale, così le righe non corrette restano uguali).

## 4. Traduzione (la fai tu, a lotti per scena)
- Prima di tradurre crea `text/glossary-<lang>.tsv` (nomi propri, oggetti d'inventario,
  luoghi, tormentoni) e `text/voices.md` (registro di ogni personaggio). Fallo approvare.
- Traduci per scena, non per riga: le battute si rispondono. Mantieni giochi di parole
  adattandoli (annota in `note` quando un gioco di parole è stato sostituito).
- Rispetta la **larghezza massima** del riquadro (il tool misura con il font HD:
  `rstool.py text check text/catalog-<lang>.tsv --font remaster/fonts/<font>.dat`); se sfora,
  riformula (il Layer comune non comprime il testo).
- Etichette degli oggetti e verbi dell'interfaccia: brevi e coerenti col glossario.
- Testi dentro le immagini (cartelli, titoli): elencali in `text/in-image.tsv`; li
  ridisegna `hd-graphics` (fondale localizzato `<scena>.<lang>.png`).

## 5. Glifi
`rstool.py text glyphs text/*.tsv` elenca i caratteri usati per lingua → passali a
`rstool.py font build`. Codepage: la codepage del gioco se basta (CP437/850 per l'Europa
occidentale), altrimenti font per lingua (`fonts/<font>.<lang>.dat`) e testi in UTF-8
convertiti dal Layer.

## 5b. Contenuti tagliati
Confronta gli script della lingua dell'utente con quelli delle altre lingue sul disco: le
edizioni localizzate a volte tagliano scene (con gli script della lingua comunque presenti sul
disco). Il ripristino si fa con un file dati della patch (deviazioni tra stanze), non nel codice. Segnalalo all'orchestratore: il ripristino si decide con
l'utente e si fa nel motore (skill `engine-integration`, §1c).

## 6. Revisione
Per ogni lingua: rilettura completa di un secondo agente (non quello che ha tradotto) con
il copione originale a fianco; poi passaggio del driver automatico con screenshot dei
fumetti per scovare troncamenti.
