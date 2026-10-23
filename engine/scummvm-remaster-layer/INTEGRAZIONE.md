# Remaster Layer per ScummVM — integrazione in un motore

`0001-ENGINES-Add-remaster-layer.patch` aggiunge `engines/remaster/` (codice comune, namespace
`Remaster`) e i test `test/graphics/remaster.h`. Verificata su ScummVM `5d13ee16` (14 ottobre 2026):
si applica pulita, compila, i 415 test di `make test` passano e l'eseguibile si collega.

```
git clone https://github.com/scummvm/scummvm && cd scummvm
git checkout 5d13ee16a88e724ccc32b6ceea5c74e54ab21878
git am <plugin>/engine/scummvm-remaster-layer/0001-ENGINES-Add-remaster-layer.patch
./configure --disable-all-engines --enable-engine=<motore> && make -j$(nproc) && make test
```

## Regole del progetto ScummVM sull'AI (`AI-GUIDELINES.md`, obbligatorie)
- nei commit del fork: trailer `Assisted-by: Claude:<modello>`, **mai** `Co-Authored-By` di un'AI;
- l'autore del codice è la persona che lo rivede e ne risponde: prima di proporre qualcosa
  upstream va riletto, capito, testato e il messaggio di commit riscritto da lei;
- nessun asset grafico generato con AI può entrare nel progetto ScummVM ufficiale.
  Gli asset del remaster restano nel pack dell'utente (`remaster/`), mai in una pull request.
La suite non apre pull request verso ScummVM per conto dell'utente.

## Hook nel motore (esempio con nomi generici: adattali al motore)

```cpp
#include "engines/remaster/layer.h"

// init grafica (Screen::Screen); _remaster resta nullptr senza pack o con remaster=false:
// tutti gli hook qui sotto vanno chiamati solo se _remaster esiste
Remaster::Layer::Desc d;
d.gameId = "<id>"; d.screenW = 640; d.screenH = 400; d.pixelAspect = 1.0f;	// 36 px per lato in 16:9
// pixelAspect != 1 solo se deciso nell'analisi (gioco pensato per pixel non quadrati):
// con 1.2 un 320x200 a 3x esce 960x720 (righe ricampionate), in 16:9 54 px per lato
d.codePage = Common::kDos850;
_remaster = Remaster::Layer::create(d);
if (!_remaster)
	initGraphics(640, 400);

// palette (Screen::setPalette)
if (_remaster) _remaster->setPalette(rgb, 0, n); else g_system->getPaletteManager()->setPalette(rgb, 0, n);

// nuovo fondale (Screen::setRoomImage) — chiave scena = percorso della risorsa
// ("part1/bg/room" → remaster/gfx/bg/part1_bg_room.png)
// (con part1_bg_room.<lang>.png presente, per quella lingua si usa il fondale localizzato)
if (_remaster) _remaster->setBackground(roomPath, bg8, rgb, bgX, bgY);

// inizio frame (Screen::beginFrame, prima di disegnare gli oggetti)
if (_remaster) _remaster->beginScene(_frameBuffer.w, _frameBuffer.h);

// blitter degli sprite (Screen::drawSprite e blitter)
if (_remaster) _remaster->beginSprite(data, w, h, w, transparentKey);
...	// per ogni pixel effettivamente scritto (dopo maschere e clipping):
if (_remaster) _remaster->mark(dstX, dstY, srcX, srcY);
...
if (_remaster) _remaster->endSprite();

// copie di pixel che non sono sprite (copyRectToScreen dell'engine)
if (_remaster) _remaster->clearArea(x, y, w, h);

// testi: correzioni/traduzioni sempre; font HD se c'è, altrimenti il font originale
Common::String t = _remaster ? _remaster->text(s, "balloon", roomName.c_str(), speaker.c_str(), boxW) : s;
if (!_remaster || !_remaster->addText(_speechFont /* = _remaster->font("dialogue") */, x, y, t, color, 0, boxW))
	font->drawString(surf, x, y, t.c_str());

// presentazione (aggiornamento dello schermo) e ritmo (ciclo principale del motore)
if (_remaster) {
	_remaster->present(_frameBuffer, _cameraX, _cameraY);
	_remaster->pace(33);                      // invece di delayMillis: frame interpolati fino al tick
} else {
	... // copyRectToScreen + updateScreen + delayMillis come prima
}

// input (Events::poll), per ogni evento letto
if (_remaster && _remaster->handleEvent(e)) continue;   // F8 + coordinate mouse
// 16:9: un clic (pressione) fuori dallo schermo originale, nelle bande, va scartato e non
// riportato al bordo della scena (si attiverebbe un oggetto o un'uscita sul bordo); movimenti e
// rilasci passano sempre (il rilascio chiude un trascinamento iniziato dentro la scena)
// spostamenti del cursore decisi dal gioco (coordinate di gioco → schermo, anche con l'allungamento)
if (_remaster) _remaster->warpMouse(x, y); else g_system->warpMouse(x, y);

// voci (fumetti, sottotitoli, risposte)
if (!_remaster || !_remaster->playVoice(original)) showSubtitle(...);
```

## Doppiaggio parziale (solo alcune parti del gioco)

Il pacchetto può contenere le voci nuove solo per una o più parti del gioco (capitoli, atti,
dischi, percorsi: `voice.scope` nel progetto, quando i crediti non bastano per tutto). Il motore
non sa nulla delle parti e non deve saperlo: decide **riga per riga** dalla presenza del file.
`Layer::playVoice()` restituisce `false` quando `voice/<lang>/<textKey>.ogg` non esiste (oltre che
con le voci spente, in modalità classica o senza lingua), e allora il gancio segue **il percorso
originale del gioco**:

