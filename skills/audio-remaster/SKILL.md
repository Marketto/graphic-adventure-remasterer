---
name: audio-remaster
description: Migliora musica ed effetti di un'avventura d'epoca senza tradirne il carattere — per la musica MIDI a comando dinamico la strategia "orchestra" (il MIDI resta al motore, SoundFont orchestrale composito da ricetta, diagnosi del suono acuto), rendering dei brani MIDI/AdLib/MT-32 lineari con soundfont o emulazione di qualità, rimasterizzazione delle tracce CD, ricampionamento e pulizia degli effetti, normalizzazione per gruppo (musica, effetti, parlato) e poi livelli di mix tra i gruppi — producendo file conformi al contratto RAC con toggle verso l'audio originale. Usala nella fase asset del remaster.
---

# Audio

Strumenti locali: `ffmpeg` (soxr, loudnorm, afftdn, adeclip, alimiter), `fluidsynth`, `munt`
(MT-32) se disponibile. `rstool.py audio backends` (FluidSynth conta anche come sola libreria: al
motore basta quella; il programma serve per i rendering di prova). Regole ricavate dal progetto di riferimento
(`${CLAUDE_PLUGIN_ROOT}/references/conoscenza/voci-testi-audio-flusso.md`, §3).

## Livelli: prima per gruppo, poi il mix tra i gruppi
Le tracce si dividono in tre **gruppi**: `music` (bgm: CD, MIDI renderizzato, MOD), `sfx`
(effetti) e `voice` (parlato). Il lavoro ha due fasi distinte e si codifica **una volta sola**,
con la somma dei due guadagni (niente doppia compressione con perdita):

**Fase 1 — normalizzazione per gruppo** (`rstool.py audio normalize <gruppo> <file o cartelle>`):
ogni gruppo viene portato allo stesso livello di riferimento (-23 LUFS, EBU R128) con la regola
del gruppo, e il risultato va in `analysis/audio-norm.json` (solo misure e guadagni):
| Gruppo | Regola | Perché |
|---|---|---|
| `music` | **per file**: ogni brano al riferimento | tutte le tracce devono suonare allo stesso volume |
| `voice` | **per file**: ogni battuta al riferimento | nessun personaggio più forte di un altro |
| `sfx` | **per gruppo**: un solo guadagno per tutti, calcolato sugli effetti forti (90° percentile) | resta la differenza voluta dagli autori tra un sussurro e un'esplosione |
Clip più corte di 400 ms (la misura integrata le dà a -70 LUFS): `normalize` le misura insieme,
concatenate, e dà a tutte lo stesso guadagno (campo `short` nel piano).
Prima della fase 1: effetti puliti e ricampionati (`audio sfx --lossless`), MIDI renderizzato in
WAV/FLAC (`audio render-midi ... --out x.flac`), tracce CD estratte: tutto senza perdita.

**Fase 2 — mix** (`rstool.py audio mix analysis/audio-norm.json --mix audio/mix.json --out remaster`):
un livello per gruppo fissa il rapporto tra le tracce. Valori di partenza (banco di prova):
| Gruppo | Livello nel mix | Note |
|---|---|---|
| Parlato | -18 LUFS | mono 44,1 kHz |
| Effetti | -16 LUFS gli effetti forti, nessun file oltre -16 (`cap`) | mai più forti dell'originale se l'originale era già forte |
| Musica | -25 LUFS | ~7 dB sotto il parlato: a livelli uguali la musica lo copre |
Guadagno statico (al massimo ±8 dB, la dinamica non cambia), `adeclip` solo sulle tracce già
saturate nell'originale, limitatore a 0,89, OGG Vorbis q6; i file limitati sono elencati.
I livelli stanno in `remaster.json` (`audio.mix`, usato quando non si passa `--mix`) o in un
`audio/mix.json` nel repository privato, per esempio `{"voice": -18, "sfx": -16, "music": -25,
"cap": {"sfx": -16}}`. **Si decide ascoltando**: `rstool.py audio mix-preview --music <brano>
--sfx <effetto> --voice <battuta> --music-offsets 0 -3 3` produce 2-3 prove (musica di sottofondo,
un effetto, una battuta) da far sentire all'utente; il valore scelto vale per tutto il gioco.
Se il gioco non viene doppiato, la musica può salire (es. -20): chiedilo con una prova
d'ascolto. Registra i livelli in `remaster.json` (`audio.mix`) e nelle decisioni, e rifai la
fase 2 (non la 1) quando cambiano. Gli slider musica/effetti/parlato di ScummVM restano al
giocatore: partono uguali, quindi il mix scelto è quello che sente.

