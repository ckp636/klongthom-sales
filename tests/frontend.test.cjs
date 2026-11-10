const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../app.html'), 'utf8');
const source = html.match(/<script type="text\/x-dc" data-dc-script>([\s\S]*?)<\/script>/)[1];
const person = { p7PID: 1, p7Role: 'staff', fullName: 'Test Staff' };
const txn = { t1TID: 42, t1Pid: 1, t1Date: '2026-11-10', t1Shift: 'afternoon',
  t1Cash: '100.25', t1Transfer: '0.10', t1Expense: '0.05', t1CreatedAt: '2026-11-10T10:00:00',
  storeCode: 'A1', storeName: 'Store', employeeName: 'Test Staff', t1Status: 'submitted', fileCount: 0 };
const response = (data, status = 200) => new Response(status === 204 ? null : JSON.stringify(data), { status });

function setup(fetcher = async () => { throw Error('offline'); }, hostname = 'localhost') {
  const calls = [];
  const location = { hostname, search: '', origin: `http://${hostname}:8080`, href: `http://${hostname}:8080/app.html` };
  const context = {
    DCLogic: class { setState(update) { Object.assign(this.state, typeof update === 'function' ? update(this.state) : update); } },
    location, window: { location }, URL, URLSearchParams, Intl, Date, FormData, Blob,
    console: { error() {} },
    fetch: async (...args) => { calls.push(args); return fetcher(...args); },
  };
  vm.createContext(context);
  vm.runInContext(source + '\nglobalThis.component = new Component();', context);
  return { c: context.component, context, calls };
}

function form(c) {
  Object.assign(c.state, { personnelId: 1, employeeName: person.fullName, storeCode: 'A1',
    cash: '100.25', transfer: '0.10', expense: '0.05', qrSig: 'signed' });
}

test('empty startup renders without fixtures or mock identities', () => {
  const { c } = setup();
  assert.equal(c.state.allHistory.length, 0);
  assert.equal(c.state.stores.length, 0);
  assert.equal(c.state.personnelId, null);
  assert.equal(c.renderVals().isLoggedIn, false);
});

test('failed dev login and submit never manufacture success', async () => {
  const { c, calls } = setup();
  await c.devLoginAdmin();
  assert.equal(c.state.personnelId, null);
  assert.equal(c.state.isAdminUser, false);
  form(c);
  await c.submitForm();
  assert.equal(c.state.justSubmitted, false);
  assert.equal(c.state.allHistory.length, 0);
  assert.equal(c.state.cash, '100.25');
  assert.ok(c.state.apiError);
  assert.equal(calls.length, 2);
});

test('missing backend identity prevents submission', async () => {
  const { c, calls } = setup();
  Object.assign(c.state, { employeeName: 'LINE name only', storeCode: 'A1', cash: '10' });
  await c.submitForm();
  assert.equal(calls.length, 0);
  assert.equal(c.state.justSubmitted, false);
});

test('existing LINE session uses verified-token backend login before form', async () => {
  const { c, context, calls } = setup(async (url, opts) => {
    if (url.endsWith('/auth/me')) return response({ detail: 'login required' }, 401);
    if (url.endsWith('/auth/login')) {
      assert.equal(JSON.parse(opts.body).id_token, 'verified-by-server');
      return response({ personnel: person });
    }
    return response([]);
  }, 'staging.example');
  context.liff = { init: async () => {}, isLoggedIn: () => true, getIDToken: () => 'verified-by-server' };
  c.state.storeCode = 'A1';
  await c.bootstrap();
  assert.equal(c.state.personnelId, 1);
  assert.equal(c.state.screen, 'form');
  assert.ok(calls.every(([, options]) => options.credentials === 'include'));
});

test('submission uses Decimal strings, server ID and reloads persisted data', async () => {
  const { c, calls } = setup(async (url, options) => {
    if (options.method === 'POST') {
      const body = JSON.parse(options.body);
      assert.equal(body.t1Cash, '100.25');
      assert.equal(body.t1Pid, undefined);
      return response(txn, 201);
    }
    if (url.endsWith('/transactions/')) return response([txn]);
    return response([]);
  });
  form(c);
  await c.submitForm();
  assert.equal(c.state.lastSubmission.id, 42);
  assert.equal(c.state.allHistory[0].id, 42);
  assert.equal(c.state.justSubmitted, true);
  assert.equal(c.renderVals().lastTotalDisplay, '100.30');
  assert.equal(calls.filter(([, o]) => o.method === 'POST').length, 1);
});

