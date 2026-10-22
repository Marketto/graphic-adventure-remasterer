---
name: style-bible
description: Ricava da solo lo stile artistico di un'avventura grafica d'epoca (palette, tratto, luce, inquadrature, autori), le sue ispirazioni (film, fumetti, serie, illustratori) e i riferimenti visivi dell'anno di uscita (attori, costumi, fotografia), e produce la style bible e le ricette di prompt per il remaster HD. Usala prima di generare qualunque asset.
---

# Style bible

Obiettivo: ogni pixel nuovo deve sembrare dipinto dagli stessi autori, con gli strumenti di
oggi. La style bible è il riferimento vincolante per `hd-graphics` e `widescreen`.

## 1. Ricerca (web) — cita sempre le fonti
- Crediti: direzione artistica, grafici dei fondali, animatori, musicisti, sceneggiatori.
- Interviste, recensioni dell'epoca, manuale, scatola, materiale promozionale.
- **Ispirazioni dichiarate o evidenti**: film, serie TV, fumetti, cartoni, illustratori,
  movimenti (es. satira politica, parodia di generi cinematografici). Distingui "dichiarato dagli autori" da "nostra deduzione".
- **Riferimenti dell'epoca di uscita**: attori e personaggi celebri a cui i personaggi
  somigliano o fanno parodia, moda, auto, oggetti, fotografia e pubblicità di quegli anni.
  Usali per costumi, trucco, materiali, luce e inquadratura. **Non** per copiare volti:
  il personaggio resta quello disegnato dall'autore, mai il ritratto di una persona reale.
- **Volti dei personaggi riconoscibili** (§1b): riferimento solo l'**artwork ufficiale dello
  stesso gioco** (copertina, scatola, manuale, schermate di primo piano, ritratti dei dialoghi),
  per tenere i lineamenti coerenti; **mai fotografie o fotogrammi della persona reale**.

## 1b. Opera d'origine (sempre, anche quando sembra di no)
Verifica **sempre** se il gioco è tratto da un film, una serie, un cartone o un'altra opera
cinematografica o d'animazione (gioco su licenza, tie-in, seguito ufficiale, parodia dichiarata).
Fonti: scatola e manuale dell'utente, crediti del gioco ("basato su", "su licenza di"),
schede di database di giochi e di film, recensioni dell'epoca. Poi:
- **personaggi riconoscibili**: quelli che sono lo stesso personaggio dell'opera (non le
  somiglianze generiche o le parodie, che restano riferimenti d'epoca del §1);
- per ciascuno: **interprete originale** (attore o voce del cartone) e, per **ogni lingua di
  destinazione** del remaster, il **doppiatore dell'edizione di quell'epoca** (quella uscita
  più vicina all'anno del gioco; se ce ne sono due, entrambe con l'anno), con le fonti;
  "non trovato" è una risposta valida, inventare no.
Registra tutto nel progetto (solo nel repository privato del gioco):
```
rstool.py project set source_work '{"checked": true, "type": "film", "title": "...", "year": 1990,
  "sources": ["<url>"], "characters": [{"name": "...", "performer": "...",
  "voices": {"en": {"name": "...", "sources": ["<url>"]}, "it": {"name": "...", "year": 1991, "sources": ["<url>"]}},
  "sources": ["<url>"], "imitate_voice": null}]}'
```
`type`: film, series, animation, comic, book, other. Nessuna opera d'origine:
`project set source_work.checked true` (resta senza titolo). `rstool.py project missing`
segnala fonti mancanti e lingue doppiate senza la voce dell'epoca. Questi dati servono al
casting (`voice-dubbing` §2b, solo se il doppiaggio è scelto) e ai volti in HD (`hd-graphics`).

## 2. Analisi degli asset (dai file dell'utente)
`rstool.py style analyze <cartella dump>` (dump del Layer `.raw` o PNG di un'estrazione senza
Layer: fondali RGB, sprite RGBA; il numero di fotogrammi da `spr/index.json` se presente) produce
in `analysis/style/`:
- palette dominanti per scena e globali, rampe di colore usate (quante sfumature per tinta);
- statistiche del dithering (scacchiera, ordinato, assente), contorni (neri, colorati, assenti);
- direzione della luce stimata, contrasto, saturazione media;
- contact sheet dei fondali e dei personaggi.
Guarda tu i contact sheet (Read sulle immagini) e descrivi: tratto (pittorico, cel, pixel art
pura, digitalizzato da acquerello/foto/plastilina), prospettive, proporzioni dei personaggi.

## 3. Scrivi `analysis/style-bible.md`
Sezioni: Identità (3 righe) · Autori e strumenti originali · Ispirazioni (con fonti) ·
Riferimenti d'epoca · Palette e luce · Tratto e texture · Personaggi (scheda per ciascuno:
silhouette, colori fissi, tratti da non cambiare mai; per i personaggi riconoscibili del §1b,
l'artwork ufficiale **dello stesso gioco** da cui prendere i lineamenti) · Cosa NON fare (es. niente
fotorealismo, niente bloom moderno, niente contorni che l'originale non ha) ·
Livelli di intervento consentiti (vedi sotto).

## 4. Ricette di generazione (`analysis/style-recipes.json`)
Per ogni categoria (fondale interno, esterno, personaggio, oggetto, UI):
- prompt positivo e negativo in inglese, ancorati alla style bible;
- modello base e **LoRA di stile addestrato sugli asset originali del gioco stesso**
  (piano di training: 40-150 immagini di fondali upscalati, didascalie automatiche,
  1500-3000 step, rank 16-32) — è il modo più affidabile per restare nello stile;
- denoise img2img consigliato (0.15-0.35: dettagli sì, ridisegno no), ControlNet (tile +
  lineart) per bloccare la composizione;
- seed fissi (servono alla modalità `recipe`).

## Livelli di intervento
1. **Fedele** (default per i personaggi): upscaling + pulizia, stessi contorni e colori.
2. **Arricchito** (default per i fondali): dettagli e texture coerenti, stessa composizione.
3. **Reinventato** (solo estensioni 16:9 e solo con conferma): parti nuove in stile.

Chiudi con un confronto: 3 fondali e 2 personaggi rifatti in prova al livello proposto,
affiancati all'originale, da mostrare all'utente prima della produzione in serie.
