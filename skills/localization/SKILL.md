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
un parser dei file di script del motore che scriva lo stesso JSONL (estrazione senza Layer:
`rstool.py engine extract`, formato in `tools/remaster_tools/extract.py`).

**Tipi di battuta** (`kind` in `text.jsonl`), e cosa conta come **parlato** (copione da doppiare,
`voice.SPOKEN_KINDS`):
| Tipo | Cos'è | Parlato |
|---|---|---|
| `balloon` | fumetto o battuta di un personaggio | sì |
| `question` | domanda/scelta di dialogo **con voce** (il codice della voce è nella stringa): parlato del protagonista | sì |
| `answer` | risposta di un personaggio | sì |
| `examine`, `comment` | esame di un oggetto, commento di stanza | sì |
| `subtitle` | sottotitolo di un filmato | sì |
| `choice` | scelta di dialogo **senza voce** | no (si traduce, non si recita) |
| `label`, `name`, `menu`, `system` | etichette e nomi di oggetti, menu, messaggi del motore | no |
| `scene` | testo di una sequenza (didascalia) | dipende dal gioco |
Le righe ripetute (stesso testo in più punti) restano nel dump; catalogo e stime contano i
**testi unici** (deduplicati sul campo `hex`).
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
`rstool.py text glyphs text/*.tsv` elenca i caratteri usati per lingua. I font in gioco sono l'HD
dei font bitmap originali (`hd-graphics` §4): passa i testi a
`rstool.py font from-bitmap <dump> --name <font> --compose-accents --texts remaster/text/*.tsv`
e chiudi con `rstool.py font coverage remaster/fonts --texts remaster/text/*.tsv` (deve dare `ok`).
- Lettere mancanti: prima da un'altra edizione dell'utente dello stesso gioco (`--extra-edition`),
  poi costruite (base + accento dello stesso font) in codici liberi; la corrispondenza
  Unicode → glifo sta in `fonts/charmap.tsv` (override `fonts/<font>.charmap.tsv`), il Layer
  converte il testo UTF-8 con quella mappa.
- **Maiuscole accentate** (`È`, `À`, `Ò`…) a piena altezza con l'accento sopra la riga; mai
  sostituirle con `E'` o con la minuscola. Una `É` usata al posto della `È` nei testi originali è
  un problema dei testi (correggila in `text/<lang>.tsv`), non del font.
- Codepage: quella del gioco se basta, altrimenti font per lingua (`fonts/<font>.<lang>.dat`).
- **Verbi dell'interfaccia** che sbordano: `ui/verbs.<lang>.tsv` (id, x, y, larghezza massima; il
  motore riduce la spaziatura di 1–2 px oltre la larghezza). Se c'è un'edizione tradotta ufficiale,
  prendi le posizioni da lì; misura le larghezze col font del gioco (tabelle delle larghezze del
  font originale) e, se non basta, accorcia la parola d'accordo col glossario.
- Testi lunghi nei menu e negli aiuti: font leggibile con tutti gli accenti (vedi `hd-graphics` §4).

## 5b. Contenuti tagliati
Confronta gli script della lingua dell'utente con quelli delle altre lingue sul disco: le
edizioni localizzate a volte tagliano scene (con gli script della lingua comunque presenti sul
disco). Il ripristino si fa con un file dati della patch (deviazioni tra stanze), non nel codice. Segnalalo all'orchestratore: il ripristino si decide con
l'utente e si fa nel motore (skill `engine-integration`, §1c).

## 6. Revisione
Per ogni lingua: rilettura completa di un secondo agente (non quello che ha tradotto) con
il copione originale a fianco; poi passaggio del driver automatico con screenshot dei
fumetti per scovare troncamenti.
