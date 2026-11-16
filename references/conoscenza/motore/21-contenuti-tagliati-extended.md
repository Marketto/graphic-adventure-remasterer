# Contenuti tagliati: versione "extended"

Molti giochi contengono battute, scene e suoni scritti ma spenti. Si possono offrire in una modalità
"extended" (o "director's cut"): un interruttore nel launcher e nel menu. Se l'utente vuole la
modalità, sceglie anche se è accesa di predefinito; spenta, il gioco è identico all'originale.

## Censimento (gratuito, prima di proporre)
`rstool.py usage scan` con il profilo della sintassi degli script:
- **righe e blocchi commentati**, raggruppati per file (`analysis/extended-candidates.tsv`);
- **flag richiesti ma mai impostati**: rami di dialogo e zone mai raggiungibili;
- **risposte che portano a domande inesistenti** (spesso un refuso nel nome: è un bug, non un taglio);
- **zone spente** che nessuno accende, animazioni mai avviate;
- **comandi che il motore legge ma non esegue**: confrontare con l'eseguibile originale o con un altro motore della stessa famiglia, perché a volte l'originale li mostrava e il port no (per esempio un commento di fine stanza);
- **stanze irraggiungibili**: grafo dalle stanze di partenza.

## Classificazione (una riga per candidato)
| Classe | Esempio | Cosa fare |
|---|---|---|
| contenuto tagliato vero | una domanda a un personaggio, coerente con la scena dopo | proporre per l'extended |
| bug dell'originale | risposta verso un nome sbagliato | correggere sempre (righe della patch), non solo nell'extended |
| avanzo | prove, versioni scartate dello stesso enigma, blocchi di debug, battute interne degli autori | non ripristinare |
| incerto | condizione con comportamento indefinito | verificare col driver prima di proporre |

Per ognuno: battute (e voci da generare, col preventivo), file usati, rischio per la completabilità,
lavoro stimato. L'utente sceglie dalla pagina di scelta.

## Meccanismi generici nel motore (il contenuto sta nella patch)
- **Righe della patch per gli script** (`script/line-edits.txt`): sostituzione di righe al caricamento; un secondo file opzionale legato all'interruttore (`script/extended.txt`). Il log dice quante volte ogni riga è stata applicata. Lo stesso meccanismo riaccende effetti spenti.
- **Zone nuove in fondo alla stanza**, mai in mezzo: i flag delle zone nei salvataggi sono per posizione. Così i salvataggi restano compatibili nei due modi.
- **Flag che passano da una parte all'altra** (`script/part-flags.txt`): alla fine della parte A, se una condizione è vera (flag, inventario, contatori), si ricorda un flag per la parte B. Va salvato nei salvataggi in una riga opzionale che i motori vecchi ignorano.
- **Commento di fine stanza** e simili: ripristinati come nel motore originale, verificandone il comportamento (quando esce, con che transizione).
- **Robustezza**: un contenuto ripristinato attraversa codice mai provato. Per esempio un ritratto fuori intervallo deve dare un avviso e mostrare il fotogramma 0, non far cadere il gioco.
- Cambio dell'interruttore a partita in corso: vale dalla prossima stanza, dalla prossima parte o dalla prossima uscita. Nessun flag già impostato si toglie.

## Prove
Un caso del driver per ogni ripristino, con interruttore acceso e spento: righe applicate, flag ricordati, musica o voce partita, nessun crash. Più un salvataggio vecchio che si carica.
