// End-to-end: real browser → real FastAPI app → in-memory test DB (never Azure).
// Starts tests/e2e/server.py itself. Run from the repo root:
//   cd tests && npm install && cd ..          (once: installs Playwright)
//   node --test tests/e2e/app.e2e.cjs
// Screenshots + UX report: tests/e2e/screenshots/ (git-ignored).
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { test, before, after } = require('node:test');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '../..');
const PORT = Number(process.env.E2E_PORT || 8180);
const ORIGIN = `http://app.localhost:${PORT}`;
const APP = `${ORIGIN}/app.html`;
const SHOTS = path.join(__dirname, 'screenshots');
const PYTHON = process.env.PYTHON || [path.join(ROOT, '.venv/Scripts/python.exe'), path.join(ROOT, '.venv/bin/python')]
  .find(p => fs.existsSync(p)) || 'python';
const QR_SECRET = 'e2e-qr-secret';
const qrSig = (code, ver = 1) => crypto.createHmac('sha256', QR_SECRET).update(`${code}:${ver}`).digest('hex').slice(0, 32);
const PHONE = { width: 390, height: 844 };
const SMALL_PHONE = { width: 360, height: 740 };
const DESKTOP = { width: 1280, height: 860 };

let server, browser;
const uxReport = [];

// ── harness ──────────────────────────────────────────────────────────────
before(async () => {
  fs.rmSync(SHOTS, { recursive: true, force: true });
  fs.mkdirSync(SHOTS, { recursive: true });
  server = spawn(PYTHON, [path.join(__dirname, 'server.py')], { cwd: ROOT, env: { ...process.env, E2E_PORT: String(PORT) } });
  let log = '';
  const logFile = fs.createWriteStream(path.join(SHOTS, 'server.log'));
  server.stdout.on('data', d => { log += d; logFile.write(d); });
  server.stderr.on('data', d => { log += d; logFile.write(d); });
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`http://127.0.0.1:${PORT}/api/health`)).ok) break; } catch { /* starting */ }
    if (server.exitCode !== null) throw new Error('e2e server exited:\n' + log);
    await new Promise(r => setTimeout(r, 500));
  }
  browser = await chromium.launch({
    channel: process.env.PW_CHANNEL || 'chrome',
    args: [`--host-resolver-rules=MAP app.localhost 127.0.0.1`],
  });
});

after(async () => {
  await browser?.close();
  server?.kill();
  fs.writeFileSync(path.join(SHOTS, 'ux-report.json'), JSON.stringify(uxReport, null, 2));
  const issues = uxReport.flatMap(r => r.issues.map(i => `  [${r.screen}] ${i}`));
  console.log(`\nUX audit: ${uxReport.length} screens, ${issues.length} findings` + (issues.length ? '\n' + issues.join('\n') : ''));
});

const LIFF_STUB = `window.liff = { init: async () => {}, isLoggedIn: () => false, login() {}, logout() {},
  getIDToken: () => null, isInClient: () => false, scanCodeV2: async () => ({ value: '' }) };`;

async function openApp(viewport = PHONE, url = APP, context) {
  const ctx = context || await browser.newContext({ viewport, locale: 'th-TH', timezoneId: 'Asia/Bangkok' });
  const page = await ctx.newPage();
  page.errors = [];
  page.on('pageerror', e => page.errors.push(String(e)));
  page.on('response', async r => {  // any server crash is a failure, with its body for the report
    if (r.status() >= 500) page.errors.push(`HTTP ${r.status()} ${r.request().method()} ${r.url()} ${(await r.text().catch(() => '')).slice(0, 300)}`);
  });
  await page.route('https://static.line-scdn.net/**', r => r.fulfill({ contentType: 'text/javascript', body: LIFF_STUB }));
  await page.goto(url, { waitUntil: 'networkidle' });
  return page;
}

const text = async page => (await page.locator('body').innerText()).replace(/\s+/g, ' ');
const tap = (page, label, which = 'first') => page.getByText(label, { exact: true })[which]().click();
const settle = page => page.waitForLoadState('networkidle').then(() => page.waitForTimeout(300));

