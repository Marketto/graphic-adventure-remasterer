---
name: launcher-sync
description: Launcher a tema del remaster (desktop e mobile con una sola pagina), importazione dei file originali e salvataggi sincronizzati su Dropbox. Usala quando l'utente vuole un'app o una pagina per avviare il gioco o i salvataggi nel cloud.
---

# Launcher a tema e salvataggi nel cloud

Regole trasversali: `${CLAUDE_PLUGIN_ROOT}/references/regole-comuni.md`. Tecniche e motivi:
`${CLAUDE_PLUGIN_ROOT}/references/conoscenza/motore/22-launcher-e-salvataggi-cloud.md` (leggila prima di iniziare).

## Passi
1. **Una pagina, più contenitori**: la stessa interfaccia in Electron (desktop) e WebView (mobile), con un ponte nativo minimo. Le differenze si fanno con uno script di adattamento che si ferma se non trova le frasi.
2. **Tema** dallo `style-bible`: font del gioco, palette, pulsanti primario/secondario/pericolo, bersagli ≥ 44 px, *riduci movimento*. Tema dei menu del motore generato da script.
3. **Importazione** dei file originali in streaming (zip, volumi, ISO, 7z), "completo o niente", controllo dello spazio. Avviatore fisso con contratto versionato.
4. **Musica del launcher** solo da brani di pubblico dominio (arrangiati da MIDI), stesso livello, spegnibile.
5. **Salvataggi**: copia `tools/remaster_tools/templates/launcher/` (`merge.js`, `cloud-sync.js`) nel repository **privato**.
   - L'app Dropbox la crea l'utente: accesso *App folder*, permessi `files.content.read/write`, client pubblici.
   - L'app key va solo nel repository privato.
6. **Prove**: finto servizio con routing del browser, due contesti, conflitto, token scaduto, assenza di rete, nessun token nella console; `pytest tools/tests/test_launcher.py` per l'unione.
7. **Privacy**: sul sito pubblico solo il motore e la pagina di importazione; tema e grafica del gioco in un ramo privato.

## Da chiedere all'utente (una volta)
- Servizio cloud (Dropbox di predefinito) e se vuole l'app desktop, mobile o solo la pagina.
- Creazione dell'app nel servizio cloud: la fa lui, con la tua guida passo per passo. Le chiavi non passano mai dalla chat.
