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
    const data = await response.json();
    serviceStatus.textContent = data.ai_enabled
      ? 'Backend ready · optional AI flag enabled'
      : 'Backend ready · CPU mode only';
    serviceStatus.dataset.state = 'ready';
  } catch (error) {
    serviceStatus.textContent = `Backend unavailable · ${error.message || error}`;
    serviceStatus.dataset.state = 'error';
  }
}

async function refreshAiStatus() {
  try {
    const response = await fetch('/api/ai/status');
    if (!response.ok) throw new Error(await readErrorMessage(response));
    const data = await response.json();
    const message = data.enabled
      ? (data.available ? `AI ready · ${data.model_id}` : `AI flag on · ${data.model_id}`)
      : 'AI off · CPU mode only';
    serviceStatus.title = data.message || '';
    if (data.enabled) {
      serviceStatus.textContent = data.available ? `Backend ready · ${data.model_id}` : 'Backend ready · AI flag enabled';
    }
    return message;
  } catch {
    return null;
  }
}

refreshServiceStatus();
refreshAiStatus();

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
    for (const key of ['use_ai', 'remove_background', 'outline', 'shadow', 'smart_prompt']) {
      if (!fd.has(key)) fd.append(key, 'false');
      else fd.set(key, 'true');
    }
    const endpoint = fd.get('use_ai') === 'true' ? '/api/ai/generate' : '/api/generate';
    const res = await fetch(endpoint, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await readErrorMessage(res));
    const data = await res.json();
    const cacheBust = `?t=${Date.now()}`;
    gif.src = data.downloads.gif + cacheBust;
    document.getElementById('dlGif').href = `/download/${data.job_id}/gif`;
    document.getElementById('dlSheet').href = `/download/${data.job_id}/spritesheet`;
    document.getElementById('dlZip').href = `/download/${data.job_id}/zip`;
    downloads.hidden = false;
    statusEl.dataset.state = 'success';
    meta.textContent = JSON.stringify(data, null, 2);
    statusEl.textContent = 'Done.';
  } catch (err) {
    statusEl.dataset.state = 'error';
    statusEl.textContent = 'Error: ' + (err.message || err);
  } finally {
    go.disabled = false;
  }
});
