# 6b. Interfaccia del motore nello stile del gioco

Dettaglio della skill `engine-integration`.

Tutto ciò che il motore aggiunge (menu globale, salva/carica, opzioni remaster, finestra degli
aiuti, lettore del manuale, messaggi) deve sembrare parte del gioco, non di ScummVM:
1. Colori dall'**interfaccia originale** (menu, inventario, riquadri dei dialoghi), non dai
   fondali: `rstool.py ui palette <screenshot dell'interfaccia> --out analysis/ui-palette.json`
   propone i ruoli (fondo, pannello, pulsante, evidenza, testo...); correggili guardando.
2. `rstool.py ui theme --base <scummvm>/gui/themes/scummremastered --roles analysis/ui-palette.json
   --name "<gioco> Remaster" --out remaster/theme/<gioco>.zip [--font <ttf in stile>] [--logo <png>]`:
   copia del tema **dello stesso commit del fork** (la sintassi `.stx` cambia tra versioni), con
   palette, font (scalabile, con licenza che permette di ridistribuirlo) e logo sostituiti.
   Contrasto del testo ≥ 4,5 sia sul pannello sia sul fondo (il tool avvisa). Prova subito il
   tema nel ScummVM del fork: `xvfb-run scummvm --themepath=<cartella dello zip>
   --gui-theme=<nome dello zip>` e uno screenshot. Prepara 2-3 varianti e lascia scegliere.
3. Il fork lo rende predefinito (`gui_theme` e `themepath` nella configurazione distribuita col
   pacchetto: il tema di ScummVM è globale, non per gioco); FreeType nella build web, altrimenti
   alla scala del telefono il menu è a blocchi.
4. Un'etichetta più larga del pulsante passa al font normale invece di essere tagliata; niente
   pulsanti inutili ("Torna a elenco giochi" se si parte diretti nel gioco); versione della patch
   nel menu principale; finti alfabeti o lettering del gioco preservati dove il gioco li usa.
5. Verifica col driver (`gui` per aprire i menu, `shot`) a 1x e alla scala del telefono.
