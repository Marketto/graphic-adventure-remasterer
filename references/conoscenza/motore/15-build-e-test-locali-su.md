# Build e test locali su macOS

- **Dipendenze statiche** (SDL2, jpeg, png, ogg, vorbis) compilate da uno script in un prefisso locale, senza Homebrew.
- **Build fuori sorgente**, così `git add -A` nel sorgente non raccoglie i file compilati. Si disattiva ciò che non serve: mad, flac, freetype, fluidsynth, curl, rete, cloud, tts.
- **Cartella di gioco di prova** fatta di collegamenti simbolici: dati originali + asset della patch. Non si copia nulla.
- **Test senza finestra**: driver video `dummy` di SDL e renderer software; gli screenshot funzionano. `perl` sostituisce `timeout`. Per i crash: `lldb -b -o run -o bt`.
