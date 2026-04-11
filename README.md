# Golf Match Tracker Simple

Versione minimale con:
- SQLite locale
- frontend statico in `docs/`
- backend locale per import/export
- pubblicazione semplice su GitHub Pages

## Avvio locale frontend

```bash
python3 -m http.server 8081 -d docs
```

Apri `http://127.0.0.1:8081/`

## Inizializza il DB con dati demo

```bash
python3 backend/init_db.py --db data/golf_tracker.sqlite --seed-demo
```

## Rigenera le statistiche frontend

```bash
python3 backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
```

## Importa una partita JSON

```bash
python3 backend/import_match.py --db data/golf_tracker.sqlite --input /path/partita.json --export-docs docs
```

## Note importanti

- Il form "Nuova partita" precompila data e ora locali.
- Il JSON generato include un `import_key` univoco, così due partite identiche nei contenuti possono comunque essere importate come eventi distinti.
- Se provi a reimportare esattamente lo stesso file JSON, il backend lo riconosce e non duplica il record.
