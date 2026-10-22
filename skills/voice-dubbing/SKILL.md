---
name: voice-dubbing
description: Doppia un'avventura d'epoca con voci sintetiche ElevenLabs — censimento di chi parla (dallo script, mai dal nome della stanza), cast fisso con provini approvati, regia per battuta, tempi e pause, generazione per capitolo con stima dei crediti, verifica dopo la generazione. Usala quando l'utente vuole il doppiaggio nel remaster.
---

# Doppiaggio (ElevenLabs)

Regole nate sul progetto di riferimento (`${CLAUDE_PLUGIN_ROOT}/references/conoscenza/voci-testi-audio-flusso.md`): valgono per
ogni gioco. Prerequisiti: `voice.license_confirmed = true` (piano con uso commerciale se il
remaster si distribuisce), catalogo testi corretti della lingua.

Accesso: connettore ElevenLabs in chat (`creative_list_voices`, `creative_design_voice`,
`creative_save_designed_voice`, `creative_generate_speech`, `creative_get_flow_run_status`;
un flow per progetto, annotato in `remaster.json`) oppure API (`rstool.py voice generate`,
chiave `ELEVENLABS_API_KEY`, anche da una GitHub Action con secret). Il piano gratuito non
permette le voci della Voice Library via API (errore 402).

## 0. Regole fisse
- **Una voce per personaggio**, sempre con le stesse impostazioni (`voice/cast.json`),
  coerente con età e genere; una volta approvata non cambia più. Default: modello
  `eleven_v4` (riserva `eleven_multilingual_v2`), similarità 0,8, stabilità 0,25-0,3,
  stile 0,6-0,85. La velocità si regola **nella voce** (es. 0,92-0,95 per narratori), mai
  accelerando l'audio dopo.
- **Recitazione, non lettura**: niente sussurri né voci "inquietanti", anche nelle battute
  misteriose (a voce piena).
- Ogni chiamata che costa crediti si fa **una volta sola**: su errore ci si ferma e si dice
  perché; mai riprovare da soli, mai cambiare voce da soli.
- Generazione di un capitolo intero solo dopo **approvazione esplicita** con la stima dei crediti.
- Mono 44,1 kHz, -18 LUFS, silenzi tolti a inizio e fine (livelli del mix: skill `audio-remaster`).

## 1. Censimento: chi parla (prima di ogni capitolo)
Il personaggio **non si deduce mai dal nome della stanza o del file** (nel progetto di
riferimento le battute di una stanza chiamata come un personaggio erano di una comparsa).
**L'attribuzione dagli script statici è una prima stima**: dove l'attore è un numero riassegnato
da scena a scena o sta in una variabile, la mappa attore → nome per stanza sbaglia in parte
(antagonisti finiti sotto nomi generici). La **conferma** viene dal driver di test, che con il
Layer registra il nome dell'attore nel momento in cui la battuta va a schermo: prima di generare
un capitolo, confronta le due attribuzioni e risolvi le differenze.
1. **Dalla struttura dello script**: file del dialogo e domande → personaggio non giocante;
   risposte, esami degli oggetti → personaggio giocante della stanza (attenzione ai
   travestimenti: alias); commenti di stanza → narratore; un file con due persone → separale
   (es. dal numero del ritratto); stesso personaggio con due nomi → una voce; eccezioni
   verificate a mano in una tabella. Scrivi l'estrattore per il motore (modello:
   un estrattore che legga la struttura dei dialoghi) che produca `voice/script-<lang>.tsv`.
   Trappole viste: un'eccezione manuale vale **solo per la riga indicata** (non per la risposta
   con lo stesso id di domanda); i nomi dei file di dialogo con simboli (`&`) vanno normalizzati
   bene, o un personaggio resta senza voce senza che nessuno se ne accorga; nelle scene animate
   parla chi muove la bocca dopo il comando di testo; il copione si estrae dall'edizione
   dell'utente.
