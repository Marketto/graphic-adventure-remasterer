# Remaster Layer per ScummVM — integrazione in un motore

`0001-ENGINES-Add-remaster-layer.patch` aggiunge `engines/remaster/` (codice comune, namespace
`Remaster`) e i test `test/graphics/remaster.h`. Verificata su ScummVM `5d13ee16` (14 ottobre 2026):
si applica pulita, compila, i 410 test di `make test` passano e l'eseguibile si collega.

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
// pixelAspect != 1 solo se deciso nell'analisi (gioco pensato per pixel non quadrati)
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

// voci (fumetti, sottotitoli, risposte)
if (!_remaster || !_remaster->playVoice(original)) showSubtitle(...);
```

## Opzioni (ScummVM .ini o menu del gioco)
| chiave | default | effetto |
|---|---|---|
| `remaster` | true | spegne del tutto il layer |
| `remaster_scale` | dal manifest (3) | 2-4 |
| `remaster_classic` | false | parte in versione originale (stesso stato del toggle) |
| `remaster_toggle_key` | 8 | tasto F1-F12 per il cambio in tempo reale |
| `remaster_widescreen` | true | viewport 16:9 |
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

## Limiti noti (da completare per motore)
- `pixelAspect` cambia solo la larghezza della viewport 16:9: la scala verticale per i giochi
  pensati per pixel non quadrati (es. 320x200 a 3x → 960x720) e la conversione del mouse
  relativa non sono ancora implementate nel Layer comune.
- L'interpolazione riguarda lo scorrimento e i frame intermedi tra un tick e l'altro; gli
  spostamenti degli sprite sono interpolati solo se il motore ridisegna gli oggetti con
  la posizione intermedia (hook specifico del motore, es. le camminate).
- Per `scroll-wide` il back buffer del motore deve contenere più del solo schermo
  (vero per i motori che tengono in memoria tutto il fondale).
- Il testo HD del Layer comune è semplice (niente condensazione automatica): per motori con
  fumetti complessi serve la cattura delle stringhe per superficie descritta in
  `references/conoscenza/motore-e-test.md` §4.
