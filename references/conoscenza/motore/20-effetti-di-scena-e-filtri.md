# Effetti di scena, dissolvenze e filtri

## Effetti dichiarati nei dati (mai nel codice per una stanza)
Un file per scena nel pacchetto (`gfx/bg/<scena>.effects.txt`, formato in `references/asset-contract.md`).
I motori vecchi lo ignorano; in modalità classica restano gli effetti originali.
- `freeze <voci>`: lo sfondo HD ignora i cicli di colore che sfarfallano.
- `water <ampiezza> <lunghezza> <giri/s>` + maschera: ogni ~80 ms i pixel di sfondo non coperti da sprite si spostano lungo seni, solo da acqua ad acqua.
- `parallax [mask <png>] <striscia> <vel> …`: strisce in ciclo, dalla più lontana alla più vicina, solo dove si vede lo sfondo. Vale anche nelle bande 16:9. Segue solo le dissolvenze di tutta la scena (soglia sul numero di voci cambiate), non i cambi delle voci del ciclo.
- `ground`: trama in prospettiva verso un punto di fuga; sfuma nel colore medio dove le ripetizioni sono più fitte di ~3 px (anti-sfarfallio).
- `glass <chiavi sprite>`: il paesaggio passa anche dentro gli sprite che mostrano un vetro.
- Maschere: si ricavano dalle voci del ciclo di colori originale (`rstool.py gfx effect-mask`); **vanno mostrate all'utente**, perché un vetro sbagliato copre un mobile.

## Dissolvenze
Molti giochi scuriscono la palette **a passi costanti** (sottrazione) invece che a fattore: il motore riconosce il passo comune e sottrae lo stesso valore al pixel HD. Senza, l'immagine alterna HD e bassa risoluzione e lascia un fantasma dei bordi.

## Filtri: solo dove servono
Quando tutto è HD, un filtro di ingrandimento (xBR, Scale3x) che gira su tutta la tessera sporca è lavoro buttato.
- Si salta ogni pixel che prenderà lo sfondo o uno sprite HD (maschera per tessera dai modi già calcolati).
- Contatore `lowres=` nel log dei fotogrammi: misura quanto passa ancora dal filtro.
- Opzione `remaster_filter=xbr|scale3x|none`: `none` = pixel netti, utile per vedere i buchi.
- Report per stanza dopo un giro del driver: elenco di ciò che non è ancora HD.
- Strumenti per trovarlo: tinta di debug sui pixel HD, dump di tutti gli sprite dichiarati dalla stanza, pacchetto canary. Alcuni casi si trovano solo guardando: icone copiate senza passare dai blitter, cicli usati come paesaggio.

## Audio senza lavoro a runtime
Gli effetti suonati a frequenze diverse si preparano offline, uno per coppia (suono, frequenza): `sfx/<nome>_<freq>.ogg`, già a 44,1 kHz con ricampionamento polifase. Se il file manca, il motore usa l'originale.

## Prestazioni misurate (ordini di grandezza)
- Un ciclo parziale di palette (≤ 64 voci) ricompone solo le tessere che usano quei colori: da ~30 ms a ~12 ms.
- Durante lo scorrimento si ricompone ~7% dei pixel.
- Le bande 16:9 si ridipingono solo se le colonne di bordo usano i colori cambiati.
- Il driver MIDI/AdLib si apre solo al primo brano MIDI.
- Ogni ottimizzazione si misura prima e dopo (`hd=` in ms nel log).
