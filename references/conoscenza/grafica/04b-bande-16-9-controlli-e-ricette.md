# Bande 16:9: controlli, ricette locali, bordi, motore
## Controllo automatico (`band_check`) e i suoi limiti
Per ogni banda il controllo misura, rispetto alla colonna di bordo dell'originale:
- la frazione di pixel bianchi (luminanza > 215), oltre il 12% in più;
- lo scarto di luminosità media, oltre il 18%;
- su un bordo scuro e piatto (media < 40), un eccesso di variazione oltre 10, che indica macchie chiare o firme.

Se il primo tentativo viene scartato se ne fa uno solo in più. Se si scarta anche il secondo si torna al ripiego locale (LaMa + quilting + APISR). Il limite è al massimo 2 tentativi.

Limite scoperto: il controllo rifiuta anche bande buone che sono solo più scure o più chiare del bordo, per esempio un tronco accanto a un vialetto chiaro. In una passata su 16 stanze ne aveva accettate 2, mentre a occhio se ne sono salvate 11. Per questo esiste uno strumento che compone i tentativi scelti a mano, anche quelli scartati, eventualmente prendendo una sola delle due bande e lasciando l'altra com'era.

## Ricette locali per le stanze residue (gratis)
Quando entrambi i tentativi a pagamento inventano persone, cornici o scritte, la banda si ricostruisce a 1x con una ricetta specifica per la stanza. Poi la striscia [banda + 24 colonne di contesto] passa per APISR RRDB e viene incollata. Il centro resta invariato: la differenza media è di 0,02-0,07 livelli, dovuta solo alla ricodifica JPEG.
- **Continuazione riga per riga del colore del bordo**, sempre più sfumata verso l'esterno, con la grana dell'originale specchiata. Funziona per nebbia, neve e cielo, ed evita blocchi ripetuti.
- **Copia di texture spostata**, per esempio da 40 px più a sinistra, con correzione di quota e pendenza per elementi lineari come binari o crinali, e raccordo a specchio sul bordo.
- **Riuso parziale di un tentativo già pagato**: per esempio la parte alta di una banda, mentre la parte bassa si ripete da una striscia vera dell'originale.
- **Continuazione geometrica** (per interni con travi, pannelli e file di rivetti). Una copia traslata ripeteva lo spigolo e i rivetti e creava scalini sul bordo. La soluzione è misurare sull'originale le rette (bordo della trave, diagonale del pannello, filo, fila di rivetti con pendenza e passo) e copiare ogni zona lungo la propria retta, colonna per colonna. Lo spigolo prosegue sulla stessa retta, senza un secondo spigolo.

## Righe e colonne di bordo (artefatti di scansione)
Problema: righe sottili di 1-4 px a 1x, scure o chiare, lungo i bordi dell'originale. Nel 16:9 separano visibilmente la banda dal centro.
- **Ricerca automatica su tutti gli sfondi:** si confrontano le righe e colonne 0-2 con le 3 successive verso l'interno (frazione di pixel più scuri o più chiari, scarto mediano). Si guardano anche le colonne HD attorno ai bordi del centro. I candidati vanno poi rivisti ingranditi: molti sono disegno vero (tronchi, pali, cornici) e differenze deboli, tra −6 e −11 livelli.
- **Ritocco:** si interpola tra un'ancora 12 px fuori dal centro e una 3K+4 px dentro. Si sostituiscono solo i pixel più scuri o più chiari dell'interpolazione di oltre 10 livelli. Le linee vere che attraversano il bordo sono scure anche sulle ancore, quindi restano. Gli stessi pixel vanno scritti sia nello sfondo normale sia in quello allargato.
- **Colonna chiara sul bordo:** si sottrae la differenza mediana (su 41 righe) rispetto ai due lati, solo dove i due lati hanno lo stesso colore.

## "Bande a fuoco" e indice di nitidezza
L'indice è l'energia ad alta frequenza, |L − sfocatura gaussiana σ=1,5|, della banda divisa per quella dei 108 px di centro accanto. Sotto 0,6 la banda si vede sfocata. L'indice non ha senso per scene buie o piatte, che vanno escluse.

La nitidezza si recupera con il quilting dall'originale, con la ripetizione di strisce vere, e con un unsharp mask tarato sulla banda:
- soglia di 2 livelli;
- sovraelongazione limitata ai minimi e massimi locali, così non nascono aloni;
- effetto sfumato sui 12 px accanto al centro.

Esempi: un indice da 0,32 a 0,93, uno da 0,32 a 1,00.

## Le bande nel motore
- La banda prende la stessa dissolvenza del pixel originale più vicino.
- Gli sprite che escono dai 640 px vengono ridisegnati in due strisce laterali, con la maschera di priorità letta nella colonna di bordo più vicina. Senza questo i personaggi apparirebbero tagliati al bordo.
- Le zone cliccabili che toccano il bordo valgono anche nella banda.
- Limite: uno sprite "parcheggiato" dagli script appena fuori schermo diventa visibile.
