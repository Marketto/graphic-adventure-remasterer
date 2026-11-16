# Chi parla davvero (prima di ogni lotto)

Il nome del file del dialogo non basta. Prima di ogni lotto si lancia `rstool.py voice speaker-audit`, che usa le colonne opzionali `shown` e `players` dello script.
- **Ritratto o nome mostrato** (`shown`): conta il fotogramma del ritratto visualizzato. Un file di ritratti può contenere più persone. Se lo script mostra il ritratto sbagliato, si corregge con le correzioni dei dialoghi della patch (ritratto e file di ritratti per battuta, valide in ogni lingua perché le chiavi sono per testo), mai nel motore.
- **Battute raggiungibili da più personaggi giocabili**: le zone fuori dalle condizioni sul personaggio (`players=*`) le può usare chiunque giochi. Serve una copia per ognuno: `<chiave>_<personaggio>.ogg`, e il motore sceglie quella del personaggio attivo.
- **Genere ed età della voce** rispetto al personaggio, presi da `cast.json` (`gender`, `age`, `voice_gender`, `voice_age`).
- **Nomi propri e sigle**: la pronuncia si decide con un provino di 2 grafie su una battuta vera, poi si fissa nel testo detto.
- **Chi finge di essere un altro** (imita il coniuge alla porta): si recita un'imitazione palesemente finta con la propria voce, non con la voce dell'altro.
- **Valori variabili** (numeri, nomi inseriti dal gioco): si compongono in locale da pezzi registrati una volta, invece di registrare tutte le combinazioni. In un caso reale ha ridotto la spesa di circa 20 volte.
- Nel preventivo, per ogni voce: uso (usata, usabile, mai usata) e personaggio verificato.
