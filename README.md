# Golf Match Tracker

App statica per registrare partite di golf, salvare lo storico in SQLite e pubblicare una dashboard con classifiche, media punti, Head2Head e Albo d'oro.

## Cosa contiene

```text
backend/                 script Python per database, import/export e manutenzione
data/golf_tracker.sqlite database locale, creato dall'utente
docs/                    frontend statico pubblicabile su GitHub Pages
  index.html             dashboard
  new-match/index.html   creazione match e download JSON
  data/stats.json        dati letti dalla dashboard
check.js                 controllo sintassi JavaScript
```

Non ci sono dipendenze frontend, build step o framework.

## Requisiti

- Python 3.10+
- browser moderno
- opzionale: Node.js per `node --check check.js`
- opzionale: `sqlite3` per ispezionare il database

## Avvio locale su localhost

Dalla root del progetto:

```bash
python -m http.server 8000 --directory docs
```

Apri:

```text
http://localhost:8000/
```

Pagina nuova partita:

```text
http://localhost:8000/new-match/
```

Usare `localhost` è consigliato rispetto al doppio click su `index.html`, perché il browser carica correttamente `docs/data/stats.json`.

## Primo setup

```bash
mkdir -p data
python backend/init_db.py --db data/golf_tracker.sqlite
python backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
```

## Flusso operativo

1. Avvia il server locale.
2. Vai su `/new-match/`.
3. Inserisci la partita e scarica il JSON.
4. Importa il match:

```bash
python backend/import_match.py --db data/golf_tracker.sqlite --input golf-match.json --export-docs docs
```

5. Ricarica la dashboard.
6. Se usi GitHub Pages, fai commit e push dei file aggiornati.

## Punteggio

| Risultato | Punti |
|---|---:|
| Vittoria | 3 |
| Pareggio | 1 |
| Sconfitta | 0 |

Nel JSON ogni side con:

```json
"is_winner": true
```

è considerato vincente. Se più side hanno `is_winner: true`, la partita è un pareggio e ciascun side prende 1 punto.

## Media punti

La media punti misura quanti punti produce in media un giocatore o team per ogni partita giocata:

```text
media punti = punti / partite giocate
```

Esempio: 12 punti in 6 partite = media punti 2.00.

È diverso dai punti totali: i punti premiano anche la partecipazione, mentre la media punti aiuta a confrontare chi ha giocato un numero diverso di partite. Per questo è la classifica predefinita e il criterio usato per decretare i leader dell’albo d’oro nelle viste generale, stagioni e competizioni/tag. Per i giocatori, nella classifica per media punti, servono almeno 7 partite: sotto soglia restano visibili in fondo ma sono esclusi dalla posizione.

## Classifiche e tie breaker

### Giocatori

La classifica giocatori include anche i punti ottenuti quando il giocatore partecipa a una partita a squadre.

Ordine:

1. punti totali;
2. vittorie totali;
3. media punti;
4. nome.

Gli scontri diretti non sono usati come tie breaker giocatori, perché nelle partite a squadre due giocatori possono essere compagni in un match e avversari in un altro.

### Squadre

Ordine:

1. punti totali;
2. punti negli scontri diretti tra team a pari punti;
3. vittorie negli scontri diretti tra team a pari punti;
4. vittorie totali;
5. media punti;
6. nome.

La colonna `TB` è in fondo alle tabelle e riassume lo spareggio solo quando serve.

Esempi:

```text
V 2 · Media 1.5
SD 3 · V 1 · Media 1.5
```

`SD` indica i punti negli scontri diretti tra team a pari punti.

## Head2Head

La sezione Head2Head ha due modalità:

- **Confronta due**: scegli due giocatori o due team e leggi il riepilogo diretto. È la modalità principale su mobile.
- **Vista completa**: matrice disponibile su desktop. Ogni cella si legge dal punto di vista della riga e mostra:

```text
V-P-S
PF-PS
```

Dove `V` = vittorie, `P` = pareggi, `S` = sconfitte, `PF` = punti fatti, `PS` = punti subiti.

Note di calcolo:

- Head2Head Player considera solo partite individuali 1 contro 1.
- I punti ottenuti in squadra valgono nella classifica giocatori, ma non entrano nell'Head2Head Player.
- Head2Head Team considera side composti da almeno due giocatori.

## Albo d'oro

L'Albo d'oro legge, per ogni anno presente in `stats.json`, il leader annuale di:

- classifica giocatori;
- classifica squadre.

L'anno corrente è marcato `Ongoing`: mostra il leader provvisorio, non un vincitore definitivo. Gli anni passati sono marcati `Finale`.

## Storico partite

Lo storico è collassabile e si apre con click. Mostra le ultime partite, ID/import key e il comando pronto per eliminare un match.

## Comandi utili

Rigenerare statistiche:

```bash
python backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
```

Eliminare un match:

```bash
python backend/delete_match.py --db data/golf_tracker.sqlite --id 3 --export-docs docs
```

Rinominare una squadra/side:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "Team A" --to "I Ferri Corti" --export-docs docs
```

Rinominare un giocatore:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "Mario R." --to "Mario Rossi" --export-docs docs
```

Anteprima senza modifiche:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "Mario R." --to "Mario Rossi" --dry-run
```

## Correggere un match

La modifica diretta di un match non è prevista. Flusso consigliato:

1. elimina il match errato;
2. crea un nuovo JSON corretto;
3. importa il nuovo JSON con `--export-docs`.

## Pubblicazione GitHub Pages

Il frontend è nella cartella `docs/`.

Su GitHub abilita:

```text
Settings -> Pages -> Deploy from a branch -> main / docs
```

Dopo ogni modifica dati, pubblica almeno:

```bash
git add data/golf_tracker.sqlite docs/data/stats.json docs/data/match.schema.json
git commit -m "Update golf stats"
git push
```

## Controlli

```bash
node --check check.js
python -m compileall backend
```

## Note

- Il frontend è statico e non scrive nel database.
- Il database viene aggiornato solo dagli script Python.
- GitHub Pages non esegue Python: dopo import, eliminazioni o rinomine bisogna rigenerare `docs/data/stats.json`.
- Il restyling è solo CSS: nessuna libreria aggiunta.
