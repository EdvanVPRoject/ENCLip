const form = document.querySelector('#clip-form');
const submitButton = document.querySelector('#submit-button');
const progressPanel = document.querySelector('#progress-panel');
const results = document.querySelector('#results');
const reviewPanel = document.querySelector('#review-panel');
const renderButton = document.querySelector('#render-button');
const addManualButton = document.querySelector('#add-manual-clip');
const fullVideoPlayer = document.querySelector('#full-video-player');
const currentTimeLabel = document.querySelector('#video-current-time');
const totalTimeLabel = document.querySelector('#video-total-time');
const setManualStartButton = document.querySelector('#set-manual-start');
const setManualEndButton = document.querySelector('#set-manual-end');
let activeJobId = null;
let reviewJob = null;
const clipMode = document.querySelector('#clip-mode');
const smartDurationMode = document.querySelector('#smart-duration-mode');
let timer;

clipMode.addEventListener('change', () => {
  document.querySelector('#smart-options').classList.toggle('hidden', clipMode.value !== 'smart');
  document.querySelector('#split-count-options').classList.toggle('hidden', clipMode.value !== 'split_count');
  document.querySelector('#split-duration-options').classList.toggle('hidden', clipMode.value !== 'split_duration');
});

smartDurationMode.addEventListener('change', () => {
  document.querySelector('#smart-fixed-duration-field').classList.toggle('hidden', smartDurationMode.value !== 'fixed');
});

['review-subtitle-style', 'review-aspect-ratio', 'review-framing', 'review-layout'].forEach((id) => {
  document.querySelector(`#${id}`).addEventListener('change', updateSubtitlePreview);
});

renderButton.addEventListener('click', async () => {
  if (!activeJobId) return;
  renderButton.disabled = true;
  reviewPanel.classList.add('hidden');
  progressPanel.classList.remove('hidden');
  document.querySelector('#status-message').textContent = 'Menyiapkan render...';
  try {
    const payload = {
      subtitle_style: document.querySelector('#review-subtitle-style').value,
      aspect_ratio: document.querySelector('#review-aspect-ratio').value,
      framing: document.querySelector('#review-framing').value,
      layout: document.querySelector('#review-layout').value,
    };
    const response = await fetch(`/api/jobs/${activeJobId}/render`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error((await response.json()).detail || 'Tidak dapat memulai render');
    poll(activeJobId);
  } catch (error) {
    renderButton.disabled = false;
    showError(error.message);
  }
});

addManualButton.addEventListener('click', async () => {
  if (!activeJobId) return;
  const start = parseTime(document.querySelector('#manual-start').value);
  const end = parseTime(document.querySelector('#manual-end').value);
  const title = document.querySelector('#manual-title').value.trim() || 'Manual clip';
  const errorBox = document.querySelector('#manual-error');
  errorBox.textContent = '';
  if (start === null || end === null || end <= start) {
    errorBox.textContent = 'Masukkan waktu mulai dan selesai yang valid.';
    return;
  }
  addManualButton.disabled = true;
  try {
    const response = await fetch(`/api/jobs/${activeJobId}/manual-clips`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start, end, title }),
    });
    if (!response.ok) throw new Error((await response.json()).detail || 'Tidak dapat menambahkan clip manual');
    reviewJob = await response.json();
    document.querySelector('#review-info').textContent = `${reviewJob.clips.length} CLIP · TRANSKRIP SIAP`;
    renderReviewClips(reviewJob);
    renderManualClipList(reviewJob);
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    addManualButton.disabled = false;
  }
});

