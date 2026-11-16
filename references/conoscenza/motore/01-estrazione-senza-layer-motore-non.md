# Estrazione senza Layer (motore non ancora agganciato)
Il dump del Layer (`remaster_dump=`) esiste solo dopo l'aggancio del Layer al motore. Prima, per
l'analisi della Fase 1, si estrae con gli **strumenti open source di estrazione del motore**
(estrattori dei blocchi, dei testi con stanza e codice operativo, decompilatore degli script che
dà attore e riferimento della voce per ogni battuta) più un piccolo decodificatore in Python di
fondali e costumi (per un gioco 320x200 bastano qualche centinaio di righe per tutti i
codec). Regole:
- l'**adattatore** specifico del motore vive nel **repository privato** del gioco (script o
  comando); la suite ne fissa solo il contratto: `rstool.py engine extract --adapter <script>
  --game <cartella> --out analysis/dump` lo esegue (con `{game}` e `{out}` nel comando, o con
  `--game`/`--out` aggiunti) e valida il risultato; `rstool.py engine validate-dump <dump>`
  rifà il controllo su un dump scritto a mano;
- il **formato del dump** è quello del Layer, con i PNG ammessi (`tools/remaster_tools/extract.py`):
  `bg/<scena>.png` a misura originale, `bg/names.json` con i **nomi delle stanze dall'indice del
  gioco** (servono al classificatore 16:9: i nomi dei file del dump sono numeri), `spr/` PNG RGBA
  (più `spr/index.json` se ci sono solo dei campioni), `obj/`, `text.jsonl` (una riga per
  occorrenza, campo `hex` obbligatorio: i conteggi deduplicano sul testo), `voice-index.json`
  (con `lipsync` se la clip ha dati di movimento della bocca), `midi/*.mid`, `meta.json`;
- gli strumenti di estrazione si compilano spesso da sorgente: se lo script di configurazione
  rifiuta un'opzione (es. un `--disable-<libreria>` che non esiste), togli quelle inesistenti e
  disattiva solo le dipendenze facoltative davvero presenti (interfaccia grafica, boost, codec
  audio, PNG); se non c'è un target per il solo strumento che serve, compila quel target con
  `make <nome>` invece di tutto il pacchetto. Annota la riga di configurazione funzionante nel
  repository privato.
