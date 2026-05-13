# Golf Match Tracker

Golf Match Tracker è una piccola app statica per registrare partite di golf, salvare lo storico in SQLite e pubblicare una dashboard con classifiche, statistiche e confronti Head2Head.

Il progetto è pensato per due utilizzi:

- **in locale**, tramite `localhost`, per consultare e testare l'app;
- **online**, tramite GitHub Pages, pubblicando la cartella `docs/`.

## Funzionalità principali

- Creazione di una nuova partita da interfaccia web.
- Download del JSON della partita.
- Import del match in SQLite tramite script Python.
- Dashboard statica con:
  - KPI generali;
  - classifica giocatori con tie breaker;
  - classifica squadre con tie breaker;
  - filtro per anno;
  - albo d'oro annuale con stato ongoing per la stagione in corso;
  - storico partite collassabile;
  - Head2Head Player;
  - Head2Head Team.
- Vista Head2Head responsive:
  - confronto diretto “Confronta due”;
  - vista completa su desktop;
  - card di confronto su mobile.
- Script di manutenzione per:
  - importare match;
  - esportare statistiche;
  - eliminare match;
  - rinominare squadre/side;
  - rinominare giocatori.

## Struttura progetto

```text
backend/
  common.py
  init_db.py
  import_match.py
  export_stats.py
  delete_match.py
  rename_side.py
  rename_player.py

# opzionale, creata localmente
data/
  golf_tracker.sqlite

docs/
  index.html              # dashboard
  new-match/
    index.html            # creazione nuovo match
  data/
    stats.json            # dati statici letti dalla dashboard
    match.schema.json
  assets/
    style.css

check.js                  # controllo sintassi JS
README.md
```

## Requisiti

- Python 3.10 o superiore.
- Un browser moderno.
- Opzionale: `sqlite3`, utile solo per ispezionare il database da terminale.

Non servono dipendenze frontend, framework o build step.

## Avvio in locale su localhost

Dalla root del progetto, avvia un server statico puntando alla cartella `docs/`:

```bash
python -m http.server 8000 --directory docs
```

Poi apri nel browser:

```text
http://localhost:8000/
```

Per creare una nuova partita:

```text
http://localhost:8000/new-match/
```

Per fermare il server, torna nel terminale e premi `CTRL+C`.

### Perché usare localhost invece di aprire i file direttamente

Puoi aprire anche `docs/index.html` con doppio click, ma è meglio usare `localhost` perché il browser gestisce in modo più corretto il caricamento di file JSON come `docs/data/stats.json`.

## Primo setup del database

Se non esiste ancora il database, crealo con:

```bash
mkdir -p data
python backend/init_db.py --db data/golf_tracker.sqlite
```

Poi genera i file statici della dashboard:

```bash
python backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
```

## Flusso operativo consigliato

1. Avvia l'app in locale:

   ```bash
   python -m http.server 8000 --directory docs
   ```

2. Apri la pagina di creazione match:

   ```text
   http://localhost:8000/new-match/
   ```

3. Inserisci la partita e scarica il file JSON.

4. Importa il JSON nel database:

   ```bash
   python backend/import_match.py --db data/golf_tracker.sqlite --input golf-match.json --export-docs docs
   ```

5. Ricarica la dashboard locale:

   ```text
   http://localhost:8000/
   ```

6. Se pubblichi su GitHub Pages, fai commit e push dei file aggiornati.

## Punteggio

Il sistema usa il punteggio all'italiana:

| Risultato | Punti |
|---|---:|
| Vittoria | 3 |
| Pareggio | 1 |
| Sconfitta | 0 |

Nel JSON ogni side con:

```json
"is_winner": true
```

è considerato un side a punto.

Regole:

- se un solo side ha `is_winner: true`, quel side vince e prende 3 punti;
- se due o più side hanno `is_winner: true`, la partita è un pareggio e ciascuno prende 1 punto;
- i side con `is_winner: false` prendono 0 punti.

La regola vale sia per giocatori singoli sia per squadre.

## Dashboard

La dashboard principale si trova in:

```text
docs/index.html
```

Legge i dati da:

```text
docs/data/stats.json
```

Mostra:

- riepilogo generale;
- classifiche giocatori e squadre;
- filtro per anno;
- albo d'oro annuale;
- ultime partite;
- Head2Head Player e Team.

## Albo d'oro

La scheda `Albo d'oro` mostra, per ogni anno disponibile in `docs/data/stats.json`, il leader annuale di:

