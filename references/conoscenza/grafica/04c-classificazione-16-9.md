# Classificazione 16:9 delle stanze
## Classificazione 16:9 su un secondo gioco: cosa sbagliava
Prova su un gioco a bassa risoluzione con barra comandi fissa (~100 scene etichettate a mano): il
classificatore della prima versione sbagliava più di metà delle scene statiche e quasi tutte le
`open-static`. Cause e correzioni (ora nel codice):
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
Risultato: classi giuste da circa due terzi a più di quattro quinti, decisione "inventare o no"
da tre quarti a quasi tutte; i nomi delle stanze valgono qualche punto in più.
