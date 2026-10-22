# Distribuire un remaster in modo lecito

Non è consulenza legale: è la mappa dei rischi che la suite usa per scegliere cosa mettere
nella patch. Per un rilascio pubblico importante conviene sentire un legale.

## Cosa si può distribuire senza permessi
- **Il motore modificato** (fork di ScummVM, AGS, ...): è GPL. Si distribuisce con i sorgenti
  (o la patch `git format-patch` sul commit di partenza) e il testo della licenza.
- **Gli strumenti e le ricette** scritti da noi (script, configurazioni, prompt, parametri).
- **Opere interamente nuove**: musiche composte da zero, font originali.

## Cosa NON si distribuisce mai
- I file del gioco originale, in nessuna forma (nemmeno "abandonware", che non è uno status
  legale). L'utente usa la propria copia; l'installer ne verifica gli MD5.

## Zona che richiede il permesso del titolare dei diritti
Sono opere derivate dell'originale, quindi la loro diffusione richiede il permesso:
- fondali e sprite HD ricavati dall'arte originale (anche se ridipinti dall'IA);
- testi corretti e **traduzioni** del copione;
- **doppiaggio** del copione (oltre alla licenza commerciale ElevenLabs per le voci sintetiche);
- musiche ri-orchestrate o rimasterizzate a partire dai brani originali.

## Le due modalità della suite
| Modalità | Cosa contiene la patch | Quando usarla |
|---|---|---|
| `recipe` (default) | motore + strumenti + ricette; gli asset si rigenerano dalla copia dell'utente | nessun permesso dei titolari |
| `asset-pack` | come sopra + asset HD, testi, voci già pronti | permesso scritto del titolare |

La modalità `recipe` riduce il rischio ma non lo elimina per testi tradotti e voci, che sono
nuove opere ma derivate dal copione: per quelle la suite raccomanda comunque di chiedere il
permesso, e propone la lettera in `templates/richiesta-permesso.md`.

Note pratiche per `recipe`:
- versioni di modelli e strumenti fissate (hash nel `manifest.json`), seed fissi;
- la generazione su GPU può non essere bit-identica tra macchine: piccole differenze sono
  accettate (`rstool.py gfx check` ne misura la fedeltà); senza GPU la ricetta ripiega
  sull'upscaling deterministico e le estensioni inventate restano bordi;
- le parti inventate (estensioni 16:9) con i metodi locali (LaMa, quilting, ricette) si
  rigenerano con gli stessi parametri e seed (`references/recipe.example.json`); quelle scelte
  da un servizio a pagamento (fal.ai) **non** sono riproducibili in modo identico: in modalità
  `recipe` quelle scene usano la variante locale, oppure si distribuiscono solo col permesso;
- il manuale (anche tradotto o ripulito) è un'opera protetta come il gioco: in `recipe` si
  consegna solo la sezione nuova scritta per il remaster, il resto si ricava dalla copia
  dell'utente.

## Marchi e loghi
Logo e titolo del gioco (anche nel tema dei menu, `ui theme --logo`) sono marchi dei titolari:
vanno bene nella copia privata dell'utente e nei pacchetti distribuiti con permesso; in un
pacchetto distribuito senza permesso il tema usa un'intestazione neutra (titolo in testo
semplice o nessun logo). Mai loghi o nomi dei titolari su siti pubblici del progetto.

## Regole del progetto ScummVM sull'AI
Il fork resta dell'utente e si distribuisce sotto GPL; ma ScummVM vieta la co-autorialità
AI nei commit (si usa `Assisted-by:`), chiede che ogni contributo upstream sia rivisto e
firmato da una persona e non accetta asset grafici generati con AI. Quindi: patch del
motore eventualmente proponibili upstream solo dopo revisione dell'utente; asset del
remaster mai proposti al progetto.

## Scopo della suite
La suite serve a produrre **patch HD non ufficiali, senza scopo di lucro e lecite** per giochi
che il giocatore possiede: niente file originali distribuiti, niente vendita, niente
imitazione di prodotti o persone. Ogni scelta tecnica (ricette, installer che verifica la copia,
voci sintetiche senza cloni) discende da questo.

## Doppiaggio ElevenLabs
- Serve un piano con diritti d'uso commerciale per distribuire l'audio generato.
- Voci create con Voice Design o dalla libreria; niente cloni di persone reali (inclusi
  interpreti e doppiatori originali); la voce simile a un personaggio di un'opera d'origine si
  ottiene solo scegliendo e regolando voci esistenti (sezione sopra).
- Annotare nei crediti: "Voci sintetiche generate con ElevenLabs".

## Somiglianza di voce e volto di persone reali
Per i giochi tratti da un film, una serie o un cartone i personaggi possono avere il volto e la
voce di persone reali (attori, doppiatori). La voce e l'immagine di una persona sono protette
(diritti della personalità, diritto all'immagine, in alcuni paesi leggi specifiche sulle voci
sintetiche) anche quando il personaggio appartiene a un'opera.
- **Voce simile**: si ottiene **solo scegliendo e regolando voci esistenti** della libreria
  ElevenLabs (parametri e regia). Nessuna clonazione, né istantanea né professionale, dal
  materiale di riferimento; il materiale (trailer, spot, clip) si usa solo per misure numeriche
  in locale, non si carica su alcun servizio e si cancella dopo la misura. È vietato anche dalle
  condizioni d'uso dei servizi di sintesi (niente voci di persone senza il loro consenso).
- **Mai presentare la voce come quella della persona**: nessun nome di persona reale nei nomi
  delle voci, nei file del cast o nei crediti; nei crediti "voci sintetiche generate con
  ElevenLabs", eventualmente "ispirate ai personaggi di <opera>".
- **Distribuzione pubblica**: una somiglianza molto marcata con una voce celebre può essere
  contestata anche senza clonazione (imitazione a fini di confusione). Nel dubbio, per i
  personaggi riconoscibili si pubblica con una voce meno vicina o si lascia la scelta della
  voce simile solo alla build privata dell'utente; la decisione va in `decisions[]`.
- **Volti**: per i lineamenti si usa solo l'artwork ufficiale dello stesso gioco (copertina,
  scatola, manuale, schermate); mai fotografie o fotogrammi della persona reale come guida,
  LoRA o riferimento di generazione.

## Persone reali come riferimento di stile
Attori e personaggi dell'epoca servono a capire costumi, trucco, luce, inquadrature.
Non si usano per riprodurre il volto o la somiglianza di una persona reale nei personaggi:
oltre ai diritti d'immagine, tradirebbe il disegno dell'autore.
