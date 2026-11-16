---
name: voice-dubbing
description: Doppiaggio con ElevenLabs: chi parla davvero, cast fisso con provini, regia per battuta, stima dei crediti per parte, generazione e verifica. Usala quando l'utente vuole il doppiaggio nel remaster.
---

# Doppiaggio (ElevenLabs)

Regole comuni: `${CLAUDE_PLUGIN_ROOT}/references/regole-comuni.md`. Tecniche: cartella
`${CLAUDE_PLUGIN_ROOT}/references/conoscenza/voci-audio/` (`01a`-`01e`). Prerequisiti: `voice.license_confirmed = true` (piano con uso commerciale se il
remaster si distribuisce), catalogo testi corretti della lingua.

Accesso: connettore ElevenLabs in chat (`creative_list_voices`, `creative_design_voice`,
`creative_save_designed_voice`, `creative_generate_speech`, `creative_get_flow_run_status`;
un flow per progetto, annotato in `remaster.json`) oppure API (`rstool.py voice generate`,
chiave `ELEVENLABS_API_KEY`, anche da una GitHub Action con secret). Il piano gratuito non
permette le voci della Voice Library via API (errore 402). Il connettore può **non esporre
stabilità, stile e velocità**: va bene per esplorare voci e ascoltare anteprime, ma provini
definitivi e lotti veri si fanno con l'API diretta (`rstool.py voice generate`, chiave nei
segreti d'ambiente), così le impostazioni del cast arrivano davvero.

## 0. Regole fisse
- **Una voce per personaggio**, sempre con le stesse impostazioni (`voice/cast.json`),
  coerente con età e genere; una volta approvata non cambia più. Modello: i **personaggi
  principali sempre con il modello che recita gli audio tag** (`voice.model_main`, oggi
  `eleven_v4`), mai con un modello "piatto"; i secondari possono usare un modello più economico
  solo se i crediti lo chiedono, scelta registrata nel progetto (`voice.model_secondary` e
  `voice.cast.<nome>.secondary true`; il generatore rifiuta un principale con un modello senza tag), similarità 0,8, stabilità 0,25-0,3,
  stile 0,6-0,85. La velocità si regola **nella voce** (es. 0,92-0,95 per narratori), mai
  accelerando l'audio dopo.
- **Recitazione, non lettura**: niente sussurri né voci "inquietanti", anche nelle battute
  misteriose (a voce piena).
- Spese e chiamate a pagamento: regola comune 2 (una volta sola, approvazione esplicita con la
  stima); in più, mai cambiare voce da soli.
- Mono 44,1 kHz, -18 LUFS, silenzi tolti a inizio e fine (livelli del mix: skill `audio-remaster`).

## 1. Censimento: chi parla (prima di ogni capitolo)
Il personaggio **non si deduce mai dal nome della stanza o del file** (le battute di una stanza
chiamata come un personaggio possono essere di una comparsa).
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
4. **Audit prima di ogni lotto**: `rstool.py voice speaker-audit voice/script-<lang>.tsv --cast
   voice/cast.json --voice-dir remaster/voice/<lang> --players A,B,C`. Colonne `shown` (ritratto o
   nome mostrato) e `players` (`*` = zona usabile da chiunque giochi) dall'estrattore. Segnala ritratto
   diverso da chi parla (si corregge con `text/dialogue.tsv`), voce di genere o età incoerente, copie
   mancanti `<chiave>_<personaggio>` per le zone fuori dalle condizioni sul personaggio. Pronuncia di
   nomi e sigle: provino a 2 grafie su una battuta vera. Chi finge un'altra persona la imita con la
   propria voce, in modo palesemente finto (`01e-chi-parla-davvero.md`).
4. All'utente arrivano **solo i casi dubbi**, con l'audio originale da confrontare.
5. Escludi o componi a pezzi (§5b): frasi con valori variabili (`%nome` e simili), messaggi per i tester, testi senza
   lettere. Stessa chiave detta da due personaggi → segnalala.
Scrivi `docs/censimento-voci.md` (personaggi, battute e caratteri per capitolo, varianti dello
stesso personaggio, oggetti parlanti, personaggi in più capitoli → stessa voce).

## 2. Casting
- Per ogni personaggio nuovo una scheda (età, timbro, accento voluto, ruolo comico) e
  **2-3 voci** proposte; sceglie l'utente.
- **Provini con una sola battuta vera** del gioco per voce, la stessa per tutte le candidate,
  nel **registro tipico** del personaggio: per un personaggio ironico una battuta ironica, per un
  burbero una burbera; mai frasi inventate o neutre, che non dicono come la voce regge il ruolo.
  Con il modello e le impostazioni che userà il lotto (API diretta, §intro) e con la regia
  ricavata come al §3. Se dopo l'ascolto l'utente (o tu, dalle misure) resta **in dubbio su una
  o più voci**, proponi una **battuta addizionale** solo per quelle, di registro diverso (es. una
  battuta di pericolo dopo una ironica), con il costo stimato; mai più battute a priori.
