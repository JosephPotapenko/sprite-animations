function resolveAssetUrl(assetUrl) {
  if (!assetUrl) return '';
  if (assetUrl.startsWith('data:')) return assetUrl;
  return `${assetUrl}?t=${Date.now()}`;
}

function setDownloadLink(linkId, assetUrl, fallbackHref, filename) {
  const link = document.getElementById(linkId);
  const href = assetUrl || fallbackHref;
  link.href = resolveAssetUrl(href);
  link.download = filename;
}
const form = document.getElementById('form');
const statusEl = document.getElementById('status');
const input = document.getElementById('sprite');
const inputPreview = document.getElementById('inputPreview');
const gif = document.getElementById('gif');
const downloads = document.getElementById('downloads');
const meta = document.getElementById('meta');
const go = document.getElementById('go');
const serviceStatus = document.getElementById('serviceStatus');

async function readErrorMessage(response) {
  const text = await response.text();
  if (!text) return 'Request failed.';
  try {
    const payload = JSON.parse(text);
    return payload.detail || payload.message || text;
  } catch {
    return text;
  }
}

async function refreshServiceStatus() {
  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error(await readErrorMessage(response));
    await response.json();
    serviceStatus.textContent = 'Backend ready · CPU animation mode';
    serviceStatus.dataset.state = 'ready';
  } catch (error) {
    serviceStatus.textContent = `Backend unavailable · ${error.message || error}`;
    serviceStatus.dataset.state = 'error';
  }
}

refreshServiceStatus();

input.addEventListener('change', () => {
  const file = input.files?.[0];
  if (!file) return;
  inputPreview.src = URL.createObjectURL(file);
  inputPreview.hidden = false;
  document.querySelector('#drop span').style.display = 'none';
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  statusEl.textContent = 'Generating...';
  statusEl.dataset.state = 'pending';
  go.disabled = true;
  downloads.hidden = true;
  meta.textContent = '';
  try {
    const fd = new FormData(form);
    for (const key of ['remove_background', 'outline', 'shadow', 'smart_prompt']) {
      if (!fd.has(key)) fd.append(key, 'false');
      else fd.set(key, 'true');
    }
    const res = await fetch('/api/generate', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await readErrorMessage(res));
    const data = await res.json();
    gif.src = resolveAssetUrl(data.downloads?.gif);
    setDownloadLink('dlGif', data.downloads?.gif, `/download/${data.job_id}/gif`, 'spriteforge-preview.gif');
    setDownloadLink('dlSheet', data.downloads?.spritesheet, `/download/${data.job_id}/spritesheet`, 'spriteforge-spritesheet.png');
    setDownloadLink('dlZip', data.downloads?.zip, `/download/${data.job_id}/zip`, 'spriteforge-frames.zip');
    downloads.hidden = false;
    statusEl.dataset.state = 'success';
    meta.textContent = JSON.stringify({
      job_id: data.job_id,
      animation: data.animation,
      frames: data.frames,
      fps: data.fps,
      canvas_size: data.canvas_size,
      downloads: Object.keys(data.downloads || {}),
    }, null, 2);
    statusEl.textContent = 'Done.';
  } catch (err) {
    statusEl.dataset.state = 'error';
    statusEl.textContent = 'Error: ' + (err.message || err);
  } finally {
    go.disabled = false;
  }
});
