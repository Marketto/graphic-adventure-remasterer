# Nota tecnica: rendere completabile e rimasterizzare un'avventura punta-e-clicca degli anni '90 su un fork di ScummVM

Questa nota riguarda solo il lato motore. Descrive le tecniche e le regole usate per rendere un'avventura 2D DOS (640x400, 256 colori) completabile, più comoda da giocare e rimasterizzata in HD/16:9, senza modificare i dati originali. Ogni punto dice la regola o la tecnica e il problema che ha risolto.

---

## 1. Principio guida: motore e contenuto separati

- **Regola**: il motore non contiene mai correzioni o varianti del contenuto. Sono contenuto i testi, chi parla in una battuta (ritratto o fotogramma), le scene, l'ordine delle stanze, gli oggetti e le eccezioni per una stanza o una battuta. Il motore fornisce solo un **meccanismo generico** che legge le correzioni dai file della patch dati (es. `text/<lingua>.txt`, `text/dialoghi.txt`, `loc/deviazioni.txt`, `hint/<lingua>.txt`).
- **Perché**: le correzioni scritte nel codice (scene tagliate rimesse con un `if` sulla stanza, ritratti cambiati per una battuta) si accumulano. Sono difficili da rivedere, impossibili da cambiare senza ricompilare e mescolano codice GPL e dati privati.
- **Cosa resta nel motore**: le correzioni di crash e bug, le routine ricostruite dall'eseguibile originale (tabelle delle tracce CD, effetti di palette), le regole generali di disegno (ordine a parità di Z, scala prospettica), l'input e il rendering.
- **Come si fa**: se il meccanismo manca, lo si aggiunge in forma generica, con chiave e formato documentati, e il dato va nella patch. Ogni meccanismo ha un'opzione per spegnerlo, così il comportamento originale resta raggiungibile.
- **Chiave stabile per i testi**: un CRC32 del testo originale normalizzato (senza spazi, a capo e caratteri di controllo). Serve a correggere testi, ritratti e voci senza dipendere da indici interni. Più tabelle condividono la stessa chiave.
- **Deviazioni tra stanze**: una riga `parte da a invece_di opzione=<nome>` agganciata nel cambio di stanza. Rimette scene che un'edizione localizzata aveva tagliato, senza scrivere nomi di stanze nel codice.
- **Debito noto**: un'eccezione di contenuto ancora nel motore va elencata nella documentazione, con la proposta di conversione in file dati.

## 2. Renderer HD: composizione del frame

- **Il gioco resta a bassa risoluzione**: la logica, gli script, le maschere e il clipping lavorano sempre sul frame originale a 8 bit. Il renderer HD produce a ogni frame un'immagine true color a scala intera (3x; 2x supportata).
- **Sfondo HD per corrispondenza**: un pixel prende lo sfondo HD solo se nel frame 8 bit coincide con il pixel dello sfondo originale. Tutto il resto (sprite, effetti, testo non catturato) passa da un filtro sugli indici (xBR 3x, oppure Scale3x).
  - Perché: è robusto a qualunque cosa il gioco disegni sopra lo sfondo, senza conoscere la semantica degli script.
- **Palette per indice**: per ogni colore si confronta la palette di riferimento con quella corrente. Il risultato è una delle quattro modalità che seguono.
  - Uguale.
  - Dissolvenza: fattore applicato all'HD.
  - Grigio: vista in bianco e nero, valida solo se il colore non diventa più chiaro.
  - Ciclo di colore: il pixel HD si sposta della differenza, con un alone morbido sulle accensioni.
  - Qualsiasi altro caso: si usa la bassa risoluzione.
  - Perché: le dissolvenze e i cicli di palette dell'originale continuano a funzionare in HD.
- **Ridisegno a tessere 16x16**: si ricompone solo dove il frame 8 bit **o** gli id degli sprite sono cambiati.
  - Perché gli id: due fotogrammi diversi possono avere gli stessi pixel in una tessera ma immagini HD diverse. Se si controllano solo i pixel, una testa che si gira lascia il collo del fotogramma precedente.