test('in-flight submit lock prevents double POST', async () => {
  let release;
  const waiting = new Promise(resolve => { release = resolve; });
  const { c, calls } = setup(async (url, options) => options.method === 'POST' ? waiting : response([]));
  form(c);
  const first = c.submitForm();
  await c.submitForm();
  assert.equal(calls.length, 1);
  release(response(txn, 201));
  await first;
});

test('failed photo preserves saved transaction and retry does not resubmit it', async () => {
  let uploads = 0;
  const { c, calls } = setup(async (url, options) => {
    if (url.endsWith('/files')) {
      uploads++;
      if (uploads === 1) throw Error('photo offline');
      return response({ f1FID: 1 }, 201);
    }
    if (options.method === 'POST') return response(txn, 201);
    return response(url.endsWith('/transactions/') ? [txn] : []);
  });
  form(c);
  c._photoBlob = new Blob(['photo'], { type: 'image/jpeg' });
  await c.submitForm();
  assert.equal(c.state.pendingPhotoTid, 42);
  assert.equal(c.state.justSubmitted, false);
  assert.ok(c._photoBlob);
  await c.retryPhoto();
  assert.equal(c.state.pendingPhotoTid, null);
  assert.equal(c.state.justSubmitted, true);
  assert.equal(calls.filter(([url, o]) => url.endsWith('/transactions/') && o.method === 'POST').length, 1);
});

test('late data response cannot restore data after logout', async () => {
  let release;
  const waiting = new Promise(resolve => { release = resolve; });
  const { c } = setup(async url => url.endsWith('/transactions/') ? waiting : response([]));
  form(c);
  const loading = c.loadData();
  c.resetSession();
  release(response([txn]));
  await loading;
  assert.equal(c.state.allHistory.length, 0);
  assert.equal(c.state.personnelId, null);
});

test('logout removes identity, reports, privileged mode and QR secrets', async () => {
  const { c } = setup(async () => response(null, 204));
  form(c);
  Object.assign(c.state, { isAdminUser: true, mode: 'admin', allHistory: [txn], pendingPhotoTid: 42 });
  await c.doLogout();
  assert.equal(c.state.personnelId, null);
  assert.equal(c.state.qrSig, '');
  assert.equal(c.state.allHistory.length, 0);
  assert.equal(c.state.pendingPhotoTid, null);
  assert.equal(c.state.mode, 'staff');
});

test('generated QR comes from signed backend query', async () => {
  let payload;
  const { c, context } = setup(async () => response({ qrQuery: '?shop=A1&sig=server-signature' }));
  c.state.stores = [{ id: 1, code: 'A1', name: 'Store' }];
  context.QRCode = { toDataURL: async text => { payload = text; throw Error('stop before canvas'); } };
  await c.openStoreQR('A1');
  assert.equal(new URL(payload).searchParams.get('sig'), 'server-signature');
});

test('Bangkok midnight and decimal amounts retain their meaning', async () => {
  const { c, calls } = setup();
  assert.equal(c.bangkokDate(new Date('2026-11-10T18:00:00Z')), '2026-11-11');
  assert.equal(c.onlyDigits('123.45'), '123.45');
  assert.equal(c.fmt(0.1 + 0.2), '0.30');
  form(c);
  c.state.cash = '1.234';
  await c.submitForm();
  assert.equal(calls.length, 0);
});

test('personnel management includes staff with no reports; names are not IDs', () => {
  const { c } = setup();
  form(c);
  Object.assign(c.state, {
    isAdminUser: true, adminDateFrom: '', adminDateTo: '',
    selectedHistoryEmployee: '1',
    personnel: [{ ...person, p7Status: true }, { ...person, p7PID: 2, p7Status: true }],
    allHistory: [c.adaptTransaction(txn), c.adaptTransaction({ ...txn, t1TID: 43, t1Pid: 2 })],
  });
  const values = c.renderVals();
  assert.equal(values.userManageRows.length, 2);
  assert.equal(values.filteredHistory.length, 1);
  assert.equal(values.employeeChartBars.length, 2);
});