2. **Dall'audio originale**, dove esiste (spesso solo intro/filmati): altezza media e timbro
   (embedding Resemblyzer) di ogni battuta confrontati con i personaggi noti; segnala chi non
   somiglia a nessuno.
3. **Revisione indipendente**: un secondo agente, che non ha preparato il lotto, rilegge
   attribuzioni e indicazioni di regia rispetto alla scena.
4. All'utente arrivano **solo i casi dubbi**, con l'audio originale da confrontare.
5. Escludi o componi a pezzi (§5b): frasi con valori variabili (`%nome` e simili), messaggi per i tester, testi senza
   lettere. Stessa chiave detta da due personaggi → segnalala.
Scrivi `docs/censimento-voci.md` (personaggi, battute e caratteri per capitolo, varianti dello
stesso personaggio, oggetti parlanti, personaggi in più capitoli → stessa voce).

## 2. Casting
- Per ogni personaggio nuovo una scheda (età, timbro, accento voluto, ruolo comico) e
  **2-3 voci** proposte con una battuta vera del personaggio; sceglie l'utente.
- **Personaggio riconoscibile di un film, una serie o un cartone** (`source_work.characters`) con
  `imitate_voice` true: le candidate si scelgono misurando il riferimento (§2b); con false o
  null si fa il casting normale dalla scheda.
- Prima di proporre controlla la **lista nera** (`cast.json` → `scartate`, con motivo).
  Motivi tipici: riverbero (stanzino, chiesa, grotta), voce non usabile via API.
  La misura automatica del riverbero non è affidabile: proponi voci di studi professionali e
  fidati dell'orecchio dell'utente.
- Voci di bambino: Voice Design le blocca → voce femminile giovane + filtro fisso "ragazzo"
  (formanti -10%, altezza -15%). Altri filtri fissi per personaggio: robot, telefono.
- Gag volute (accenti, parlate) vanno recitate, non corrette (vedi `localization`).

