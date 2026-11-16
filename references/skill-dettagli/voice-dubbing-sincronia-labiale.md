# 6b. Sincronia labiale

Dettaglio della skill `voice-dubbing`.

Nei giochi parlati in cui ogni clip ha i suoi dati di movimento della bocca (blocchi di
controllo accanto al campione; nel dump `voice-index.json` → `"lipsync": true`) le voci nuove
**perdono la sincronia originale**: la durata e le sillabe cambiano. Opzioni, da proporre con il
preventivo del doppiaggio (pacchetto `lipsync` del piano):
1. **dati di sincronia generati dall'audio nuovo**: inviluppo dell'ampiezza o fonemi
   (riconoscimento vocale locale con i tempi delle parole) convertiti nel formato del motore e
   salvati accanto alla voce, `voice/<lang>/<textKey>.lip.json` (`{"fps": 60, "frames": [indici
   della bocca]}`, letto dal codice del motore);
2. **ripiego**: bocca guidata dall'ampiezza in tempo reale (aperta sopra una soglia), senza dati;
3. bocca ferma o animazione originale in ciclo, se il gioco lo regge.
Prova la scelta su un capitolo col driver di test prima di estenderla.
