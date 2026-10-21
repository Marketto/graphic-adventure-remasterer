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
- Prima di proporre controlla la **lista nera** (`cast.json` → `scartate`, con motivo).
  Motivi tipici: riverbero (stanzino, chiesa, grotta), voce non usabile via API.
  La misura automatica del riverbero non è affidabile: proponi voci di studi professionali e
  fidati dell'orecchio dell'utente.
- Voci di bambino: Voice Design le blocca → voce femminile giovane + filtro fisso "ragazzo"
  (formanti -10%, altezza -15%). Altri filtri fissi per personaggio: robot, telefono.
- Gag volute (accenti, parlate) vanno recitate, non corrette (vedi `localization`).

## 3. Regia
- Un **audio tag** in inglese per personaggio (es. `[cocky, ironic]`), quello del provino
  approvato, adattato alla scena quando serve; scelto dal contesto, **non copiato** dal doppiaggio
  originale. Salva in `voice/regia.json`.
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
  nuovi. Confronta con i crediti rimasti (modalità `verifica`, gratuita) e mostra il conto.
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
anomale. Poi trascrizione automatica di **ogni** battuta (`creative_transcribe_audio` o un
modello locale) e confronto col testo: parole mancanti, audio tag letti ad alta voce, pronunce
sbagliate. Le battute da rifare vanno in `voice/retake.tsv` e si rifanno in blocco, con conferma.
Soglia: WER oltre il 20% o qualunque parola mancante → da ascoltare. Falsi positivi noti: nomi
propri trascritti con un'altra grafia e parlate volute.
Verifica gratuita dopo l'integrazione: altezza media della voce dei file integrati confrontata
con il personaggio a schermo (una battuta del protagonista a ~100 Hz invece di 150-190 Hz ha
rivelato la voce sbagliata).
Scrivi `docs/<capitolo>-rapporto-voci.md` (battuta, voce, durata, esito).

## 7. In gioco
Opzioni del Layer: `remaster_voices` (on/off), volume "Parlato" separato, sottotitoli sempre
attivi, click per saltare la battuta; la voce della risposta scelta finisce prima della
domanda successiva. Il toggle originale spegne le voci.
Crediti: "Voci sintetiche generate con ElevenLabs" + elenco voci per personaggio.
