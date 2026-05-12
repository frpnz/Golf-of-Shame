
    function pointsValue(value) {
      return value == null ? '-' : Number(value).toFixed(2).replace(/\.00$/, '');
    }

    function pctValue(value) {
      if (value == null) return '-';
      return (Number(value) * 100).toFixed(1).replace(/\.0$/, '') + '%';
    }

    function niceDate(value) {
      if (!value) return '-';
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return value;
      return d.toLocaleString('it-IT', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }

    function deleteCommand(match) {
      if (match && match.id != null) {
        return 'python backend/delete_match.py --db data/golf_tracker.sqlite --id ' + match.id + ' --export-docs docs';
      }
      if (match && match.import_key) {
        return 'python backend/delete_match.py --db data/golf_tracker.sqlite --import-key "' + String(match.import_key).replace(/"/g, '\"') + '" --export-docs docs';
      }
      return 'ID/import_key non disponibile: rigenera docs/data/stats.json con export_stats.py';
    }

    function table(el, headers, rows) {
      el.innerHTML = '';
      const thead = document.createElement('thead');
      const trh = document.createElement('tr');
      headers.forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        trh.appendChild(th);
      });
      thead.appendChild(trh);
      const tbody = document.createElement('tbody');
      rows.forEach(row => {
        const tr = document.createElement('tr');
        row.forEach((cell, index) => {
          const td = document.createElement('td');
          td.textContent = cell;
          td.dataset.label = headers[index];
          if (index > 0) td.className = 'num';
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      el.appendChild(thead);
      el.appendChild(tbody);
    }

    function renderMatches(data) {
      const container = document.getElementById('matches');
      const limitValue = document.getElementById('matches_limit').value;
      const limit = limitValue === 'all' ? data.matches.length : Number(limitValue);
      const rows = data.matches.slice(0, limit);
      container.innerHTML = '';
      if (!rows.length) {
        container.innerHTML = '<p class="small">Nessuna partita disponibile.</p>';
        return;
      }
      rows.forEach(match => {
        const item = document.createElement('article');
        item.className = 'match-item';

        const meta = document.createElement('div');
        meta.className = 'match-meta';
        const sideCount = match.sides.length;
        meta.innerHTML = '<span class="match-id">ID #' + (match.id ?? 'n/d') + '</span>' +
          '<span class="match-dot">•</span>' +
          '<span class="match-date">' + niceDate(match.played_at) + '</span>' +
          '<span class="match-dot">•</span>' +
          '<span>' + (match.course || 'Campo n/d') + '</span>' +
          '<span class="match-dot">•</span>' +
          '<span>' + (match.holes || '-') + ' buche</span>' +
          '<span class="match-dot">•</span>' +
          '<span>' + sideCount + ' side</span>' +
          (match.is_draw ? '<span class="match-dot">•</span><span>Pareggio</span>' : '');

        const body = document.createElement('div');
        body.className = 'match-sides';

        match.sides.forEach(side => {
          const row = document.createElement('div');
          row.className = 'match-side' + (side.is_winner ? ' is-winner' : '');
          const label = side.team_name || side.players.join('-');
          row.innerHTML =
            '<span class="result-badge ' + (side.is_winner ? 'winner' : 'loser') + '">' + (side.is_winner ? (match.is_draw ? '1 punto' : '3 punti') : '0 punti') + '</span>' +
            '<div class="match-side-text">' +
              '<strong>' + label + '</strong>' +
              '<span>' + side.players.join(' + ') + '</span>' +
            '</div>';
          body.appendChild(row);
        });

        item.appendChild(meta);
        item.appendChild(body);

        const admin = document.createElement('details');
        admin.className = 'match-admin';
        const summary = document.createElement('summary');
        summary.textContent = 'Eliminazione match';
        const importKey = document.createElement('p');
        importKey.className = 'small match-import-key';
        importKey.textContent = 'Import key: ' + (match.import_key || 'n/d');
        const pre = document.createElement('pre');
        pre.className = 'delete-command';
        pre.textContent = deleteCommand(match);
        admin.appendChild(summary);
        admin.appendChild(importKey);
        admin.appendChild(pre);
        item.appendChild(admin);

        if (match.notes) {
          const notes = document.createElement('p');
          notes.className = 'match-notes';
          notes.textContent = match.notes;
          item.appendChild(notes);
        }

        container.appendChild(item);
      });
    }

    fetch('../data/stats.json')
      .then(r => r.json())
      .then(data => {
        window.__statsData = data;

        document.getElementById('updated-at').textContent = 'Aggiornato: ' + niceDate(data.generated_at || data.generated_utc || data.generated || '');
        document.getElementById('kpi-matches').textContent = data.counts.matches;
        document.getElementById('kpi-players').textContent = data.counts.players;
        document.getElementById('kpi-teams').textContent = data.counts.teams;
        document.getElementById('kpi-latest').textContent = data.matches.length ? niceDate(data.matches[0].played_at) : '-';
        document.getElementById('players-count').textContent = data.by_player.length + ' player';
        document.getElementById('teams-count').textContent = data.by_team.length + ' team';

        table(
          document.getElementById('players'),
          ['Giocatore', 'Partite giocate', 'Vittorie', 'Pareggi', 'Sconfitte', 'Punti', 'Win Rate'],
          data.by_player.map(x => [x.player, x.games, x.wins || 0, x.draws || 0, x.losses || 0, x.points || 0, pctValue(x.winrate || 0)])
        );

        table(
          document.getElementById('teams'),
          ['Squadra', 'Componenti', 'Partite giocate', 'Vittorie', 'Pareggi', 'Sconfitte', 'Punti', 'Win Rate'],
          data.by_team.map(x => [x.team_name || x.team_label, x.team_label, x.games, x.wins || 0, x.draws || 0, x.losses || 0, x.points || 0, pctValue(x.winrate || 0)])
        );

        renderMatches(data);
        document.getElementById('matches_limit').addEventListener('change', function () {
          renderMatches(window.__statsData);
        });
      })
      .catch(err => {
        document.getElementById('updated-at').textContent = 'Impossibile leggere i dati';
        console.error(err);
      });
  