# Manuale, guida agli indizi e provenienza dei file
## Manuale, guida agli indizi e provenienza dei file
- I PDF del manuale e della guida erano **solo immagini** (`pdftotext` 0 caratteri); tesseract a
  250 dpi dava un testo quasi pulito: `rstool.py manual ocr <pdf> --out <cartella>`. Una guida agli
  indizi a domande progressive è la fonte migliore per la struttura a livelli degli aiuti.
- Tra i file forniti c'era un collegamento a un sito di redistribuzione: `engine detect` ora
  segnala i collegamenti a siti di terze parti, e l'orchestratore chiede all'utente di confermare
  la provenienza dalla sua copia.