async function expectVisible(page, label, why) {
  const el = page.getByText(label).first();
  await el.waitFor({ state: 'visible', timeout: 8000 }).catch(() => {});
  assert.ok(await el.isVisible(), `${why}: "${label}" not visible`);
  const box = await el.boundingBox();
  const vp = page.viewportSize();
  assert.ok(box && box.y >= 0 && box.y + box.height <= vp.height, `${why}: "${label}" is outside the screen (y=${box && box.y})`);
}

// UX/UI audit of the current screen; layout overflow fails, the rest is reported.
async function audit(page, screen, { strictTargets = true } = {}) {
  await page.screenshot({ path: path.join(SHOTS, `${screen}.png`) });
  const r = await page.evaluate(() => {
    const out = { overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth, issues: [] };
    const visible = el => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el);
      return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    for (const el of document.querySelectorAll('input, select, textarea')) {
      if (!visible(el) || el.type === 'file') continue;
      const size = parseFloat(getComputedStyle(el).fontSize);
      const label = el.placeholder || el.name || el.type;
      if (size < 16) out.issues.push(`input "${label}" font ${size}px < 16px (iOS zooms the page)`);
    }
    for (const el of document.querySelectorAll('input[placeholder="0"]'))
      if (visible(el) && el.inputMode !== 'decimal') out.issues.push('money input without inputmode=decimal');
    const seen = new Set();
    for (const el of document.querySelectorAll('[onclick], button, a, div, span')) {
      if (!visible(el) || getComputedStyle(el).cursor !== 'pointer') continue;
      if (el.parentElement && getComputedStyle(el.parentElement).cursor === 'pointer') continue;
      const b = el.getBoundingClientRect();
      const label = (el.innerText || el.title || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 30) || '(icon)';
      if (Math.min(b.width, b.height) < 32 && !seen.has(label)) {
        seen.add(label); out.issues.push(`tap target "${label}" ${Math.round(b.width)}×${Math.round(b.height)}px (< 32px)`);
      }
    }
    return out;
  });
  const issues = r.issues.filter(i => strictTargets || !i.startsWith('tap target'));
  uxReport.push({ screen, viewport: page.viewportSize(), issues });
  assert.ok(r.overflowX <= 1, `[${screen}] page scrolls sideways by ${r.overflowX}px`);
  assert.deepEqual(page.errors, [], `[${screen}] page errors`);
}

async function login(page, user, password = 'demo1234') {
  await tap(page, 'เข้าสู่ระบบ');
  await tap(page, 'เข้าด้วยบัญชีทดลอง / ฝึกใช้งาน');
  await page.getByPlaceholder('ชื่อผู้ใช้').fill(user);
  await page.getByPlaceholder('รหัสผ่าน').fill(password);
  await tap(page, 'เข้าสู่ระบบ', 'last');
  await settle(page);
}

async function pickStore(page, name) {
  await tap(page, 'หรือเลือกร้านค้าด้วยตนเอง');
  await page.getByText(name, { exact: true }).first().click();
  await settle(page);
}

async function fillMoney(page, cash, transfer = '', expense = '') {
  const inputs = page.getByPlaceholder('0', { exact: true });
  if (cash !== null) await inputs.nth(0).fill(cash);
  if (transfer) await inputs.nth(1).fill(transfer);
  if (expense) await inputs.nth(2).fill(expense);
}

async function jpeg(page) {
  const b64 = await page.evaluate(() => {
    const c = document.createElement('canvas'); c.width = 1200; c.height = 900;
    const g = c.getContext('2d'); g.fillStyle = '#c8e6d8'; g.fillRect(0, 0, 1200, 900);
    g.fillStyle = '#0E7C66'; g.font = '80px sans-serif'; g.fillText('slip', 480, 470);
    return c.toDataURL('image/jpeg', 0.9).split(',')[1];
  });
  return { name: 'slip.jpg', mimeType: 'image/jpeg', buffer: Buffer.from(b64, 'base64') };
}