- **Altezza**: si sceglie una voce che sta già nel registro giusto e si controlla con la regia
  (tag che non alzano il tono). **Niente correzione di tono a posteriori**: vocoder e pitch-shift,
  anche con le formanti preservate, tendono a suonare metallici; si giudica a orecchio.
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
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/voice-dubbing-voce-opera-d-origine.md` solo per i personaggi con `imitate_voice` true.

## 3. Regia
- **Per battuta, non per personaggio**: il tono si ricava dal testo e dal contesto (scena,
  battuta prima e dopo, interlocutore, situazione, carattere del personaggio dalla scheda); mai
  un tag fisso uguale per tutte le battute di un personaggio, mai copiato dal doppiaggio
  originale (per i personaggi del §2b i toni vengono dai riferimenti dell'opera d'origine,
  descritti senza citare la persona).
- Scheda di contesto e proposta: `rstool.py voice direct voice/copione.tsv --out voice/regia.tsv
  --context 2 --cast voice/cast.json [--rules voice/regole-regia.json]`. Per ogni battuta:
  chiave, personaggio, scena, le N battute prima/dopo con chi parla, interlocutore, durata
  stimata e limite (colonna `limit_s` del copione, se c'è) e un `tag` proposto da euristiche
  semplici (puntini, domande, esclamazioni, parole chiave per lingua nel file di regole) con il
  motivo. È solo un punto di partenza: il voice-director **rivede ogni riga** leggendo il
  contesto, toglie i tag inutili e corregge quelli sbagliati. I tag scritti a mano restano
  (`--retag` per riproporli).
- **Tag sobri, al massimo uno per battuta** (il generatore rifiuta righe con più tag); nessun
  tag se la battuta si recita bene da sola. Per le **voci gravi** (`"register": "deep"` nel
  cast) niente tag che alzano energia o registro (`[excited]`, `[shouting]`...) salvo che il
  contesto lo richieda davvero: lo strumento non li propone e lo scrive nel motivo.
- Generazione: `rstool.py voice generate voice/copione.tsv --cast voice/cast.json --direction
  voice/regia.tsv ...` legge colonne `tag` e `recita` della regia e il modello per personaggio
  dal progetto (`--dry-run` mostra crediti e modelli).
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
- Stima: caratteri del testo recitato **con i tag** × ~0,43 crediti (`voice.credits_per_char`
  per cambiarlo), più i provini (una battuta di ~100 caratteri × 2 prese
  per voce candidata ≈ 250-500 crediti a voce con un modello che recita i tag; le battute
  addizionali si stimano a parte, solo per le voci in dubbio). Contala sui **testi unici** (le clip originali ripetono spesso la stessa frase: spesso
  il 10-20% di clip in più rispetto ai testi) e sulla **lunghezza nella lingua di arrivo**
  (italiano ≈ +10-15% sull'inglese): `rstool.py voice estimate <dump>/text.jsonl --expand 1.12`
  (deduplica di default, `--no-dedupe` per contare ogni clip). Confronta con i crediti rimasti
  (modalità `verifica`, gratuita) e mostra il conto.
- Ordine: censimento → provini → regia → stima → **approvazione** → generazione → verifica.
- File: `remaster/voice/<lang>/<textKey>.ogg` (chiave del testo **originale**, non di quello
  corretto); battute delle scene come sostituti dei suoni (`sfx/...`) se il motore le suona così.
- Tieni gli MP3 generati (`voice/originali/`) per poter rifare l'adattamento senza crediti.

## 5a. Stima per parte e doppiaggio parziale
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/voice-dubbing-stima-per-parte.md` quando i crediti non bastano per tutto il gioco o l'utente sceglie le parti.

## 5b. Battute con valori variabili
"Ho ancora N monete": genera una volta la parte fissa (con i tag), poi solo il numero, in cifre, con
il resto della frase come contesto per l'intonazione; componi in locale e salva con la chiave del
testo che contiene il numero (il motore la cerca per prima).

## 5c. Stesso testo, personaggi diversi
La chiave è il CRC del testo: "Grazie..." detto da due personaggi ha un solo file. Il motore cerca
prima `<chiave>_<personaggio>` e poi `<chiave>`: è lo stesso meccanismo delle copie per chi gioca
(§1, punto 4).

## 5d. Versi e canto
Grida con parole, canti e cori di un personaggio sono battute sue (voce del cast e audio tag
d'azione), non effetti: il modello degli effetti non segue sillabe precise (skill `audio-remaster`).

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
con il personaggio a schermo (una battuta molto più grave o più acuta delle altre dello stesso
personaggio è quasi sempre la voce sbagliata).
Scrivi `docs/<capitolo>-rapporto-voci.md` (battuta, voce, durata, esito).

## 6b. Sincronia labiale
Leggi `${CLAUDE_PLUGIN_ROOT}/references/skill-dettagli/voice-dubbing-sincronia-labiale.md` solo nei giochi con dati di movimento della bocca.

## 7. In gioco
Opzioni del Layer: `remaster_voices` (on/off), volume "Parlato" separato, sottotitoli sempre
attivi, click per saltare la battuta; la voce della risposta scelta finisce prima della
domanda successiva. Il toggle originale spegne le voci.
Crediti: "Voci sintetiche generate con ElevenLabs" + elenco voci per personaggio.
