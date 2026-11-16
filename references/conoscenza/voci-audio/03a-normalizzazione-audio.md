# Normalizzazione di audio e musica
Regola generalizzata (21/10/2026): le tracce si **normalizzano per gruppo** (musica, effetti,
parlato: musica e parlato file per file, effetti con un guadagno unico per il gruppo, così resta
la differenza voluta tra un effetto piano e uno forte) e **poi** si fissa il **livello di mix**
tra i gruppi, scelto ascoltando prove con musica, effetto e battuta insieme. I valori sotto sono
quelli che hanno funzionato in pratica.

| Tipo | Livello | Dettagli |
|---|---|---|
| Voci | **-18 LUFS** | `loudnorm=I=-18:TP=-1.5:LRA=11`, mono 44,1 kHz, OGG Vorbis |
| Effetti | **massimo -16 LUFS** | stesso livello dell'originale ma mai sopra; `alimiter=limit=0.89` |
| Musica (CD e MIDI) | **-25 LUFS** | guadagno limitato a ±8 dB; `adeclip` sulle tracce che saturano; limiter; Vorbis q6 |

- *Problema risolto:* la musica copriva il parlato. Con circa 7 dB di distanza dalle voci il parlato resta intelligibile.
- **Effetti rifatti con ElevenLabs Sound Effects**: stessa durata e loudness dell'originale, eventuale `loop`, descrizione in inglese.
  - La descrizione si scrive da ciò che succede nella scena e da ciò che si sente, **non dal nome del file**. *Problema:* un file chiamato "sparo" era in realtà un'esplosione.
- **Rimasterizzazione dei campioni PCM a 8 bit originali**:
  - offset DC tolto;
  - riduzione del fruscio di quantizzazione (denoiser FFT con la soglia al livello di rumore degli 8 bit);
  - ricampionamento polifase a 44,1 kHz, senza immagini oltre la banda originale;
  - limiter morbido.

  La frequenza di riproduzione non è nel file ma nello script che lo suona, quindi si produce un file per ogni coppia (suono, frequenza) usata. Il motore usa il file nuovo se esiste e altrimenti torna all'originale.
- Musica MIDI **lineare** convertita in WAV con FluidSynth e una soundfont, poi normalizzata come le tracce CD (quella a comando dinamico resta al motore: §3.1b).

---