## 2b. Voce simile all'opera d'origine (solo personaggi con `imitate_voice` true)
Vale solo se il doppiaggio è scelto e l'utente ha detto sì per quel personaggio
(`source_work.characters` in `remaster.json`, vedi `style-bible` §1b). Riferimento: nella lingua
originale l'interprete, nelle altre il doppiatore dell'edizione dell'epoca del gioco.
**Paletti fissi** (nessuna eccezione, neanche se l'utente la chiede per comodità):
- **nessuna clonazione**, né istantanea né professionale, da quel materiale;
- i frammenti **non si caricano mai** su ElevenLabs o su altri servizi (niente trascrizione,
  speech-to-speech, isolamento della voce in cloud): restano in locale, nella cartella di lavoro
  privata, e **si cancellano dopo la misura** (`--delete-after`);
- nessun nome di persona reale nel nome della voce, in `cast.json` o nei crediti come se fosse
  la sua voce; mai presentare la voce come quella della persona ("voce ispirata al
  personaggio", non "voce di <nome>");
- per la distribuzione pubblica vale la nota sulla somiglianza in
  `references/legal-distribution.md`.
Procedura:
1. **Materiale di riferimento** (lo cerchi tu): trailer, spot e clip ufficiali dello stesso
   periodo dell'opera, nella lingua o nelle lingue target; fonti ufficiali prima (canali dello
   studio o del distributore, edizioni home video). Annota le fonti (link, intervalli) solo nel
   progetto privato.
   - **Requisiti**: `ffmpeg`; per le piattaforme video `yt-dlp` recente con un runtime JS
     (`--js-runtimes node` più il pacchetto `yt-dlp-ejs`): senza, i metadati arrivano ma gli
     stream rispondono 403. Scarica solo l'audio (`-x`).
   - **Gli ambienti cloud vengono spesso bloccati** dalle piattaforme video (403, poi 429 e la
     verifica "non sono un bot"). **Al massimo 2 tentativi per piattaforma**, senza raffiche: il
     blocco peggiora. Poi prova le altre fonti consentite (un'altra piattaforma video, archivi
     pubblici, il sito del distributore) e infine chiedi all'utente di caricare lui l'audio
     nella cartella privata di lavoro: anche registrato dal telefono mentre il video suona (va
     bene per altezza e ritmo, meno per il timbro: dillo), oppure scaricato sul suo computer con
     un comando pronto da copiare, per esempio
     `yt-dlp -x --audio-format wav --js-runtimes node -o "rif-%(id)s.%(ext)s" "<link>"`
     (prima `pip install -U yt-dlp yt-dlp-ejs` e Node.js). In alternativa tutta la misura gira
     sul suo computer.
   - **Mai** cookie del browser, account o credenziali personali dell'utente per aggirare il
     blocco, neanche se li offre: si cambia fonte o si chiede il file.
   - **Verifica il doppiatore** dell'edizione dell'epoca con almeno una fonte (database del
     doppiaggio, crediti dell'edizione); senza fonte scrivi "da verificare" e non procedere con
     quel riferimento come se fosse certo. Si annota solo nel progetto privato
     (`source_work.characters`, con le fonti).
2. **Tratti del personaggio**: 3-6 pezzi puliti di 2-8 s del solo personaggio (niente musica,
   effetti o altre voci sopra). Con file lunghi (trailer, clip con più voci) non tagliare a mano:
   `rstool.py voice segments <audio...> --lang it --out voice/ref/segmenti.tsv --speakers 2`
   trascrive in locale (faster-whisper, `--model small` o `medium`) e raggruppa i parlanti con
   impronte vocali locali (resemblyzer se installato, con `setuptools<81`; altrimenti impronte
   semplici, più deboli: `--prints simple`). Il TSV ha id, file, inizio, fine, gruppo, sicurezza
   dell'attribuzione, testo. Con un numero noto di parlanti usa `--speakers N`: le impronte
   separano poco e la soglia (`--threshold`) va tarata. **Ascolta** 2-3 tratti per gruppo per
   capire qual è il personaggio e scarta quelli con musica sopra o a bassa sicurezza. Per un
   solo tratto di un file resta `--start`/`--end`.
3. **Misura** (solo numeri):
   `rstool.py voice reference <frammenti...> --out voice/ref/<personaggio>-<lingua>.json --gender male --age old --delete-after`
   oppure, dai tratti del TSV senza tagliare i file,
   `rstool.py voice reference --segments voice/ref/segmenti.tsv --group G1 --out voice/ref/<personaggio>-<lingua>.json --delete-after`
   (`--select 3,5-7` per scegliere le righe). → altezza media e variabilità (semitoni),
   brillantezza, pendenza e forma media dello spettro (12 MFCC fino a 4 kHz), ruvidità
   (rapporto armoniche/rumore), velocità d'eloquio, quota e durata delle pause, dinamica. Con
   `--segments` il JSON registra le fonti (file, intervalli, gruppo, sicurezza, mai il testo)
   per rifare o controllare la misura dopo aver cancellato l'audio. Genere ed età dichiarati
   servono al controllo dell'altezza (errori d'ottava).
4. **Candidati**: voci **esistenti** della libreria ElevenLabs coerenti con età, genere e lingua
   (connettore `creative_list_voices` o API della Voice Library), con le loro anteprime; salvale
   come `voices.json` (`voice_id`, `name`, `file` o `preview_url`, `gender` e `age` o le
   `labels` della libreria) o in una cartella. Misurale una volta sola, le misure si riusano tra
   personaggi e sessioni (le voci già misurate non si rimisurano):
   `rstool.py voice measure voices.json --out voice/ref/misure.json`
   poi
   `rstool.py voice match voice/ref/<...>.json --measured voice/ref/misure.json --top 5 --out voice/ref/<...>-shortlist.json`
   (oppure `--candidates voices.json` per misurare al volo). Ordina per distanza pesata (pesi
   in `tools/remaster_tools/voiceref.py`: altezza e timbro contano di più perché i parametri non
   li cambiano; velocità e pause di meno perché si correggono con `speed` e con la regia) e
   propone le impostazioni di partenza (`speed` dal rapporto delle velocità, stabilità più bassa
   e stile più alto se il riferimento è più mosso, note su timbro e pause). **Leggi gli avvisi**:
   anteprime con musica o senza pause (pesate meno su pause e ruvidità: ascoltale), altezza fuori
   dall'intervallo plausibile per genere ed età (possibile errore d'ottava o etichetta sbagliata),
   genere o età dichiarati diversi (`--strict` le esclude), meno di 5 candidate dell'età giusta
   (cercane altre prima di scegliere).
