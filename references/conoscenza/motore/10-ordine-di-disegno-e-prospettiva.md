# Ordine di disegno e prospettiva

- **Ordinamento stabile**: a parità di Z va sopra l'oggetto col bordo inferiore più in alto (le teste sopra i corpi).
- **Zone-oggetto con immagine alla stessa Z**: va sopra quella dichiarata **prima** nello script, come nell'originale.
  - Una regola ad hoc del tipo "alza la zona accesa per ultima" risolveva un caso e ne rompeva altri: si ricava la regola dall'originale.
- **Scala prospettica**: si applica sempre al personaggio che cammina e alle animazioni dichiarate scalate. Un'altra figura viene scalata solo se la sua Z coincide col bordo inferiore (±8 px). Così una Z usata per ordinare una parte del corpo non la sposta.
- **Scala 0**: non si disegna. Prima causava una divisione per zero in uno script con un parametro mancante.
