# Rimasterizzazione grafica di un'avventura 2D anni '90: strategie e lezioni

Nota tecnica generica. Il caso di partenza è uno sfondo a 640x400 e 256 colori, portato a 3x (1920x1200) e allargato a 16:9 aggiungendo 36 px per lato a 1x, cioè 108 px in HD. Ogni voce indica la tecnica e il problema che ha risolto.

## 1. Ambiente e vincoli

- **Solo calcolo locale per il grosso del lavoro.** Il lavoro gira su CPU a 2 core con 7 GB di RAM e rete limitata a GitHub e ai registri di pacchetti. Sono quindi esclusi i modelli di diffusione da usare in locale: i pesi non si scaricano e su CPU sono troppo lenti. I servizi a pagamento si usano solo per le parti "inventate" (le bande 16:9).
- **Il gioco resta alla risoluzione originale.** Il motore compone l'immagine HD sopra il frame a 8 bit. Un pixel prende lo sfondo HD solo se nel frame originale coincide con lo sfondo. In questo modo maschere, priorità e dissolvenze restano quelle originali e la grafica HD non può introdurre errori di logica.
- **Palette.** Per ogni indice di colore il motore confronta la palette di riferimento con quella corrente. I casi sono: uguale, dissolvenza (si applica un fattore), vista in grigio, oppure diversa (si torna alla bassa risoluzione). I cicli di palette, come l'acqua animata, spostano il pixel HD della differenza di colore, con un alone morbido.
- **Il resto del frame (cioè tutto ciò che non ha un asset HD) passa per xBR 3x sugli indici**, con Scale3x come alternativa.
- **Ridisegno a tessere 16x16.** Una tessera si ricompone se cambiano i pixel a 8 bit oppure gli id degli sprite. Il secondo criterio serve perché due fotogrammi diversi possono avere gli stessi pixel in una tessera ma immagini HD diverse: senza di esso, in una testa che si gira il collo restava quello del fotogramma precedente.

## 2. Upscaler: modelli provati e scelta

Il confronto si fa su fogli numerati: 0 = originale, 1 = versione attualmente nel gioco, poi i candidati. Ci sono due batterie separate, una di 5 sfondi e una di 5 personaggi, perché il modello migliore per gli sfondi non è necessariamente il migliore per gli sprite. Tutti i modelli sono caricati con `spandrel`, con i pesi dalle release GitHub.

| Modello | Esito |
|---|---|
| RealESRGAN_x4plus_anime_6B (la base di partenza) | Accettabile, ma con tratti morbidi |
| realesr-animevideov3 | Impasta i dettagli. È circa 5 volte più veloce, utile solo per anteprime |
| 2x-AnimeSharpV3 / V4_RCAN | Fedeli alla retinatura ma sfocati; il V4 cancella i volti. Scartati |
| APISR RRDB / GRL / DAT (4x, GAN) | Linee d'inchiostro nette, campiture pulite, dettagli leggibili |
| AnimeSharpV4 + APISR 2x in cascata | Rovina i personaggi. Scartato |

Tempi misurati su CPU a 2 core, con pezzi da 192x192:

| Modello | s/pezzo | µs/pixel | ~100 sfondi (~35 Mpx) | ~1.400 sprite (~42 Mpx) |
|---|---|---|---|---|
| APISR RRDB | 2,7 | 73 | ~50 min | ~1 h |
| APISR GRL | 3,0 | 82 | ~55 min | ~1 h 05 |
| APISR DAT | 20,6 | 558 | ~6 h | ~7 h |

Scelta:
- **Sfondi: APISR RRDB.** È quasi pulito come DAT con contorni un po' più marcati, e 7-8 volte più veloce.
- **Sprite: APISR GRL.** È il più nitido e dettagliato, con qualche alone che però sugli sprite si gestisce con l'alpha.
- **Riduzione da 4x a 3x** con LANCZOS (BOX per gli sprite), poi JPEG q90 senza sottocampionamento della crominanza (4:4:4). Il 4:2:0 sporca i bordi colorati.
- **Lezione importante.** Sugli sprite le differenze tra modelli erano piccole: le macchie e le ombre scure della versione precedente venivano dal ritocco successivo (vedi §6), non dal modello. Prima di cambiare upscaler bisogna isolare quale passo della pipeline causa il difetto.