- **Commutazione classica/HD al volo** con un tasto. In modalità classica: frame ingrandito senza filtri, niente sprite né testi HD. I testi catturati conservano l'originale e vengono ridisegnati col font bitmap, salvando i pixel sotto. Anche la musica riprende dallo stesso punto (seek dell'OGG, ricerca del tick per il MIDI).

## 3. Sprite HD tramite buffer degli id

- **Chiave di un fotogramma**: CRC32 di larghezza, altezza e pixel decodificati. È indipendente dal file e dalla posizione.
- **Buffer degli id**: i blitter originali (senza maschera, con maschera, scalato) scrivono per ogni pixel `slot<<20 | sx<<10 | sy` in un buffer grande quanto il backbuffer. La composizione campiona lo sprite HD nel pixel sorgente corrispondente.
  - Perché: maschere di priorità, clipping, scala prospettica e occlusione si ereditano gratis dal blitter originale, senza reimplementarli.
- **Due livelli** (sprite in cima e sprite sotto): i bordi semitrasparenti di uno sprite HD si fondono con l'immagine HD dello sprite sotto, non col pixel ingrandito. Evita gli scalini tra testa e corpo che cambiano a ogni fotogramma.
- **Bordi**: l'alpha si ricava dalla maschera originale sfocata (gaussiana σ≈0,65 px), campionata bilineare, con soglia morbida stretta. Gli scalini diventano curve. Dove l'alpha HD è 0 si vede l'HD sottostante. L'alpha dei JPEG si ricostruisce dalla sagoma (bilineare + smoothstep 0,3–0,7).
- **Prospettiva**: uno sprite scalato si ricampiona bilineare nella posizione esatta, invece di ripetere o saltare righe come l'originale. Uno slot per disegno.
- **Ripiego**: se un colore del fotogramma non è mappabile sulla palette corrente, si usa lo sprite originale.
- **Cache** in memoria limitata (96 MB). Un'opzione da sviluppatore scarica i fotogrammi visti, per alimentare la pipeline di rimasterizzazione (vedi `fuzz` nel §13).

## 4. Testo HD

