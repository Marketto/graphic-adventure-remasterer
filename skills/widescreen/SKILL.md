---
name: widescreen
description: Porta le scene di un'avventura 2D d'epoca al 16:9 secondo regole precise — scenari a scorrimento allargati automaticamente, interni chiusi lasciati in 4:3 con bordi, esterni aperti estesi inventando la parte mancante in stile, sempre con conferma dell'utente — e prepara i dati per la viewport del motore. Usala quando l'utente sceglie il formato 16:9.
---

# 16:9

## Geometria
La logica resta nelle coordinate originali. Il Layer mostra una viewport più larga, con lo
stesso numero di pixel aggiunti per lato. Dipende da come il remaster mostra i pixel:
- **pixel quadrati** (default: il Layer non corregge l'aspetto):
  640x400 → **+36 per lato** (712x400, a 3x 2136x1200; approvato nel progetto di riferimento), 320x200 → +18,
  640x480 → +107;
- con correzione 4:3 dei pixel (320x200 mostrato come su un CRT, `--par 1.2`): 320x200 → +54.
`rstool.py widescreen geometry --w 640 --h 400 [--par 1.2]` calcola i valori esatti.
Le bande sono piccole (~11% dell'immagine): l'obiettivo è che non si notino.

## Classificazione (`rstool.py widescreen classify <dump>/bg --screen-w W --screen-h H`)
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

## Estensione di `open-static` (metodo del progetto di riferimento)
Dettagli, numeri e costi: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/grafica.md` (§3-4, §9).
Le bande si costruiscono **a 1x** e poi l'immagine 16:9 intera (centro + bande) si ingrandisce
in un solo passaggio con lo stesso upscaler dei fondali: niente cuciture di texture; il centro
HD si ritaglia dalla stessa immagine.
1. **Ripiego locale, gratuito** (sempre disponibile):
   `rstool.py widescreen extend analysis/widescreen-plan.json --hd remaster/gfx/bg --lama big-lama.pt`
   LaMa a 1x (la scala del disegno) + upscaler, 24 px di contesto, sfumatura verso il centro;
   colonne nere ai bordi dell'originale ridipinte. Migliorabile con *image quilting* guidato da
   LaMa (ogni pixel della banda viene da una patch dello stesso sfondo) e con ricette per stanza:
   continuazione riga per riga (nebbia, cielo), copia di texture spostata, **continuazione
   geometrica lungo rette misurate** (travi, pannelli, file di rivetti).
2. **Outpainting con maschera a pagamento** (scelto nel progetto di riferimento): FLUX.1 Fill pro
   via fal.ai (~0,05 $ a immagine, tela a 1,5x dell'originale, `sync_mode`), prompt "fondale
   dipinto, finito, a colori; not a sketch, no people, no text, no signature, no logos"; frase in
   più per le scene buie. Al massimo 2 tentativi per stanza, poi ripiego locale. **Preventivo e
   approvazione** prima di spendere (es. 100 stanze ≈ 9 $). Da evitare i modelli di modifica
   dell'intera immagine (spostano l'inquadratura).
3. Scartato: LaMa direttamente sull'HD → **bande sfocate**. Regola: bande inventate **nitide**.
4. Controlli: `band_check` (pixel bianchi, scarto di luminosità, macchie su bordo scuro) solo come
   filtro: scarta anche bande buone, quindi **decide l'occhio** sui fogli numerati, anche
   componendo tentativi diversi per lato. Indice di nitidezza banda/centro (energia ad alta
   frequenza, < 0,6 = sfocata) e unsharp mask tarato sulla banda.
5. Correggi a mano ciò che i modelli inventano: **lettere di insegne tagliate** (il testo giusto
   viene dai dati del gioco, mai dal modello), **firme negli angoli bassi**, persone, cornici,
   oggetti duplicati. Cerca anche righe/colonne sottili di bordo (artefatti di scansione) da
   ritoccare sia nello sfondo normale sia in quello allargato.
6. **I pixel originali non vengono mai modificati** senza approvazione; nelle aree nuove niente
   porte o oggetti che sembrino cliccabili.
7. Nel motore: le bande prendono la dissolvenza del pixel originale più vicino; gli sprite che
   escono dall'area originale si ridisegnano nelle bande (maschera di priorità della colonna di
   bordo); le zone cliccabili che toccano il bordo valgono anche nella banda.

## Cancello di conferma
`rstool.py review gallery --widescreen analysis/widescreen-plan.json --out review/widescreen.html`
genera una pagina con le scene **numerate** (originale e varianti affiancate), scelta per
scena (varianti, "bordi", 4:3, "rifai") ed esportazione delle decisioni in JSON. Dal telefono
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
