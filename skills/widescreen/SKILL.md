---
name: widescreen
description: Porta le scene di un'avventura 2D d'epoca al 16:9 secondo regole precise — proporzione dei pixel decisa dalla piattaforma e dai monitor dell'epoca, scenari a scorrimento allargati automaticamente, interni chiusi lasciati in 4:3 con bordi, esterni aperti estesi con le tecniche locali collaudate (fal.ai solo se l'utente lo sceglie), sempre con conferma — e prepara i dati per la viewport del motore. Usala quando l'utente sceglie il formato 16:9.
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
`rstool.py widescreen aspect --platform dos --w 320 --h 200 --year 1992 [--art pixel|digitized]`
dà l'allungamento candidato, i motivi e quanto è sicuro. Poi **decide l'occhio**:
`rstool.py widescreen aspect-sheet <3-4 fondali con oggetti tondi, volti, ruote, lune, testo
disegnato> --out review/aspect.png` mette le scene a pixel quadrati e allungati affiancate; la
versione giusta li mostra rotondi. In caso di dubbio guarda l'originale sull'emulatore di
riferimento (skill `engine-integration` §1b) con la correzione d'aspetto dell'epoca.
Registra la scelta con i motivi (`graphics.pixel_aspect` e una decisione con la data).
Default: **pixel quadrati** (`stretch` 1.0). Se l'allungamento serve, il Layer deve anche
scalare in verticale: oggi non lo fa (vedi `INTEGRAZIONE.md`).

Larghezza delle bande per lato (`rstool.py widescreen geometry --w W --h H [--par <stretch>]`):
- pixel quadrati: 640x400 → **+36 per lato** (712x400, a 3x 2136x1200; approvato nel progetto
  di riferimento), 320x200 → +18, 640x480 → +107;
- con allungamento 1,2 (320x200 pensato per un CRT 4:3): 320x200 → +54.
Le bande sono piccole (~11% dell'immagine): l'obiettivo è che non si notino.

## Classificazione (`rstool.py widescreen classify <dump>/bg --screen-w W --screen-h H --par <allungamento deciso>`)
Per ogni scena il tool propone una classe; tu verifichi guardando l'immagine (Read):
| Classe | Riconoscimento | Azione |
|---|---|---|
| `scroll-wide` | fondale più largo dello schermo di almeno 2×estensione | automatica: la viewport mostra più fondale; ai bordi del fondale la camera si ferma prima, così non si vede mai il vuoto |
| `scroll-narrow` | fondale più largo dello schermo ma meno della viewport 16:9 | estensione solo dei lati mancanti come `open-static`, oppure bordi |
| `closed-static` | interno chiuso: pareti/soffitto/cornici che chiudono i lati, porte, stanza | resta 4:3 con **bande nere** (scelta del progetto di riferimento); bordi decorati solo se l'utente li preferisce |
| `open-static` | esterno o spazio aperto delimitato: cielo, orizzonte, strada, paesaggio che continuano oltre il bordo | **parte mancante inventata** coerente con la scena; conferma obbligatoria |
| `ui-fixed` | menu, mappe, inventario a tutto schermo, filmati | resta 4:3 centrato |

Indizi usati dal tool: larghezza del fondale, continuità ai bordi (linee orizzontali che
escono dal quadro, gradienti di cielo nelle colonne di bordo), verticali forti vicino ai
bordi (pareti), varianza dei bordi. È una proposta: la decisione finale è tua + dell'utente.

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
Nell'intervista si chiede se vuole provarlo (`graphics.widescreen.fal_ai`); se no, non si usa
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
