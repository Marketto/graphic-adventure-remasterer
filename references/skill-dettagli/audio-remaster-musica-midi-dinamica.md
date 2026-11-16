# Musica MIDI dinamica: strategia orchestra

Dettaglio della skill `audio-remaster`.

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
