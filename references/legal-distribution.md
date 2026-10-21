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

## Doppiaggio ElevenLabs
- Serve un piano con diritti d'uso commerciale per distribuire l'audio generato.
- Voci create con Voice Design o dalla libreria; niente cloni di persone reali (inclusi i
  doppiatori originali) senza il loro consenso scritto.
- Annotare nei crediti: "Voci sintetiche generate con ElevenLabs".

## Persone reali come riferimento di stile
Attori e personaggi dell'epoca servono a capire costumi, trucco, luce, inquadrature.
Non si usano per riprodurre il volto o la somiglianza di una persona reale nei personaggi:
oltre ai diritti d'immagine, tradirebbe il disegno dell'autore.
