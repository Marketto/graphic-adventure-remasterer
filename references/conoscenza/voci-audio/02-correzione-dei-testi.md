# Correzione dei testi

- **I file originali non si toccano.** Le correzioni stanno in un file di testi della patch, indicizzato per chiave del testo originale, che il motore carica sopra l'originale.
- **Base e correzioni separate.** C'è un JSON base (battute ed etichette) e più file di correzioni manuali `(indice, vecchio, nuovo)`, applicate in ordine.
  - Se il "vecchio" non si trova, la correzione viene **segnalata** e non applicata in silenzio.
  - Una lista di refusi globali vale ovunque, anche nelle etichette.
  - Una tabella sostituisce le etichette intere.
- **Correzione automatica degli accenti**: l'apostrofo al posto dell'accento diventa una lettera accentata (`e'` → `è`; `perche'` → `perché`, con l'acuto). Restano esclusi `po'`, `be'`, `di'`, `da'` e i passaggi tra virgolette semplici.
- Si correggono refusi, punteggiatura e spazi (`..` → `...`, ` ?` → `?`, virgole dei vocativi) e si traducono le battute rimaste in inglese.
- **Si preservano** giochi di parole, nomi storpiati, parlate e accenti voluti dei personaggi, e il lettering stilizzato del gioco. Non sono refusi.
- **Non si toccano segnaposto e separatori** del formato (`%valore`, `/`).
- **Set di caratteri**: i caratteri fuori dalla codepage del gioco (CP850/CP437) non si vedono.
- **Le chiavi restano quelle del testo originale**, che servono anche per le voci.
- Si genera un elenco leggibile di tutte le correzioni, perché l'utente possa rivederle.
- I testi degli script che non sono nel JSON base si correggono con coppie `(testo originale esatto, testo corretto)`. Lo stesso vale per le differenze tra edizioni.
- **Le correzioni che non sono solo testo** (ritratto di chi parla, battuta attribuita al personaggio sbagliato, scene tagliate) diventano file di dati della patch, mai eccezioni nel codice del motore.
- Si prova con i font HD e con quelli bitmap originali.

---
