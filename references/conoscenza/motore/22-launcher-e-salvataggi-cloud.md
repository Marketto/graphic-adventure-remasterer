# Launcher a tema e salvataggi nel cloud

Skill: `launcher-sync`. Modelli di codice: `tools/remaster_tools/templates/launcher/`.

## Una sola interfaccia
- La stessa pagina gira nell'app desktop (Electron) e in una WebView mobile, con un piccolo ponte nativo.
  - Uno script adatta le poche frasi diverse e **si ferma se non le trova più**.
- Tema del gioco:
  - transizioni senza ricaricare la pagina;
  - pulsanti primario, secondario e pericolo;
  - bersagli di almeno 44 px;
  - focus sul titolo di ogni passo;
  - barra di avanzamento annunciata a ogni quarto;
  - rispetto di *riduci movimento*.
- Tema dei menu del motore generato da uno script, con il font del gioco; un'etichetta troppo larga ripiega sul font normale.
- Musica del launcher:
  - brani di pubblico dominio arrangiati da MIDI con un SoundFont, tutti allo stesso livello;
  - parte un brano a caso, poi si alternano;
  - pulsante per spegnerla;
  - sfuma all'avvio del gioco e si sospende quando l'app va in secondo piano.

## Importazione dei file originali
- Formati: zip, volumi, ISO, immagini raw, 7z. La decompressione va in streaming: un'immagine CD dentro un archivio si legge mentre si decomprime e ci si ferma a fine traccia dati.
- **Gioco completo o niente**: un segno "incompleto" durante l'importazione e il controllo dei file indispensabili. Il pulsante d'avvio resta spento finché il controllo non passa.
- Spazio:
  - `navigator.storage.persist()`;
  - stima dello spazio libero;
  - gestione di `QuotaExceededError`;
  - riapertura di IndexedDB.
- **Avviatore fisso con contratto versionato**: su mobile un HTML sostituito è un'altra origine e perde i dati. Motore e patch si aggiornano dietro un avviatore che non cambia.

## Salvataggi su Dropbox (o servizio equivalente)
- Desktop nativo: il cloud del motore, se esiste. Web e WebView: sincronizza la pagina, perché il cloud del motore ha problemi di CORS sul refresh e scrive i token nella console.
- **OAuth PKCE senza server**:
  - l'utente incolla il codice;
  - il verificatore resta salvato finché non viene usato;
  - il refresh token va nello storage, l'access token solo in memoria;
  - `invalid_grant` fa dimenticare il collegamento;
  - "Scollega" revoca il token;
  - nessun token nella console;
  - l'app key sta in un solo punto e nel repository è vuota (senza chiave la sezione non compare).
- **App con accesso alla sola cartella dell'app**, permessi di lettura e scrittura dei file, client pubblici consentiti.
- **Dati**: un solo zip dei salvataggi.
  - Il primo invio è `add`.
  - Gli invii successivi sono `update` sulla revisione nota: se un altro dispositivo ha scritto, nasce un conflitto e mai una sovrascrittura silenziosa.
  - `overwrite` solo dopo conferma dell'utente.
- **Unione a tre vie**, con gli hash dell'ultima sincronizzazione come base:
  - un file cambiato da una sola parte prende quella versione, cancellazioni comprese;
  - cambiato da entrambe le parti, o senza base, vince il più recente a parità di nome, invece di creare doppioni.
- **Quando sincronizza**:
  - all'apertura, e "Avvia" aspetta al massimo 15 s;
  - ogni minuto;
  - quando la pagina viene nascosta o chiusa;
  - **mai scaricare a gioco avviato**.
- L'hash dei cambiamenti esclude la configurazione che il motore riscrive a ogni avvio.
- Mobile: sincronizzazione a ogni uscita dallo schermo, poi pausa dei timer.
- **Test**:
  - finto servizio con routing del browser, due contesti (desktop e telefono);
  - controllo del verificatore PKCE;
  - conflitti, token scaduto, assenza di rete;
  - nessun token nella console;
  - unione provata senza browser.

## Privacy
Sul sito pubblico solo il motore e la pagina di importazione; il tema con la grafica del gioco sta in un ramo privato. La CI controlla che non ci siano token negli HTML.
