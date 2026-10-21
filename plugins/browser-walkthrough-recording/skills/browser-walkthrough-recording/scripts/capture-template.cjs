// Copy into a scratch Playwright project and replace the example steps.
const fs = require('node:fs');
const path = require('node:path');

const viewport = { width: 1440, height: 900 };

function validate_local_url(address) {
  const url = new URL(address);
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    || url.hostname.endsWith('.localhost');
  if (!local || !['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
    throw new Error('Use a verified local demo URL without embedded credentials.');
  }
  return url.href;
}

function get_caption_duration(text) {
  return Math.max(2500, text.trim().split(/\s+/).length * 350);
}

async function add_caption(page, text, position = 'bottom') {
  if (!['top', 'bottom'].includes(position)) throw new Error('Caption position must be top or bottom.');
  await page.evaluate(({ text, position }) => {
    document.getElementById('__walkthrough_caption')?.remove();
    const caption = document.createElement('div');
    caption.id = '__walkthrough_caption';
    Object.assign(caption.style, {
      position: 'fixed', left: '50%', transform: 'translateX(-50%)',
      [position]: '24px', zIndex: '2147483647', pointerEvents: 'none',
      background: 'rgba(15,23,42,.96)', color: '#fff',
      font: '600 24px/1.45 system-ui,sans-serif', padding: '12px 22px',
      borderRadius: '10px', maxWidth: '80%', textAlign: 'center',
    });
    caption.textContent = text;
    document.documentElement.appendChild(caption);
  }, { text, position });
  await page.waitForTimeout(get_caption_duration(text));
}

async function remove_highlight(page) {
  await page.evaluate(() => document.getElementById('__walkthrough_highlight')?.remove());
}

async function add_highlight(locator) {
  await locator.scrollIntoViewIfNeeded();
  await locator.evaluate((element) => {
    document.getElementById('__walkthrough_highlight')?.remove();
    const bounds = element.getBoundingClientRect();
    const highlight = document.createElement('div');
    highlight.id = '__walkthrough_highlight';
    Object.assign(highlight.style, {
      position: 'fixed', left: `${bounds.left - 4}px`, top: `${bounds.top - 4}px`,
      width: `${bounds.width + 8}px`, height: `${bounds.height + 8}px`,
      border: '3px solid #f59e0b', boxSizing: 'border-box', borderRadius: '6px',
      zIndex: '2147483646', pointerEvents: 'none',
    });
    document.documentElement.appendChild(highlight);
  });
  // Re-add after scrolling, zooming, or layout changes: this marks a stable scene.
}

async function add_zoom(page, scale = 1.5) {
  if (!Number.isFinite(scale) || scale < 1 || scale > 2) throw new Error('Zoom must be between 1 and 2.');
  await remove_highlight(page);
  await page.evaluate((scale) => {
    if (!Object.hasOwn(document.body.dataset, 'walkthroughOriginalZoom')) {
      document.body.dataset.walkthroughOriginalZoom = document.body.style.zoom;
    }
    document.body.style.zoom = String(scale);
  }, scale);
}

async function remove_zoom(page) {
  await remove_highlight(page);
  await page.evaluate(() => {
    if (Object.hasOwn(document.body.dataset, 'walkthroughOriginalZoom')) {
      document.body.style.zoom = document.body.dataset.walkthroughOriginalZoom;
      delete document.body.dataset.walkthroughOriginalZoom;
    }
  });
}

async function build_screenshot(page, filename, locator) {
  // Screenshot-only CSS restores overlays afterwards; review the video for capture-time flicker.
  const options = {
    path: filename,
    style: '#__walkthrough_caption, #__walkthrough_highlight { visibility: hidden !important; }',
  };
  if (locator) await locator.screenshot(options);
  else await page.screenshot(options);
}

async function build_example_recording(output_directory, address) {
  const local_address = validate_local_url(address);
  // An existing directory is refused before launching a browser or writing media.
  fs.mkdirSync(output_directory);
  fs.mkdirSync(path.join(output_directory, 'shots'));
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({
      viewport, recordVideo: { dir: path.join(output_directory, 'raw'), size: viewport },
    });
    try {
      const page = await context.newPage();
      await page.goto(local_address);
      await page.locator('body').waitFor();
      // Replace these steps with app-specific ready states, actions, and outcomes.
      await add_caption(page, '1 · Start from the prepared demo screen');
      await build_screenshot(page, path.join(output_directory, 'shots', '01-start.png'));
      const video = page.video();
      await context.close();
      const video_path = await video.path();
      fs.writeFileSync(path.join(output_directory, 'videos.json'), JSON.stringify({ example: video_path }, null, 2));
      return video_path;
    } finally {
      await context.close();
    }
  } finally {
    await browser.close();
  }
}

module.exports = {
  validate_local_url, get_caption_duration, add_caption, add_highlight,
  remove_highlight, add_zoom, remove_zoom, build_screenshot, build_example_recording,
};

if (require.main === module) {
  const output_directory = process.argv[2];
  if (!output_directory || !process.env.APP_URL) {
    console.error('Usage: APP_URL=http://localhost:8000 node capture-template.cjs <new-output-dir>');
    process.exitCode = 1;
  } else {
    build_example_recording(output_directory, process.env.APP_URL)
      .then((video_path) => console.log(video_path))
      .catch((error) => { console.error(error.message); process.exitCode = 1; });
  }
}
