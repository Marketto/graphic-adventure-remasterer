---
name: audio-remaster
description: Migliora musica ed effetti di un'avventura d'epoca senza tradirne il carattere — rendering dei brani MIDI/AdLib/MT-32 con soundfont o emulazione di qualità, rimasterizzazione delle tracce CD, ricampionamento e pulizia degli effetti, normalizzazione per gruppo (musica, effetti, parlato) e poi livelli di mix tra i gruppi — producendo file conformi al contratto RAC con toggle verso l'audio originale. Usala nella fase asset del remaster.
---

# Audio

Strumenti locali: `ffmpeg` (soxr, loudnorm, afftdn, adeclip, alimiter), `fluidsynth`, `munt`
(MT-32) se disponibile. `rstool.py audio backends`. Regole ricavate dal progetto di riferimento
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
- **MIDI/proprietari** → converti in .mid standard (convertitore scritto per quel formato dalla
  documentazione pubblica del motore; attenzione a varianti interne come campi in big-endian
  in alcuni brani) o
  registra l'uscita MIDI del motore (hook da aggiungere al driver MIDI: non è nel Layer comune),
  poi `rstool.py audio render-midi <mid> --soundfont <sf2> --out audio/render/<nome>.flac` e le
  due fasi sopra.
  Dispositivo pensato dai compositori (style bible/crediti): MT-32 per molti giochi
  1989-92 (munt con ROM dell'utente), General MIDI con soundfont di qualità dopo.
  Prepara 2 varianti di un brano e falle ascoltare prima di renderizzare tutto.
- **Tracce CD** → estrazione dall'immagine dell'utente; per ogni traccia misura la loudness
  (`rstool.py audio loudness`); quelle già saturate nell'originale si indicano in fase 1
  (`audio normalize music ... --declip <nomi>`) e ricevono `adeclip` nella codifica della fase 2.
- **Loop**: mantieni i punti di loop: `audio normalize ... --loops loops.json` (`{nome: [inizio,
  lunghezza]}` in campioni, o campo `loop` nel piano) → metadati `LOOPSTART/LOOPLENGTH` nell'OGG.

## Effetti originali
`rstool.py audio sfx <cartella> --rates analysis/sfx-rates.json --out audio/clean/sfx --lossless`
(poi fase 1 come gruppo `sfx` e fase 2)
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
