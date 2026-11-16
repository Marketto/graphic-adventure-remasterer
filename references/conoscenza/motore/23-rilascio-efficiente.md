# Rilascio efficiente

- **Compressione con cache**: si ricomprime solo ciò che è cambiato. Musica Vorbis q4, voci q2, PNG quantizzati, JPEG q85. Gli sfondi 4:3 si tolgono se il motore li ritaglia dal 16:9. Risparmio tipico: un terzo.
  - I metadati di provenienza (IA, licenze) vanno conservati: XMP nelle immagini, tag Vorbis nell'audio, senza ricodificare.
- **Pacchetti incrementali**: zip completo più aggiornamenti dalle ultime 3 versioni, con l'elenco degli SHA per versione.
- **Rilascio da una macchina locale** quando i minuti di CI costano. Prima di partire si controlla:
  - ramo principale;
  - nessuna modifica locale;
  - allineamento col remoto;
  - tag non ancora esistente.

  Alla fine lo script pulisce dopo di sé.
- **CI**:
  - artifact con conservazione breve e solo la copia più recente;
  - il motore passa tra i job tramite cache;
  - timeout sui passi di pubblicazione (uno stallo di ore costa);
  - `http.postBuffer` alto per i push grandi;
  - commit a blocchi sotto il limite dell'host.
- **Provenienza IA e crediti**: un file nel pacchetto con l'elenco dei file generati, il servizio usato e la dicitura sui diritti del gioco originale, che appartengono ai rispettivi titolari, con nota di progetto non ufficiale. Più i titoli di coda del remaster.
- **Piattaforme** (trappole tipiche):
  - versione esatta dell'NDK;
  - APK costruibile senza Gradle;
  - keystore da conservare;
  - `allowBackup` spento;
  - una versione di Electron che supporti ancora il macOS minimo voluto;
  - librerie statiche per Windows;
  - build fuori dalla cartella dei sorgenti.

  Ridurre le piattaforme native, quando il motore web basta, taglia molto lavoro di manutenzione.