- La funzione di disegno del font, per i font con un sostituto HD, **registra la stringa** per superficie invece di disegnarla. Quando la superficie finisce nel backbuffer, le stringhe passano al renderer. Il renderer le disegna da atlanti HD centrate nel riquadro della riga originale (i menu allineati a sinistra) e le comprime fino al 70% se più larghe.
- I colori vengono dalla palette corrente, così le dissolvenze funzionano anche sul testo. La riga evidenziata dei menu, ottenuta con uno XOR nell'originale, viene ricostruita.
- I caratteri che il font originale rende vuoti diventano spazi.
- **Prestazioni**: un testo che compare, sparisce o si muove (l'etichetta che segue il puntatore) ridisegna solo le tessere sotto la vecchia e la nuova posizione.
  - Problema risolto: prima ogni movimento del mouse con l'etichetta visibile ricomponeva la scena e il puntatore rallentava.
- **Sottotitoli**: spostati in basso, con una fascia scura semitrasparente in HD. Un'opzione ripristina la posizione originale.
- **Font**: atlanti generati da font liberi vicini allo stile originale. Gli alfabeti stilizzati dell'originale vanno preservati, non "corretti".

## 5. Viewport 16:9, sprite nelle bande e bande cliccabili

- **Finestra estesa**: (640 + 2·36) x 400 pixel di gioco. Il gioco resta 640x400: il renderer compone la finestra larga e riempie le bande con lo sfondo allargato `<nome>_w`, se esiste, altrimenti di nero. Il colore delle bande segue la dissolvenza del pixel originale più vicino. Le stanze "chiuse" restano con bande nere.
- **Il centro dell'immagine allargata sostituisce anche lo sfondo HD normale**: così le colonne di bordo dell'originale (spesso artefatti) non si vedono.
- **Sprite nelle bande** (solo nelle stanze con `_w`, solo in HD):
  - Si disegna di nuovo, con lo stesso blitter, la parte degli oggetti di scena che esce dal backbuffer. Si usano due strisce da 36 colonne, con i loro id degli sprite.
  - La maschera di priorità si legge nella colonna di bordo più vicina.
  - Le strisce partono ogni scena da un riferimento 8 bit dello sfondo allargato (l'originale con le colonne di bordo ripetute), così la regola "sfondo HD per corrispondenza" vale anche lì.
  - Esclusi etichette, fumetti e inventario.
  - Problema risolto: personaggi tagliati di netto al bordo dei 640 px.
  - Limite: uno sprite "parcheggiato" dagli script appena fuori schermo ora si vede.
- **Bande cliccabili**: le coordinate del mouse si riportano al gioco togliendo il margine.
  - Nelle stanze più larghe dello schermo la banda mostra la stanza stessa: valgono la zona e la camminata in quel punto.
  - Oltre il bordo della stanza vale una zona che tocca il bordo o ci arriva entro 16 px alla stessa altezza (zone di percorso escluse).
  - Senza zone: camminata verso il bordo.
  - Problema risolto: limitare il punto a x=0/639 non colpiva mai le uscite laterali, perché il test del rettangolo esclude il pixel di bordo.

## 6. Scorrimento fluido

- **Problema**: l'originale sposta lo sfondo di 32 px (8 in verticale) per passo di gioco. Lo scorrimento veniva eseguito a ogni fotogramma, quindi a salti di 32 px. In HD questo significava una ricomposizione completa per fotogramma (~90 ms a 3x, cioè ~10 fps).
- **Soluzione**: la stessa distanza alla stessa velocità del DOS, ma suddivisa in pochi pixel per fotogramma, e 60 fps solo durante lo scorrimento. Il personaggio e lo sfondo sono interpolati entrambi nel tempo, in coordinate della stanza, così non tremolano l'uno rispetto all'altro.
- **Spostamento della finestra HD**: l'immagine composta, il frame 8 bit e gli id del frame precedente vengono spostati del delta. Si ricompongono solo:
  - la striscia scoperta;
  - i bordi (il filtro usa 2 px di vicinato);
  - le colonne fuori dallo sfondo;
  - i testi;
  - le tessere cambiate.

  Sono ~20k pixel invece di ~285k. Lo scorrimento è a pixel interi di gioco: a 10–20 px per fotogramma non serve un sotto-pixel, che il frame 8 bit non potrebbe comunque rappresentare.
- **Bug collaterali trovati**: un contatore senza segno mandava lo scorrimento a sinistra fino al bordo della stanza invece di fermarsi dopo la distanza chiesta. Uno scorrimento in corso non deve passare alla stanza successiva.
- **Verifica**: una modalità del driver ricompone da zero ogni fotogramma scorso e lo confronta con quello spostato (`differing=0` atteso).

## 7. Tempi calibrati su DOSBox

- **Il gioco DOS non ha un timer**: ogni passo disegna e poi aspetta due ritracce verticali. La durata di un passo è quindi 2 ritracce + il tempo di disegno, limitato dalle porte VGA e non dalla CPU (identico a 40k e a 120k cicli in DOSBox).
- **Misura**: si registra DOSBox su Xvfb con `ffmpeg -f x11grab -framerate 60` e si contano i fotogrammi tra due cambi (7–8 fotogrammi a 60 fps = ~128 ms). Il mouse si pilota con `xdotool` (`autolock=false`). Valori trovati: da ~43 ms senza animazioni fino a ~160 ms con molte figure grandi.
- **Modello**: la durata del passo si stima dall'area dei fotogrammi animati a schermo, interpolando i punti misurati e arrotondando a ritracce intere (70 Hz). Un'opzione forza un valore fisso.
  - Problema risolto: a 33 ms fissi il gioco andava fino a 4 volte più veloce dell'originale.
  - Confronto ottenuto: durata di una sequenza animata entro il 2% dell'originale.
- **Logica e disegno separati**: la logica avanza ogni passo; lo schermo e l'input vanno a 30 fps (60 a scelta).
  - Nei fotogrammi intermedi gli sprite vanno rimessi nella lista di disegno, altrimenti sfarfallano.
- **Movimento fluido**: tra due passi ogni animazione si disegna a metà strada tra la posizione precedente e la nuova (un passo di ritardo; il fotogramma cambia come prima). I salti grandi (>48x32 px) non si ammorbidiscono, perché sono teletrasporti.
- **Cursore a ~120 Hz**: mentre aspetta il fotogramma il motore legge gli eventi, li rimette in coda nello stesso ordine e ridisegna solo il puntatore.
- **Suoni che comandano gli script**: i comandi legati a una zona sonora partono **quando il suono finisce**, come nell'originale. Gli effetti in loop si fermano allo scaricamento della stanza.
- **Attese bloccate**: se uno script aspetta la fine di una voce e il backend audio non la segnala, un clic o un tasto la interrompe e lo script prosegue.

## 8. Input

- **Clic destro breve per l'inventario**: il gesto originale è "tieni premuto, spostati, rilascia". Il gesto agevolato: rilascio entro 350 ms senza spostamento, e l'inventario resta aperto. Poi un sinistro su un oggetto lo prende, un sinistro fuori chiude, il destro chiude.
- **Soglia di trascinamento in pixel di gioco** (6 px), non in pixel dello schermo.
  - Problema risolto: in HD 3x 16:9 su una finestra o su un telefono il tremolio di un tocco valeva decine di pixel schermo e veniva preso per un trascinamento.
  - La distanza si misura tra pressione e rilascio, non sui movimenti intermedi.
- **Pressione e rilascio nello stesso frame** (tap del trackpad, touch): si usa la pressione e si rimette il rilascio in coda per il frame dopo. Altrimenti il solo rilascio non apriva nulla.
- **Combinare dall'inventario**, con un oggetto in mano:
  - il sinistro su un altro oggetto lo **prende**;
  - il destro su un secondo oggetto **tenta la combinazione**: con una coppia valida va in mano il risultato e l'inventario si chiude; con una coppia non valida l'inventario resta aperto e l'oggetto resta in mano.
  - L'oggetto in mano si identifica dal suo id, non da un indice valido solo in certi percorsi di apertura.
- **Clic durante la camminata**: cambiano la destinazione. Un'azione in sospeso aspetta l'arrivo o si annulla col nuovo clic. Una sorveglianza chiude una camminata ferma da 15 passi.
- **Esc/F5** aprono il menu di ScummVM.
- **Robustezza**: un cambio di personaggio verso una figura senza inventario mantiene l'inventario corrente. Prima il renderer dell'inventario restava scollegato e il clic destro chiudeva il gioco.

## 9. Ordine di disegno e prospettiva

- **Ordinamento stabile**: a parità di Z va sopra l'oggetto col bordo inferiore più in alto (le teste sopra i corpi).
- **Zone-oggetto con immagine alla stessa Z**: va sopra quella dichiarata **prima** nello script, come nell'originale.
  - Una regola ad hoc del tipo "alza la zona accesa per ultima" risolveva un caso e ne rompeva altri: si ricava la regola dall'originale.
- **Scala prospettica**: si applica sempre al personaggio che cammina e alle animazioni dichiarate scalate. Un'altra figura viene scalata solo se la sua Z coincide col bordo inferiore (±8 px). Così una Z usata per ordinare una parte del corpo non la sposta.
- **Scala 0**: non si disegna. Prima causava una divisione per zero in uno script con un parametro mancante.

## 10. Salvataggi con miniature

- **Formato originale invariato**: si accoda l'intestazione estesa di ScummVM (data, ora, tempo di gioco, miniatura; offset negli ultimi 4 byte). Il lettore originale si ferma prima, quindi:
  - le versioni vecchie leggono i file nuovi;
  - i file vecchi si caricano ancora, con un segnaposto "Nessuna immagine".
- **Miniatura presa dallo schermo del gioco** (frame HD o 640x400), non dall'overlay del menu aperto. Larga 160 px con le proporzioni dello schermo (160x90 in 16:9), ridotta con media a blocchi, che non produce scalettature come il campionamento.
- La metaengine dichiara le capacità relative (meta info, miniatura, data, tempo di gioco). Così i dialoghi Salva/Carica mostrano la griglia e l'elenco con l'anteprima.
- **Bug trovato**: caricare durante il gioco una partita con lo stesso personaggio non ricaricava la sua grafica (crash). Ora si ricarica quando la grafica manca, non solo quando cambia il nome.

## 11. Menu nello stile del gioco

- **Tema GUI dedicato** (archivio zip del tema): colori, pulsanti e font ricavati dallo stile del gioco, generati da uno script. Il logo è rimpicciolito con un filtro.
  - Un'etichetta più larga del pulsante passa al font normale invece di essere tagliata.
- **FreeType nella build web**: con i soli font bitmap, alla scala del telefono (~2,5x) il menu era a blocchi.
- **Senza FreeType**: si preferisce il `.bdf` alla sua cache `.fcc`, che non ha dimensioni né nomi. Ingrandire la cache faceva cadere l'avvio successivo.
- **Niente "Torna a elenco giochi"**: la capacità corrispondente non viene dichiarata e il pulsante sparisce, invece di restare disattivato.
- **Versione della patch** nel menu principale, letta da un `VERSIONE.txt` nel pacchetto (assente: niente). Non c'è più bisogno di chiedere al giocatore quale versione usa.

## 12. Sistema di aiuti in gioco (tasto H)

- **Finestra** disegnata dal motore con i font del tema: situazione e indizio, più un pulsante "Mostra la soluzione" che la aggiunge nella stessa finestra.
  - Se H arriva durante una battuta o un dialogo, resta in attesa e la finestra si apre appena il gioco torna interattivo.
  - Nel menu principale H viene ignorato. Sul web c'è un pulsante che manda H.
- **Formato** (`hint/<lingua>.txt`, UTF-8, ripiego sulla lingua base):
  ```
  @parte N
  obiettivo: <titolo>
  fatto: <condizione>
  situazione: <dove si è, cosa si vuole>
  indizio: <spinta senza spoiler, dice dove andare>
  soluzione: <passi precisi>
  ```
- **Scelta**: si mostra il **primo obiettivo, in ordine di gioco, la cui condizione `fatto` è falsa**. Se sono tutti fatti, un messaggio generico.
- **Condizioni**: termini separati da spazio sono in AND; alternative separate da `|` sono in OR, che lega più forte (`A | B C` = (A o B) e C); `!` nega. Termini disponibili:
  - flag globale della parte;
  - flag locale di una stanza (`LF:<stanza>:<flag>`): il motore conserva i flag locali per stanza, anche nei salvataggi, e risolve il nome rileggendo la dichiarazione dello script quando non si è nella stanza;
  - oggetto nell'inventario del personaggio attuale;
  - contatore `>`, `<`, `=`;
  - stanza attuale;
  - stanza già visitata (da un registro proprio: il flag "visitata" del motore valeva solo dal secondo ingresso);
  - `sempre` / `mai`.
- **Le condizioni devono essere monotone**: una volta vere, restano vere. Un oggetto che poi si consuma va messo in OR con ciò che si ottiene dopo, altrimenti l'aiuto "torna indietro".
- **Uno stato che lo script non riesce a salvare non si vede impostandolo a mano**. Impostare un flag col driver prova la catena degli aiuti, non che il gioco lo imposti davvero. Per i passi critici bisogna rifare le azioni vere e controllare lo stato.
  - Caso reale: un bit di marcatore ("questo comando agisce sui flag globali") stava nello stesso campo dei bit dei flag. Il flag con l'indice più alto coincideva col marcatore e non veniva mai memorizzato. Correzione: marcatore in un campo separato, con le condizioni degli script invariate. I vecchi salvataggi si coprono con un'alternativa su un flag locale impostato dallo stesso comando.

## 13. Driver di test automatico e casi di regressione

- **Driver nel motore**, attivo solo con una variabile d'ambiente che punta a un file di comandi.

  | Gruppo | Comandi | Note |
  |---|---|---|
  | Mouse | `move/click/rclick/rhold/rtap x y` | coordinate di gioco, anche negative o >639 per le bande; `rtap` = pressione e rilascio nello stesso frame |
  | Tempo, tastiera, catture | `wait N` (frame), `key`, `shot file.png`, `time`, `quit` | |
  | Spostamenti | `loc <stanza> [parte]`, `ingame` | `ingame` clicca finché il gioco torna interattivo |
  | Ispezione | `poke [doors]`, `zones`, `zoneon/zoneoff`, `scene` | `poke` clicca tutte le zone; `scene` dà l'ordine di disegno con Z |
  | Stato | `state`, `flag`, `item`, `flags`, `hintlog`, `save n` / `load n` | `state`: modo input, oggetto in mano, personaggio, stanza, scroll, zona sotto il puntatore; `flag`/`item` impostano lo stato, `flags` lo legge; `hintlog`: aiuto che H mostrerebbe |
  | Configurazione e menu | `conf chiave valore`, `gui w:<ms> k:<tasto> shot:<file>` | `gui` pilota e cattura i menu di ScummVM; l'ultimo passo deve chiudere il menu |
  | Prestazioni | `framelog on/off`, `verifyscroll on/all/off`, `fullredraw` | `framelog`: ms di disegno, pixel ricomposti, frame spostato |
  | Mouse dopo un salto | `mouseon` | riattiva il mouse spento da una scena interrotta |

- **Trappola trovata**: in ScummVM `warpMouse` cancella gli eventi del mouse ancora in coda. Il driver deve muovere il puntatore solo col primo evento di ogni comando. Prima i clic simulati perdevano la pressione e i test dell'inventario non potevano funzionare.
- **Script di supporto**:
  - `at.sh`: esegue un file di comandi e riassume warning ed errori. Lavora su una copia della configurazione (ScummVM la riscrive all'uscita) e su una cartella di salvataggi isolata.
  - `atgdb.sh`: come sopra, con backtrace in caso di crash.
  - `sweep.sh`: visita tutte le stanze di una parte.
  - `fuzz.sh`: visita le stanze e clicca tutte le zone; serve anche a estrarre gli sprite.
- **Entrare a metà**: prima si salta alla prima stanza della parte, che imposta personaggio e inventario, poi alla stanza voluta. Un salto diretto lascia lo stato incoerente.
- **Due configurazioni sempre**: originale e HD. Ogni correzione si prova in entrambe.
- **Casi di regressione**: per ogni bug corretto, un file di comandi in `tools/test/casi/` con l'atteso scritto nella documentazione. L'atteso è un valore nel log (`state mode 3`, `hover <zona>`, `SHIFTCHECK differing=0`, `HINT #i`) o uno screenshot da confrontare. A questi si aggiunge una checklist manuale per ciò che richiede occhio o mani (trackpad, telefono).
- **Finestre modali**: il driver video `dummy` non le cattura. Su Linux si usa `ffmpeg -f x11grab` sul display Xvfb.

## 14. Build e test locali su macOS

- **Dipendenze statiche** (SDL2, jpeg, png, ogg, vorbis) compilate da uno script in un prefisso locale, senza Homebrew.
- **Build fuori sorgente**, così `git add -A` nel sorgente non raccoglie i file compilati. Si disattiva ciò che non serve: mad, flac, freetype, fluidsynth, curl, rete, cloud, tts.
- **Cartella di gioco di prova** fatta di collegamenti simbolici: dati originali + asset della patch. Non si copia nulla.
- **Test senza finestra**: driver video `dummy` di SDL e renderer software; gli screenshot funzionano. `perl` sostituisce `timeout`. Per i crash: `lldb -b -o run -o bt`.

## 15. Patch del motore: generazione e normalizzazione

- Il motore è una **patch unica** su un commit base fissato. Uno script scarica quel commit e la applica come modifiche non committate. Le CI fanno lo stesso.
- **Rigenerazione**: `git add -A && git diff --cached <commit base>`. Un `git diff` semplice perde i file nuovi non tracciati (renderer HD, driver di test, aiuti).
- **Mai correggere a mano i conteggi delle righe degli hunk**. Le modifiche manuali al `.patch` hanno richiesto più commit di "normalizzazione" per riallineare conteggi e contesto. La patch si rigenera sempre dal sorgente.
- **Verifica**: applicazione da zero in una cartella pulita; deve stampare `applied …`.
- **Codice comune a più giochi dello stesso motore**: le modifiche si limitano al tipo di gioco interessato e gli altri restano invariati. Correzioni minime, commenti in inglese come il resto del motore.
- Se qualcosa "non funziona più", si cerca nella storia della patch (`git log -p -- engine/patches`) il commit che l'ha introdotto.

## 16. Web: pagina unica e pagina leggera che si aggiorna da sola

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

## 17. Rilasci e versioni

- **Tag progressivi `patch-N`**, non SemVer. Mai riutilizzare o spostare un tag pubblicato: una correzione dopo la pubblicazione è una nuova versione.
- **Release private**: lo zip unico della patch e i checksum (MD5/SHA-256), più le pagine HTML prodotte da un workflow separato. Il sito pubblico contiene solo il motore e la pagina di importazione, mai dati derivati dal gioco.
- **La pagina leggera prende da sola l'ultima Release**: una nuova versione arriva ai giocatori al loro avvio successivo, senza ridistribuire la pagina.
- **Il rilascio non è completato** finché la CI non è verde e gli asset non sono stati verificati (checksum, download che richiede l'accesso).
- **Ogni correzione resta "in verifica"** nel documento di stato finché l'utente non la conferma giocando.

---

## Errori da non ripetere

- Scrivere nel motore correzioni di contenuto (stanze, battute, ritratti) invece di un meccanismo generico con i dati nella patch.
- Correggere a mano gli hunk del `.patch`, o rigenerarlo con `git diff` senza `add -A`: si perdono i file nuovi o la patch non si applica più.
- Misurare le soglie dei gesti in pixel dello schermo invece che in pixel di gioco.
- Considerare solo il rilascio quando pressione e rilascio arrivano nello stesso frame.
- Chiamare `warpMouse` tra eventi in coda: cancella le pressioni simulate.
- Ridisegnare le tessere guardando solo i pixel 8 bit e non gli id degli sprite.
- Ricomporre tutta la scena per ogni testo in movimento o per ogni fotogramma di scorrimento.
- Eseguire lo scorrimento dell'originale a ogni fotogramma (salti di 32 px) invece di distribuirlo nel tempo del passo.
- Usare un tempo fisso per passo: l'originale dipende dal carico di disegno e va misurato in DOSBox.
- Limitare il mouse a x=0/639 sopra le bande: le zone di bordo non vengono mai colpite.
- Inventare regole d'ordine di disegno ad hoc invece di ricavare quella dell'originale.
- Tenere un marcatore nello stesso campo di bit dei dati: collide con un flag valido.
- Verificare gli aiuti solo impostando i flag a mano: non rivela i flag che il gioco non riesce a memorizzare.
- Scrivere condizioni di aiuto non monotone (oggetti che si consumano).
- Prendere la miniatura del salvataggio dall'overlay del menu invece che dallo schermo di gioco.
- Supporre che un cambio di personaggio abbia sempre un inventario, o che ricaricare lo stesso personaggio non serva.
- Ingrandire una cache di font bitmap senza metadati.
- Usare i soli font bitmap per un menu che sul telefono viene scalato.
- Mettere un token, o qualunque dato derivato dal gioco, in pagine, rami o Release pubblici.
- Dichiarare un test superato senza averlo eseguito, o una versione rilasciata prima della CI verde e degli asset verificati.
- Spostare o riutilizzare un tag già pubblicato.