fullVideoPlayer.addEventListener('timeupdate', () => {
  currentTimeLabel.textContent = formatTime(fullVideoPlayer.currentTime);
});
fullVideoPlayer.addEventListener('loadedmetadata', () => {
  totalTimeLabel.textContent = formatTime(fullVideoPlayer.duration);
});
setManualStartButton.addEventListener('click', () => {
  document.querySelector('#manual-start').value = formatTime(fullVideoPlayer.currentTime);
});
setManualEndButton.addEventListener('click', () => {
  document.querySelector('#manual-end').value = formatTime(fullVideoPlayer.currentTime);
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  results.classList.add('hidden');
  progressPanel.classList.remove('hidden');
  submitButton.disabled = true;
  document.querySelector('#error-message').textContent = '';
  const data = Object.fromEntries(new FormData(form));
  data.clip_count = Number(data.clip_count || 0);
  data.min_duration = Number(data.min_duration || 20);
  data.max_duration = Number(data.max_duration || 60);
  data.smart_fixed_duration = Number(data.smart_fixed_duration || 60);
  data.max_clips = Number(data.max_clips || 10);
  data.split_count = Number(data.split_count || 10);
  data.segment_duration = Number(data.segment_duration || 120);
  data.use_local_llm = form.elements.use_local_llm.checked;
  try {
    const response = await fetch('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    if (!response.ok) throw new Error((await response.json()).detail || 'Tidak dapat membuat job');
    const job = await response.json();
    poll(job.id);
  } catch (error) {
    showError(error.message);
  }
});

async function poll(id) {
  clearTimeout(timer);
  try {
    const response = await fetch(`/api/jobs/${id}`);
    const job = await response.json();
    document.querySelector('#status-message').textContent = job.message;
    document.querySelector('#progress-value').textContent = `${job.progress}%`;
    document.querySelector('#progress-bar').style.width = `${job.progress}%`;
    if (job.status === 'awaiting_render') return showReview(job);
    if (job.status === 'completed') return renderResults(job);
    if (job.status === 'failed') return showError(job.error || 'Proses gagal');
    timer = setTimeout(() => poll(id), 900);
  } catch (error) {
    showError(error.message);
  }
}

function renderResults(job) {
  submitButton.disabled = false;
  renderButton.disabled = false;
  reviewPanel.classList.add('hidden');
  results.classList.remove('hidden');
  document.querySelector('#result-count').textContent = `${job.clips.length} CLIP`;
  document.querySelector('#clip-grid').innerHTML = job.clips.map((clip, index) => `
    <article class="clip-card">
      <video controls preload="metadata" src="${clip.video_url}"></video>
      <div class="clip-body"><div class="clip-number">CLIP ${String(index + 1).padStart(2, '0')} · ${formatTime(clip.start)} — ${formatTime(clip.end)}${clip.source === 'manual' ? ' · MANUAL' : ''}</div><h3>${escapeHtml(clip.title)}</h3><p class="clip-caption">${escapeHtml(clip.caption || '')}</p><div class="clip-hashtags">${(clip.hashtags || []).map(escapeHtml).join(' ')}</div><a class="download" href="${clip.video_url}" download>Download MP4 ↗</a></div>
    </article>`).join('');
}

function showReview(job) {
  activeJobId = job.id;
  reviewJob = job;
  submitButton.disabled = true;
  reviewPanel.classList.remove('hidden');
  document.querySelector('#review-info').textContent = `${job.clips.length} CLIP · TRANSKRIP SIAP`;
  document.querySelector('#review-subtitle-style').value = form.elements.subtitle_style.value;
  document.querySelector('#review-aspect-ratio').value = form.elements.aspect_ratio.value;
  document.querySelector('#review-framing').value = form.elements.framing.value;
  document.querySelector('#review-layout').value = form.elements.layout.value;
  fullVideoPlayer.src = job.source_url || '';
  fullVideoPlayer.load();
  updateSubtitlePreview();
  renderReviewClips(job);
  renderManualClipList(job);
}

function updateSubtitlePreview() {
  const style = document.querySelector('#review-subtitle-style').value;
  const preview = document.querySelector('#subtitle-preview');
  preview.className = `subtitle-preview ${style}`;
  const sampleText = reviewJob?.transcript?.[0]?.text || 'Ini contoh tampilan subtitle';
  document.querySelector('#preview-caption').textContent = sampleText;
}

function renderManualClipList(job) {
  const list = document.querySelector('#manual-clip-list');
  const manualClips = (job.clips || []).filter((clip) => clip.source === 'manual');
  list.innerHTML = manualClips.length ? manualClips.map((clip) => `<div class="manual-item"><span><b>${escapeHtml(clip.title)}</b><small>${formatTime(clip.start)} — ${formatTime(clip.end)}</small></span><i>MANUAL</i></div>`).join('') : '<span class="manual-empty">Belum ada clip manual.</span>';
}

function renderReviewClips(job) {
  const grid = document.querySelector('#review-clip-grid');
  grid.innerHTML = (job.clips || []).map((clip, index) => clip.video_url
    ? `<article class="review-clip-card"><video controls preload="metadata" src="${clip.video_url}"></video><div><b>${String(index + 1).padStart(2, '0')} · ${escapeHtml(clip.title)}</b><small>${formatTime(clip.start)} — ${formatTime(clip.end)} · ${clip.source === 'manual' ? 'MANUAL' : 'AI'}</small></div></article>`
    : `<article class="review-clip-card pending"><div><b>${String(index + 1).padStart(2, '0')} · ${escapeHtml(clip.title)}</b><small>${formatTime(clip.start)} — ${formatTime(clip.end)} · MANUAL · akan dirender</small></div></article>`
  ).join('');
}

function showError(message) {
  submitButton.disabled = false;
  document.querySelector('#status-message').textContent = 'Ada yang perlu diperiksa';
  document.querySelector('#error-message').textContent = message;
}
function formatTime(seconds) { return new Date(seconds * 1000).toISOString().slice(14, 19); }
function parseTime(value) {
  const text = String(value).trim();
  if (!text) return null;
  if (/^\d+(\.\d+)?$/.test(text)) return Number(text);
  const parts = text.split(':').map(Number);
  if (parts.some(Number.isNaN) || parts.length > 3) return null;
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return null;
}
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char])); }
