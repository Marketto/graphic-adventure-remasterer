# Rilasci e versioni

- **Tag progressivi `patch-N`**, non SemVer. Mai riutilizzare o spostare un tag pubblicato: una correzione dopo la pubblicazione è una nuova versione.
- **Release private**: lo zip unico della patch e i checksum (MD5/SHA-256), più le pagine HTML prodotte da un workflow separato. Il sito pubblico contiene solo il motore e la pagina di importazione, mai dati derivati dal gioco.
- **La pagina leggera prende da sola l'ultima Release**: una nuova versione arriva ai giocatori al loro avvio successivo, senza ridistribuire la pagina.
- **Il rilascio non è completato** finché la CI non è verde e gli asset non sono stati verificati (checksum, download che richiede l'accesso).
- **Ogni correzione resta "in verifica"** nel documento di stato finché l'utente non la conferma giocando.

---
