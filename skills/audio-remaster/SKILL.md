---
name: audio-remaster
description: Migliora musica ed effetti di un'avventura d'epoca senza tradirne il carattere — rendering dei brani MIDI/AdLib/MT-32 con soundfont o emulazione di qualità, rimasterizzazione delle tracce CD, ricampionamento e pulizia degli effetti, livelli del mix fissi (voci -18, effetti ≤ -16, musica -25 LUFS) — producendo file conformi al contratto RAC con toggle verso l'audio originale. Usala nella fase asset del remaster.
---

# Audio

Strumenti locali: `ffmpeg` (soxr, loudnorm, afftdn, adeclip, alimiter), `fluidsynth`, `munt`
(MT-32) se disponibile. `rstool.py audio backends`. Regole ricavate dal progetto di riferimento
(`${CLAUDE_PLUGIN_ROOT}/references/conoscenza/voci-testi-audio-flusso.md`, §3).

## Livelli del mix (fissi per tutto il gioco)
| Tipo | Livello | Note |
|---|---|---|
| Voci (doppiaggio) | -18 LUFS | mono 44,1 kHz |
| Effetti | ≤ -16 LUFS | picchi limitati; mai più forti dell'originale se l'originale era già forte |
| Musica (CD, MIDI, MOD) | **-25 LUFS** | tutte le tracce allo stesso livello |
La musica va 7 dB sotto le voci: a livelli uguali copre il parlato (verificato sul progetto di riferimento).
Se il gioco non viene doppiato, chiedi all'utente se tenere comunque la musica a -25 o
alzarla (es. -20). Registra i livelli in `remaster.json` (`audio.levels`) e rispettali per
ogni asset nuovo.

## Musica
Riconosci il formato (`rstool.py audio scan <cartella>`): MIDI generico, formati proprietari
(varianti MIDI specifiche del motore, XMI, MUS), MOD/tracker, tracce CD audio.
- **MIDI/proprietari** → converti in .mid standard (convertitore scritto per quel formato dalla
  documentazione pubblica del motore; attenzione a varianti interne come campi in big-endian
  in alcuni brani) o
  registra l'uscita MIDI del motore (hook da aggiungere al driver MIDI: non è nel Layer comune),
  poi `rstool.py audio render-midi <mid> --soundfont <sf2> --out remaster/music/<nome>.ogg`.
  Dispositivo pensato dai compositori (style bible/crediti): MT-32 per molti giochi
  1989-92 (munt con ROM dell'utente), General MIDI con soundfont di qualità dopo.
  Prepara 2 varianti di un brano e falle ascoltare prima di renderizzare tutto.
- **Tracce CD** → estrazione dall'immagine dell'utente; per ogni traccia misura la loudness
  (`ffmpeg -af ebur128`), poi `rstool.py audio master <in> <out> --lufs -25 [--declip]`:
  guadagno limitato a ±8 dB, `adeclip` solo sulle tracce già saturate nell'originale,
  limitatore, OGG q6.
- **Loop**: mantieni i punti di loop (metadati `LOOPSTART/LOOPLENGTH` nell'OGG).

## Effetti originali
`rstool.py audio sfx <cartella> --rates analysis/sfx-rates.json --out remaster/sfx`
- la frequenza di riproduzione spesso non è nel file ma nello script che lo suona (con un
  valore predefinito, es. 11025 Hz): ricavala dagli script, un file per ogni frequenza usata,
  `nome_<rate>.ogg`;
- DC tolto, fruscio di quantizzazione a 8 bit ridotto, ricampionamento a 44,1 kHz senza
  aliasing, limitatore morbido; **stessa durata e livello percepito** dell'originale;
- niente "migliorie" che cambiano il timbro.

## Effetti rifatti (solo se l'utente lo chiede)
ElevenLabs Sound Effects (~10 crediti al secondo): stessa durata dell'originale, livello
dell'originale ma mai sopra -16 LUFS, `loop` se l'originale è in loop. La descrizione (in
inglese) si scrive da **ciò che succede nella scena e da ciò che si sente**, mai dal nome del
file (un file chiamato come uno sparo può essere un'esplosione). Tieni l'originale di riserva e fai
approvare un campione prima del lotto.

## Toggle
Il toggle originale/remaster commuta anche l'audio (opzione `remaster_audio_follow_toggle`):
la musica riparte dallo stesso punto nel formato originale.
