# Errori da non ripetere

- **Non lanciare LaMa (o un altro inpainting) direttamente sull'HD:** le bande vengono sfocate. Si lavora a 1x e si ingrandisce dopo.
- **Non ingrandire separatamente centro e bande:** si creano cuciture di texture. Si ingrandisce l'immagine 16:9 intera.
- **Non fidarsi del solo controllo automatico:** scarta bande buone e non vede le firme piccole.
- **Non lasciare che un modello completi una scritta tagliata:** inventa lettere. Il testo si ricava dai dati del gioco e si ridisegna a mano.
- **Non usare modelli di modifica guidata dell'intera immagine** (Kontext, Qwen e simili) per l'outpainting: spostano l'inquadratura. Serve un modello con maschera.
- **Non attribuire al modello un difetto prima di aver escluso i passi successivi:** le ombre scure degli sprite venivano dal ritocco, non dall'upscaler.
- **Non usare la copia traslata per strutture geometriche ripetute** (pannelli, rivetti): raddoppia spigoli e crea scalini. Si continua lungo le rette misurate.
- **Non dimenticare le colonne o righe nere e gli artefatti di scansione dei bordi:** nel 16:9 diventano una riga ben visibile.
- **Non salvare gli sprite JPEG senza riempire i colori fuori dalla sagoma:** compaiono frange scure.
- **Non usare JPEG con crominanza sottocampionata per grafica a contorni netti.**
- **Non spendere crediti senza preventivo e approvazione, e non rifare un tentativo pagato senza prima rivedere i fogli di quelli già fatti:** spesso contengono parti riutilizzabili.
- **Non dare per scontato che l'utente abbia la stessa edizione dei dati:** dimensioni diverse fanno scartare l'HD in silenzio. Bisogna controllare il log.
- **Non pubblicare immagini, fogli di confronto o asset derivati dal gioco:** restano solo nei rami privati.
