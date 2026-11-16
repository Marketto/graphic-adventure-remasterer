# 1b. Tempi: confronto con l'originale sulla sua piattaforma (obbligatorio)

Dettaglio della skill `engine-integration`.

Mai assumere un passo fisso. Molti giochi d'epoca non hanno timer: un passo dura il tempo di
disegno più l'attesa del ritraccio verticale, quindi le scene leggere vanno più veloci di
quelle animate, indipendentemente dalla CPU (caso reale: 43-160 ms; il port andava a 33 ms fissi,
fino a 4 volte più veloce).
1. **Riferimento**: la piattaforma di destinazione dell'originale (`game.platform`) decide
   come si simula: `rstool.py engine reference --platform <dos|windows|windows3|mac|amiga-pal|
   atari-st|pc-98|...>` dà la soluzione affidabile più vicina, in ordine di fedeltà:
   DOSBox Staging/DOSBox-X per DOS (86Box/PCem se i tempi dipendono dall'hardware), una
   macchina virtuale d'epoca (86Box/PCem, QEMU, VirtualBox con Windows 95/98) per Windows, Wine
   solo per ciò che non dipende dai tempi (logica, testi), WinUAE/FS-UAE cycle-exact per Amiga,
   Hatari per Atari ST, Basilisk II/SheepShaver per Mac, MAME o l'emulatore dedicato per le altre.
   Stessa edizione del gioco (lingua, floppy/CD). ROM, BIOS e sistemi d'epoca li fornisce l'utente.
2. Avvia l'originale sotto Xvfb (per DOSBox `[sdl] autolock=false`, `mount c` + `imgmount d <iso>
   -t iso`), pilota il mouse con `xdotool`, registra con `ffmpeg -f x11grab -framerate 60`.
3. Misura: `rstool.py engine timing rec.mkv --segments seg.json --crop x,y,w,h --out
   qa/timing-originale.json` (intervalli tra fotogrammi che cambiano) in 4-5 tratti diversi
   (leggero, medio, molto animato, filmato, titoli) e la durata totale dell'intro.
4. Registra allo stesso modo il remaster (o fai stampare al motore la durata di ogni passo) e
   confronta: `rstool.py engine timing-compare qa/timing-originale.json qa/timing-remaster.json`.
5. Se il tempo dipende dal carico, modella il passo (es. dall'area animata a schermo,
   arrotondato a ritracce intere) e lascia un override in configurazione (`<gioco>_tick_ms`).
6. Obiettivo: durata dell'intro entro il 2-3% e cadenza delle animazioni uguale; annota
   misure, emulatore e impostazioni in `docs/test.md`.
Per i test automatici con molte attese si può forzare un passo corto nella configurazione.
Lo stesso riferimento serve per l'aspetto (proporzione dei pixel, skill `widescreen`) e per
la sensazione dei controlli (skill `engine-integration` §1g).
