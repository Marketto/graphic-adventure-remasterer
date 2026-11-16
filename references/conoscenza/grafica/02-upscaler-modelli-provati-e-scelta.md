# Upscaler: modelli provati e scelta

Il confronto si fa su fogli numerati: 0 = originale, 1 = versione attualmente nel gioco, poi i candidati. Ci sono due batterie separate, una di 5 sfondi e una di 5 personaggi, perché il modello migliore per gli sfondi non è necessariamente il migliore per gli sprite. Tutti i modelli sono caricati con `spandrel`, con i pesi dalle release GitHub.

| Modello | Esito |
|---|---|
| RealESRGAN_x4plus_anime_6B (la base di partenza) | Accettabile, ma con tratti morbidi |
| realesr-animevideov3 | Impasta i dettagli. È circa 5 volte più veloce, utile solo per anteprime |
| 2x-AnimeSharpV3 / V4_RCAN | Fedeli alla retinatura ma sfocati; il V4 cancella i volti. Scartati |
| APISR RRDB / GRL / DAT (4x, GAN) | Linee d'inchiostro nette, campiture pulite, dettagli leggibili |
| AnimeSharpV4 + APISR 2x in cascata | Rovina i personaggi. Scartato |

Tempi misurati su CPU a 2 core, con pezzi da 192x192:

| Modello | s/pezzo | µs/pixel | ~100 sfondi (~35 Mpx) | ~1.400 sprite (~42 Mpx) |
|---|---|---|---|---|
| APISR RRDB | 2,7 | 73 | ~50 min | ~1 h |
| APISR GRL | 3,0 | 82 | ~55 min | ~1 h 05 |
| APISR DAT | 20,6 | 558 | ~6 h | ~7 h |

Scelta:
- **Sfondi: APISR RRDB.** È quasi pulito come DAT con contorni un po' più marcati, e 7-8 volte più veloce.
- **Sprite: APISR GRL.** È il più nitido e dettagliato, con qualche alone che però sugli sprite si gestisce con l'alpha.
- **Riduzione da 4x a 3x** con LANCZOS (BOX per gli sprite), poi JPEG q90 senza sottocampionamento della crominanza (4:4:4). Il 4:2:0 sporca i bordi colorati.
- **Lezione importante.** Sugli sprite le differenze tra modelli erano piccole: le macchie e le ombre scure della versione precedente venivano dal ritocco successivo (vedi §6), non dal modello. Prima di cambiare upscaler bisogna isolare quale passo della pipeline causa il difetto.