- **Dettaglio generativo sull'HD (secondo progetto, scelto come predefinito per i fondali):**
  `fal-ai/clarity-upscaler` sul fondale HD 3x già fatto (bande comprese), upscale 2 → 6x, creativity
  0,4, resemblance 0,8, guidance 4, 18 passi, seed fisso. Linee pulite, superfici e cieli molto più
  definiti, composizione conservata (deriva globale ≈ 0, spostamento mediano ≈ 0,3 px a 3x); qualche
  oggetto piccolo viene ridisegnato. 0,03 $/MP d'uscita, ~7 $ per ~95 stanze. La variante "bassa"
  (0,25 / 0,9) con blocco del colore e riduzione a 3x ha misure perfette ma differenza invisibile.

## 3. Pipeline degli sfondi

1. **Conversione dello sfondo originale in PNG** con la stessa palette che usa il motore. Se si usa una palette diversa, i pixel HD non coincidono con il test di uguaglianza del motore.
2. **Colonne nere ai bordi dell'originale.** Molti sfondi hanno da 1 a 20 colonne quasi nere ai lati (soglia: media di luminanza < 18 e deviazione < 12). Vanno trovate e ridipinte, altrimenti nel 16:9 compare una riga nera tra il centro e la banda.
3. **Bande 16:9 costruite a 1x**, non in HD (vedi §4).
4. **Ingrandimento dell'immagine 16:9 intera in un solo passaggio**, centro più bande, con lo stesso modello. Il centro HD si ritaglia poi dalla stessa immagine, quindi sfondo normale e sfondo allargato sono identici al pixel. Così non ci sono cuciture di texture tra parti ingrandite separatamente.
5. **Scene non allargabili.** Le stanze chiuse e le scene filmate restano in 4:3 con bande nere. Le stanze più larghe dello schermo (a scorrimento) hanno solo l'HD.
6. **Script ripartibile** che salta le stanze già fatte, con le bande 1x tenute in cache. Rifare l'upscaling non deve rigenerare le bande.

## 4. Bande 16:9: tecniche in ordine di adozione

