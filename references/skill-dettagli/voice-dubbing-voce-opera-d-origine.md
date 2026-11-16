# 2b. Voce simile all'opera d'origine (solo personaggi con `imitate_voice` true)

Dettaglio della skill `voice-dubbing`.

Vale solo se il doppiaggio è scelto e l'utente ha detto sì per quel personaggio
(`source_work.characters` in `remaster.json`, vedi `style-bible` §1b). Riferimento: nella lingua
originale l'interprete, nelle altre il doppiatore dell'edizione dell'epoca del gioco.
**Paletti fissi** (nessuna eccezione, neanche se l'utente la chiede per comodità):
- **nessuna clonazione**, né istantanea né professionale, da quel materiale;
- i frammenti **non si caricano mai** su ElevenLabs o su altri servizi (niente trascrizione,
  speech-to-speech, isolamento della voce in cloud): restano in locale, nella cartella di lavoro
  privata, e **si cancellano dopo la misura** (`--delete-after`);
- nessun nome di persona reale nel nome della voce, in `cast.json` o nei crediti come se fosse
  la sua voce; mai presentare la voce come quella della persona ("voce ispirata al
  personaggio", non "voce di <nome>");
- per la distribuzione pubblica vale la nota sulla somiglianza in
  `references/legal-distribution.md`.
Procedura:
1. **Materiale di riferimento** (lo cerchi tu): trailer, spot e clip ufficiali dello stesso
   periodo dell'opera, nella lingua o nelle lingue target; fonti ufficiali prima (canali dello
   studio o del distributore, edizioni home video). Annota le fonti (link, intervalli) solo nel
   progetto privato.
   - **Requisiti**: `ffmpeg`; per le piattaforme video `yt-dlp` recente con un runtime JS
     (`--js-runtimes node` più il pacchetto `yt-dlp-ejs`): senza, i metadati arrivano ma gli
     stream rispondono 403. Scarica solo l'audio (`-x`).
   - **Gli ambienti cloud vengono spesso bloccati** dalle piattaforme video (403, poi 429 e la
     verifica "non sono un bot"). **Al massimo 2 tentativi per piattaforma**, senza raffiche: il
     blocco peggiora. Poi prova le altre fonti consentite (un'altra piattaforma video, archivi
     pubblici, il sito del distributore) e infine chiedi all'utente di caricare lui l'audio
     nella cartella privata di lavoro: anche registrato dal telefono mentre il video suona (va
     bene per altezza e ritmo, meno per il timbro: dillo), oppure scaricato sul suo computer con
     un comando pronto da copiare, per esempio
     `yt-dlp -x --audio-format wav --js-runtimes node -o "rif-%(id)s.%(ext)s" "<link>"`
     (prima `pip install -U yt-dlp yt-dlp-ejs` e Node.js). In alternativa tutta la misura gira
     sul suo computer.
   - **Mai** cookie del browser, account o credenziali personali dell'utente per aggirare il
     blocco, neanche se li offre: si cambia fonte o si chiede il file.
   - **Verifica il doppiatore** dell'edizione dell'epoca con almeno una fonte (database del
     doppiaggio, crediti dell'edizione); senza fonte scrivi "da verificare" e non procedere con
     quel riferimento come se fosse certo. Si annota solo nel progetto privato
     (`source_work.characters`, con le fonti).
2. **Tratti del personaggio**: 3-6 pezzi puliti di 2-8 s del solo personaggio (niente musica,
   effetti o altre voci sopra). Con file lunghi (trailer, clip con più voci) non tagliare a mano:
   `rstool.py voice segments <audio...> --lang it --out voice/ref/segmenti.tsv --speakers 2`
   trascrive in locale (faster-whisper, `--model small` o `medium`) e raggruppa i parlanti con
   impronte vocali locali (resemblyzer se installato, con `setuptools<81`; altrimenti impronte
   semplici, più deboli: `--prints simple`). Il TSV ha id, file, inizio, fine, gruppo, sicurezza
   dell'attribuzione, testo. Con un numero noto di parlanti usa `--speakers N`: le impronte
   separano poco e la soglia (`--threshold`) va tarata. **Ascolta** 2-3 tratti per gruppo per
   capire qual è il personaggio e scarta quelli con musica sopra o a bassa sicurezza. Per un
   solo tratto di un file resta `--start`/`--end`.
3. **Misura** (solo numeri):
   `rstool.py voice reference <frammenti...> --out voice/ref/<personaggio>-<lingua>.json --gender male --age old --delete-after`
   oppure, dai tratti del TSV senza tagliare i file,
   `rstool.py voice reference --segments voice/ref/segmenti.tsv --group G1 --out voice/ref/<personaggio>-<lingua>.json --delete-after`
   (`--select 3,5-7` per scegliere le righe). → altezza media e variabilità (semitoni),
   brillantezza, pendenza e forma media dello spettro (12 MFCC fino a 4 kHz), ruvidità
   (rapporto armoniche/rumore), velocità d'eloquio, quota e durata delle pause, dinamica. Con
   `--segments` il JSON registra le fonti (file, intervalli, gruppo, sicurezza, mai il testo)
   per rifare o controllare la misura dopo aver cancellato l'audio. Genere ed età dichiarati
   servono al controllo dell'altezza (errori d'ottava).
4. **Candidati**: voci **esistenti** della libreria ElevenLabs coerenti con età, genere e lingua
   (connettore `creative_list_voices` o API della Voice Library), con le loro anteprime; salvale
   come `voices.json` (`voice_id`, `name`, `file` o `preview_url`, `gender` e `age` o le
   `labels` della libreria) o in una cartella. Misurale una volta sola, le misure si riusano tra
   personaggi e sessioni (le voci già misurate non si rimisurano):
   `rstool.py voice measure voices.json --out voice/ref/misure.json`
   poi
   `rstool.py voice match voice/ref/<...>.json --measured voice/ref/misure.json --top 5 --out voice/ref/<...>-shortlist.json`
   (oppure `--candidates voices.json` per misurare al volo). Ordina per distanza pesata (pesi
   in `tools/remaster_tools/voiceref.py`: altezza e timbro contano di più perché i parametri non
   li cambiano; velocità e pause di meno perché si correggono con `speed` e con la regia) e
   propone le impostazioni di partenza (`speed` dal rapporto delle velocità, stabilità più bassa
   e stile più alto se il riferimento è più mosso, note su timbro e pause). **Leggi gli avvisi**:
   anteprime con musica o senza pause (pesate meno su pause e ruvidità: ascoltale), altezza fuori
   dall'intervallo plausibile per genere ed età (possibile errore d'ottava o etichetta sbagliata),
   genere o età dichiarati diversi (`--strict` le esclude), meno di 5 candidate dell'età giusta
   (cercane altre prima di scegliere).
5. **Raffina** sulle 2-3 migliori: stability, similarity, style, speed (skill `voice-dubbing` §0 per i limiti) e
   **toni interpretativi** dal modo di recitare nei riferimenti (ritmo, ironia, pause, attacchi),
   annotati nella scheda del personaggio come guida per la regia per battuta (skill `voice-dubbing` §3), mai citando la persona.
6. **Provini** come nella skill `voice-dubbing` §2: 2-3 voci con una sola battuta vera (una addizionale solo per le voci
   in dubbio), sceglie l'utente; solo voci della
   libreria, nessuna voce progettata "a somiglianza" con Voice Design partendo dal materiale.