5. **Raffina** sulle 2-3 migliori: stability, similarity, style, speed (§0 per i limiti) e
   **toni interpretativi** dal modo di recitare nei riferimenti (ritmo, ironia, pause, attacchi),
   scritti come audio tag e note di regia in `voice/regia.json` (§3), mai citando la persona.
6. **Provini** come al §2: 2-3 voci con una battuta vera, sceglie l'utente; solo voci della
   libreria, nessuna voce progettata "a somiglianza" con Voice Design partendo dal materiale.

## 3. Regia
- Un **audio tag** in inglese per personaggio (es. `[cocky, ironic]`), quello del provino
  approvato, adattato alla scena quando serve; scelto dal contesto, **non copiato** dal doppiaggio
  originale (per i personaggi del §2b i toni vengono dai riferimenti dell'opera d'origine,
  descritti senza citare la persona). Salva in `voice/regia.json`.
- **Testo recitato ≠ sottotitolo** dove la sintesi sbaglierebbe: sigle ("ONU" → "o enne u", "TV" → "tivù"), simboli ("Rossi & Figli" → "Rossi e Figli"),
  numeri, codici ("007" → "zero zero sette"), ore, numeri romani, unità, nomi stranieri in grafia
fonetica, parole tutte maiuscole (la sintesi le compita); punteggiatura pensata per
  l'intonazione. Il sottotitolo a schermo resta quello corretto.
- Continuità: nelle **scene in sequenza** (sottotitoli di filmati) ogni richiesta passa la battuta
  prima e quella dopo dello stesso personaggio (`previous_text` / `next_text`). **Nei dialoghi no**:
  le battute corte copiavano parole da quelle vicine.
- Gli audio tag si mandano solo ai modelli che li recitano (v3/v4); i precedenti li leggono.

## 4. Tempi
- **Pause**: 0,6 s dopo una battuta che finisce con `. ! ? …`; 0,15 s se la frase continua nella
  battuta successiva.
- Dialoghi e fumetti: tempi naturali della voce; la durata deve stare nel tempo del testo a
  schermo (fumetti: finché il giocatore clicca; sottotitoli: tempo dello script). Se troppo
  lunga, rigenera con velocità della voce più alta o accorcia il testo recitato.
- Scene animate con audio originale: il motore deve far partire la battuta/azione successiva
  **a fine suono** (come facevano gli script originali delle zone sonore), così la scena segue l'audio nuovo;
  solo se impossibile, modalità "tempi originali" con accelerazione massima 1,25x.
- Script a tempo (scene temporizzate, filmati con sottotitoli) devono aspettare la fine della battuta: hook nel motore.

