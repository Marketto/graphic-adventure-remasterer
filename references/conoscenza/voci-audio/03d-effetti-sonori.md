# Effetti sonori: restauro, rifacimento con IA, versi

1. **Censimento d'uso prima di tutto** (`rstool.py usage scan`, poi `usage gate` sul lotto).
   - In un caso reale circa 800 crediti sono andati in effetti che il gioco non suona mai.
   - Attenzione ai nomi contenuti in altri nomi: il confronto va fatto a parole intere.
   - Una parte dei file "rimasti" non viene mai suonata.
2. **Restauro gratuito**: riduzione del rumore con soglia sul rumore degli 8 bit, ricampionamento polifase a 44,1 kHz, limitatore. Stessa durata e stesso livello dell'originale.
3. **Rifacimento con ElevenLabs Sound Effects** (~11 crediti al secondo, costo nel preventivo).
   - Descrizione in inglese scritta da ciò che succede nella scena e dall'analisi del suono, **non dal nome del file**: un file chiamato "sparo" può essere un'esplosione.
   - Durata e loop dell'originale; poi correzioni dell'utente all'ascolto.
   - **Durata minima 0,5 s**: gli effetti più corti si generano a 0,5 s e si tagliano dopo, controllando che il suono non si perda.
   - **Stesso suono a frequenze diverse**: un file per coppia, `<nome>_<freq>`, altrimenti le generazioni si sovrascrivono.
4. **Versi e onomatopee**. Trascrivere prima il suono originale per sapere se contiene parole.
   - Urla, starnuti, singhiozzi e russare senza parole: effetto.
   - **Canto, cori, parole o sillabe precise: il modello degli effetti non le segue.** Diventano una battuta del personaggio con la sua voce del cast, con un audio tag d'azione.
5. **Effetti spenti nell'originale** (righe commentate, zone mai avviate): si riaccendono con le righe della patch, solo se l'utente lo vuole (vedi la versione extended).
6. **Volume**: mix per categoria (ambiente, azioni, interfaccia, voci), poi controllo del volume applicato dal motore. Molti motori suonano gli effetti a una frazione del volume: con file nuovi già livellati va usato il volume pieno, lasciando il livello nel file.
