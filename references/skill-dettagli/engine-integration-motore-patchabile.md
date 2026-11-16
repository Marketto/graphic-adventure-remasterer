# 1f. Motore patchabile: testi, voci, immagini (requisito)

Dettaglio della skill `engine-integration`.

Il motore (ScummVM o un altro) va adeguato perché **ogni** contenuto mostrato o suonato passi
da un punto in cui la patch può sostituirlo, senza toccare i file originali:
| Contenuto | Punto di aggancio | File della patch |
|---|---|---|
| testi (fumetti, risposte, etichette, menu, titoli) | `Layer::text()` prima del disegno | `text/<lang>.tsv` |
| voci | `Layer::playVoice()` quando la battuta appare; attesa dello script legata alla voce | `voice/<lang>/<textKey>.ogg` |
| fondali, sprite, cursori, interfaccia | `setBackground`, `beginSprite`/`mark`, copie con `clearArea` | `gfx/bg`, `gfx/spr` |
| testi dentro le immagini | fondale localizzato: `setBackground` lo sceglie da solo per la lingua del Layer, altrimenti il fondale normale | `gfx/bg/<scena>.<lang>.png`, `gfx/bg/<scena>.<lang>.wide.png` |
| font | `addText` con atlante HD | `fonts/` |
| musica ed effetti | hook nel driver audio del motore | `music/`, `sfx/` |
| manuale e aiuti | lettori generici nel motore del gioco | `manual/`, `hint/` |
| altre correzioni del contenuto | lettori generici (skill `engine-integration` §1d) | es. `text/dialoghi.tsv` |
Verifica (obbligatoria prima degli asset):
1. `rstool.py assets canary <dump> --out /tmp/canary --lang <lang> [--voices 20]`: pacchetto
   che marca tutto (testi tra «», cornice magenta su fondali e sprite, un bip sulle voci).
   Gioca col driver (`sweep`/`fuzz` + screenshot): **ogni testo o immagine senza marcatore è un
   percorso del motore da agganciare** (testo disegnato direttamente, fondale copiato senza il
   Layer, cursore o icona dell'inventario, crediti, salvataggi).
2. `rstool.py assets coverage <dump> remaster --lang <lang>`: le voci del pacchetto mai
   richieste dal motore (orfani) indicano un aggancio mancante o una chiave sbagliata.
3. Toggle F8 con il pacchetto canary: tutto torna senza marcatori (il percorso originale resta).
