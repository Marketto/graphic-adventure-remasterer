# Conoscenza (esperienza pratica, in forma generica)

Tecniche, ordini di grandezza e lezioni ricavati da remaster completi di avventure 2D degli anni '90 su un fork di ScummVM. Nessun riferimento ai giochi usati come prova. **Leggi solo il file che serve**: ogni file è una sezione breve.
Regole trasversali: `../regole-comuni.md`. Se una nota e una skill divergono, la nota è più recente: aggiorna la skill.

| Cartella | File | Quando leggerlo |
|---|---|---|
| `motore/` | `01` estrazione senza Layer · `02` motore e contenuto separati · `03` composizione del frame · `04` sprite HD (buffer degli id) · `05` testo HD | prima di agganciare un motore |
| | `06` viewport 16:9 · `07` scorrimento fluido · `08` tempi calibrati · `09` input · `10` ordine di disegno | rendering, 16:9, tempi, mouse |
| | `11` salvataggi · `12` menu · `13` aiuti (tasto H) · `14` driver di test | funzioni in gioco, QA |
| | `15` build locali · `16` patch del motore · `17` web · `18` rilasci e versioni · `23` rilascio efficiente | build e rilascio |
| | `19` camera, veicoli e navigazione · `20` effetti di scena, dissolvenze, filtri · `21` contenuti tagliati (extended) · `22` launcher e salvataggi nel cloud | funzioni avanzate |
| `grafica/` | `01` ambiente · `02` upscaler · `03` sfondi · `04a-d` bande 16:9 (generazione, controlli, classificazione, proporzione dei pixel) | sfondi e 16:9 |
| | `05` scritte e insegne · `06` sprite · `07` font · `08` sfondi alti · `09` revisione e costi · `10` controlli · `11` oggetti, icone, puntatori, animazioni | sprite, testi, revisione |
| `voci-audio/` | `01a` chi parla e casting · `01b` voce di un'opera d'origine · `01c` regia e tempi · `01d` controllo, crediti, lotti · `01e` chi parla davvero (audit) | doppiaggio |
| | `02` correzione dei testi · `03a` normalizzazione · `03b` musica in blocchi e MIDI dinamica · `03c` manuale e indizi · `03d` effetti sonori e versi · `03e` musica lineare (riorchestrazione, ibrido col CD) · `04` flusso con agenti | testi, audio, organizzazione |

Ogni cartella ha `errori-da-non-ripetere.md`: leggilo prima di iniziare quell'area.