## 5. Stima e generazione per capitolo
- Stima: caratteri del testo recitato **con i tag** × ~0,43 crediti (misurato: 45.000
  caratteri ≈ 19.200 crediti), più ~2.000 crediti di provini se ci sono molti personaggi
  nuovi. Contala sui **testi unici** (le clip originali ripetono spesso la stessa frase: sul
  banco di prova +15% di clip rispetto ai testi) e sulla **lunghezza nella lingua di arrivo**
  (italiano ≈ +10-15% sull'inglese): `rstool.py voice estimate <dump>/text.jsonl --expand 1.12`
  (deduplica di default, `--no-dedupe` per contare ogni clip). Confronta con i crediti rimasti
  (modalità `verifica`, gratuita) e mostra il conto.
- Ordine: censimento → provini → regia → stima → **approvazione** → generazione → verifica.
- File: `remaster/voice/<lang>/<textKey>.ogg` (chiave del testo **originale**, non di quello
  corretto); battute delle scene come sostituti dei suoni (`sfx/...`) se il motore le suona così.
- Tieni gli MP3 generati (`voice/originali/`) per poter rifare l'adattamento senza crediti.

- **Registro delle spese**: per ogni esecuzione id del run, caratteri, crediti spesi, crediti
  rimasti sul totale del mese. Prima di rifare una battuta cerca una correzione gratuita (un file
  esistente equivalente); i rifacimenti si fanno con la lista `solo` delle battute indicate.
- Lotti via GitHub Action (`workflow_dispatch`) con modalità `verifica` (gratis), `genera`,
  `adatta` (solo tagli, pause e volume, senza chiave) e `controlla` (ritrascrive); limite
  `max_caratteri` per esecuzione, `concurrency` per evitare due generazioni insieme, risultato in
  un ramo privato per lotto con `rapporto.md` (crediti prima e dopo). Entra negli asset solo ciò
  che l'utente ha ascoltato e approvato.

## 5b. Battute con valori variabili
"Ho ancora N monete": genera una volta la parte fissa (con i tag), poi solo il numero, in cifre, con
il resto della frase come contesto per l'intonazione; componi in locale e salva con la chiave del
testo che contiene il numero (il motore la cerca per prima). Caso reale: 390 caratteri invece di
5.956, 131 crediti invece di ~2.600.

## 5c. Stesso testo, personaggi diversi
La chiave è il CRC del testo: "Grazie..." detto da due personaggi ha un solo file. Segnalalo nel
rapporto; se serve, il motore cerca prima `<chiave>_<personaggio>` e poi `<chiave>`.

## 6. Verifica dopo la generazione
`rstool.py voice check voice/script-<lang>.tsv remaster/voice/<lang>`: file mancanti, durate
anomale. Poi trascrizione automatica di **ogni** battuta, gratis e in locale:
`rstool.py voice transcribe remaster/voice/<lang> --lang <lang> --out qa/trascrizioni-<lang>.json`
(faster-whisper `small` su CPU; ripartibile) oppure `creative_transcribe_audio` di ElevenLabs;
poi `rstool.py voice transcripts voice/script-<lang>.tsv qa/trascrizioni-<lang>.json` confronta col
testo: parole mancanti, audio tag letti ad alta voce, pronunce
sbagliate. Le battute da rifare vanno in `voice/retake.tsv` e si rifanno in blocco, con conferma.
Soglia: WER oltre il 20% o qualunque parola mancante → da ascoltare. Falsi positivi noti: nomi
propri trascritti con un'altra grafia e parlate volute.
Verifica gratuita dopo l'integrazione: altezza media della voce dei file integrati confrontata
con il personaggio a schermo (una battuta del protagonista a ~100 Hz invece di 150-190 Hz ha
rivelato la voce sbagliata).
Scrivi `docs/<capitolo>-rapporto-voci.md` (battuta, voce, durata, esito).

## 6b. Sincronia labiale
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

## 7. In gioco
Opzioni del Layer: `remaster_voices` (on/off), volume "Parlato" separato, sottotitoli sempre
attivi, click per saltare la battuta; la voce della risposta scelta finisce prima della
domanda successiva. Il toggle originale spegne le voci.
Crediti: "Voci sintetiche generate con ElevenLabs" + elenco voci per personaggio.
