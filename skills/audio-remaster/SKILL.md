---
name: audio-remaster
description: Musica (lineare o MIDI dinamica), effetti sonori (restauro, rifacimento con ElevenLabs, versi), voci originali e mix per gruppi, con toggle verso l'audio originale. Usala nella fase asset del remaster.
---

# Audio

Strumenti locali: `ffmpeg` (soxr, loudnorm, afftdn, adeclip, alimiter), `fluidsynth`, `munt`
(MT-32) se disponibile. `rstool.py audio backends` (FluidSynth conta anche come sola libreria: al
motore basta quella; il programma serve per i rendering di prova). Regole comuni:
`${CLAUDE_PLUGIN_ROOT}/references/regole-comuni.md` (prima l'uso: `usage scan` su brani ed effetti).

## Livelli: prima per gruppo, poi il mix tra i gruppi
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/audio-remaster-livelli-e-mix.md` prima di normalizzare e mixare i gruppi.

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
  Non basta il render GM: riorchestrazione dalle note del MIDI e, con il CD, **ibrido** (CD separato
  con Demucs come corpo, orchestra sotto, stessa sala, allineamento CD↔MIDI), con verifiche
  numeriche per brano e confronto annunciato a pari livello: leggi
  `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/voci-audio/03e-musica-lineare.md` prima di iniziare.
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
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/audio-remaster-musica-midi-dinamica.md` per la musica MIDI dinamica (brani a blocchi, transizioni dal motore).

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
ElevenLabs Sound Effects (~11 crediti al secondo). Prima `rstool.py usage gate <lotto.json>`: blocca
gli effetti mai suonati, segnala quelli sotto 0,5 s (si generano a 0,5 s e si tagliano) e i nomi
d'uscita ripetuti (`<nome>_<freq>`). Stessa durata e `loop` dell'originale, gruppo `sfx` come gli
altri. Descrizione in inglese da **ciò che succede nella scena e da ciò che si sente**, mai dal nome
del file. **Versi**: trascrivi prima; canto, cori, parole o sillabe precise diventano una battuta del
personaggio (skill `voice-dubbing`), perché il modello degli effetti non le segue. Volume nel motore:
con file già livellati, volume pieno. Originale di riserva, un campione approvato prima del lotto.
Dettagli: `${CLAUDE_PLUGIN_ROOT}/references/conoscenza/voci-audio/03d-effetti-sonori.md`.

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