## Musica
Riconosci il formato (`rstool.py audio scan <cartella>`): MIDI generico, formati proprietari
(varianti MIDI specifiche del motore, XMI, MUS), MOD/tracker, tracce CD audio.
- **MIDI a comando dinamico** (il motore salta, ripete, cambia volumi e trasposizioni delle parti
  per ordine degli script) → **non si renderizza**: strategia "orchestra", sezione sotto.
- **MIDI/proprietari lineari** (il brano si suona da capo a fine, al massimo in loop) → converti in .mid standard (convertitore scritto per quel formato dalla
  documentazione pubblica del motore; attenzione a varianti interne come campi in big-endian
  in alcuni brani) o
  registra l'uscita MIDI del motore (hook da aggiungere al driver MIDI: non è nel Layer comune),
  poi `rstool.py audio render-midi <mid> --soundfont <sf2> --out audio/render/<nome>.flac` e le
  due fasi sopra.
  Dispositivo pensato dai compositori (style bible/crediti): MT-32 per molti giochi
  1989-92 (munt con ROM dell'utente), General MIDI con soundfont di qualità dopo.
  Prepara 2 varianti di un brano e falle ascoltare prima di renderizzare tutto.
- **Blocchi con più varianti**: alcuni motori tengono nello stesso blocco di suono più versioni
  (MT-32/General MIDI, AdLib, altoparlante, campioni digitali) e `audio scan` non li vede:
  l'estrazione (adattatore, `rstool.py engine extract`) scrive in `midi/` la variante più vicina
  al General MIDI come .mid standard. Poi `rstool.py audio midi-classify <dump>/midi` separa
  **brani** ed **effetti** (brano: durata ≥ 20 s **e** ≥ 80 note, `--min-seconds`/`--min-notes`
  per un altro gioco) e dà i minuti di musica. Con un sistema di **musica interattiva** (punti di
  ripetizione e di salto) la durata del file è più lunga di un ascolto: i minuti sono un limite
  superiore, e i loop vanno misurati sul rendering (o registrando l'uscita MIDI del motore).
- **Tracce CD** → estrazione dall'immagine dell'utente; per ogni traccia misura la loudness
  (`rstool.py audio loudness`); quelle già saturate nell'originale si indicano in fase 1
  (`audio normalize music ... --declip <nomi>`) e ricevono `adeclip` nella codifica della fase 2.
- **Loop**: mantieni i punti di loop: `audio normalize ... --loops loops.json` (`{nome: [inizio,
  lunghezza]}` in campioni, o campo `loop` nel piano) → metadati `LOOPSTART/LOOPLENGTH` nell'OGG.

## Musica MIDI dinamica: strategia orchestra
**Regola (decisione dell'utente).** Per la musica MIDI a comando dinamico, tipica delle avventure
anni '90 scritte per moduli sintetizzatori (MT-32, GS e simili), la strategia migliore è
**"orchestra"**: il MIDI resta suonato dal motore e si costruisce un **SoundFont orchestrale
composito**. Non si renderizza in file (`music/<nome>.ogg`), non si usano generatori di musica.

**a. Riconoscerla.** Segni: sysex o marcatori propri del motore nei MIDI, punti di salto e di
ripetizione, volumi delle parti cambiati dagli script, cambi di brano agganciati agli eventi,
effetti sonori MIDI sullo stesso sintetizzatore. Prova decisiva: registra il motore
(`SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE=<file>.raw`) e confronta con la durata del file
(`audio midi-classify`): se nel gioco un brano suona molto più a lungo, o cambia senza
ricominciare, è dinamico. Un file fisso perderebbe cicli, transizioni ed effetti MIDI.

**b. Diagnosi del suono "acuto/finto"** (`rstool.py audio midi-diagnose <mid...> --table
<tabella.json> [--compare] [--audio <registrazioni>]`):
- **note per canale tra le versioni** dello stesso brano (varianti per dispositivi diversi nello
  stesso blocco, `--compare`): stesso numero di note, stesse altezze, nessuno spostamento d'ottava.
  Controlla anche le trasposizioni che il motore applica alle parti (dai suoi sysex).
- **tabella di conversione dei programmi** del modulo d'epoca → GM che usa il motore (la fornisce
  il progetto in JSON, ricavata dal sorgente o dalla documentazione del motore; mai inventata):
  `midi-diagnose` dice per ogni canale quale slot GM suona davvero e avvisa sugli slot sospetti.
  Timbri sbagliati tipici: **tromba con sordina (59) al posto di tromba aperta (56)**, **ocarina
  (79) al posto di flauto (73)**. Pesa ogni errore con il numero di note che lo usano nel gioco.
- **curva di velocità**: i sintetizzatori GM moderni attenuano le note piano molto più dei moduli
  d'epoca (legge quadratica, 960 cB): le parti d'accompagnamento a velocità e CC7 bassi scendono
  10-15 dB sotto la melodia e **l'accompagnamento sparisce** (resta solo l'acuto). Il rapporto
  mostra il livello di ogni canale con le due curve.
- **riverbero e mandata reale**: le prove offline devono avere la mandata (CC91) che il motore
  manda davvero (`audio midi-remap --reverb-send`), altrimenti si giudica un suono secco.
- **misura**: `rstool.py audio bands <file>`: baricentro, energia < 250 Hz / 250-2k / 2-4k /
  > 4 kHz, quota delle ottave C1-B3, nota dominante. "Acuto" = baricentro alto e quasi niente
  sotto 250 Hz rispetto all'originale e al riferimento.

**c. SoundFont composito da ricetta** (`rstool.py audio sf2-compose <ricetta.json> --out
<file.sf2>`, formato nel docstring di `tools/remaster_tools/audio_sf2.py`; `audio sf2-info` per
elencare i preset):
- banco base GM con **licenza libera** (FluidR3_GM, MuseScore_General, GeneralUser GS);
- sezioni orchestrali (ottoni, timpani, archi, legni) da banchi liberi (Sonatina Symphonic
  Orchestra, VSCO-2...) importate negli slot GM (`imports`, con `attenuation_cb`/`transpose`
  per pareggiare livelli e registri);
- **correzioni negli slot che la tabella sceglie male** (`copies`/`imports`: lo slot 59 riceve
  una tromba aperta, lo slot 79 un flauto) solo se nel gioco quello slot arriva **solo** dal
  programma sbagliato (verificalo con `midi-diagnose` su tutti i brani): il motore non cambia;
- curva di velocità meno ripida: `velocity_attenuation_cb` (es. -480 = metà della curva GM);
- riverbero da sala nelle impostazioni del motore (sotto), non nel SoundFont;
- **licenze**: ogni fonte va in `credits` (fonte, autore, licenza, URL); il comando scrive
  `<out>.crediti.txt` e avvisa se manca qualcosa. CC Sampling Plus e CC BY chiedono la citazione
  dell'autore nei crediti del rilascio. I banchi non si committano (repository privato o
  download dell'utente) se la licenza non lo permette o se pesano troppo;
- **variante leggera** (web/telefono): base sf3 compressa (es. MuseScore_General Lite) con le
  sole `copies` (gli import vogliono campioni PCM: per una variante leggera completa componi in
  sf2 e comprimi alla fine con `sf3convert`, se disponibile). Controlla che il FluidSynth della
  build legga sf3 (libsndfile con Vorbis: `rstool.py audio backends` → `fluidsynth_sf3`; per le
  build statiche web/Android guarda la configurazione della build); ripiego: un sf2 con le sole
  correzioni o un banco base piccolo.

**d. Riferimento d'ascolto.** Se esiste una registrazione orchestrale dell'opera d'origine (colonna
sonora di un film, di una serie), usala con le **stesse regole della voce di riferimento**: solo
misure (organico, registro, tempo, tonalità, coda della sala con `audio bands` e l'ascolto), mai
nel pacchetto né nel repository, cancellata dopo la misura; al massimo 2 tentativi di download per
piattaforma, mai cookie.

**e. Livello nel motore.** Il livello vero si misura **nel motore** (driver audio su disco, come
sopra) su 3-4 brani, perché i volumi delle parti decisi dagli script non ci sono nelle prove
offline; poi si regola `midi_gain` perché la musica stia **~7 dB sotto il parlato** (come il mix).
Una curva di velocità più dolce alza il livello di 4-11 dB a pari guadagno: rimisura dopo ogni
ricetta. Impostazioni del motore nel pacchetto (es. `music/impostazioni-motore.ini`, predefinite
del dominio, vince l'utente): `music_driver=fluidsynth`, `soundfont=`, `midi_gain=`, riverbero
(in ScummVM i parametri FluidSynth sono interi: roomsize, damping, level divisi per 100, **la
larghezza divisa per 10**), chorus spento, interpolazione alta. MT-32 emulato resta l'alternativa
più fedele solo con le ROM dell'utente.

**Domanda all'utente.** Proponi "orchestra" come **raccomandata**, con prove d'ascolto a **pari
volume** (stesso LUFS, 30 s per brano su 2 brani diversi): originale (registrato dal motore), GM
semplice, orchestra, leggera. Le prove offline si fanno con `audio midi-remap` (tabella del motore
+ mandata del riverbero) e `audio render-midi`; di' che non contengono i cicli del motore.

## Effetti originali
`rstool.py audio sfx <cartella> --rates analysis/sfx-rates.json --out audio/clean/sfx --lossless`
(poi fase 1 come gruppo `sfx` e fase 2)
- `--rates`: file JSON `{"nome": 11025}` o `{"nome": [11025, 22050]}`, oppure un numero solo per
  tutti i file (`--rates 11025`);
- la frequenza di riproduzione spesso non è nel file ma nello script che lo suona (con un
  valore predefinito, es. 11025 Hz): ricavala dagli script, un file per ogni frequenza usata,
  `nome_<rate>.ogg`;
- DC tolto, fruscio di quantizzazione a 8 bit ridotto, ricampionamento a 44,1 kHz senza
  aliasing, limitatore morbido; **stessa durata e livello percepito** dell'originale;
- niente "migliorie" che cambiano il timbro.

## Effetti rifatti (solo se l'utente lo chiede)
ElevenLabs Sound Effects (~10 crediti al secondo): stessa durata dell'originale, entrano nel
gruppo `sfx` come gli altri (stesso guadagno di gruppo, mai oltre il `cap`), `loop` se l'originale è in loop. La descrizione (in
inglese) si scrive da **ciò che succede nella scena e da ciò che si sente**, mai dal nome del
file (un file chiamato come uno sparo può essere un'esplosione). Tieni l'originale di riserva e fai
approvare un campione prima del lotto.

## Toggle
Il toggle originale/remaster commuta anche l'audio (opzione `remaster_audio_follow_toggle`):
la musica riparte dallo stesso punto nel formato originale.

## Voci originali (giochi già parlati)
Il parlato registrato d'epoca (spesso 8 bit, 11-22 kHz, fruscio e clic) si **restaura**, non si
sostituisce: `rstool.py audio restore-speech <cartella> --out audio/clean/voice [--model
deepfilternet]` toglie rombo e continua, ripara i clic, riduce il fruscio di quantizzazione e
ricampiona a 44,1 kHz senza inventare banda; il modello locale DeepFilterNet (gratuito, se
installato) pulisce di più ma va ascoltato su 5-10 battute prima del lotto (a volte "impasta"
le consonanti). Poi gruppo `voice` delle due fasi. Il doppiaggio nuovo (skill `voice-dubbing`)
si propone solo per le lingue senza voci originali o se l'utente lo chiede.

## Voci
Le battute generate (skill `voice-dubbing`) sono il gruppo `voice`: la regola è per file, quindi
`voice generate` fa fase 1 e 2 in un solo passaggio, dalla MP3 originale (conservata in
`originali/`) al livello del parlato nel mix (`loudnorm` per battuta: sul parlato una leggera
compressione è voluta). Se quel livello cambia: `rstool.py voice reencode <copione> --cast
<cast> --out <cartella voci>`, dalle MP3, senza nuove chiamate a pagamento. Le voci originali del gioco, se ci sono, passano per le due fasi
come gli altri gruppi.
