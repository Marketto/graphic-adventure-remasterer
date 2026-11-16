# Musica in blocchi e MIDI dinamica
## Musica in blocchi con più varianti
Nella seconda prova ogni suono del motore conteneva più versioni (MT-32/General MIDI, AdLib,
altoparlante, a volte campioni digitali) e non c'erano tracce CD: si estrae la variante più vicina
al General MIDI come .mid standard e `rstool.py audio midi-classify` separa brani ed effetti
(brano: ≥ 20 s e ≥ 80 note). Alcuni estrattori scrivono una lunghezza di traccia sbagliata: il
parser non legge oltre la fine del file. Con la musica interattiva (punti di ripetizione) la
durata dei file sovrastima l'ascolto: i minuti sono un limite superiore.

## Musica MIDI dinamica: strategia "orchestra"
Regola: quando la musica è MIDI **a comando dinamico** (salti,
cicli, volumi e trasposizioni delle parti decisi dagli script, effetti MIDI sullo stesso
sintetizzatore) il MIDI **resta al motore** e si rifà il **SoundFont**: niente rendering in file,
niente generatori di musica. Un brano breve reso come file suonava circa 4 volte più a lungo, di fila
nel motore.
- *Problema:* con FluidSynth e un banco GM la musica suonava "acuta e finta". Diagnosi, in
  ordine: (1) note uguali per canale tra le versioni del brano (nessun errore d'ottava, nessuna
  trasposizione delle parti); (2) la tabella di conversione dei programmi del motore manda due
  timbri al posto sbagliato (tromba con sordina per una tromba aperta, sul canale più forte;
  ocarina per un flauto); (3) la curva di velocità GM attenua le note piano molto più del modulo
  d'epoca: corni, archi e batteria d'accompagnamento scendono 10-15 dB e sotto 250 Hz resta il
  4% dell'energia (35% nell'originale, 28% nel riferimento orchestrale); (4) la prova offline non
  aveva la mandata di riverbero che il motore manda davvero.
- *Soluzione:* SoundFont composito da ricetta (`rstool.py audio sf2-compose`): base GM libera
  (licenza MIT) + ottoni e timpani da un banco orchestrale libero (CC Sampling Plus / CC BY:
  autore nei crediti), slot 59 e 79 corretti (usati nel gioco solo dai programmi sbagliati),
  modulatore velocità→attenuazione -480 cB, sala con coda ~3 s nelle impostazioni del motore.
  Risultato: sotto 250 Hz dal 4% al 21%, nota dominante scesa di due ottave come nel
  riferimento. Variante leggera sf3 (~40 MB) per web/telefono con le sole correzioni.
- Misure con `audio midi-diagnose` (canali, programmi, curva) e `audio bands` (bande, baricentro,
  ottave gravi); livello vero misurato registrando il motore (driver audio su disco), poi
  `midi_gain` per stare ~7 dB sotto il parlato. Una curva più dolce alza il livello di 4-11 dB a
  pari guadagno. In ScummVM la larghezza del riverbero FluidSynth è divisa per 10 (gli altri
  parametri per 100).
- Bug corretti negli strumenti: clip < 400 ms misurate a -70 LUFS (ora guadagno unico misurato
  sulla concatenazione), `--rates` con un numero semplice, FluidSynth dato per assente quando
  c'era solo la libreria.