**Regola generalizzata per la suite (decisa con l'utente, 21/10/2026).** Si parte sempre dalle
tecniche locali collaudate qui (§4.2 LaMa a 1x, §4.3 quilting, §4.7 ricette, §4.9 nitidezza) e
l'outpainting a pagamento (§4.5) si usa **solo se l'utente lo sceglie**, chiedendolo
dopo l'analisi, con preventivo e approvazione per ogni lotto. Nel banco di prova fal.ai è
stato scelto per molte stanze; in un nuovo progetto è un'opzione, non il default.

**Proporzione dei pixel.** Il banco di prova mostra i pixel quadrati (36 px per lato a 640x400)
perché la sua arte non era pensata per pixel allungati. La correzione dell'aspetto si fa solo
se il gioco era concepito per un monitor che li allungava: si decide da data di uscita,
piattaforma di destinazione, monitor dell'epoca e origine dell'arte (disegnata su quel monitor o
digitalizzata a pixel quadrati), e si verifica guardando oggetti tondi affiancati.

### 4.1 LaMa direttamente sull'HD (scartato)
Lavorando sull'HD, LaMa (big-lama TorchScript, ~200 MB) produce bande molto sfocate.

### 4.2 LaMa a 1x più upscaler
Problema risolto: LaMa sbaglia meno la composizione se lavora alla risoluzione nativa. LaMa ricostruisce 36 px per lato a 1x. L'upscaler porta poi a 3x la striscia con 24 px di contesto dell'originale, sfumata su 24 px verso il centro HD. Il centro non viene mai toccato.

### 4.3 Image quilting guidato da LaMa
Problema: LaMa indovina la disposizione (dove vanno cielo, muro, prato) ma dipinge liscio, con un effetto da "schizzo" su un fondale dipinto a mano.
Soluzione (Efros & Freeman 2001, nella variante "texture transfer"): la banda si ricompone a tessere di 12 px con 4 px di sovrapposizione, a partire dal bordo verso l'esterno. Per ogni tessera si sceglie la patch dello stesso sfondo che:
- continua bene ciò che c'è già;
- ha i colori che LaMa ha messo in quel punto;
- viene da un'altezza simile nell'immagine;
- è stata usata poche volte.

Le tessere si uniscono lungo il taglio di minima differenza. Ogni pixel della banda è quindi un pixel dipinto dall'artista. Dove nessuna patch combacia (un oggetto tagliato dal bordo) resta il colore di LaMa.

### 4.4 Gemini (outpainting con prompt)
Il centro HD viene messo su una tela 16:9 con bande grigie piatte, e il prompt chiede di dipingere solo le aree grigie nello stesso stile, senza persone, testi o loghi. Dalla risposta si tiene solo la banda:
- **Allineamento:** si cerca scala e spostamento del centro restituito, con scala da 0,97 a 1,03 e ±6 px su una copia ridotta a 1/4, perché il modello sposta o ridimensiona leggermente l'immagine.
- **Raccordo dei colori:** per ogni riga si calcola lo scarto di colore su 18 px dentro l'originale, lo si smussa in verticale (finestra di 61 righe) e lo si fa svanire allontanandosi dalla cucitura.
- **Sfumatura** su 24 px.

Costo: circa 0,134 $ a immagine a 2K. Rimasto come alternativa più costosa.

### 4.5 fal.ai: FLUX.1 Fill pro (scelto), Kontext pro, Qwen Image Edit
- **Confronto su 9 sfondi x 3 modelli, circa 1,2 $.**
  - **Fill pro:** è vero outpainting con maschera (il centro non viene toccato) e allinea bene, con scarto 1-10.
  - **Kontext pro e Qwen:** sono modifiche guidate dell'intera immagine, cambiano l'inquadratura (scarto fino a 100) e lasciano bande scure o sfocate. Scartati.
- **Prezzi indicativi:** Fill pro ~0,05 $, Kontext pro ~0,04 $, Qwen 0,03-0,045 $ a immagine.
- **Riduzione dei costi:** la tela si manda a metà della risoluzione HD, cioè 1,5x l'originale, che basta per bande di 36 px. Con `sync_mode` le immagini non restano nello storico del servizio.
- **Passata completa: circa 100 stanze, meno di 200 immagini, meno di 10 $.** Circa due terzi delle stanze sono state accettate con le bande Fill, le altre sono tornate al ripiego, soprattutto stanze buie e a scorrimento.
- **Prompt:** descrive un fondale dipinto, finito e a colori, chiedendo di continuare pareti, pavimenti, cieli e oggetti tagliati dal bordo. Include esplicitamente "not a sketch, not line art, no white paper, no people, no text, no signature, no logos". Se i bordi sono scuri si aggiunge una frase "scena buia", perché in quei casi il modello disegnava schizzi bianchi su carta.

- **Lezioni del secondo progetto** (dettagli in `skills/widescreen` §2): lati neri nell'ingresso →
  il modello li tiene neri (letterbox), quindi si parte dal ripiego locale; con il quadro 16:9 intero
  disegna riquadri da fumetto, quindi un lato per volta su un ritaglio quasi quadrato; misure
  multiple di 32; con la sola coda raggiungibile, data URI + `sync_mode`. Su un bazar affollato un
  lato è riuscito e l'altro no (cortile inventato, striscione ripetuto): ibrido lato fal + lato locale.

### 4.6 Controllo automatico (`band_check`) e i suoi limiti
Per ogni banda il controllo misura, rispetto alla colonna di bordo dell'originale:
- la frazione di pixel bianchi (luminanza > 215), oltre il 12% in più;
- lo scarto di luminosità media, oltre il 18%;
- su un bordo scuro e piatto (media < 40), un eccesso di variazione oltre 10, che indica macchie chiare o firme.

Se il primo tentativo viene scartato se ne fa uno solo in più. Se si scarta anche il secondo si torna al ripiego locale (LaMa + quilting + APISR). Il limite è al massimo 2 tentativi.

Limite scoperto: il controllo rifiuta anche bande buone che sono solo più scure o più chiare del bordo, per esempio un tronco accanto a un vialetto chiaro. In una passata su 16 stanze ne aveva accettate 2, mentre a occhio se ne sono salvate 11. Per questo esiste uno strumento che compone i tentativi scelti a mano, anche quelli scartati, eventualmente prendendo una sola delle due bande e lasciando l'altra com'era.

### 4.7 Ricette locali per le stanze residue (gratis)
Quando entrambi i tentativi a pagamento inventano persone, cornici o scritte, la banda si ricostruisce a 1x con una ricetta specifica per la stanza. Poi la striscia [banda + 24 colonne di contesto] passa per APISR RRDB e viene incollata. Il centro resta invariato: la differenza media è di 0,02-0,07 livelli, dovuta solo alla ricodifica JPEG.
- **Continuazione riga per riga del colore del bordo**, sempre più sfumata verso l'esterno, con la grana dell'originale specchiata. Funziona per nebbia, neve e cielo, ed evita blocchi ripetuti.
- **Copia di texture spostata**, per esempio da 40 px più a sinistra, con correzione di quota e pendenza per elementi lineari come binari o crinali, e raccordo a specchio sul bordo.
- **Riuso parziale di un tentativo già pagato**: per esempio la parte alta di una banda, mentre la parte bassa si ripete da una striscia vera dell'originale.
- **Continuazione geometrica** (per interni con travi, pannelli e file di rivetti). Una copia traslata ripeteva lo spigolo e i rivetti e creava scalini sul bordo. La soluzione è misurare sull'originale le rette (bordo della trave, diagonale del pannello, filo, fila di rivetti con pendenza e passo) e copiare ogni zona lungo la propria retta, colonna per colonna. Lo spigolo prosegue sulla stessa retta, senza un secondo spigolo.

### 4.8 Righe e colonne di bordo (artefatti di scansione)
Problema: righe sottili di 1-4 px a 1x, scure o chiare, lungo i bordi dell'originale. Nel 16:9 separano visibilmente la banda dal centro.
- **Ricerca automatica su tutti gli sfondi:** si confrontano le righe e colonne 0-2 con le 3 successive verso l'interno (frazione di pixel più scuri o più chiari, scarto mediano). Si guardano anche le colonne HD attorno ai bordi del centro. I candidati vanno poi rivisti ingranditi: molti sono disegno vero (tronchi, pali, cornici) e differenze deboli, tra −6 e −11 livelli.
- **Ritocco:** si interpola tra un'ancora 12 px fuori dal centro e una 3K+4 px dentro. Si sostituiscono solo i pixel più scuri o più chiari dell'interpolazione di oltre 10 livelli. Le linee vere che attraversano il bordo sono scure anche sulle ancore, quindi restano. Gli stessi pixel vanno scritti sia nello sfondo normale sia in quello allargato.
- **Colonna chiara sul bordo:** si sottrae la differenza mediana (su 41 righe) rispetto ai due lati, solo dove i due lati hanno lo stesso colore.

### 4.9 "Bande a fuoco" e indice di nitidezza
L'indice è l'energia ad alta frequenza, |L − sfocatura gaussiana σ=1,5|, della banda divisa per quella dei 108 px di centro accanto. Sotto 0,6 la banda si vede sfocata. L'indice non ha senso per scene buie o piatte, che vanno escluse.

La nitidezza si recupera con il quilting dall'originale, con la ripetizione di strisce vere, e con un unsharp mask tarato sulla banda:
- soglia di 2 livelli;
- sovraelongazione limitata ai minimi e massimi locali, così non nascono aloni;
- effetto sfumato sui 12 px accanto al centro.

Esempi: un indice da 0,32 a 0,93, uno da 0,32 a 1,00.

### 4.10 Le bande nel motore
- La banda prende la stessa dissolvenza del pixel originale più vicino.
- Gli sprite che escono dai 640 px vengono ridisegnati in due strisce laterali, con la maschera di priorità letta nella colonna di bordo più vicina. Senza questo i personaggi apparirebbero tagliati al bordo.
- Le zone cliccabili che toccano il bordo valgono anche nella banda.
- Limite: uno sprite "parcheggiato" dagli script appena fuori schermo diventa visibile.

### 4.11 Classificazione 16:9 su un secondo gioco: cosa sbagliava
Seconda prova (un'avventura del 1993 a 320x200, area di gioco 320x144 sopra una barra di verbi,
96 scene etichettate a mano): il classificatore della prima versione ne sbagliava 35 su 63
statiche; `open-static` era giusto in 7 casi su 30. Cause e correzioni (ora nel codice):
- il "cielo" (terzo superiore liscio) scattava su **soffitti e interni bui**: ora serve anche una
  luminanza media > 0,25, il blu pesa 0,2-1,0 e conta la monotonia del gradiente; restano fuori
  i **cieli notturni** e le strade senza cielo, da riconoscere a vista;
- **primi piani, documenti, mappe, schermata di morte, logo** non venivano mai riconosciuti
  (i nomi dei file del dump erano numeri): ora contano i **nomi delle stanze** dall'indice del
  gioco (`bg/names.json`) e i fondali quasi a tinta unita (≤ 3 colori, il contenuto è negli
  oggetti); una scena a tutto schermo in un gioco con l'area di gioco più bassa è segnalata come
  probabile primo piano (`full_height`), ma da sola non decide (vale per metà dei casi);
- le **stanze fittizie** larghe 8-16 px vanno in `skip`, non si estendono;
- una mappa larga che scorre resta `scroll-wide` anche se il nome dice "mappa";
- `scroll-narrow` ora ha `sides` (`open`/`closed`): solo i lati aperti si inventano, e il
  preventivo fal.ai conta solo quelli.
Risultato sulle 96 scene: classi giuste dal 64% all'86% (statiche dal 44% al 79%), decisione
"inventare o no" dal 74% al 96%; senza i nomi delle stanze 80% e 94%.

### 4.12 Proporzione dei pixel: misurare invece di guardare
Su viste in prospettiva e documenti il foglio a confronto non aiuta. È stata decisiva la misura
di un oggetto rotondo visto dall'alto, diviso tra quattro stanze e ricomposto: larghezza/altezza
1,20-1,23, quindi pixel pensati per un CRT 4:3 (`rstool.py widescreen aspect-measure ... --compose 2x2`).
Oggi la ricerca è automatica (`rstool.py widescreen aspect-auto ... --evidence <dump>/bg <dump>/obj`):
sul banco di prova (97 fondali, 946 oggetti, ~50 s) ha trovato 78 forme rotonde distinte: 33 più
larghe (in prospettiva) e 27 più alte (non rotonde) scartate, 18 utili con moda 1,225, 8 vicine
a 1,2 contro 2 vicine a 1,0, tra cui gli archi della pianta divisa tra le stanze (1,20-1,29);
decisione automatica 1,2, uguale a quella misurata a mano. Le forme in prospettiva sono la
maggioranza: conta la distribuzione delle forme frontali, mai la singola forma.

## 5. Scritte, insegne e firme

- **I modelli inventano lettere.** Un'insegna tagliata dal bordo originale viene "completata" con lettere sbagliate. Va corretta a mano:
  - si copre la parte inventata con la texture dell'insegna presa da una zona senza lettere, adattando il colore e sfumando i bordi;
  - si disegna la lettera mancante nello stile delle altre, misurando contorno, metà chiara e metà scura su una lettera esistente;
  - il testo giusto si ricava dalle etichette delle zone o dagli script, mai dal modello.
- **Lettering stilizzato:** le insegne con un alfabeto fantasioso vanno preservate così come sono. Non sono refusi.
- **Firme inventate:** i modelli generativi aggiungono spesso piccole firme negli angoli bassi delle bande. "No signature" nel prompt le riduce ma non le elimina: i secondi tentativi ne avevano spesso. Rimozione: maschera dei soli tratti, riempimento armonico dai bordi con la grana della zona, oppure copia della superficie accanto. Gli angoli vanno controllati sempre a piena risoluzione.
- **Altri elementi inventati da scartare a occhio:** persone sulle porte, cornici, bande nere, loghi, icone e oggetti duplicati (per esempio un veicolo ripetuto).

## 6. Sprite

- **Estrazione:** il motore salva ogni fotogramma decodificato mentre un driver di test visita automaticamente stanze e zone. La chiave è il CRC32 di larghezza, altezza e pixel a 8 bit, così il motore ritrova lo sprite HD senza conoscere i file del gioco. I fotogrammi mancanti si coprono con altri giri di esplorazione automatica.
- **Upscaling sul solo riquadro utile** con APISR GRL.
- **Contorno smussato.** L'upscaler conserva gli scalini dei contorni neri di 1 px. La sagoma si ridefinisce come livello 0,5 della maschera originale sfocata (gaussiana σ=0,65 px a 1x, lo stesso campo usato dal motore per l'alpha). Dove il pixel di bordo originale è scuro, si dipinge lungo il bordo smussato una fascia di inchiostro spessa quanto il contorno originale (circa 1,05), con antialiasing. Linee interne e colori restano quelli dell'upscaler.
- **Alpha.** I JPEG non hanno alpha, quindi il motore la ricostruisce dalla sagoma originale: bilineare più smoothstep 0,3-0,7, con bordi estesi. Nel pacchetto, i colori fuori dalla sagoma si riempiono allargando i colori di bordo (box blur a raggi 2, 4, 8, 16). Senza questo passo il JPEG crea frange scure.
- **Sprite sovrapposti.** Il buffer degli id ha due livelli (sprite in cima e sprite sotto). Il bordo semitrasparente di una testa si fonde con l'HD del corpo sotto, invece che con il pixel originale ingrandito.
- **Prospettiva.** Con una scala diversa da 100, lo sprite HD si ricampiona bilineare nella posizione esatta, invece di saltare o ripetere righe come faceva l'originale.
- **Se un colore del fotogramma non si mappa sulla palette corrente, si usa l'originale.** Uno sprite che peggiora si toglie dall'indice e il motore torna da solo all'originale.
- **Clarity sugli sprite (scartato):** su un foglio di 19 fotogrammi la camminata sfarfalla 2-3 volte
  più della pipeline locale, il dettaglio inventato è granuloso e l'alfa a blocchi lascia la scaletta.
