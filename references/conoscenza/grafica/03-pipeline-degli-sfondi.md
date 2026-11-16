# Pipeline degli sfondi

1. **Conversione dello sfondo originale in PNG** con la stessa palette che usa il motore. Se si usa una palette diversa, i pixel HD non coincidono con il test di uguaglianza del motore.
2. **Colonne nere ai bordi dell'originale.** Molti sfondi hanno da 1 a 20 colonne quasi nere ai lati (soglia: media di luminanza < 18 e deviazione < 12). Vanno trovate e ridipinte, altrimenti nel 16:9 compare una riga nera tra il centro e la banda.
3. **Bande 16:9 costruite a 1x**, non in HD (vedi `04a-bande-16-9-generazione.md`).
4. **Ingrandimento dell'immagine 16:9 intera in un solo passaggio**, centro più bande, con lo stesso modello. Il centro HD si ritaglia poi dalla stessa immagine, quindi sfondo normale e sfondo allargato sono identici al pixel. Così non ci sono cuciture di texture tra parti ingrandite separatamente.
5. **Scene non allargabili.** Gli interni chiusi si continuano (pareti, pavimento, soffitto) con le tecniche locali; bande nere solo su richiesta. Le scene filmate restano in 4:3. Le stanze più larghe dello schermo (a scorrimento) hanno solo l'HD.
6. **Script ripartibile** che salta le stanze già fatte, con le bande 1x tenute in cache. Rifare l'upscaling non deve rigenerare le bande.