const money = s => Number(String(s).replace(/[฿,\s]/g, ''));

// ── 1. first visit ─────────────────────────────────────────────────────────
test('guide page: loads, swipe gallery, link to the app', async () => {
  const page = await openApp(PHONE, `${ORIGIN}/index.html`);
  assert.match(await text(page), /ส่งยอดใน 4 ขั้นตอน/);
  assert.equal(await page.locator('#gallery .slide').count(), 4);
  assert.equal(await page.locator('#dots button').count(), 4);
  assert.ok(await page.locator('a[href="app.html"]').count() >= 1);
  assert.doesNotMatch(await text(page), /แดชบอร์ด/, 'guide must not show admin features');
  await audit(page, '01-guide-phone', { strictTargets: false });
  await page.context().close();
});

test('start screen: login button, no DEV tools, fits a small phone', async () => {
  const page = await openApp(SMALL_PHONE);
  const t = await text(page);
  assert.match(t, /สแกน QR รหัสร้านค้า/);
  assert.doesNotMatch(t, /DEV/, 'production build must not show DEV tools');
  await expectVisible(page, 'เข้าสู่ระบบ', 'start screen');
  await audit(page, '02-start-360');
  await page.context().close();
});

// ── 2. login ─────────────────────────────────────────────────────────────
test('login: every failure explains itself next to the button', async () => {
  const page = await openApp();
  await tap(page, 'เข้าสู่ระบบ');
  assert.doesNotMatch(await text(page), /ร้านค้าที่เลือก/, 'no empty store block before a store is chosen');
  assert.equal(await page.getByPlaceholder('รหัสผ่าน').count(), 0, 'training login is hidden until asked for');
  const selectable = await page.evaluate(() => getComputedStyle(document.querySelector('.kt-app div')).userSelect);
  assert.equal(selectable, 'none', 'screen text cannot be highlighted with the mouse');
  await audit(page, '03-login');
  await tap(page, 'เข้าด้วยบัญชีทดลอง / ฝึกใช้งาน');
  assert.equal(await page.getByPlaceholder('รหัสผ่าน').count(), 1, 'link opens the training login');
  assert.equal(await page.getByPlaceholder('ชื่อผู้ใช้').evaluate(el => getComputedStyle(el).userSelect), 'text',
    'inputs stay editable');
  await audit(page, '03b-login-training');
  const submit = () => tap(page, 'เข้าสู่ระบบ', 'last');

  await submit();
  await expectVisible(page, 'กรุณากรอกชื่อผู้ใช้และรหัสผ่าน', 'empty form');

  await page.getByPlaceholder('ชื่อผู้ใช้').fill('staff01');
  await page.getByPlaceholder('รหัสผ่าน').fill('wrong-pass');
  await submit(); await settle(page);
  await expectVisible(page, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'wrong password');
  await audit(page, '04-login-error');

  await page.getByPlaceholder('ชื่อผู้ใช้').fill('nobody');
  await page.getByPlaceholder('รหัสผ่าน').fill('demo1234');
  await submit(); await settle(page);
  await expectVisible(page, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'unknown user (same message, no user enumeration)');

  await page.getByPlaceholder('ชื่อผู้ใช้').fill('ห่ฟะะ01');
  await page.getByPlaceholder('รหัสผ่าน').fill('กำทน1234');
  await submit(); await settle(page);
  await expectVisible(page, 'สลับเป็นภาษาอังกฤษ', 'Thai keyboard');

  await page.getByPlaceholder('ชื่อผู้ใช้').fill('staff99');
  await page.getByPlaceholder('รหัสผ่าน').fill('demo1234');
  await submit(); await settle(page);
  await expectVisible(page, 'บัญชีนี้ถูกระงับ', 'suspended account');

  await page.getByPlaceholder('ชื่อผู้ใช้').fill('staff01');
  await submit(); await settle(page);
  const t = await text(page);
  assert.match(t, /สตาฟ หนึ่ง/); assert.match(t, /ออกจากระบบ/);
  assert.doesNotMatch(t, /รายงานยอดขาย/, 'staff must not see admin entry');
  await audit(page, '05-staff-home');

  await page.reload({ waitUntil: 'networkidle' }); await settle(page);
  assert.match(await text(page), /สตาฟ หนึ่ง/, 'session survives a reload');
  await page.context().close();
});

