
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
        return 'python backend/delete_match.py --db data/golf_tracker.sqlite --import-key "' + String(match.import_key).replace(/"/g, '\\"') + '" --export-docs docs';
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

    function getView(data, year) {
      const views = data.views || { all: data };
      return views[year] || views.all || data;
    }

    function selectedYearLabel(year) {
      return year === 'all' ? 'Tutti gli anni' : year;
    }

    function populateYearFilter(data) {
      const select = document.getElementById('season_filter');
      const years = Array.isArray(data.years) ? data.years : [];
      select.innerHTML = '<option value="all">Tutti gli anni</option>';
      years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        select.appendChild(option);
      });

      // Default: anno piu recente disponibile. Se non ci sono partite, resta "Tutti gli anni".
      select.value = years.length ? years[0] : 'all';
    }

    function renderMatches(view) {
      const container = document.getElementById('matches');
      const matches = view.matches || [];
      const limitValue = document.getElementById('matches_limit').value;
      const limit = limitValue === 'all' ? matches.length : Number(limitValue);
      const rows = matches.slice(0, limit);
      container.innerHTML = '';
      if (!rows.length) {
        container.innerHTML = '<p class="small">Nessuna partita disponibile per il periodo selezionato.</p>';
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



    function setActiveButton(selector, activeButton) {
      document.querySelectorAll(selector).forEach(button => {
        button.classList.toggle('active', button === activeButton);
      });
    }

    function currentMatrixType() {
      const select = document.getElementById('matrix_type');
      return select ? select.value : 'players';
    }

    function currentMatrixFormat() {
      const select = document.getElementById('matrix_format');
      return select ? select.value : 'record';
    }

    function h2hCellClass(entry) {
      if (!entry || !entry.games) return 'empty';
      if (entry.wins > entry.losses) return 'positive';
      if (entry.wins < entry.losses) return 'negative';
      return 'neutral';
    }

    function h2hCellText(entry, format) {
      if (!entry || !entry.games) return '·';
      if (format === 'points') {
        return String(entry.points_for || 0) + '-' + String(entry.points_against || 0);
      }
      return String(entry.wins || 0) + '-' + String(entry.draws || 0) + '-' + String(entry.losses || 0);
    }

    function h2hTitle(rowLabel, colLabel, entry) {
      if (!entry || !entry.games) return rowLabel + ' vs ' + colLabel + ': nessuna partita';
      return rowLabel + ' vs ' + colLabel + ': ' +
        entry.games + ' partite · ' +
        (entry.wins || 0) + ' vittorie · ' +
        (entry.draws || 0) + ' pareggi · ' +
        (entry.losses || 0) + ' sconfitte · punti ' +
        (entry.points_for || 0) + '-' + (entry.points_against || 0);
    }

    function h2hWinRate(entry) {
      if (!entry || !entry.games) return 0;
      return (entry.wins || 0) / entry.games;
    }

    function updateH2HSubjectOptions(labels) {
      const subjectSelect = document.getElementById('h2h_subject');
      if (!subjectSelect) return '';
      const previous = subjectSelect.value;
      subjectSelect.innerHTML = '';
      labels.forEach(label => {
        const option = document.createElement('option');
        option.value = label;
        option.textContent = label;
        subjectSelect.appendChild(option);
      });
      if (labels.includes(previous)) {
        subjectSelect.value = previous;
      } else if (labels.length) {
        subjectSelect.value = labels[0];
      }
      return subjectSelect.value;
    }

    function sortH2HOpponents(rows) {
      return rows.slice().sort((a, b) => {
        return b.entry.games - a.entry.games || (b.entry.points_for || 0) - (a.entry.points_for || 0) || a.label.localeCompare(b.label, 'it');
      });
    }

    function renderH2HMobile(labels, matrix, type, minGames) {
      const listEl = document.getElementById('h2h-mobile-list');
      const subjectSelect = document.getElementById('h2h_subject');
      if (!listEl || !subjectSelect) return;

      listEl.innerHTML = '';
      const subject = updateH2HSubjectOptions(labels);
      if (!subject) {
        listEl.innerHTML = '<p class="small">Nessun confronto disponibile con il filtro selezionato.</p>';
        return;
      }

      const rows = labels
        .filter(label => label !== subject)
        .map(label => ({ label, entry: matrix[subject] && matrix[subject][label] }))
        .filter(row => row.entry && row.entry.games >= minGames);

      const sortedRows = sortH2HOpponents(rows);
      if (!sortedRows.length) {
        listEl.innerHTML = '<p class="small">Nessun avversario disponibile per ' + subject + ' con questo filtro.</p>';
        return;
      }

      sortedRows.forEach(row => {
        const entry = row.entry;
        const card = document.createElement('article');
        card.className = 'h2h-duel-card ' + h2hCellClass(entry);

        const title = document.createElement('div');
        title.className = 'h2h-duel-title';
        const subjectSpan = document.createElement('span');
        subjectSpan.textContent = subject;
        const vsSpan = document.createElement('span');
        vsSpan.className = 'h2h-vs';
        vsSpan.textContent = 'vs';
        const opponentStrong = document.createElement('strong');
        opponentStrong.textContent = row.label;
        title.appendChild(subjectSpan);
        title.appendChild(vsSpan);
        title.appendChild(opponentStrong);
        card.appendChild(title);

        const summary = document.createElement('div');
        summary.className = 'h2h-duel-summary';
        [
          ['Partite', String(entry.games)],
          ['Record', (entry.wins || 0) + 'V - ' + (entry.draws || 0) + 'P - ' + (entry.losses || 0) + 'S'],
          ['Punti', (entry.points_for || 0) + '-' + (entry.points_against || 0)],
          ['Win rate', pctValue(h2hWinRate(entry))]
        ].forEach(([label, value]) => {
          const item = document.createElement('span');
          const itemLabel = document.createElement('small');
          itemLabel.textContent = label;
          const itemValue = document.createElement('strong');
          itemValue.textContent = value;
          item.appendChild(itemLabel);
          item.appendChild(itemValue);
          summary.appendChild(item);
        });
        card.appendChild(summary);

        const bar = document.createElement('div');
        bar.className = 'h2h-duel-bar';
        const fill = document.createElement('span');
        fill.style.width = Math.round(h2hWinRate(entry) * 100) + '%';
        bar.appendChild(fill);
        card.appendChild(bar);

        listEl.appendChild(card);
      });
    }




    function setupLeaderboardStickyFallback() {
      const isFirefox = /firefox/i.test(navigator.userAgent);
      document.querySelectorAll('.leaderboard-table').forEach(wrap => {
        wrap.classList.toggle('leaderboard-js-sticky', !isFirefox);
        if (isFirefox) {
          wrap.style.removeProperty('--leaderboard-scroll-left');
          return;
        }

        const update = () => {
          wrap.style.setProperty('--leaderboard-scroll-left', `${wrap.scrollLeft || 0}px`);
        };

        if (wrap.dataset.leaderboardStickyBound !== 'true') {
          wrap.addEventListener('scroll', update, { passive: true });
          wrap.dataset.leaderboardStickyBound = 'true';
        }
        requestAnimationFrame(update);
      });
    }

    function setupH2HStickyFallback() {
      const wrap = document.querySelector('.h2h-table-wrap');
      if (!wrap) return;

      const isFirefox = /firefox/i.test(navigator.userAgent);
      wrap.classList.toggle('h2h-js-sticky', !isFirefox);
      if (isFirefox) {
        wrap.style.removeProperty('--h2h-scroll-left');
        return;
      }

      const update = () => {
        wrap.style.setProperty('--h2h-scroll-left', `${wrap.scrollLeft || 0}px`);
      };

      if (wrap.dataset.h2hStickyBound !== 'true') {
        wrap.addEventListener('scroll', update, { passive: true });
        wrap.dataset.h2hStickyBound = 'true';
      }
      requestAnimationFrame(update);
    }

    function renderH2H(view) {
      const tableEl = document.getElementById('h2h-matrix');
      const legend = document.getElementById('matrix-legend');
      const type = currentMatrixType();
      const format = currentMatrixFormat();
      const minGames = Number(document.getElementById('matrix_min_games').value || 1);
      const h2h = (view.head_to_head || {})[type] || { labels: [], matrix: {} };
      const allLabels = h2h.labels || [];
      const matrix = h2h.matrix || {};

      const labels = allLabels.filter(label => {
        return allLabels.some(other => {
          if (label === other) return false;
          const entry = matrix[label] && matrix[label][other];
          return entry && entry.games >= minGames;
        });
      });

      renderH2HMobile(labels, matrix, type, minGames);
      tableEl.innerHTML = '';
      legend.textContent = format === 'points'
        ? 'Desktop: punti = punti riga - punti avversario. Mobile: punti del soggetto selezionato - punti dell avversario.'
        : 'Desktop: V-P-S della riga. Mobile: V-P-S del soggetto selezionato contro l avversario.';

      if (!labels.length) {
        const caption = document.createElement('caption');
        caption.textContent = 'Nessun confronto disponibile con il filtro selezionato.';
        tableEl.appendChild(caption);
        return;
      }

      const thead = document.createElement('thead');
      const headerRow = document.createElement('tr');
      const corner = document.createElement('th');
      corner.textContent = type === 'players' ? 'Player ↓ / vs →' : 'Team ↓ / vs →';
      headerRow.appendChild(corner);
      labels.forEach(label => {
        const th = document.createElement('th');
        th.textContent = label;
        th.title = label;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);

      const tbody = document.createElement('tbody');
      labels.forEach(rowLabel => {
        const tr = document.createElement('tr');
        const rowHead = document.createElement('th');
        rowHead.scope = 'row';
        rowHead.textContent = rowLabel;
        rowHead.title = rowLabel;
        tr.appendChild(rowHead);

        labels.forEach(colLabel => {
          const td = document.createElement('td');
          if (rowLabel === colLabel) {
            td.textContent = '—';
            td.className = 'diag';
          } else {
            const entry = matrix[rowLabel] && matrix[rowLabel][colLabel];
            td.textContent = h2hCellText(entry, format);
            td.className = h2hCellClass(entry);
            td.title = h2hTitle(rowLabel, colLabel, entry);
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });

      tableEl.appendChild(thead);
      tableEl.appendChild(tbody);
      setupH2HStickyFallback();
    }

    function renderDashboard(data) {
      const year = document.getElementById('season_filter').value || 'all';
      const view = getView(data, year);
      const counts = view.counts || { matches: 0, players: 0, teams: 0 };
      const byPlayer = view.by_player || [];
      const byTeam = view.by_team || [];
      const matches = view.matches || [];
      const suffix = selectedYearLabel(year);

      document.getElementById('kpi-matches').textContent = counts.matches || 0;
      document.getElementById('kpi-players').textContent = counts.players || 0;
      document.getElementById('kpi-teams').textContent = counts.teams || 0;
      document.getElementById('kpi-latest').textContent = matches.length ? niceDate(matches[0].played_at) : '-';
      document.getElementById('players-count').textContent = byPlayer.length + ' player · ' + suffix;
      document.getElementById('teams-count').textContent = byTeam.length + ' team · ' + suffix;

      table(
        document.getElementById('players'),
        ['Giocatore', 'Punti', 'Partite giocate', 'Vittorie', 'Pareggi', 'Sconfitte', 'Win Rate'],
        byPlayer.map(x => [x.player, x.points || 0, x.games, x.wins || 0, x.draws || 0, x.losses || 0, pctValue(x.winrate || 0)])
      );

      table(
        document.getElementById('teams'),
        ['Squadra', 'Punti', 'Componenti', 'Partite giocate', 'Vittorie', 'Pareggi', 'Sconfitte', 'Win Rate'],
        byTeam.map(x => [x.team_name || x.team_label, x.points || 0, x.team_label, x.games, x.wins || 0, x.draws || 0, x.losses || 0, pctValue(x.winrate || 0)])
      );

      setupLeaderboardStickyFallback();
      renderH2H(view);
      renderMatches(view);
    }

    fetch('data/stats.json')
      .then(r => r.json())
      .then(data => {
        window.__statsData = data;

        document.getElementById('updated-at').textContent = 'Aggiornato: ' + niceDate(data.generated_at || data.generated_utc || data.generated || '');
        populateYearFilter(data);
        renderDashboard(data);

        document.getElementById('season_filter').addEventListener('change', function () {
          renderDashboard(window.__statsData);
        });
        document.getElementById('matches_limit').addEventListener('change', function () {
          renderDashboard(window.__statsData);
        });
        ['matrix_type', 'matrix_format', 'matrix_min_games', 'h2h_subject'].forEach(id => {
          const control = document.getElementById(id);
          if (control) {
            control.addEventListener('change', function () {
              renderDashboard(window.__statsData);
            });
          }
        });
      })
      .catch(err => {
        document.getElementById('updated-at').textContent = 'Impossibile leggere i dati';
        console.error(err);
      });
  