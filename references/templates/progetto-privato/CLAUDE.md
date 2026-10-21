# Istruzioni per agenti AI — <TITOLO> HD (repository privato)

Progetto: rendere *<TITOLO>* giocabile e rimasterizzato su un fork di ScummVM.
Lingua di lavoro con l'utente: italiano. L'utente può lavorare dal telefono.
Creato con graphic-adventure-remasterer: le regole generali sono nelle sue skill.

## Regole
- **Chiusura del lavoro**: ogni lavoro completato si chiude con la skill `chiusura-lavoro`
  (documentazione, commit, push, PR verso `main`; mai commit diretti su `main`). L'hook Stop
  `.claude/hooks/lavoro-in-sospeso.sh` segnala modifiche non committate o non inviate.
- **Dati del gioco** e tutto ciò che ne deriva (asset, sprite, testi, voci, script) restano
  privati: niente Pages, artifact pubblici, gist, Release di repo pubblici. Il sito pubblico
  contiene solo il motore e la pagina di importazione.
- **Motore e contenuto separati**: il motore offre meccanismi generici; le correzioni di
  contenuto stanno nei file della patch (`assets/patch/...`). Mai modificare i file originali.
- **Stile del gioco**: <stilizzazioni da preservare, es. alfabeti finti, gag volute nei testi>.
- **Spese** (voci, immagini generative...): solo dopo approvazione esplicita con preventivo;
  le stime gratuite si possono fare. Registra speso e rimasto.
- **Voci**: una voce per personaggio, sempre con le stesse impostazioni (`docs/voci.md`).
- Motore = patch git in `engine/patches/` sul commit di `engine/SCUMMVM_COMMIT`.

## Router: richiesta → procedura
| Richiesta | Skill | Agente |
|---|---|---|
| Bug giocando (crash, input, dialoghi, script bloccati, audio) | `bug-gioco` → integrazione nel motore | motore |
| Rendering HD/16:9, opzioni del motore | `engine-integration` | motore |
| Fondali, bande 16:9, insegne, upscaler, costi | `hd-graphics`, `widescreen` | grafica |
| Voci, testi | `voice-dubbing`, `localization` | voci-testi |
| Pacchetto e versione `patch-N` | `build-release` | — |
| Fine di qualunque lavoro | `chiusura-lavoro` | `revisore` |
Problemi indipendenti: un agente per area in parallelo; gli agenti non committano, chi coordina
integra, documenta e chiude.

## Mappa
`docs/architettura.md`, `docs/formati.md`, `docs/build.md`, `docs/rilascio.md`,
`docs/strumenti.md`, `docs/test.md`, `docs/censimento-voci.md`, `docs/voci.md`, `docs/stato.md`
(fatto, in verifica, da fare, decisioni prese con l'utente con la data).