- classifica giocatori;
- classifica squadre.

Il vincitore viene letto dalla prima posizione della classifica annuale gia ordinata con i tie breaker. Per l'anno corrente la card non proclama un vincitore definitivo: mostra il leader provvisorio con stato `Ongoing` e overlay grigio.

Ogni riga dell'albo mostra:

- punti;
- record vittorie, pareggi, sconfitte;
- rendimento.

## Head2Head

La sezione Head2Head è pensata per restare consultabile anche quando aumentano giocatori e squadre.

### Confronta due

La modalità principale è `Confronta due`:

- scegli il primo giocatore o team;
- scegli l'avversario;
- la card mostra partite, record, punti e rendimento di entrambi.

Il valore dei punti è sempre mostrato come:

```text
Punti primo selezionato - punti avversario
```

Esempio: se scegli `Lele` contro `Ale P`, la card spiega il confronto dal punto di vista di `Lele` e mostra anche il record inverso di `Ale P`.

Su mobile questa è la vista principale: non c'è il concetto di riga della vista completa, quindi la lettura è esplicita e legata ai due soggetti selezionati.

### Desktop

Su schermi grandi resta disponibile anche la vista completa:

- righe = soggetto;
- colonne = avversario;
- ogni cella mostra entrambi i formati del confronto.

Nella vista completa il valore è sempre letto dal punto di vista della riga.

Ogni cella è composta da due righe:

```text
V-P-S
PF-PS
```

Dove:

- `V` = vittorie;
- `P` = pareggi;
- `S` = sconfitte;
- `PF` = punti fatti;
- `PS` = punti subiti.

Non ci sono più selettori per formato o minimo partite: la vista desktop mostra direttamente tutte le informazioni disponibili in una sola tabella.

### Mobile

Su mobile la vista completa viene nascosta e rimane solo la card `Confronta due`. Questa vista evita lo scroll orizzontale e rimane leggibile anche con molti giocatori o team.

### Criteri di calcolo

`Head2Head - Player` considera solo partite individuali 1 contro 1, cioè match con due side e un solo giocatore per side.

I punti ottenuti in squadra continuano a valere nella classifica giocatori, ma non entrano nella tabella Head2Head Player.

`Head2Head - Team` considera i confronti tra side composti da almeno due giocatori.

## Classifiche

### Giocatori

La classifica giocatori mostra:

- giocatore;
- punti;
- partite;
- vittorie;
- pareggi;
- sconfitte;
- rendimento.

Il rendimento è calcolato come:

```text
punti / partite giocate
```

Questo valore tiene conto anche dei pareggi, perché usa gli stessi punti della classifica: vittoria = 3, pareggio = 1, sconfitta = 0.

I punti ottenuti in squadra vengono attribuiti a ogni componente del team anche nella classifica giocatori. Per questo motivo gli scontri diretti non sono usati come tie breaker tra giocatori: in un match a squadre due giocatori possono essere avversari in una partita e compagni in un'altra.

### Tie breaker

La classifica giocatori è ordinata con questi criteri:

1. punti totali;
2. vittorie totali;
3. rendimento;
4. nome, come ultimo ordinamento stabile.

La classifica squadre è ordinata con questi criteri:

1. punti totali;
2. punti negli scontri diretti tra team con pari punti;
3. vittorie negli scontri diretti tra team con pari punti;
4. vittorie totali;
5. rendimento;
6. nome, come ultimo ordinamento stabile.

Nelle tabelle la colonna `TB` riassume lo spareggio solo quando esiste una parità di punti.

Per i giocatori il formato è:

```text
V 2 · Rend 1.5
```

Per le squadre il formato include anche gli scontri diretti:

```text
SD 3 · V 1 · Rend 1.5
```

Dove `SD` indica i punti ottenuti negli scontri diretti contro gli altri team con pari punti. Se non c'è parità di punti, il valore è `-`.

### Squadre

La classifica squadre mostra:

- squadra;
- componenti;
- punti;
- partite;
- vittorie;
- pareggi;
- sconfitte;
- rendimento.

Una squadra viene identificata dalla combinazione dei suoi giocatori.

## Filtro per anno

Le statistiche vengono esportate in viste multiple dentro `docs/data/stats.json`:

```json
{
  "years": ["2026"],
  "views": {
    "all": {},
    "2026": {}
  }
}
```

Il filtro anno aggiorna insieme:

