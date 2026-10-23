---
name: widescreen
description: Porta le scene di un'avventura 2D d'epoca al 16:9 secondo regole precise — proporzione dei pixel decisa da sola (piattaforma, monitor dell'epoca e forme rotonde misurate nel dump; chiede solo nel dubbio), scenari a scorrimento allargati automaticamente, interni chiusi lasciati in 4:3 con bordi, esterni aperti estesi con le tecniche locali collaudate (fal.ai solo se l'utente lo sceglie), sempre con conferma — e prepara i dati per la viewport del motore. Usala quando l'utente sceglie il formato 16:9.
---

# 16:9

## Geometria e proporzione dei pixel
La logica resta nelle coordinate originali. Il Layer mostra una viewport più larga, con lo
stesso numero di pixel aggiunti per lato.

**Proporzione dei pixel: si corregge solo se il gioco era concepito per quel tipo di monitor.**
Non basta la risoluzione: decidi nell'analisi, prima di classificare, da
- **data di uscita** e **piattaforma di destinazione** (`game.year`, `game.platform`);
- **dispositivi dell'epoca**: monitor CRT 4:3 che allungavano i pixel (VGA 320x200, EGA, Amiga
  NTSC, Atari ST) o pixel quadrati (640x480, Windows, Mac, Amiga PAL lowres);
- **come è nata l'arte**: disegnata a mano su quel monitor (l'artista vedeva i pixel allungati)
  o digitalizzata/renderizzata a pixel quadrati (allora la versione fedele è quadrata).
