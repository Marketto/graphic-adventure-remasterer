# Salvataggi con miniature

- **Formato originale invariato**: si accoda l'intestazione estesa di ScummVM (data, ora, tempo di gioco, miniatura; offset negli ultimi 4 byte). Il lettore originale si ferma prima, quindi:
  - le versioni vecchie leggono i file nuovi;
  - i file vecchi si caricano ancora, con un segnaposto "Nessuna immagine".
- **Miniatura presa dallo schermo del gioco** (frame HD o 640x400), non dall'overlay del menu aperto. Larga 160 px con le proporzioni dello schermo (160x90 in 16:9), ridotta con media a blocchi, che non produce scalettature come il campionamento.
- La metaengine dichiara le capacità relative (meta info, miniatura, data, tempo di gioco). Così i dialoghi Salva/Carica mostrano la griglia e l'elenco con l'anteprima.
- **Bug trovato**: caricare durante il gioco una partita con lo stesso personaggio non ricaricava la sua grafica (crash). Ora si ricarica quando la grafica manca, non solo quando cambia il nome.