// ── 3. staff: send a report ───────────────────────────────────────────────
test('staff: store picker lists only open stores', async () => {
  const page = await openApp();
  await login(page, 'staff01');
  await tap(page, 'หรือเลือกร้านค้าด้วยตนเอง');
  const t = await text(page);
  assert.match(t, /กอล์ฟ/); assert.match(t, /นิ่ม/);
  assert.doesNotMatch(t, /ร้านปิด/, 'a suspended store must not be offered');
  await audit(page, '06-store-picker');
  await page.context().close();
});

test('staff: form validation, live total, submit with photo, history + detail', async () => {
  const page = await openApp();
  await login(page, 'staff01');
  await pickStore(page, 'กอล์ฟ');
  assert.match(await text(page), /A1 กอล์ฟ/);
  await audit(page, '07-form-empty');

  await tap(page, 'ส่งยอดขาย');
  await expectVisible(page, 'กรุณากรอกยอดเงินสดที่นำส่ง', 'missing cash');
  await audit(page, '08-form-cash-error');

  const cash = page.getByPlaceholder('0', { exact: true }).nth(0);
  await cash.fill('-12a3');
  assert.equal(await cash.inputValue(), '123', 'only digits and a dot are kept');
  await cash.fill('1.234');
  await tap(page, 'ส่งยอดขาย'); await settle(page);
  await expectVisible(page, 'ทศนิยมไม่เกิน 2 ตำแหน่ง', 'three decimals');

  await fillMoney(page, '1000.50', '200', '50.25');
  await tap(page, 'เช้า');
  assert.match(await text(page), /฿1,150\.25/, 'total = cash + transfer − expense');
  await page.locator('input[type=file]').setInputFiles(await jpeg(page));
  await page.waitForTimeout(1500);
  await audit(page, '09-form-filled');

  await tap(page, 'ส่งยอดขาย'); await settle(page);
  await expectVisible(page, 'ส่งยอดสำเร็จ', 'success banner');
  const t = await text(page);
  assert.match(t, /1,150\.25/);
  assert.match(t, /· A1/); assert.match(t, /เช้า/);
  await audit(page, '10-history-after-submit');

  await page.getByText(/\d{4} · A1/).first().click(); await settle(page);
  const d = await text(page);
  assert.match(d, /รอยืนยัน/); assert.match(d, /1,150\.25/);
  assert.doesNotMatch(d, /ยืนยันรายการ|ยกเลิกรายการ/, 'staff cannot verify or void');
  await page.getByText('ดู / แนบหลักฐาน').first().click(); await settle(page);
  assert.ok(await page.locator('img[src^="blob:"]').count() >= 1, 'uploaded photo is shown back');
  await audit(page, '11-history-detail');
  await page.context().close();
});

test('staff: same store + date + shift twice is refused with a clear reason', async () => {
  const page = await openApp();
  await login(page, 'staff01');
  await pickStore(page, 'กอล์ฟ');
  await tap(page, 'เช้า');
  await fillMoney(page, '500');
  await tap(page, 'ส่งยอดขาย'); await settle(page);
  await expectVisible(page, 'ส่งยอดรอบนี้ของร้านนี้ไปแล้ว', 'duplicate shift');
  await audit(page, '12-duplicate-error');
  await page.context().close();
});

