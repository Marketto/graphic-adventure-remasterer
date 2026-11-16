# Proporzione dei pixel
## Proporzione dei pixel: misurare invece di guardare
Su viste in prospettiva e documenti il foglio a confronto non aiuta. È stata decisiva la misura
di un oggetto rotondo visto dall'alto, diviso tra quattro stanze e ricomposto: larghezza/altezza
1,20-1,23, quindi pixel pensati per un CRT 4:3 (`rstool.py widescreen aspect-measure ... --compose 2x2`).
Oggi la ricerca è automatica (`rstool.py widescreen aspect-auto ... --evidence <dump>/bg <dump>/obj`):
su un gioco medio (~100 fondali e ~1000 oggetti, in meno di un minuto) trova qualche decina di forme
rotonde; scarta quelle più larghe (prospettiva) e più alte (non rotonde) e ne restano una ventina
utili, con la moda vicina a 1,2: decisione automatica uguale a quella misurata a mano. Le forme in prospettiva sono la
maggioranza: conta la distribuzione delle forme frontali, mai la singola forma.
