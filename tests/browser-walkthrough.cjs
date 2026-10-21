// Run with Playwright available in NODE_PATH; uses only synthetic local content.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
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
    console.log('PASS: captions, single highlight, clean screenshots, zoom/reset, invalid inputs');
  } finally {
    await browser.close();
    fs.rmSync(directory, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