- KPI;
- classifiche;
- Head2Head;
- ultime partite.

## Importare una partita

Dalla root del progetto:

```bash
python backend/import_match.py --db data/golf_tracker.sqlite --input golf-match.json --export-docs docs
```

L'opzione `--export-docs docs` rigenera subito:

```text
docs/data/stats.json
docs/data/match.schema.json
```

## Rigenerare le statistiche

Quando vuoi aggiornare solo i file statici della dashboard:

```bash
python backend/export_stats.py --db data/golf_tracker.sqlite --docs docs
```

## Eliminare un match

Per eliminare un match tramite ID:

```bash
python backend/delete_match.py --db data/golf_tracker.sqlite --id 3 --export-docs docs
```

Per eliminarlo tramite `import_key`:

```bash
python backend/delete_match.py --db data/golf_tracker.sqlite --import-key match-abc123 --export-docs docs
```

La dashboard mostra ID, `import_key` e comando pronto nella sezione `Ultime partite`.

## Trovare ID e import_key

Con `sqlite3`:

```bash
sqlite3 data/golf_tracker.sqlite "SELECT id, import_key, played_at, course, holes, notes FROM match ORDER BY played_at DESC;"
```

Senza `sqlite3`, usando Python:

```bash
python -c "import sqlite3; con=sqlite3.connect('data/golf_tracker.sqlite'); cur=con.execute('SELECT id, import_key, played_at, course, holes, notes FROM match ORDER BY played_at DESC'); [print(row) for row in cur.fetchall()]"
```

## Rinominare una squadra o side

Esempio:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "Team A" --to "I Ferri Corti" --export-docs docs
```

Anteprima senza modificare il database:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "Team A" --to "I Ferri Corti" --dry-run
```

Ricerca ignorando maiuscole e minuscole:

```bash
python backend/rename_side.py --db data/golf_tracker.sqlite --from "team a" --to "I Ferri Corti" --case-insensitive --export-docs docs
```

## Rinominare un giocatore

Esempio:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "Mario R." --to "Mario Rossi" --export-docs docs
```

Anteprima senza modificare il database:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "Mario R." --to "Mario Rossi" --dry-run
```

Ricerca ignorando maiuscole e minuscole:

```bash
python backend/rename_player.py --db data/golf_tracker.sqlite --from "mario r." --to "Mario Rossi" --case-insensitive --export-docs docs
```

Nota: i nomi dei giocatori e i nomi delle side/team sono campi diversi. La rinomina giocatore viene però bloccata se il nuovo nome è già presente nello stesso match, per evitare duplicati nella stessa partita.

## Correggere un match

La modifica diretta dei match non è prevista.

Flusso consigliato:

1. elimina il match errato;
2. crea un nuovo JSON corretto;
3. importa il nuovo JSON;
4. rigenera le statistiche, se non hai usato `--export-docs`.

## Pubblicazione con GitHub Pages

Il progetto è già organizzato per pubblicare il frontend dalla cartella `docs/`.

### 1. Crea il repository

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
3. vai in `Pages`;
4. imposta `Source` su `Deploy from a branch`;
5. seleziona branch `main` e cartella `/docs`;
6. salva.

La dashboard sarà disponibile a un indirizzo simile a:

```text
https://TUO-USERNAME.github.io/golf-match-tracker/
```

La pagina per creare match sarà:

```text
https://TUO-USERNAME.github.io/golf-match-tracker/new-match/
```

## Aggiornare il sito dopo nuovi dati

Dopo import, eliminazione o rinomina, assicurati che siano aggiornati:

```text
data/golf_tracker.sqlite
docs/data/stats.json
docs/data/match.schema.json
```

Poi pubblica:

```bash
git add data/golf_tracker.sqlite docs/data/stats.json docs/data/match.schema.json
git commit -m "Update golf stats"
git push
```

GitHub Pages si aggiornerà automaticamente dopo il push.

## Controlli utili

Controllo sintassi JavaScript:

```bash
node --check check.js
```

Controllo sintassi Python:

```bash
python -m compileall backend
```

## Note importanti

- Il frontend è statico e non scrive direttamente nel database.
- Il database viene aggiornato solo dagli script Python in `backend/`.
- GitHub Pages pubblica i file in `docs/`, ma non esegue script Python.
- Dopo ogni modifica ai dati bisogna rigenerare `docs/data/stats.json`.
- In locale usa `localhost` per testare correttamente il caricamento dei file JSON.
