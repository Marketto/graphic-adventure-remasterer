# Bande 16:9: generazione (LaMa, quilting, Gemini, fal.ai)
**Regola.** Si parte sempre dalle tecniche locali collaudate (LaMa a 1x e quilting qui sotto, ricette
locali e indice di nitidezza in `04b-bande-16-9-controlli-e-ricette.md`) e l'outpainting a pagamento
(fal.ai, qui sotto) si usa **solo se l'utente lo sceglie**, chiedendolo
dopo l'analisi, con preventivo e approvazione per ogni lotto. In pratica fal.ai è
stato scelto per molte stanze, ma resta un'opzione, non il default.

**Proporzione dei pixel.** Gli esempi qui usano pixel quadrati (es. 640x400: 36 px per lato)
perché quell'arte non era pensata per pixel allungati. La correzione dell'aspetto si fa solo
se il gioco era concepito per un monitor che li allungava: si decide da data di uscita,
piattaforma di destinazione, monitor dell'epoca e origine dell'arte (disegnata su quel monitor o
digitalizzata a pixel quadrati), e si verifica guardando oggetti tondi affiancati.

## LaMa direttamente sull'HD (scartato)
Lavorando sull'HD, LaMa (big-lama TorchScript, ~200 MB) produce bande molto sfocate.

## LaMa a 1x più upscaler
Problema risolto: LaMa sbaglia meno la composizione se lavora alla risoluzione nativa. LaMa ricostruisce la banda (e px per lato) a 1x. L'upscaler porta poi a 3x la striscia con 24 px di contesto dell'originale, sfumata su 24 px verso il centro HD. Il centro non viene mai toccato.

## Image quilting guidato da LaMa
Problema: LaMa indovina la disposizione (dove vanno cielo, muro, prato) ma dipinge liscio, con un effetto da "schizzo" su un fondale dipinto a mano.
Soluzione (Efros & Freeman 2001, nella variante "texture transfer"): la banda si ricompone a tessere di 12 px con 4 px di sovrapposizione, a partire dal bordo verso l'esterno. Per ogni tessera si sceglie la patch dello stesso sfondo che:
- continua bene ciò che c'è già;
- ha i colori che LaMa ha messo in quel punto;
- viene da un'altezza simile nell'immagine;
- è stata usata poche volte.

Le tessere si uniscono lungo il taglio di minima differenza. Ogni pixel della banda è quindi un pixel dipinto dall'artista. Dove nessuna patch combacia (un oggetto tagliato dal bordo) resta il colore di LaMa.

## Gemini (outpainting con prompt)
Il centro HD viene messo su una tela 16:9 con bande grigie piatte, e il prompt chiede di dipingere solo le aree grigie nello stesso stile, senza persone, testi o loghi. Dalla risposta si tiene solo la banda:
- **Allineamento:** si cerca scala e spostamento del centro restituito, con scala da 0,97 a 1,03 e ±6 px su una copia ridotta a 1/4, perché il modello sposta o ridimensiona leggermente l'immagine.
- **Raccordo dei colori:** per ogni riga si calcola lo scarto di colore su 18 px dentro l'originale, lo si smussa in verticale (finestra di 61 righe) e lo si fa svanire allontanandosi dalla cucitura.
- **Sfumatura** su 24 px.

Costo: circa 0,134 $ a immagine a 2K. Rimasto come alternativa più costosa.

## fal.ai: FLUX.1 Fill pro (scelto), Kontext pro, Qwen Image Edit
- **Confronto su 9 sfondi x 3 modelli, circa 1,2 $.**
  - **Fill pro:** è vero outpainting con maschera (il centro non viene toccato) e allinea bene, con scarto 1-10.
  - **Kontext pro e Qwen:** sono modifiche guidate dell'intera immagine, cambiano l'inquadratura (scarto fino a 100) e lasciano bande scure o sfocate. Scartati.
- **Prezzi indicativi:** Fill pro ~0,05 $, Kontext pro ~0,04 $, Qwen 0,03-0,045 $ a immagine.
- **Riduzione dei costi:** la tela si manda a metà della risoluzione HD, cioè 1,5x l'originale, che basta per bande strette (qualche decina di pixel a 1x). Con `sync_mode` le immagini non restano nello storico del servizio.
- **Passata completa: circa 100 stanze, meno di 200 immagini, meno di 10 $.** Circa due terzi delle stanze sono state accettate con le bande Fill, le altre sono tornate al ripiego, soprattutto stanze buie e a scorrimento.
- **Prompt:** descrive un fondale dipinto, finito e a colori, chiedendo di continuare pareti, pavimenti, cieli e oggetti tagliati dal bordo. Include esplicitamente "not a sketch, not line art, no white paper, no people, no text, no signature, no logos". Se i bordi sono scuri si aggiunge una frase "scena buia", perché in quei casi il modello disegnava schizzi bianchi su carta.