test('staff: QR link opens the form; a forged QR is refused', async () => {
  const ctx = await browser.newContext({ viewport: PHONE, locale: 'th-TH', timezoneId: 'Asia/Bangkok' });
  let page = await openApp(PHONE, APP, ctx);
  await login(page, 'staff01');
  await page.close();

  page = await openApp(PHONE, `${APP}?shop=A2&sig=${qrSig('A2')}`, ctx); await settle(page);
  assert.match(await text(page), /A2 นิ่ม/, 'valid QR goes straight to the form');
  await tap(page, 'ค่ำ');
  await fillMoney(page, '800', '100');
  await tap(page, 'ส่งยอดขาย'); await settle(page);
  await expectVisible(page, 'ส่งยอดสำเร็จ', 'QR submit');
  await page.close();

  page = await openApp(PHONE, `${APP}?shop=A2&sig=${'0'.repeat(32)}`, ctx); await settle(page);
  await tap(page, 'เช้า');
  await fillMoney(page, '800');
  await tap(page, 'ส่งยอดขาย'); await settle(page);
  await expectVisible(page, 'QR code ไม่ถูกต้อง', 'forged QR');
  await audit(page, '13-forged-qr');
  await ctx.close();
});

test('loading message: hidden when fast, shown only when slow', async () => {
  const ctx = await browser.newContext({ viewport: PHONE, locale: 'th-TH', timezoneId: 'Asia/Bangkok' });
  const page = await openApp(PHONE, APP, ctx);
  const seen = [];
  await page.exposeFunction('__seenLoading', t => seen.push(t));
  await page.evaluate(() => new MutationObserver(() => {
    if (document.body.innerText.includes('กำลังโหลดข้อมูล')) window.__seenLoading(performance.now());
  }).observe(document.body, { subtree: true, childList: true, characterData: true }));
  await login(page, 'staff01');
  assert.equal(seen.length, 0, 'fast loads never flash the loading message');

  await ctx.route('**/api/transactions/**', async r => { await new Promise(res => setTimeout(res, 2000)); await r.continue(); });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByText('กำลังโหลดข้อมูล').waitFor({ state: 'visible', timeout: 4000 });
  await audit(page, '05b-slow-loading');
  await page.getByText('กำลังโหลดข้อมูล').waitFor({ state: 'hidden', timeout: 8000 });
  await ctx.close();
});

test('staff: logout clears the screen and the session', async () => {
  const page = await openApp();
  await login(page, 'staff01');
  await tap(page, 'ออกจากระบบ'); await settle(page);
  let t = await text(page);
  assert.doesNotMatch(t, /สตาฟ หนึ่ง/); assert.match(t, /เข้าสู่ระบบ/);
  await page.reload({ waitUntil: 'networkidle' }); await settle(page);
  t = await text(page);
  assert.doesNotMatch(t, /สตาฟ หนึ่ง/, 'no session after logout + reload');
  await page.context().close();
});

// ── 4. admin ────────────────────────────────────────────────────────────
test('admin: dashboard numbers match the database', async () => {
  const page = await openApp(DESKTOP);
  await login(page, 'admin01');
  await tap(page, 'รายงานยอดขาย →'); await settle(page);
  const t = await text(page);
  const api = await page.evaluate(async () => {
    const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Bangkok' }).format(new Date());
    const rows = await (await fetch(`/api/transactions/?date_from=${day}&date_to=${day}`, { credentials: 'include' })).json();
    const live = rows.filter(r => r.t1Status !== 'void');
    return { net: live.reduce((s, r) => s + Number(r.t1Total), 0), stores: new Set(live.map(r => r.storeCode)).size };
  });
  const net = money(t.match(/ยอดสุทธิ\s*(฿[\d,.]+)/)[1]);
  assert.equal(net, api.net, 'net card = sum of live reports today');
  assert.match(t, new RegExp(`ร้านที่ส่งยอดแล้ว ${api.stores}/2\\b`), 'reported / open stores (closed store not counted)');
  assert.doesNotMatch(t, /\d{4}-\d{2}-\d{2}/, 'dates are shown in Thai format, not ISO');
  assert.match(t, /ไม่มีรูป/, 'a report without a photo says so instead of offering "ดูรูป"');
  assert.doesNotMatch(t.match(/ร้านที่ยังไม่ส่งยอดวันนี้[^]*?(รายการนำส่งยอด|$)/)?.[0] || '', /ร้านปิด/,
    'a closed store is not chased for a report');
  await audit(page, '14-admin-dashboard', { strictTargets: false });
  for (const view of ['รายพนักงาน', 'รายร้านค้า']) {
    await tap(page, view); await settle(page);
    await audit(page, `15-admin-${view === 'รายพนักงาน' ? 'by-employee' : 'by-store'}`, { strictTargets: false });
  }
  await page.context().close();
});