- **Resa "cinematografica" (poi abbandonata).** Era calcolata solo dalla sagoma, quindi stabile tra fotogrammi: inchiostro più spesso, ombra cel-shading dal lato opposto alla luce, luce di bordo, contorno esterno. È stata approvata a forza 0.8 con contorno 1.4, ma causava ombre e macchie scure. È stata sostituita da APISR GRL con il solo contorno smussato.

## 7. Font

- **Strada migliore per i testi in gioco: l'HD dei font bitmap originali** (`rstool.py font from-bitmap`), fedele al disegno. I glifi indicizzati (riempimento, contorno/ombra) si ingrandiscono a 3x a blocchi esatti smussando solo i gradini delle diagonali vere: gli angoli retti restano vivi e il centro di ogni blocco è il pixel originale. Il primo metodo provato (Scale3x due volte → 9x → media 3x3) arrotondava gli angoli e una "D" si leggeva "O"; gli upscaler IA fanno lo stesso. Verifica: riportato a 1x ogni glifo coincide con l'originale.
- **Atlante**: PNG con R = copertura del riempimento e G = copertura della sagoma (riempimento + contorno), più una tabella di metriche (posizione nell'atlante, offset, avanzamento) per ognuno dei 256 codici. Atlanti da TTF con licenza OFL restano l'alternativa per sottotitoli e filmati o quando il font originale è inservibile.
- **Glifi mancanti** (accentate della lingua): prima da un'altra edizione dello stesso gioco (stesso disegno, a volte con 10–15 glifi di peso diverso: lì si porta solo l'accento sulla base dell'edizione principale), poi costruiti: lettera base + accento della minuscola accentata dello stesso font, contorno ridisegnato con il nocciolo misurato sul font. Vanno in codici liberi (posizioni CP850) con una mappa Unicode → glifo; il motore disegna i glifi nuovi anche in modalità originale riducendo l'atlante HD, identici pixel per pixel.
- **Maiuscole accentate**: i font piccoli d'epoca accorciano il corpo della `É` per far stare l'accento nella cella; accanto alle minuscole si legge "è". Varianti provate in un fumetto vero: corpo pieno + accento intero sopra la riga (scelta, l'unica che si legge subito maiuscola); accento piatto di una riga (diventa un macron, acuto e grave non si distinguono); corpo accorciato di una riga (ancora ambiguo). Il motore non deve tagliare l'accento alla cella; nei fumetti su più righe può coprire 1–2 righe di contorno della riga sopra, accettabile.
- **Verbi dell'interfaccia** tradotti più lunghi dell'originale: posizione e larghezza massima in un file della patch per lingua, con riduzione della spaziatura di 1–2 px oltre la larghezza; le posizioni di un'edizione tradotta ufficiale sono il riferimento migliore.
- **Menu e aiuti**: il font del gioco (anche convertito in TTF a pixel dall'atlante) va bene per titoli e pulsanti; i testi lunghi vogliono un font leggibile con tutti gli accenti, con dimensione minima legata alla scala della GUI.
- **Il motore intercetta le stringhe invece di disegnarle** e le ridisegna dagli atlanti, centrate nel riquadro della riga originale. Se sono troppo larghe le comprime fino al 70%. Colori e dissolvenze vengono dalla palette corrente.
- **Alfabeti stilizzati:** si genera l'atlante sostituendo i glifi con le forme equivalenti dello stile, mantenendo eventuali tratti tagliati intenzionali.
- **Sottotitoli:** si usa un font più leggibile, chiaro con contorno nero, separato da quello dei fumetti.
- **Accenti:** con il font HD, l'apostrofo usato al posto dell'accento (`e'`) diventa la lettera accentata. Per le lettere che mancano nel set si usa un codice privato.

## 8. Sfondi alti e casi particolari

- **Edizioni diverse con dimensioni diverse.** Uno sfondo alto esisteva in due edizioni con altezze diverse (stessa geometria nella parte comune, palette e retinatura diverse). Il motore scartava l'HD per "dimensioni inattese" e mostrava l'originale. Rimedio: rifare l'HD dalla versione dell'utente. Le bande del vecchio HD si sono riusate ridotte a 1x, tagliate e raccordate nei colori riga per riga, poi è stata ingrandita tutta l'immagine. Bisogna sempre verificare nel log del motore che l'HD sia stato caricato.
- **Scene buie:** se l'originale ha già margini neri, banda nera o sfumatura scura dal bordo, senza spese.

## 9. Flusso di revisione e costi

1. **Fogli di confronto** con la banda e 90 px di originale accanto, oppure prima e dopo affiancati, numerati, 6 stanze per foglio, con un elenco numero → stanza. Così l'utente può rispondere "scarta 12, 37" anche dal telefono.
2. **Classificazione dei difetti:**
   - (a) banda inventata sbagliata (oggetto o scritta);
   - (b) cucitura o differenza di luminosità;
   - (c) difetto dell'upscaler nel centro.

   Il centro approvato non si tocca. Qualsiasi ritocco al centro richiede un'approvazione esplicita.
3. **Preventivo scritto prima di ogni chiamata a pagamento:** stanze x tentativi x prezzo, più il tempo di revisione. Esempio: 16 stanze x 2 tentativi x 0,05 $ ≈ 1,6 $, contro circa 4-5 $ con Gemini. Prima si esegue sempre una modalità "verifica" gratuita (chiave, modelli, piano), poi la generazione.
4. **Generazione in CI**, con i risultati grezzi, i fogli e un rapporto in un ramo privato. Nulla viene pubblicato e nulla sostituisce il ramo principale in automatico.
5. **Si integra solo ciò che è stato approvato.** Il passo successivo, se c'è, è un altro giro mirato oppure una ricetta locale.
6. **Ordine di grandezza dei costi effettivi:**
   - confronto iniziale: circa 1,2 $;
   - passata completa: circa 8,8 $;
   - giro sulle residue: circa 1,5 $.

   Totale circa 10 $ di credito per 100 sfondi. Upscaling e ritocchi locali: 0 $.

## 10. Controlli di qualità

- **Confrontare sempre con l'originale 1x**, ritagliando la stessa zona in 1x e in HD.
- **Indice di nitidezza banda/centro** su tutte le stanze, per trovare le bande sfocate.
- **Scansione automatica delle righe di bordo**, poi verifica a occhio dei candidati.
- **Esecuzione con il driver di test:** log di caricamento dell'HD e screenshot HD delle stanze interessate, cercando aloni, bordi tagliati e sfarfallii.
- **Differenza media del centro dopo un ritocco della banda:** deve essere vicina a 0, cioè solo ricodifica.

## Errori da non ripetere

- **Non lanciare LaMa (o un altro inpainting) direttamente sull'HD:** le bande vengono sfocate. Si lavora a 1x e si ingrandisce dopo.
- **Non ingrandire separatamente centro e bande:** si creano cuciture di texture. Si ingrandisce l'immagine 16:9 intera.
- **Non fidarsi del solo controllo automatico:** scarta bande buone e non vede le firme piccole.
- **Non lasciare che un modello completi una scritta tagliata:** inventa lettere. Il testo si ricava dai dati del gioco e si ridisegna a mano.
- **Non usare modelli di modifica guidata dell'intera immagine** (Kontext, Qwen e simili) per l'outpainting: spostano l'inquadratura. Serve un modello con maschera.
- **Non attribuire al modello un difetto prima di aver escluso i passi successivi:** le ombre scure degli sprite venivano dal ritocco, non dall'upscaler.
- **Non usare la copia traslata per strutture geometriche ripetute** (pannelli, rivetti): raddoppia spigoli e crea scalini. Si continua lungo le rette misurate.
- **Non dimenticare le colonne o righe nere e gli artefatti di scansione dei bordi:** nel 16:9 diventano una riga ben visibile.
- **Non salvare gli sprite JPEG senza riempire i colori fuori dalla sagoma:** compaiono frange scure.
- **Non usare JPEG con crominanza sottocampionata per grafica a contorni netti.**
- **Non spendere crediti senza preventivo e approvazione, e non rifare un tentativo pagato senza prima rivedere i fogli di quelli già fatti:** spesso contengono parti riutilizzabili.
- **Non dare per scontato che l'utente abbia la stessa edizione dei dati:** dimensioni diverse fanno scartare l'HD in silenzio. Bisogna controllare il log.
- **Non pubblicare immagini, fogli di confronto o asset derivati dal gioco:** restano solo nei rami privati.
