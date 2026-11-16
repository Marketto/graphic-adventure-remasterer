# Barre fisse in 16:9

Dettaglio della skill `widescreen`.

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
