---
name: widescreen
description: Porta le scene di un'avventura 2D al 16:9 (proporzione dei pixel, classificazione, bande con tecniche locali o fal.ai, barre fisse) e prepara i dati per il motore. Usala quando l'utente sceglie il 16:9.
---

# 16:9

Regole trasversali (uso prima del lavoro, spese, motore/contenuto, scelte, repository): `${CLAUDE_PLUGIN_ROOT}/references/regole-comuni.md`.

## Geometria e proporzione dei pixel
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/widescreen-geometria-e-proporzione.md` prima di fissare risoluzione, estensione e proporzione dei pixel.

## Classificazione (`rstool.py widescreen classify <dump>/bg --screen-w W --screen-h H --par <allungamento deciso> [--names bg/names.json] [--playfield-h H]`)
Per ogni scena il tool propone una classe; tu verifichi guardando l'immagine (Read):
| Classe | Riconoscimento | Azione |
|---|---|---|
| `scroll-wide` | larghezza del fondale ≥ viewport (schermo + 2 × estensione per lato), anche se è una mappa | automatica: la viewport mostra più fondale; ai bordi del fondale la camera si ferma prima, così non si vede mai il vuoto |
| `scroll-narrow` | fondale più largo dello schermo ma meno della viewport 16:9; `sides`: `open` o `closed` | lati `open`: come `open-static`; lati `closed`: come `closed-static` |
| `closed-static` | interno chiuso: pareti/soffitto/cornici che chiudono i lati, porte, stanza | **bande vere**: pareti, pavimento e soffitto continuati con le tecniche locali (`closed_static: "extend"`, predefinito); bande nere (`"black"`) o bordi decorati (`"borders"`) solo se l'utente li preferisce o la generazione non convince |
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
piano: controlla se va in `ui-fixed`. È una proposta: la decisione finale è tua e dell'utente.

**Barra dell'interfaccia sotto l'area di gioco.** Se i fondali sono più bassi dello schermo
(es. 144 su 200: verbi e inventario sotto), il piano riporta `ui_bar` (con `option` da scegliere)
e la barra si tratta come in «Barre fisse in 16:9» qui sotto: non si allarga mai da sola.

## Estensione di `open-static`: prima le tecniche locali collaudate
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/widescreen-estensione-open-static.md` quando generi le bande delle stanze aperte.
Gli interni chiusi in modo `extend` usano le stesse tecniche locali (LaMa a 1x, quilting, ricette)
senza fal.ai: le rette di pareti e pavimento vanno continuate dritte, il soffitto e il pavimento non
devono cambiare colore nella banda.

## Barre fisse in 16:9
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/widescreen-barre-fisse.md` quando una barra fissa (verbi, inventario) resta 4:3 con bande nere accanto.

## Cancello di conferma
`rstool.py review gallery --widescreen analysis/widescreen-plan.json --out review/widescreen.html`
genera una pagina con le scene **numerate** (originale e varianti affiancate), scelta per
scena (`v-quilt`, `v-lama`, ricette, `v-fal1`, "bordi", 4:3, "rifai") con l'esito dei controlli,
ed esportazione delle decisioni in JSON. Dal telefono
l'utente può anche rispondere solo con i numeri da scartare ("scarta 4, 17, 23"). Mandala come file o come artifact **privato**; poi importa le scelte con `rstool.py widescreen apply decisions.json`.
Nessuna estensione inventata entra nel pack senza una scelta esplicita dell'utente.
Animazioni tagliate al bordo dagli autori: in 16:9 si vede il taglio; il motore le segnala e si
completano nella banda (`references/conoscenza/grafica/11-oggetti-puntatori-icone.md`).

## Uscita per il motore
`remaster/gfx/bg/<scena>.wide.png` + `<scena>.wide.json`:
```json
{"left": <e>, "right": <e>, "class": "open-static", "camera": "center", "approved": "AAAA-MM-GG"}
```
Per `scroll-wide` c'è solo il `.wide.json` con `"camera": "clamp"`: il motore mostra più fondale esistente.
I nomi dei file usano la chiave della scena con `/` sostituito da `_`.
