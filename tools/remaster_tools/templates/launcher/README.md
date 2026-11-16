# Modelli del launcher

- `merge.js`: unione a tre vie dei salvataggi e hash dei cambiamenti (funzioni pure, provate con node).
- `cloud-sync.js`: sincronizzazione con Dropbox (PKCE senza server, cartella dell'app, zip unico, `update` sulla revisione, mai scaricare a gioco avviato). Si carica dopo `merge.js`.

Si copiano nel repository **privato** del gioco; lì si mette l'app key. Regole complete: `references/conoscenza/motore/22-launcher-e-salvataggi-cloud.md`.