test('admin: verify, then void with a reason (cancel keeps it) — seeded report of staff02', async () => {
  const page = await openApp();
  await login(page, 'admin01');
  await page.getByText('แ', { exact: true }).first().click();  // profile avatar
  await tap(page, 'ประวัติส่งยอด →'); await settle(page);
  await page.locator('select').first().selectOption({ label: 'สตาฟ สอง' }); await settle(page);
  await page.getByText(/\d{4} · A2/).first().click(); await settle(page);
  await audit(page, '16-admin-detail');

  await tap(page, 'ยืนยันรายการ'); await settle(page);
  await expectVisible(page, 'ยืนยันรายการแล้ว', 'verify feedback on the same screen');
  assert.match(await text(page), /ยืนยันแล้ว/);
  assert.doesNotMatch(await text(page), /ยืนยันรายการ(?!แล้ว)/, 'verify button gone once verified');
  await audit(page, '16b-admin-verified');

  page.once('dialog', d => d.dismiss());
  await tap(page, 'ยกเลิกรายการ'); await settle(page);
  assert.doesNotMatch(await text(page), /ยกเลิกแล้ว/, 'cancelled prompt changes nothing');

  page.once('dialog', d => d.accept('พิมพ์ยอดผิด'));
  await tap(page, 'ยกเลิกรายการ'); await settle(page);
  await expectVisible(page, 'ยกเลิกรายการแล้ว', 'void feedback');
  assert.doesNotMatch(await text(page), /฿4,000\.00/, 'voided report no longer counted in history');
  await page.context().close();
});

test('admin: suspend a user blocks their login; store rename + QR', async () => {
  const page = await openApp(DESKTOP);
  await login(page, 'admin01');
  await page.getByText('แ', { exact: true }).first().click();  // profile avatar
  await tap(page, 'จัดการข้อมูล →'); await settle(page);
  await audit(page, '17-manage-users', { strictTargets: false });

  const row = page.getByText('สตาฟ สอง', { exact: true }).locator('xpath=ancestor::div[.//text()[contains(., "login ล่าสุด")]][1]');
  await row.getByText('ระงับ', { exact: true }).last().click(); await settle(page);
  assert.match(await row.innerText(), /เปิดใช้งาน/);

  const other = await openApp();
  await login(other, 'staff02');
  await expectVisible(other, 'บัญชีนี้ถูกระงับ', 'suspended by admin');
  await other.context().close();

  await row.getByText('เปิดใช้งาน', { exact: true }).click(); await settle(page);

  await tap(page, 'ร้านค้า'); await settle(page);
  await audit(page, '18-manage-stores', { strictTargets: false });
  const storeRow = page.locator('div').filter({ hasText: /^A2/ }).last();
  await page.locator('[title="แก้ไขร้านค้า"]').nth(1).click(); await settle(page);
  const nameInput = page.locator('input[type=text]').nth(1);
  await nameInput.fill('นิ่ม (ใหม่)');
  await tap(page, 'บันทึก'); await settle(page);
  assert.match(await text(page), /นิ่ม \(ใหม่\)/);

  await page.locator('[title="QR Code ร้าน"]').first().click(); await settle(page);
  await page.waitForTimeout(800);
  assert.ok(await page.locator('img[src^="data:image"]').count() >= 1, 'QR image is drawn');
  await audit(page, '19-store-qr', { strictTargets: false });
  void storeRow;
  await page.context().close();
});
