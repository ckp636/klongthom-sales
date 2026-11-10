// Optional real-browser check: serve static assets locally; API responses are isolated fixtures.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const origin = process.env.BASE_URL || 'http://127.0.0.1:8765';
    const date = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Bangkok' }).format(new Date());
    const personnel = { p7PID: 1, p7Role: 'staff', fullName: 'ทดสอบ หนึ่ง' };
    const reports = [];
    let loggedIn = false;
    let photoAttempts = 0;
    let storedImage;
    const photo = { f1FID: 1, f1FileName: 'evidence.jpg', available: true,
      contentUrl: '/api/transactions/42/files/1/content' };

    await page.route('**/api/**', async route => {
      const request = route.request();
      const pathname = new URL(request.url()).pathname;
      const headers = { 'Access-Control-Allow-Origin': origin, 'Access-Control-Allow-Credentials': 'true' };
      const json = (body, status = 200) => route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: {
        ...headers, 'Access-Control-Allow-Methods': 'GET,POST', 'Access-Control-Allow-Headers': 'content-type',
      } });
      if (pathname.endsWith('/auth/me')) return loggedIn ? json({ personnel }) : json({ detail: 'login required' }, 401);
      if (pathname.endsWith('/auth/login-dev')) { loggedIn = true; return json({ personnel }); }
      if (pathname.endsWith('/stores/')) return json([{ s7Sid: 1, s7Code: 'A1', s7Name: 'ร้านทดสอบ', s7Status: true }]);
      if (pathname.endsWith('/files/1/content')) {
        return route.fulfill({ headers, contentType: 'image/jpeg', body: storedImage });
      }
      if (pathname.endsWith('/files')) {
        if (request.method() === 'GET') return json(storedImage ? [photo] : []);
        photoAttempts++;
        if (photoAttempts === 1) return json({ detail: 'photo temporarily unavailable' }, 503);
        const multipart = request.postDataBuffer();
        const start = multipart.indexOf(Buffer.from('\r\n\r\n')) + 4;
        const end = multipart.lastIndexOf(Buffer.from('\r\n--'));
        storedImage = multipart.subarray(start, end);
        assert.ok(storedImage.length <= 2 * 1024 * 1024);
        assert.ok(storedImage.length <= 500 * 1024);
        assert.equal(storedImage[0], 0xff);
        return json(photo, 201);
      }
      if (pathname.endsWith('/transactions/')) {
        if (request.method() === 'GET') return json(reports);
        const body = request.postDataJSON();
        assert.equal(body.t1Cash, '100.25');
        assert.equal(body.t1Pid, undefined);
        const report = { ...body, t1TID: 42, t1Pid: 1, t1Status: 'submitted',
          t1CreatedAt: date + 'T10:00:00', employeeName: personnel.fullName,
          storeName: 'ร้านทดสอบ', fileCount: 0 };
        reports.push(report);
        return json(report, 201);
      }
      throw Error(`Unexpected API request: ${request.method()} ${pathname}`);
    });

    await page.goto(origin + '/app.html?shop=A1&sig=fixture', { waitUntil: 'networkidle' });
    await page.getByText('พนักงานทั่วไป', { exact: true }).click();
    const inputs = page.getByPlaceholder('0', { exact: true });
    await inputs.nth(0).fill('100.25');
    await inputs.nth(1).fill('10.10');
    await inputs.nth(2).fill('5.05');
    const png = await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      canvas.width = 1920;
      canvas.height = 1080;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#0E7C66';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      return canvas.toDataURL('image/png').split(',')[1];
    });
    await page.locator('input[type=file]').setInputFiles({
      name: 'original.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64'),
    });
    await page.getByText('ส่งยอดขาย', { exact: true }).waitFor();
    await page.getByText('ส่งยอดขาย', { exact: true }).click();
    await page.getByRole('button', { name: 'ส่งรูปอีกครั้ง', exact: true }).waitFor();
    assert.equal(reports.length, 1);
    await page.getByRole('button', { name: 'ส่งรูปอีกครั้ง', exact: true }).click();
    await page.getByText('ส่งยอดสำเร็จ · A1 ร้านทดสอบ · ฿105.30', { exact: true }).waitFor();
    assert.equal(reports.length, 1);
    assert.equal(photoAttempts, 2);

    await page.reload({ waitUntil: 'networkidle' });
    await page.getByText('ท', { exact: true }).click();
    await page.getByText('ประวัติส่งยอด →', { exact: true }).click();
    await page.getByText('สด ฿100.25 / โอน ฿10.10 / หัก ฿5.05', { exact: true }).click();
    await page.getByRole('button', { name: 'ดู / แนบหลักฐาน', exact: true }).click();
    const image = page.getByAltText('หลักฐานนำส่งเงิน', { exact: true });
    await image.waitFor();
    await image.evaluate(element => element.decode());
    assert.ok(await image.evaluate(element => Math.max(element.naturalWidth, element.naturalHeight) <= 1600));
    assert.match(await image.getAttribute('src'), /^blob:/);
    assert.deepEqual(errors, []);
    console.log('PASS: mobile login, decimal submit, photo compression/failure/retry, reload history and authenticated image display');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
