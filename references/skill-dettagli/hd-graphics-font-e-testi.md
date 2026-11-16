# 4. Font e testi

Dettaglio della skill `hd-graphics`.

**Strada preferita per i testi in gioco: l'HD dei font bitmap originali**, fedele al disegno.
```
rstool.py font from-bitmap <dump del font> --name <font> --scale 3 --out remaster/fonts \
    [--extra-edition <dump dello stesso font di un'altra edizione>] [--compose-accents] \
    [--texts remaster/text/*.tsv] [--reserve 08,12,7F]
rstool.py font coverage remaster/fonts --texts remaster/text/*.tsv
```
Dump del font: JSON (`height`, `bpp`, glifi con `w h ox oy adv px`) o cartella di PNG indicizzati
`<hex>.png` + `font.json`; valori 0 vuoto, 1 riempimento, 2 contorno/ombra, 3 secondo colore. Lo
scrive il Layer o l'adattatore del repository privato.
1. **Ingrandimento 3x con angoli vivi** (`crisp3x`): blocchi 3×3 esatti, smussatura solo dei gradini
   delle diagonali vere; angoli retti convessi e concavi restano vivi e il centro di ogni blocco è il
   pixel originale. **Mai Scale3x doppio, media o upscaler IA sui glifi**: arrotondano gli angoli e
   una D si legge O. Contorno/ombra restano quelli dell'originale (stessa matrice indicizzata);
   atlante RFNT con R = riempimento, G = sagoma (contratto RAC).
2. **Verifica automatica**: il comando riduce ogni glifo dell'atlante a 1x (centri dei blocchi,
   come il motore in modalità originale) e lo confronta con l'originale/costruito
   (`verify_mismatch` deve essere vuoto, altrimenti esce con errore).
3. **Glifi mancanti per la lingua**, in quest'ordine: (a) dall'**altra edizione dell'utente** dello
   stesso gioco (`--extra-edition`, stesso disegno; se la lettera base ha peso diverso si mette
   l'accento dell'altra edizione sulla base di questa); (b) **costruiti** (`--compose-accents`):
   lettera base dello stesso font + accento della minuscola accentata dello stesso font (acuto ↔
   grave specchiato se manca), stessa distanza dal corpo, centrato, contorno rifatto con il nocciolo
   misurato sul font. I codici nuovi vanno in posizioni libere (di preferenza CP850, mai i codici
   del motore: `--reserve`) e nella **charmap** `fonts/charmap.tsv` (override per font).
4. **Maiuscole accentate a piena altezza** con l'accento sopra la riga: `--compose-accents` rifà
   anche quelle che l'originale accorcia per far stare l'accento nella cella (si leggono minuscole).
   Controlla `outside_line` nel risultato e, in gioco, che il motore non tagli l'accento (fumetti su
   più righe: l'accento può coprire 1–2 righe di contorno della riga sopra, di solito accettabile).
   Prova le varianti in un fumetto vero (HD e classico) e falle scegliere all'utente con un foglio.
5. **Copertura**: `font coverage` deve dare `ok` per tutti i testi di tutte le lingue; i glifi
   mancanti nel font originale il motore li disegna anche in modalità originale riducendo l'atlante.
6. **Stilizzazioni volute** dell'originale (alfabeti finti, maiuscoletto, tratti tagliati) restano:
   si costruisce solo ciò che manca, nello stesso stile.

**TTF come alternativa** (sottotitoli, filmati, font originale inservibile):
`rstool.py font build <ttf> --name <font> --scale 3 --codepage cp850 --out remaster/fonts`, TTF
OFL scelto confrontando 2–3 candidati con il font bitmap; sottotitoli più leggibili dello stesso
stile, chiari con contorno nero, in basso con fascia scura (posizione originale come opzione).

**Menu, tema GUI e finestra degli aiuti**: il font del gioco solo per titoli e pulsanti; per i testi
lunghi un font leggibile con tutti gli accenti delle lingue; dimensione minima che segue la scala
della GUI (mai più piccola del font del tema a quella scala).
