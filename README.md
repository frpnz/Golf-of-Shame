# Golf Match Tracker

Applicazione statica per registrare partite di golf, importarle in un database SQLite locale e pubblicare statistiche aggregate in formato JSON per la dashboard.

Il progetto e composto da:

- `docs/`: frontend statico pubblicabile, per esempio su GitHub Pages.
- `docs/new-match/`: pagina per generare il JSON di una nuova partita.
- `docs/dashboard/`: dashboard statistiche basata su `docs/data/stats.json`.
- `backend/`: script Python per inizializzare DB, importare partite, esportare statistiche ed eliminare match.
- `data/golf_tracker.sqlite`: database SQLite locale.

## Funzionalita

- Creazione di una nuova partita da interfaccia web statica.
- Supporto a partite individuali e a squadre.
- Supporto a vittoria secca e pareggio.
- Import offline dei match in SQLite.
- Export delle statistiche in JSON per la dashboard.
- Classifiche per player e per team.
- Storico partite.
- Eliminazione di un match direttamente dal database.

## Regole punteggio

Il punteggio usa una logica all'italiana:

- **Vittoria secca**: un solo side marcato con `is_winner: true` riceve **3 punti**.
- **Pareggio**: due o piu side marcati con `is_winner: true` ricevono **1 punto ciascuno**.
- **Sconfitta**: side non marcati con `is_winner: true` ricevono **0 punti**.

La regola vale sia per i side individuali sia per i team.

Esempio individuale:

```json
{
  "sides": [
    { "players": ["Mario"], "is_winner": true },
    { "players": ["Luca"], "is_winner": false }
  ]
}
```

Risultato:

- Mario: 3 punti
- Luca: 0 punti

Esempio pareggio:

```json
{
  "sides": [
    { "players": ["Mario"], "is_winner": true },
    { "players": ["Luca"], "is_winner": true }
  ]
}
```

Risultato:

- Mario: 1 punto
- Luca: 1 punto

## Formato JSON partita

La pagina `docs/new-match/index.html` genera un file JSON compatibile con il backend.

Formato minimo:

```json
{
  "version": "golf-match.v1",
  "import_key": "match-unique-key",
  "played_at": "2026-05-12T10:00",
  "course": "Nome campo",
  "holes": 18,
  "notes": "Note opzionali",
  "sides": [
    {
      "team_name": "Team A",
      "is_winner": true,
      "players": ["Mario", "Luca"]
    },
    {
      "team_name": "Team B",
      "is_winner": false,
      "players": ["Anna", "Paolo"]
    }
  ]
}
```

Campi principali:

- `version`: versione del formato, attualmente `golf-match.v1`.
- `import_key`: chiave univoca usata per evitare import duplicati.
- `played_at`: data e ora della partita.
- `course`: campo da golf.
- `holes`: numero buche.
- `notes`: note libere.
- `sides`: elenco dei side individuali o dei team.
- `team_name`: nome del team, opzionale per partite individuali.
- `is_winner`: indica se il side riceve punti.
- `players`: giocatori del side.

Deve esserci almeno un side con `is_winner: true`.

## Inizializzazione database

Crea lo schema SQLite:

```bash
python backend/init_db.py --db data/golf_tracker.sqlite
```

Con dati demo:

```bash
python backend/init_db.py --db data/golf_tracker.sqlite --seed-demo
```

## Import di una partita

Importa un file JSON nel database:

```bash
python backend/import_match.py --db data/golf_tracker.sqlite --input golf-match.json
```

Importa e rigenera subito i dati della dashboard:

```bash
python backend/import_match.py --db data/golf_tracker.sqlite --input golf-match.json --export-docs docs
```

Se una partita con lo stesso `import_key` esiste gia, non viene duplicata.

## Export statistiche

Rigenera `docs/data/stats.json` e `docs/data/match.schema.json`:

```bash
python backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
```

Il file `stats.json` alimenta la dashboard statica.

## Eliminazione match

La cancellazione agisce direttamente sul database SQLite.

```bash
python backend/delete_match.py --db data/golf_tracker.sqlite --id 3 --export-docs docs
```

Se il match non viene trovato, lo script termina con messaggio:

```text
Nessuna partita trovata con il criterio indicato
```

## Struttura database

Il database contiene tre tabelle principali:

- `match`: informazioni generali della partita.
- `match_side`: side o team associati alla partita.
- `match_player`: giocatori associati a ogni side.

La relazione e:

```text
match
  -> match_side
      -> match_player
```

L'eliminazione di un match rimuove anche i side e i player collegati.

## Dashboard

La dashboard legge `docs/data/stats.json` e mostra:

- totale partite;
- numero giocatori;
- numero team;
- ultima partita;
- classifica player per punti;
- classifica team per punti;
- punti per partita;
- storico match;
- indicazione dei pareggi quando piu side ricevono punti.

## Note operative

Flusso tipico:

1. Crea una partita da `docs/new-match/index.html`.
2. Scarica il JSON generato.
3. Importa il JSON nel DB con `backend/import_match.py`.
4. Rigenera le statistiche con `--export-docs docs` oppure con `backend/export_stats.py`.
5. Apri la dashboard statica in `docs/dashboard/index.html`.
