# Golf Match Tracker

App statica per registrare partite di golf, salvare i dati in SQLite e pubblicare una dashboard con classifiche giocatori e squadre.

Il frontend vive in `docs/` ed è pensato per essere pubblicato con GitHub Pages. Il backend è composto da script Python che lavorano localmente sul database SQLite in `data/golf_tracker.sqlite`.

## Struttura progetto

```text
backend/
  common.py
  import_match.py
  export_stats.py
  delete_match.py
  rename_side.py
  rename_player.py
  init_db.py

data/
  golf_tracker.sqlite

docs/
  index.html              # dashboard / entry point GitHub Pages
  new-match/
    index.html
  data/
    stats.json
    match.schema.json
  assets/
    style.css
```

## Flusso operativo

1. Apri `docs/new-match/index.html` per creare una partita, oppure `docs/index.html` per vedere la dashboard.
2. Crea la partita e scarica il JSON generato.
3. Importa il JSON nel database SQLite.
4. Rigenera le statistiche statiche in `docs/data/`.
5. Pubblica/aggiorna il repository su GitHub: GitHub Pages leggerà i file aggiornati in `docs/`.

## Punteggio

Il sistema usa punteggio all'italiana:

- vittoria: 3 punti
- pareggio: 1 punto
- sconfitta: 0 punti

Nel JSON ogni side con `is_winner: true` è considerato un side a punto.

- Se un solo side ha `is_winner: true`, quel side vince e prende 3 punti.
- Se due o più side hanno `is_winner: true`, la partita è un pareggio e ciascuno di quei side prende 1 punto.
- I side con `is_winner: false` prendono 0 punti.

La regola vale sia per i giocatori sia per le squadre.

## Classifiche

### Classifica giocatori

La dashboard mostra:

- Giocatore
- Punti
- Partite giocate
- Vittorie
- Pareggi
- Sconfitte
- Win Rate

Il Win Rate è calcolato come:

```text
vittorie / partite giocate
```

I pareggi non contano come vittorie nel Win Rate, ma contano come partite giocate e assegnano 1 punto.

### Classifica squadre

La dashboard mostra:

- Squadra
- Punti
- Componenti
- Partite giocate
- Vittorie
- Pareggi
- Sconfitte
- Win Rate

Una squadra è identificata dalla stessa combinazione di giocatori.

### Filtro per anno

La dashboard genera automaticamente le classifiche per anno partendo dalle date delle partite (`played_at`).

Nel file `docs/data/stats.json` vengono salvati:

- i dati globali, compatibili con il formato precedente;
- `years`, con gli anni disponibili ordinati dal più recente;
- `views.all`, con la vista complessiva;
- `views.YYYY`, con classifiche, KPI e storico filtrati per singolo anno.

Il filtro `Anno` nella dashboard aggiorna insieme:

- classifica giocatori;
- classifica squadre;
- matrici Head2Head;
- dati aggregati;
- ultime partite.

### Matrici Head2Head

La dashboard include una sezione `Head2Head` con due matrici:

- `Head2Head - Player`
- `Head2Head - Team`

Ogni cella legge il confronto dal punto di vista della riga.

Formato `Record`:

```text
V-P-S
```

dove:

- `V` = vittorie della riga contro la colonna;
- `P` = pareggi;
- `S` = sconfitte.

Formato `Punti`:

```text
PF-PS
```

dove:

- `PF` = punti fatti dal soggetto della riga;
- `PS` = punti fatti dall'avversario in colonna.

Le matrici usano lo stesso filtro anno della dashboard. Il filtro `Min. partite` nasconde i confronti con meno partite del valore selezionato.

## Importare una partita

Dalla root del progetto:

```bash
python backend/import_match.py --db data/golf_tracker.sqlite --input golf-match.json --export-docs docs
```

L'opzione `--export-docs docs` rigenera `docs/data/stats.json` subito dopo l'import.

## Rigenerare le statistiche

```bash
python backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
```

Questo comando aggiorna:

- `docs/data/stats.json`
- `docs/data/match.schema.json`

Dopo avere rigenerato le statistiche, fai commit e push dei file aggiornati, in particolare:

```text
data/golf_tracker.sqlite
docs/data/stats.json
docs/data/match.schema.json
```

## Eliminare un match

L'eliminazione agisce direttamente sul database SQLite.

Puoi eliminare tramite ID match:

```bash
python backend/delete_match.py --db data/golf_tracker.sqlite --id 3 --export-docs docs
```

Oppure tramite `import_key`:

```bash
python backend/delete_match.py --db data/golf_tracker.sqlite --import-key match-abc123 --export-docs docs
```

L'opzione `--export-docs docs` rigenera la dashboard dopo l'eliminazione.

## Come trovare ID o import_key

