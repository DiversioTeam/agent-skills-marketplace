// Run with Playwright available in NODE_PATH; uses only synthetic local content.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const helpers = require('../plugins/browser-walkthrough-recording/skills/browser-walkthrough-recording/scripts/capture-template.cjs');

(async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'walkthrough-test-'));
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.setContent('<body style="margin:40px"><h1>Fictional demo</h1><button>Save demo</button></body>');
    const button = page.getByRole('button');
    await helpers.add_caption(page, '1 · Save the fictional demo');
    await helpers.add_highlight(button);
    await helpers.add_highlight(button);
    assert.equal(await page.locator('#__walkthrough_highlight').count(), 1);
    assert.equal(await page.locator('#__walkthrough_caption').textContent(), '1 · Save the fictional demo');
    await helpers.build_screenshot(page, path.join(directory, 'clean.png'));
    assert.equal(await page.locator('#__walkthrough_caption').isVisible(), true);
    await helpers.remove_highlight(page);
    await page.locator('#__walkthrough_caption').evaluate((element) => element.remove());
    const without_overlays = await page.screenshot();
    assert.deepEqual(fs.readFileSync(path.join(directory, 'clean.png')), without_overlays);
    await helpers.add_zoom(page);
    assert.equal(await page.locator('body').evaluate((element) => element.style.zoom), '1.5');
    await helpers.remove_zoom(page);
    assert.equal(await page.locator('body').evaluate((element) => element.style.zoom), '');
    await assert.rejects(helpers.add_zoom(page, 3));
    await assert.rejects(helpers.add_caption(page, 'Invalid placement', 'left'));
    let destination_requests = 0;
    const server = http.createServer((request, response) => {
      if (request.url === '/redirect') {
        response.writeHead(302, { Location: `http://localhost:${server.address().port}/destination` });
      } else if (request.url === '/external-redirect') {
        response.writeHead(302, { Location: 'https://production.example.test/' });
      } else if (request.url === '/destination') {
        destination_requests += 1;
      }
      response.end('<h1>Safe local fixture</h1>');
    });
    await new Promise((done) => server.listen(0, '127.0.0.1', done));
    const guarded_context = await browser.newContext({ serviceWorkers: 'block' });
    try {
      const failures = await helpers.add_local_request_guard(guarded_context);
      const guarded_page = await guarded_context.newPage();
      const local_address = `http://127.0.0.1:${server.address().port}`;
      await guarded_page.goto(local_address);
      assert.equal(await guarded_page.locator('h1').textContent(), 'Safe local fixture');
      for (const endpoint of ['/redirect', '/external-redirect']) {
        await assert.rejects(guarded_page.goto(local_address + endpoint));
        assert.match(failures.at(-1), /Redirect refused/);
      }
      assert.equal(destination_requests, 0);
      await assert.rejects(guarded_page.goto('https://production.example.test/'));
      assert.match(failures.at(-1), /verified local demo URL/);
      console.log('PASS: local page allowed; local/external redirects and external navigation blocked');
    } finally {
      await guarded_context.close();
      await new Promise((done, fail) => server.close((error) => error ? fail(error) : done()));
    }
    console.log('PASS: captions, single highlight, clean screenshots, zoom/reset, invalid inputs');
  } finally {
    await browser.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
