# Estensione di `open-static`: prima le tecniche locali collaudate

Dettaglio della skill `widescreen`.

Dettagli, numeri e costi: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/grafica/04a-bande-16-9-generazione.md`, `04b-bande-16-9-controlli-e-ricette.md` e `09-flusso-di-revisione-e-costi.md`.
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
