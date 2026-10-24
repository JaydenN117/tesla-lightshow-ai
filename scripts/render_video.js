// Render a preview.html to MP4 with the song, frame by frame (works headless, no real-time capture).
// usage: node scripts/render_video.js build/<slug>/preview.html build/<slug>/lightshow.wav out.mp4 [fps] [start] [end]
// Needs Playwright (global install is fine) and ffmpeg.
const path = require('path'), fs = require('fs'), os = require('os'), { execFileSync } = require('child_process');
let pw; try { pw = require('playwright'); } catch { pw = require('/opt/node22/lib/node_modules/playwright'); }
(async () => {
  const [html, wav, out, fpsArg, startArg, endArg] = process.argv.slice(2);
  const fps = +(fpsArg || 25);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tlvid-'));
  const browser = await pw.chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.resolve(html));
  await page.waitForTimeout(800);
  const dur = await page.evaluate(() => window.tlPreview.duration);
  const t0 = +(startArg || 0), t1 = Math.min(dur, +(endArg || dur));
  // frame = car stage + transport clock + section overview
  const box = await page.evaluate(() => {
    const a = document.querySelector('header').getBoundingClientRect();
    const b = document.getElementById('overview').getBoundingClientRect();
    return { x: Math.floor(b.left) - 8, y: Math.floor(a.top) - 8, width: Math.ceil(b.width) + 16, height: Math.ceil(b.bottom - a.top) + 16 };
  });
  box.width -= box.width % 2; box.height -= box.height % 2;
  const n = Math.floor((t1 - t0) * fps);
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => window.tlPreview.seek(t), t0 + i / fps);
    await page.screenshot({ path: path.join(dir, `f${String(i).padStart(6, '0')}.jpg`), clip: box, type: 'jpeg', quality: 85 });
    if (i % (fps * 20) === 0) console.log(`frame ${i}/${n}`);
  }
  await browser.close();
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(dir, 'f%06d.jpg'),
    '-ss', String(t0), '-t', String(t1 - t0), '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'veryfast',
    '-crf', '26', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', out], { stdio: 'inherit' });
  fs.rmSync(dir, { recursive: true, force: true });
  console.log('wrote', out);
})();
