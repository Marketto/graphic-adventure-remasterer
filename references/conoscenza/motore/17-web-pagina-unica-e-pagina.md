# Web: pagina unica e pagina leggera che si aggiorna da sola

- **Pagina unica** (~8 MB): wasm, js e dati del motore incorporati come gzip+base64.
  - `fetch` è avvolto per servire il file system HTTP di ScummVM dalla pagina. Niente service worker, quindi funziona da `file://`.
  - Gioco e patch vengono importati dai file scelti (zip, 7z, ISO) in IndexedDB. Senza IndexedDB restano in memoria.
- **Pagina leggera** (~120 KB): stesso template e stesso codice. Nella pagina ci sono solo l'indirizzo dell'API e il nome del repository.
  - **Accesso**: il login OAuth di GitHub non ha CORS. L'utente incolla una volta un token fine-grained, in sola lettura, su un solo repository e con scadenza. Il token va in `localStorage` e non compare mai nell'HTML né nei log; la CI controlla che la pagina non ne contenga.
  - **Download**: gli asset delle Release private non hanno CORS, quindi si usano l'API dei contenuti (file raw fino a 100 MB) e l'albero git ricorsivo. Ogni file si verifica con il suo SHA git (`blob <dim>\0…`) e la dimensione.
  - **Motore**: preso da un ramo dedicato a un solo commit, con un manifest e gzip deterministico. Si scaricano solo gli SHA mancanti e si passa alla build nuova solo quando è completa: mai js e wasm di build diverse.
  - **Patch**: dall'ultima Release. Si scaricano solo i file cambiati e si cancellano quelli tolti. Il tag si registra solo a patch completa. Una patch importata a mano si riconosce dagli SHA. Il salvataggio avviene a gruppi, così chiudendo la pagina si riparte dai file mancanti.
  - **Limiti di richieste**: 5 download in parallelo, 10 richieste/s. Su 403/429 si aspetta `X-RateLimit-Reset` o `Retry-After`. Gli elenchi usano `no-cache` (un 304 con ETag non consuma il limite). Un avvio già aggiornato costa 2 richieste.
  - **Robustezza**: si parte da ciò che è salvato; c'è un pulsante "Salta, gioca con quello che c'è"; senza rete si gioca con la cache; si chiama `storage.persist()`, si stima lo spazio e si gestisce `QuotaExceededError`.
  - **Rischio documentato**: da `file://` Chrome tratta tutti i file locali come la stessa origine. Per questo il token deve essere minimo e con scadenza.
  - **Prova automatica**: Playwright contro un finto GitHub locale, senza token veri. Copre primo avvio, secondo avvio senza download, file cambiati e tolti, limiti di richieste, assenza di rete e quota esaurita.
