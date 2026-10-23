---
name: build-release
description: Produce gli eseguibili (Windows, Linux, macOS, Android, Web) e la patch distribuibile di un remaster costruito su un fork di ScummVM — CI multipiattaforma, pacchetto asset o ricette, installer che verifica la copia originale dell'utente, licenze e crediti. Usala nella fase di rilascio del remaster.
---

# Build e rilascio

## Build
Le build si fanno in CI, non a mano: copia `${CLAUDE_PLUGIN_ROOT}/ci/remaster-build.yml` in
`.github/workflows/` del fork e `ci/android-libs.sh` in `.github/remaster/`, poi imposta
`ENGINE` (l'id del motore in ScummVM) e `GAME_ID`. Il job Linux è stato verificato in locale sul commit
base; Windows, macOS, Web e Android usano le ricette ufficiali di ScummVM ma vanno provati
al primo giro di CI (correggi e annota in `remaster.json`).
Il workflow produce:
| Piattaforma | Come | Artefatto |
|---|---|---|
| Windows x64 | MSYS2 / MinGW-w64 | `scummvm-remaster-<gioco>-win64.zip` |
| Linux x64 | Ubuntu 24.04, `make test` incluso | `...-linux-x86_64.tar.gz` |
| macOS (Apple Silicon) | runner macos-14, `make bundle` | `...-macos.zip` (non firmato: istruzioni per Gatekeeper) |
| Android arm64 | NDK 23.2 + librerie da `android-libs.sh`, `make androiddistdebug` | `...-android.apk` (firma di debug, o keystore dell'utente) |
| Web | `dists/emscripten/build.sh build` di ScummVM | `...-web.zip` (pagina + .wasm; i file del gioco li sceglie l'utente) |

Sempre `--disable-all-engines --enable-engine=$ENGINE` per eseguibili piccoli e un solo gioco.
Se la CI non è disponibile, `ci/build-local.sh` compila Linux (e Web, se emsdk è scaricabile) in locale.

## Patch distribuibile
```
rstool.py engine md5 <cartella del gioco> --out recipes/game-md5.json --version-name <es. dos-cd-it>
rstool.py release package --game-md5 recipes/game-md5.json --patches release/patches \
    --engines release/engines --licenses release/LICENSES \
    [--recipes recipes | --remaster remaster]  --version 1.0.0
```
Struttura prodotta:
```
release/
  <gioco>-remaster-<versione>/
    LEGGIMI.txt / README.txt   istruzioni per piattaforma
    patches/*.patch            diff del motore sul commit base (GPL)
    engine/                    eseguibili per piattaforma (dalla CI)
    remaster/                  asset (solo modalità asset-pack) oppure
    recipes/ + tools/          ricette e strumenti (modalità recipe)
    install.py                 verifica gli MD5 dei file originali, copia/genera remaster/
    checksums.sha256
    LICENSES/                  GPL-3.0, OFL dei font, note ElevenLabs, crediti
```
- `install.py` rifiuta di procedere se i file originali non corrispondono a una versione
  nota (MD5 in `recipes/game-md5.json`) e non modifica mai i file originali.
- Web: il loader chiede all'utente di scegliere la cartella/immagine del gioco dal suo
  dispositivo; nulla del gioco è incluso nel pacchetto.
- Mai includere file del gioco originale, nemmeno "di comodo" (font, palette, script).
- **Motore e patch sempre separati**, anche nella distribuzione: l'eseguibile del motore modificato
  (per piattaforma, o il sito web) e la patch del gioco (pacchetto asset o ricette, versionata
  `patch-N` col suo manifest) sono artefatti distinti, scaricati, importati e aggiornati ognuno per
  conto suo. Un motore nuovo non obbliga a riscaricare la patch, e viceversa; sul web stanno in
  chiavi di cache separate, e la pagina mostra le versioni (motore, patch) e se ci sono i file del
  gioco in tre stati distinti. Il manifest della patch dichiara la versione minima del motore.

## Versione web e pagina unica (utente da telefono)
- Sito (GitHub Pages): solo motore + pagina di importazione; il giocatore importa nel browser la
  sua immagine del CD (`.img` raw, `.iso`), uno zip o un `.7z` e la patch (zip o volumi),
  salvati in Cache Storage/IndexedDB. L'azione di deploy deve fermarsi se trova dati di gioco.
  Su un repository privato Pages richiede un piano GitHub a pagamento.
- **Pagina HTML unica** (~7 MB, wasm e dati del motore incorporati) che funziona da `file://`
  senza server né service worker: è la consegna più comoda su telefono. Il motore web viene incorporato
  come gzip+base64 e `fetch` viene avvolto per servire il file system HTTP di ScummVM.
- Patch del gioco in un file unico + **volumi da 29 MB** (limiti di chat e telefono) con
  checksum e script per ricomporli; la pagina accetta i volumi selezionati tutti insieme.
- **Pagina leggera** (~120 KB) che scarica e aggiorna da sola motore e patch da un repository
  privato con un token in sola lettura incollato dall'utente (mai nella pagina o nei log), file
  verificati con lo SHA git, aggiornamenti incrementali: dettagli nella nota del motore §16.
- Versioni `patch-N` progressive, mai riusate o spostate; Release private; rilascio completo solo
  con CI verde e asset verificati.
- Azioni GitHub manuali (Run workflow) per ogni build; repo privato: 2.000 minuti al mese,
  macOS ne consuma 10 volte tanto: lanciala solo quando serve.

## Controlli finali
Prima del pacchetto: `rstool.py release budget remaster` (peso per cartella, immagini più
pesanti da decodificare, limiti per desktop, Android e web; i fondali PNG grandi diventano JPEG
q90 4:4:4). La pagina HTML del manuale (`remaster/manual/<lang>.html` con `img/`) va copiata
anche accanto agli eseguibili, e la configurazione distribuita imposta `gui_theme`/`themepath`
sul tema del remaster. In modalità `recipe` nessun logo o manuale dei titolari (vedi
`${CLAUDE_PLUGIN_ROOT}/references/legal-distribution.md`).
Poi `rstool.py release verify release/<cartella>`: nessun file con MD5 uguale a un file
originale, licenze presenti, checksum validi, manifest RAC coerente. Poi riepilogo
all'utente: una riga per artefatto.
