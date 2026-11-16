# Viewport 16:9, sprite nelle bande e bande cliccabili

- **Finestra estesa**: (W + 2·e) x H pixel di gioco, con e la banda per lato (`widescreen geometry`). Il gioco resta W x H: il renderer compone la finestra larga e riempie le bande con lo sfondo allargato `<nome>_w`, se esiste, altrimenti di nero. Il colore delle bande segue la dissolvenza del pixel originale più vicino. Gli interni chiusi usano bande continuate come gli altri; il nero resta solo come ripiego.
- **Il centro dell'immagine allargata sostituisce anche lo sfondo HD normale**: così le colonne di bordo dell'originale (spesso artefatti) non si vedono.
- **Sprite nelle bande** (solo nelle stanze con `_w`, solo in HD):
  - Si disegna di nuovo, con lo stesso blitter, la parte degli oggetti di scena che esce dal backbuffer. Si usano due strisce da 36 colonne, con i loro id degli sprite.
  - La maschera di priorità si legge nella colonna di bordo più vicina.
  - Le strisce partono ogni scena da un riferimento 8 bit dello sfondo allargato (l'originale con le colonne di bordo ripetute), così la regola "sfondo HD per corrispondenza" vale anche lì.
  - Esclusi etichette, fumetti e inventario.
  - Problema risolto: personaggi tagliati di netto al bordo dei 640 px.
  - Limite: uno sprite "parcheggiato" dagli script appena fuori schermo ora si vede.
- **Bande cliccabili**: le coordinate del mouse si riportano al gioco togliendo il margine.
  - Nelle stanze più larghe dello schermo la banda mostra la stanza stessa: valgono la zona e la camminata in quel punto.
  - Oltre il bordo della stanza vale una zona che tocca il bordo o ci arriva entro 16 px alla stessa altezza (zone di percorso escluse).
  - Senza zone: camminata verso il bordo.
  - Problema risolto: limitare il punto a x=0/639 non colpiva mai le uscite laterali, perché il test del rettangolo esclude il pixel di bordo.