- gioco parlato: parte la clip originale (quella restaurata, se il gioco la carica al suo posto),
  con i suoi dati originali di movimento della bocca;
- gioco solo testo: resta il fumetto/sottotitolo, come prima.

Per questo il gancio va scritto sempre nella forma «prima il Layer, se dice no l'originale»
(`if (!_remaster || !_remaster->playVoice(original)) <percorso originale>`), mai «se c'è il Layer
salta l'originale». Nella stessa scena possono quindi convivere righe doppiate e righe originali;
la sincronia labiale nuova (`.lip.json`) vale solo per le righe con la voce nuova. Verifica del
gancio: un pacchetto con le voci di una sola parte, si gioca l'inizio di una parte esclusa e ogni
riga deve comportarsi come senza remaster (clip originale o sottotitolo, nessun silenzio).

## Opzioni (ScummVM .ini o menu del gioco)
| chiave | default | effetto |
|---|---|---|
| `remaster` | true | spegne del tutto il layer |
| `remaster_scale` | dal manifest (3) | 2-4 |
| `remaster_classic` | false | parte in versione originale (stesso stato del toggle) |
| `remaster_toggle_key` | 8 | tasto F1-F12 per il cambio in tempo reale |
| `remaster_widescreen` | true | viewport 16:9 |
| `remaster_aspect` | true se `pixelAspect` != 1 | allungamento verticale per i giochi pensati per pixel non quadrati; false: pixel quadrati (anche la geometria 16:9 si calcola a 1,0) |
| `remaster_smooth` | true | scorrimento interpolato tra i tick |
| `remaster_voices` | true | voci registrate |
| `remaster_language` | lingua ScummVM | testi/voci da `text/<lang>.tsv`, `voice/<lang>/`; fondali localizzati `gfx/bg/<scena>.<lang>[.wide].png` se presenti |
| `remaster_dump` | — | cartella dove scrivere `bg/` (chiave scena con `_`), `spr/`, `text.jsonl` per la pipeline |

## Driver di test: comandi per i controlli
Da aggiungere al driver del motore (attivo solo con la variabile d'ambiente di test):
- `inputlog <file>`: per ogni evento letto scrive `<ms> in mouse <x> <y>` o
  `<ms> in key <nome> down|up [repeat]` (`repeat` se `e.kbdRepeat`), per ogni fotogramma
  presentato `<ms> draw cursor <x> <y>` (coordinate dello schermo), per ogni azione a scatto
  eseguita `<ms> act <nome>` (toggle, menu, inventario, salta, aiuti, salva);
- `mousepath x0 y0 x1 y1 ms`: eventi di movimento a 120 Hz lungo una retta;
- `keyhold <tasto> ms`: pressione, eventi ripetuti come quelli del sistema, rilascio.
Il log si analizza con `rstool.py engine controls <file>`. Le azioni a scatto ignorano gli
eventi con `kbdRepeat`; il cursore si ridisegna a ogni `present()`/`pace()`, non solo a ogni tick.

## Pixel non quadrati (`pixelAspect`)
Con `pixelAspect` != 1 e `remaster_aspect` attivo l'uscita è alta `round(screenH × scala ×
pixelAspect)` (320x200 a 3x con 1,2 → 960x720; in 16:9 la viewport è calcolata sull'altezza
allungata: 54 px per lato a 1x, 1284x720). Il fotogramma si compone a pixel quadrati (fondali,
sprite, testo HD) e poi le righe si ricampionano con un filtro d'area: ogni riga d'uscita è la
media pesata delle righe che copre, quindi niente righe duplicate a scatti. La modalità classica
(F8) passa per lo stesso filtro. Il mouse torna alle coordinate di gioco con la stessa
proporzione (`y = Y × screenH / altezza`, senza salti); `warpMouse()` fa il contrario e porta il
cursore al centro della riga di gioco. Il motore non cambia: lavora sempre a 320x200.

## Testo, charmap e font bitmap HD
- Il testo della patch è UTF-8: prima di misurarlo e disegnarlo il Layer lo converte nei codici dei
  glifi con `fonts/charmap.tsv` (più `fonts/<font>.charmap.tsv` per il font in uso, se c'è). Un
  carattere assente o con glifo vuoto: `?` e una riga nel log.
- I glifi aggiunti dalla patch (accentate in codici liberi, maiuscole accentate rifatte) mancano nel
  font originale: in modalità originale il motore li disegna **riducendo l'atlante HD** (centro di
  ogni blocco `scala×scala`, riempimento = R, contorno = G senza R), così toggle e classico mostrano
  lo stesso glifo.
- Le maiuscole accentate HD salgono sopra la riga (`by` negativo): il disegno del glifo non deve
  tagliare alla cella o al rettangolo del testo (taglia solo al bordo del fotogramma), e il
  rettangolo da ridisegnare va allargato di quanto il glifo sporge.
- Etichette dei verbi: `ui/verbs.<lang>.tsv` (posizione e larghezza massima, contratto RAC); oltre
  la larghezza il motore riduce la spaziatura tra le lettere di 1–2 px, uguale in classico e in HD.

## Limiti noti (da completare per motore)
- L'interpolazione riguarda lo scorrimento e i frame intermedi tra un tick e l'altro; gli
  spostamenti degli sprite sono interpolati solo se il motore ridisegna gli oggetti con
  la posizione intermedia (hook specifico del motore, es. le camminate).
- Per `scroll-wide` il back buffer del motore deve contenere più del solo schermo
  (vero per i motori che tengono in memoria tutto il fondale).
- Il testo HD del Layer comune è semplice (niente condensazione automatica): per motori con
  fumetti complessi serve la cattura delle stringhe per superficie descritta in
  `references/conoscenza/motore-e-test.md` §4.