**Il controllo è automatico; si chiede all'utente solo in caso di dubbio.**
`rstool.py widescreen aspect-auto --platform dos --w 320 --h 200 --year 1992 [--art pixel|digitized]
--evidence <dump>/bg <dump>/obj [--measure review/misura.json] --record` combina:
- il **candidato della tabella** (piattaforma, modo video, anno, monitor dell'epoca) con la sua
  confidenza (lo stesso di `rstool.py widescreen aspect`);
- le **prove misurate da sole** sul dump: cerca forme ellittiche piene o ad anello (rapporto
  d'inerzia, sovrapposizione con l'ellisse stimata) e archi di cerchi grandi tagliati dal bordo
  (una pianta rotonda divisa tra più stanze) in oggetti, icone, sprite e fondali, e ne misura
  larghezza/altezza: un cerchio disegnato per pixel allungati di 1,2 misura ~1,2. Le forme più
  larghe di ogni candidato sono rotonde **in prospettiva** (tavoli, pozzi visti di sbieco) e si
  scartano, quelle più alte non sono rotonde; conta la distribuzione delle restanti (moda e
  sostegno attorno a 1,0, 1,2 o al candidato della tabella), non la singola forma;
- le eventuali **misure manuali** salvate da `aspect-measure` (vedi sotto).
Decide **da solo** (`decided_by: "auto"`) quando la tabella è sicura (confidenza alta) e le prove
non la contraddicono, o quando le prove concordano nettamente con il candidato della tabella;
con `--record` scrive `graphics.pixel_aspect` {stretch, decided_by, confidence, reasons, evidence}
e una decisione con la data. **Chiede** (`decided_by: "ask"`, `stretch` null, `proposed` e i motivi
in `reasons`, «dubbi: ...») quando la confidenza è media o bassa senza prove concordi, quando
prove e tabella (o le prove tra loro) si contraddicono, o con arte digitalizzata senza prove; allora
prepara il foglio di confronto (`--sheet`, default `review/aspect.png`) con le scene dove ha
trovato più forme, e `rstool.py project missing` elenca la domanda finché l'utente non risponde
(`rstool.py project set graphics.pixel_aspect.stretch 1.2 graphics.pixel_aspect.decided_by user`
e una decisione con `project decide`).

Nei casi dubbi aiutano: `rstool.py widescreen aspect-sheet <3-4 fondali con oggetti tondi, volti,
ruote, lune, testo disegnato> --out review/aspect.png` (scene a pixel quadrati e allungati
affiancate; la versione giusta li mostra rotondi; **non basta** su viste in prospettiva e
documenti) e la **misura** manuale di una forma rotonda nella realtà (disco o tavolo visto
dall'alto, ruota, luna, oblò), anche divisa tra più stanze:
`rstool.py widescreen aspect-measure <img...> [--compose 2x2] [--box x,y,w,h] [--color #rrggbb]
--out review/aspect-misura.png` dà larghezza/altezza sui pixel originali (riquadro e momenti,
quanto somiglia a un'ellisse piena) e il candidato più vicino; salvane il JSON e ripassalo ad
`aspect-auto --measure`. Se resta il dubbio guarda l'originale sull'emulatore di riferimento
(skill `engine-integration` §1b) con la correzione d'aspetto dell'epoca.
Default: **pixel quadrati** (`stretch` 1.0). Se l'allungamento serve, imposta
`Desc::pixelAspect`: il Layer scala in verticale con righe filtrate (320x200 a 3x con 1,2 →
960x720), allarga la viewport 16:9 di conseguenza e converte il mouse; `remaster_aspect=false`
lo spegne (vedi `INTEGRAZIONE.md`, "Pixel non quadrati").
Il pacchetto `pixel-aspect` del piano lo imposta nel motore del gioco e lo verifica.

Larghezza delle bande per lato (`rstool.py widescreen geometry --w W --h H [--par <stretch>]`):
- pixel quadrati: 640x400 → **+36 per lato** (712x400, a 3x 2136x1200; approvato nel progetto
  di riferimento), 320x200 → +18, 640x480 → +107;
- con allungamento 1,2 (320x200 pensato per un CRT 4:3): 320x200 → +54.
Le bande sono piccole (~11% dell'immagine): l'obiettivo è che non si notino.

## Classificazione (`rstool.py widescreen classify <dump>/bg --screen-w W --screen-h H --par <allungamento deciso> [--names bg/names.json] [--playfield-h H]`)
Per ogni scena il tool propone una classe; tu verifichi guardando l'immagine (Read):
| Classe | Riconoscimento | Azione |
|---|---|---|
| `scroll-wide` | larghezza del fondale ≥ viewport (schermo + 2 × estensione per lato), anche se è una mappa | automatica: la viewport mostra più fondale; ai bordi del fondale la camera si ferma prima, così non si vede mai il vuoto |
| `scroll-narrow` | fondale più largo dello schermo ma meno della viewport 16:9; `sides`: `open` o `closed` | lati `open`: estensione dei lati mancanti come `open-static`; lati `closed`: bande o bordi come `closed-static` |
| `closed-static` | interno chiuso: pareti/soffitto/cornici che chiudono i lati, porte, stanza | resta 4:3 con **bande nere** (scelta del progetto di riferimento); bordi decorati solo se l'utente li preferisce |
| `open-static` | esterno o spazio aperto delimitato: cielo, orizzonte, strada, paesaggio che continuano oltre il bordo | **parte mancante inventata** coerente con la scena; conferma obbligatoria |
| `ui-fixed` | menu, mappe, inventario a tutto schermo, primi piani e inserti (documenti, oggetti, volti), schermata di morte, logo, filmati | resta 4:3 centrato |
| `skip` | fondale largo meno di 64 px (stanza fittizia senza fondale vero) | nessuna: non si estende |

Indizi usati dal tool, in quest'ordine: larghezza (`skip`, `scroll-wide`); **nomi delle stanze**
da `bg/names.json` (dall'indice del gioco; i nomi dei file del dump sono spesso numeri: menu,
mappa, logo, morte, primo piano, `cu-`...); fondale **quasi a tinta unita** (≤ 3 colori: il
contenuto lo disegnano gli oggetti → `ui-fixed`); poi i bordi: **cielo** solo se il terzo
superiore è liscio, **luminoso** (luminanza media > 0,25) e **blu** (peso del blu 0,2-1,0),
meglio se il gradiente verticale è monotono; linee orizzontali che escono dal quadro; verticali
forti vicino ai bordi (pareti). Soffitti, interni bui e cieli notturni hanno il terzo superiore
scuro: il tool li mette tra i chiusi, e un **esterno notturno** o una strada senza cielo vanno
riconosciuti a vista. Punteggio > 0,40 aperto, 0,15-0,40 incerto (verifica a vista). Una scena
a tutto schermo in un gioco con l'area di gioco più bassa (`full_height`) è spesso un primo
piano: controlla se va in `ui-fixed`. Sul banco di prova (96 scene etichettate a mano) queste
regole hanno portato le classi giuste dal 64% all'86% e la decisione "inventare o no" dal 74%
al 96%. È una proposta: la decisione finale è tua + dell'utente.

**Barra dell'interfaccia sotto l'area di gioco.** Se i fondali sono più bassi dello schermo
(es. 144 su 200: verbi e inventario sotto), il piano riporta `ui_bar` (con `option` da scegliere)
e la barra si tratta come in «Barre fisse in 16:9» qui sotto: non si allarga mai da sola.

## Estensione di `open-static`: prima le tecniche locali collaudate
Dettagli, numeri e costi: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/grafica.md` (§3-4, §9).
Le bande si costruiscono **a 1x** (la scala del disegno) e poi si ingrandiscono con lo stesso
upscaler dei fondali, con 24 px di contesto e una sfumatura verso il centro HD: stesso tratto e
stessa grana del resto. Il centro HD non si tocca.

**1. Metodo predefinito, locale e gratuito** (CPU, sempre disponibile):
`rstool.py widescreen extend analysis/widescreen-plan.json --hd remaster/gfx/bg --lama big-lama.pt
[--recipes analysis/ricette-bande.json]` produce per ogni scena:
- `v-lama`: LaMa a 1x + upscaler (LaMa indovina la disposizione: cielo, muro, prato);
- `v-quilt`: LaMa + **image quilting** dall'originale (tessere di 12 px con 4 di sovrapposizione,
  dal bordo verso l'esterno, scelte per continuità, colore guida di LaMa, stessa altezza, pochi
  riusi; unione lungo il taglio di minima differenza). Ogni pixel della banda è un pixel dipinto
  dall'artista; dove nessuna tessera combacia resta LaMa. Di solito è la migliore;
- `v-<ricetta>` per le scene residue: `rows` (continuazione riga per riga del colore del bordo
  con la grana dell'originale: nebbia, neve, cielo, pareti lisce), `shift` (copia della texture
  spostata di `dx` px con correzione `dy` e pendenza `slope` per binari, crinali, file di
  elementi). La **continuazione geometrica lungo rette misurate** (travi, pannelli, file di
  rivetti) si fa a mano: misura le rette sull'originale e copia ogni zona lungo la sua retta;
- `borders`: bordi in tono con l'immagine.
Su ogni variante: unsharp mask tarato sulla banda (soglia 2 livelli, niente aloni, sfumato verso
il centro) finché l'**indice di nitidezza** banda/centro arriva a 0,8, e i controlli
`band_check` (pixel bianchi, scarto di luminosità, macchie su bordo scuro) e nitidezza, salvati
nel piano e mostrati nella galleria. `rstool.py widescreen check <img> --left L --right R` li
rifà su un'immagine corretta a mano. Sono **filtri**: scartano anche bande buone, decide l'occhio.
Scartato: LaMa direttamente sull'HD → **bande sfocate**. Regola: bande inventate **nitide**.

**2. Outpainting a pagamento con fal.ai: opzionale, solo se l'utente lo sceglie.**
Contano solo le scene con lati **aperti** (`open-static` e `scroll-narrow` con `sides` `open`).
Dopo l'analisi, col preventivo delle scene da inventare, si chiede se vuole provarlo
(`graphics.widescreen.fal_ai`); se no, non si usa
mai. Se sì, dopo il metodo locale e solo per le scene in cui le varianti locali non convincono:
1. preventivo gratuito: `rstool.py widescreen fal-estimate --plan analysis/widescreen-plan.json`
   (o `--scenes N`): immagini e dollari nel caso peggiore (2 tentativi a scena) e in quello
   probabile; verifica il prezzo attuale sul sito;
2. **approvazione esplicita** dell'utente con quel numero, registrata nelle decisioni;
3. `rstool.py widescreen extend ... --fal --approved-images N --only <scene>` (servono `FAL_KEY` e
   il progetto con `graphics.widescreen.fal_ai` vero; N è il totale approvato per il lotto,
   contato su tutte le esecuzioni dal registro `fal-spesa.jsonl`; le varianti locali già fatte
   restano nella galleria e ogni tentativo ha il suo nome, `v-fal1`, `v-fal2`):
   FLUX.1 Fill pro con maschera (il centro non viene ridipinto), tela a 1,5x dell'originale,
   `sync_mode`, prompt "fondale dipinto, finito, a colori; not a sketch, no people, no text, no
   signature, no logos" più una frase per le scene buie. Il conteggio si ferma al budget
   approvato e la spesa è registrata in `fal-spesa.jsonl`; mai ripetere da soli una chiamata;
   al massimo 2 tentativi per scena, poi si torna al metodo locale. Da evitare i modelli che
   modificano l'intera immagine (spostano l'inquadratura).
Le varianti `v-fal<n>` entrano nella stessa galleria delle altre: decide l'utente.

**3. Ritocchi** (per qualunque metodo): correggi ciò che i modelli inventano: **lettere di
insegne tagliate** (il testo giusto viene dai dati del gioco, mai dal modello), **firme negli
angoli bassi**, persone, cornici, oggetti duplicati. Cerca righe/colonne sottili di bordo
(artefatti di scansione) da ritoccare sia nello sfondo normale sia in quello allargato.
**I pixel originali non vengono mai modificati** senza approvazione; nelle aree nuove niente
porte o oggetti che sembrino cliccabili.

**4. Nel motore**: le bande prendono la dissolvenza del pixel originale più vicino; gli sprite
che escono dall'area originale si ridisegnano nelle bande (maschera di priorità della colonna di
bordo); le zone cliccabili che toccano il bordo valgono anche nella banda.

## Barre fisse in 16:9
Verbi, inventario, pannelli di stato e cornici disegnati sempre nelle stesse righe dello schermo:
in 16:9 la scena si allarga ma la barra resta 4:3 con **bande nere** ai lati. La skill la
**individua**, ne **verifica la fattibilità** nel motore e **propone 2-3 opzioni** all'utente;
non si sceglie da soli.

**1. Rilevamento** (gratuito, dal dump e dalle catture):
- `rstool.py widescreen bar-rows <catture 4:3 di almeno 3 stanze diverse>`: righe identiche in
  tutte le stanze = interfaccia (`bottom`/`top` in pixel, `playfield_h` rimasto alla scena);
- conferme: altezza della scena riportata dal motore (`meta.json` → `playfield_h`), altezza più
  comune dei fondali (`classify` → `ui_bar`), colori e oggetti dei verbi nel dump (stessa palette,
  oggetti di interfaccia sempre presenti);
- a Layer già in 16:9: `rstool.py widescreen bar-check <catture 16:9> --screen-w W --screen-h H
  --playfield-h P [--par]` → `bar_unfilled` se accanto alla barra ci sono bande nere (la scena
  sopra può essere già riempita). Annota `ui_bar_unfilled: true` nei conti dell'analisi: la domanda
  e il pacchetto compaiono anche senza `playfield_h`.

**2. Verifica di fattibilità per motore** (leggi il codice prima di proporre B/C):
- come il motore disegna verbi e inventario: oggetti/sprite del motore, un'unica immagine della
  barra, testo; in quale buffer (scena o superficie separata);
- l'inventario: quanti slot visibili, se la **paginazione** (frecce, scorrimento) è fatta dal
  motore o dagli **script** del gioco (in quel caso B deve imitare lo stesso stato);
- dove si intercettano i clic sulla barra (coordinate → verbo/slot) e se gli script ridisegnano
  la barra da soli (animazioni, verbi che cambiano, barra usata per le **scelte di dialogo**);
- scene senza barra (filmati, primi piani, mappe) e cosa entra nei **salvataggi** (pagina
  dell'inventario, verbo attivo).
Esito per opzione: fattibile / fattibile con rischi (elencati) / non fattibile (perché).

**3. Proposta all'utente** — opzioni, con **mockup gratuiti** (A/B/C affiancate su **2 scene
reali**, composte con Pillow dalle catture: nessuna generazione a pagamento) e stima di lavoro e
costo per ciascuna (pacchetti del piano):
- **A. Riempitivo**: barra invariata, pannelli decorativi laterali nello stile della barra
  (estensione della trama a 1x come le bande dei fondali, cornice, motivi) o del tema (es.
  pergamena); nessun cambio di funzioni; rischio minimo. Pacchetto `ui-bar`.
- **B. Barra allargata**: pannello a tutta larghezza, verbi ridistribuiti e più grandi,
  inventario con più slot visibili (meno scorrimento). Il motore ridisegna la barra e mappa i clic
  sugli oggetti oltre la pagina originale. Rischi: script che ridisegnano la barra, barra usata per
  le scelte di dialogo, scene senza barra, salvataggi. Pacchetto `ui-bar-B` (Layer, vedi
  `engine/scummvm-remaster-layer/INTEGRAZIONE.md` «Barra fissa in 16:9»).
- **C. B + icone dei verbi** nello stile del gioco, come secondo passo: ricavate dalla grafica
  del gioco (gratis) o generate a pagamento **con preventivo** (icone × tentativi × prezzo) e
  ritoccate a mano. Pacchetti `ui-bar-B` + `ui-bar-icons` (a pagamento solo con `icons: paid`).
- `none`: bande neutre accanto alla barra (solo se l'utente lo chiede).
Se B non è fattibile, proponi A (e il motivo); C non si propone senza B.

**4. Scelta registrata**: `rstool.py project set graphics.widescreen.ui_bar
'{"option":"B","notes":"inventario a 10 slot; dialoghi restano 4:3","icons":"game"}'`
(`option` ∈ A, B, C, none; `icons` ∈ game, paid). Il piano (`plan.py`) aggiunge i pacchetti
dell'opzione con le stime: A `tok_ui_bar`, B `tok_ui_bar_wide`, C anche `tok_ui_bar_icons` e, se
a pagamento, il preventivo (`icon_price_usd` × `icon_attempts` × verbi).

**5. Implementazione** come pacchetti del piano: `ui-bar` (pannelli in `ui/bar-side.*.png`),
`ui-bar-B` (riquadro della barra separato, disposizione dei verbi in `ui/verbs.<lang>.tsv`, griglia
dell'inventario), `ui-bar-icons`. Verifica con il driver di test: clic su ogni verbo e su ogni slot
(anche oltre la pagina originale), scelte di dialogo, scene senza barra, salva/carica, toggle
originale/remaster.

## Cancello di conferma
`rstool.py review gallery --widescreen analysis/widescreen-plan.json --out review/widescreen.html`
genera una pagina con le scene **numerate** (originale e varianti affiancate), scelta per
scena (`v-quilt`, `v-lama`, ricette, `v-fal1`, "bordi", 4:3, "rifai") con l'esito dei controlli,
ed esportazione delle decisioni in JSON. Dal telefono
l'utente può anche rispondere solo con i numeri da scartare ("scarta 4, 17, 23"). Pubblicala come artifact o
mandala come file; poi importa le scelte con `rstool.py widescreen apply decisions.json`.
Nessuna estensione inventata entra nel pack senza una scelta esplicita dell'utente.

## Uscita per il motore
`remaster/gfx/bg/<scena>.wide.png` + `<scena>.wide.json`:
```json
{"left": 36, "right": 36, "class": "open-static", "camera": "center", "approved": "2026-10-15"}
```
Per `scroll-wide` c'è solo il `.wide.json` con `"camera": "clamp"`: il motore mostra più fondale esistente.
I nomi dei file usano la chiave della scena con `/` sostituito da `_`.
