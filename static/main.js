async function fetchAuthorized() {
  const res = await fetch('/api/authorized');
  return await res.json();
}

function renderTable(rows) {
  if (!rows || rows.length === 0) return '<em>(no rows)</em>';
  const cols = Object.keys(rows[0]);
  let thead = '<thead><tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr></thead>';
  let tbody = '<tbody>' + rows.map(r => '<tr>' + cols.map(c => `<td>${r[c]}</td>`).join('') + '</tr>').join('') + '</tbody>';
  return `<table>${thead}${tbody}</table>`;
}

function renderParamInputs(auth) {
  if (!auth.params || auth.params.length === 0) return '';
  return auth.params.map(p => `
    <label>${p}
      <input type="text" id="param_${p}" placeholder="Enter ${p}">
    </label>
  `).join('');
}

async function init() {
  const authSel = document.getElementById('auth');
  const paramBox = document.getElementById('paramBox');

  const list = await fetchAuthorized();
  for (const a of list) {
    const opt = document.createElement('option');
    opt.value = a.id;
    opt.textContent = `${a.title}  —  ${a.sql}`;
    opt.dataset.auth = JSON.stringify(a);
    authSel.appendChild(opt);
  }

  function updateParams() {
    const a = JSON.parse(authSel.selectedOptions[0].dataset.auth);
    paramBox.innerHTML = renderParamInputs(a);
  }
  authSel.addEventListener('change', updateParams);
  updateParams();

  document.getElementById('submitBtn').addEventListener('click', async () => {
    const user_sql = document.getElementById('user_sql').value;
    const a = JSON.parse(authSel.selectedOptions[0].dataset.auth);
    const params = {};
    if (a.params) {
      for (const p of a.params) {
        const v = document.getElementById(`param_${p}`)?.value;
        if (v !== undefined && v !== '') params[p] = isNaN(Number(v)) ? v : Number(v);
      }
    }
    const res = await fetch('/api/submit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ authorized_id: a.id, user_sql, params })
    });
    const data = await res.json();

    document.getElementById('decision').textContent = `${data.decision ?? data.error}`;
    document.getElementById('decision').className = data.ok ? 'ok mono' : 'bad mono';
    document.getElementById('reason').textContent = data.reason ?? '';

    document.getElementById('userResults').innerHTML = renderTable(data.user_rows);
    document.getElementById('authResults').innerHTML = renderTable(data.authorized_rows);
    document.getElementById('debug').textContent = JSON.stringify(data, null, 2);
  });
}

init();