Dalla dashboard, nella sezione `Ultime partite`, ogni match mostra:

- ID match
- `import_key`
- comando di eliminazione già pronto da copiare

In alternativa, puoi interrogare il database:

```bash
sqlite3 data/golf_tracker.sqlite "SELECT id, import_key, played_at, course, holes, notes FROM match ORDER BY played_at DESC;"
```

Se non hai `sqlite3` installato, puoi usare Python:

```bash
python -c "import sqlite3; con=sqlite3.connect('data/golf_tracker.sqlite'); cur=con.execute('SELECT id, import_key, played_at, course, holes, notes FROM match ORDER BY played_at DESC'); [print(row) for row in cur.fetchall()]"
```


## Rinominare una side/squadra

La rinomina agisce direttamente sul database SQLite e aggiorna tutte le side/team con lo stesso nome.

Esempio:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "Team A" --to "I Ferri Corti" --export-docs docs
```

Per controllare prima quali side verrebbero aggiornate senza modificare il database:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "Team A" --to "I Ferri Corti" --dry-run
```

Per cercare il nome ignorando maiuscole/minuscole:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "team a" --to "I Ferri Corti" --case-insensitive --export-docs docs
```

L'opzione `--export-docs docs` rigenera la dashboard dopo la rinomina.

## Rinominare un player

La rinomina agisce direttamente sul database SQLite e aggiorna tutte le occorrenze del player in `match_player.player_name`.

Esempio:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "Mario R." --to "Mario Rossi" --export-docs docs
```

Per controllare prima quali occorrenze verrebbero aggiornate senza modificare il database:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "Mario R." --to "Mario Rossi" --dry-run
```

Per cercare il nome ignorando maiuscole/minuscole:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "mario r." --to "Mario Rossi" --case-insensitive --export-docs docs
```

L'opzione `--export-docs docs` rigenera la dashboard dopo la rinomina.

Nota: i nomi player e i nomi side/team sono campi diversi, quindi non c'è conflitto tecnico tra un player e un team con lo stesso nome. La rinomina player viene pero bloccata se il nuovo nome è già presente nello stesso match, per evitare duplicati nella stessa partita.

## Modifica match

La modifica dei match è stata rimossa dal progetto.

Per correggere una partita già importata, il flusso consigliato è:

1. elimina il match errato;
2. crea/importa nuovamente il JSON corretto;
3. rigenera le statistiche.

## Pubblicazione con GitHub Pages

Il progetto è già organizzato per pubblicare il frontend dalla cartella `docs/`.

### 1. Crea il repository GitHub

Crea un nuovo repository, ad esempio:

```text
golf-match-tracker
```

Poi inizializza e carica il progetto:

```bash
git init
git add .
git commit -m "Initial golf tracker"
git branch -M main
git remote add origin https://github.com/TUO-USERNAME/golf-match-tracker.git
git push -u origin main
```

### 2. Abilita GitHub Pages

Su GitHub:

1. apri il repository;
2. vai in `Settings`;
3. nel menu laterale vai in `Pages`;
4. in `Build and deployment`, imposta `Source` su `Deploy from a branch`;
5. in `Branch`, seleziona:
   - branch: `main`
   - folder: `/docs`
6. clicca `Save`.

GitHub pubblicherà il sito partendo dalla cartella `docs/`.

### 3. URL della dashboard

Dopo l'attivazione, GitHub Pages pubblica il sito a un indirizzo simile a:

```text
https://TUO-USERNAME.github.io/golf-match-tracker/
```

Le pagine principali saranno:

```text
https://TUO-USERNAME.github.io/golf-match-tracker/
https://TUO-USERNAME.github.io/golf-match-tracker/new-match/
```


### 4. Aggiornare il sito dopo nuovi match

Ogni volta che importi, elimini o rinomini dati nel database:

```bash
python backend/import_match.py --db data/golf_tracker.sqlite --input golf-match.json --export-docs docs
```

oppure:

```bash
python backend/delete_match.py --db data/golf_tracker.sqlite --id 3 --export-docs docs
```

oppure:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "Team A" --to "I Ferri Corti" --export-docs docs
```

oppure:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "Mario R." --to "Mario Rossi" --export-docs docs
```

poi pubblica gli aggiornamenti:

```bash
git add data/golf_tracker.sqlite docs/data/stats.json docs/data/match.schema.json
git commit -m "Update golf stats"
git push
```

GitHub Pages si aggiornerà automaticamente dopo il push su `main`.

## Note importanti

- Il frontend è statico: non scrive direttamente sul database.
- Il database viene aggiornato solo dagli script Python in `backend/`.
- GitHub Pages pubblica il contenuto di `docs/`, ma non esegue gli script Python.
- Per questo motivo, dopo ogni import/eliminazione bisogna rigenerare `docs/data/stats.json` e fare push.
