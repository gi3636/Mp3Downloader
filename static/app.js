/**
 * YouTube 音乐下载器前端应用
 * 
 * 功能模块:
 * - 下载任务管理 (创建、取消、删除)
 * - 专辑/播放列表选择
 * - 曲目选择 (支持选择性下载)
 * - 实时进度显示
 * - 音乐库管理与播放
 * - Toast 通知系统
 */

// ========== 状态管理 ==========

let currentJobId = null;
let pollTimer = null;
let currentJobTrackId = null;
let libTracks = [];
let libFilteredTracks = [];  // 搜索过滤后的曲目
let libCurrentIndex = -1;
let libShuffle = false;
let choiceResolver = null;
let trackSelectResolver = null;
let selectedTrackUrls = new Set();
let currentPlaylistData = null;
let libSearchQuery = '';  // 当前搜索关键词

// ========== DOM 元素引用 ==========

const $ = (id) => document.getElementById(id);

// 标签页
const elTabDownloadBtn = $('tabDownloadBtn');
const elTabLibraryBtn = $('tabLibraryBtn');
const elTabDownload = $('tabDownload');
const elTabLibrary = $('tabLibrary');
const elLibBadge = $('libBadge');

// 下载页面元素
const elUrlInput = $('urlInput');
const elStartBtn = $('startBtn');
const elCancelBtn = $('cancelBtn');
const elResetBtn = $('resetBtn');
const elAlbumPreview = $('albumPreview');
const elAlbumCover = $('albumCover');
const elAlbumTitle = $('albumTitle');
const elAlbumCount = $('albumCount');
const elAlbumProgress = $('albumProgress');
const elProgressSection = $('progressSection');
const elProgressBar = $('progressBar');
const elProgressValue = $('progressValue');
const elStatusBar = $('statusBar');
const elStatusDot = $('statusDot');
const elStatusText = $('statusText');
const elDownloadedCount = $('downloadedCount');
const elDownloadListCard = $('downloadListCard');
const elDownloadZipBtn = $('downloadZipBtn');
const elJobPlayer = $('jobPlayer');
const elJobTrackList = $('jobTrackList');
const elDownloadItemsCard = $('downloadItemsCard');
const elDownloadItemsList = $('downloadItemsList');
const elDownloadItemsCount = $('downloadItemsCount');

// 音乐库元素
const elLibCount = $('libCount');
const elLibPlayer = $('libPlayer');
const elLibTrackList = $('libTrackList');
const elLibEmpty = $('libEmpty');
const elLibPrevBtn = $('libPrevBtn');
const elLibPlayBtn = $('libPlayBtn');
const elLibNextBtn = $('libNextBtn');
const elLibShuffleBtn = $('libShuffleBtn');

// 专辑选择模态框
const elChoiceModal = $('choiceModal');
const elChoiceBackdrop = $('choiceBackdrop');
const elChoiceCloseBtn = $('choiceCloseBtn');
const elChoiceCancelBtn = $('choiceCancelBtn');
const elChoiceList = $('choiceList');

// 曲目选择模态框
const elTrackSelectModal = $('trackSelectModal');
const elTrackSelectBackdrop = $('trackSelectBackdrop');
const elTrackSelectCloseBtn = $('trackSelectCloseBtn');
const elTrackSelectCancelBtn = $('trackSelectCancelBtn');
const elTrackSelectConfirmBtn = $('trackSelectConfirmBtn');
const elTrackSelectAllBtn = $('trackSelectAllBtn');
const elTrackSelectNoneBtn = $('trackSelectNoneBtn');
const elTrackSelectTitle = $('trackSelectTitle');
const elTrackSelectCount = $('trackSelectCount');
const elTrackSelectTotal = $('trackSelectTotal');
const elTrackSelectList = $('trackSelectList');

// 确认模态框
const elConfirmModal = $('confirmModal');
const elConfirmBackdrop = $('confirmBackdrop');
const elConfirmTitle = $('confirmTitle');
const elConfirmText = $('confirmText');
const elConfirmOkBtn = $('confirmOkBtn');
const elConfirmCancelBtn = $('confirmCancelBtn');

// 搜索框
const elLibSearchInput = $('libSearchInput');
const elLibSearchClearBtn = $('libSearchClearBtn');

const elToastContainer = $('toastContainer');

// ========== 工具函数 ==========

function formatDuration(seconds) {
  if (typeof seconds !== 'number' || isNaN(seconds)) return '--:--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function refreshIcons() {
  if (window.lucide?.createIcons) {
    window.lucide.createIcons();
  }
}

function setButtonLoading(btn, loading, text = '处理中...') {
  if (!btn) return;
  if (loading) {
    btn.classList.add('btn-loading');
    btn.disabled = true;
    if (!btn.dataset.originalHtml) {
      btn.dataset.originalHtml = btn.innerHTML;
    }
    btn.innerHTML = `<span class="spinner"></span><span>${text}</span>`;
  } else {
    btn.classList.remove('btn-loading');
    if (btn.dataset.originalHtml) {
      btn.innerHTML = btn.dataset.originalHtml;
      delete btn.dataset.originalHtml;
    }
  }
  refreshIcons();
}

// ========== Toast 通知系统 ==========

function toast(message, type = 'info') {
  const iconMap = { success: 'check-circle', error: 'alert-circle', info: 'info' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `
    <i data-lucide="${iconMap[type] || 'info'}" class="toast-icon"></i>
    <span class="toast-message">${message}</span>
  `;
  elToastContainer.appendChild(el);
  refreshIcons();
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(20px)';
    el.style.transition = 'all 0.3s ease';
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

// ========== 确认对话框 ==========

function confirm({ title, text, okText = '确定', cancelText = '取消' }) {
  return new Promise((resolve) => {
    elConfirmTitle.textContent = title;
    elConfirmText.textContent = text;
    elConfirmOkBtn.textContent = okText;
    elConfirmCancelBtn.textContent = cancelText;
    const cleanup = () => {
      elConfirmModal.classList.remove('visible');
      elConfirmOkBtn.onclick = null;
      elConfirmCancelBtn.onclick = null;
      elConfirmBackdrop.onclick = null;
    };
    elConfirmOkBtn.onclick = () => { cleanup(); resolve(true); };
    elConfirmCancelBtn.onclick = () => { cleanup(); resolve(false); };
    elConfirmBackdrop.onclick = () => { cleanup(); resolve(false); };
    elConfirmModal.classList.add('visible');
  });
}

// ========== 专辑选择模态框 ==========

function showChoiceModal(choices) {
  return new Promise((resolve) => {
    choiceResolver = resolve;
    elChoiceList.innerHTML = '';
    choices.forEach((item) => {
      const el = document.createElement('div');
      el.className = 'choice-item';
      el.innerHTML = `
        <div class="choice-title">${item.title || item.url}</div>
        <div class="choice-url">${item.url}</div>
      `;
      el.onclick = () => { hideChoiceModal(); resolve(item.url); };
      elChoiceList.appendChild(el);
    });
    elChoiceModal.classList.add('visible');
  });
}

function hideChoiceModal() {
  elChoiceModal.classList.remove('visible');
  if (choiceResolver) { choiceResolver(null); choiceResolver = null; }
}

// ========== 曲目选择模态框 ==========

function showTrackSelectModal(playlistData) {
  return new Promise((resolve) => {
    trackSelectResolver = resolve;
    currentPlaylistData = playlistData;
    selectedTrackUrls = new Set();
    
    // 设置标题
    elTrackSelectTitle.textContent = playlistData.title || '选择要下载的曲目';
    elTrackSelectTotal.textContent = `共 ${playlistData.total || 0} 首`;
    updateTrackSelectCount();
    
    // 渲染曲目列表
    renderTrackSelectList(playlistData.entries || []);
    
    elTrackSelectModal.classList.add('visible');
  });
}

function hideTrackSelectModal() {
  elTrackSelectModal.classList.remove('visible');
  if (trackSelectResolver) {
    trackSelectResolver(null);
    trackSelectResolver = null;
  }
  currentPlaylistData = null;
  selectedTrackUrls.clear();
}

function updateTrackSelectCount() {
  const count = selectedTrackUrls.size;
  elTrackSelectCount.textContent = `已选择 ${count} 首`;
  elTrackSelectConfirmBtn.disabled = count === 0;
}

function renderTrackSelectList(entries) {
  elTrackSelectList.innerHTML = '';
  
  // 获取播放列表封面作为默认封面
  const defaultCover = currentPlaylistData?.thumbnail || '';
  
  entries.forEach((entry, idx) => {
    const el = document.createElement('div');
    el.className = 'track-select-item';
    el.dataset.url = entry.url || '';
    el.dataset.index = idx;
    
    const coverUrl = entry.thumbnail || defaultCover;
    
    el.innerHTML = `
      <div class="track-select-checkbox">
        <i data-lucide="check"></i>
      </div>
      <img class="track-select-cover" src="${coverUrl}" alt="" onerror="this.style.display='none'" />
      <span class="track-select-index">${entry.index || idx + 1}</span>
      <div class="track-select-info">
        <div class="track-select-title">${entry.title || `Track ${idx + 1}`}</div>
      </div>
      <span class="track-select-duration">${formatDuration(entry.duration)}</span>
    `;
    
    el.onclick = () => toggleTrackSelection(el, entry.url);
    elTrackSelectList.appendChild(el);
  });
  
  refreshIcons();
}

function toggleTrackSelection(el, url) {
  if (!url) return;
  
  if (selectedTrackUrls.has(url)) {
    selectedTrackUrls.delete(url);
    el.classList.remove('selected');
  } else {
    selectedTrackUrls.add(url);
    el.classList.add('selected');
  }
  
  updateTrackSelectCount();
}

function selectAllTracks() {
  if (!currentPlaylistData?.entries) return;
  
  // 只选择有有效 URL 的条目
  currentPlaylistData.entries.forEach((entry) => {
    if (entry.url) selectedTrackUrls.add(entry.url);
  });
  
  document.querySelectorAll('.track-select-item').forEach((el) => {
    if (el.dataset.url) {
      el.classList.add('selected');
    }
  });
  
  updateTrackSelectCount();
}

function selectNoTracks() {
  selectedTrackUrls.clear();
  
  document.querySelectorAll('.track-select-item').forEach((el) => {
    el.classList.remove('selected');
  });
  
  updateTrackSelectCount();
}

function confirmTrackSelection() {
  if (selectedTrackUrls.size === 0) return;
  
  const urls = Array.from(selectedTrackUrls);
  
  // 获取对应的标题
  const titles = [];
  if (currentPlaylistData?.entries) {
    urls.forEach(url => {
      const entry = currentPlaylistData.entries.find(e => e.url === url);
      titles.push(entry?.title || '');
    });
  }
  
  hideTrackSelectModal();
  
  if (trackSelectResolver) {
    const resolver = trackSelectResolver;
    trackSelectResolver = null;
    resolver({ urls, titles });
  }
}

// ========== UI 状态更新 ==========

function updateButtonStates(isRunning) {
  elStartBtn.disabled = isRunning;
  elCancelBtn.disabled = !isRunning;
  elResetBtn.disabled = !currentJobId;
}

function updateAlbumPreview(meta) {
  if (!meta || (!meta.title && !meta.thumbnail_url)) {
    elAlbumPreview.classList.remove('visible');
    return;
  }
  elAlbumPreview.classList.add('visible');
  if (meta.thumbnail_url) {
    elAlbumCover.src = meta.thumbnail_url;
    elAlbumCover.style.display = 'block';
  } else {
    elAlbumCover.style.display = 'none';
  }
  elAlbumTitle.textContent = meta.title || '未知专辑';
  const total = meta.total_items || 0;
  const current = meta.current_item || 0;
  const downloaded = meta.downloaded_count || 0;
  elAlbumCount.innerHTML = `<i data-lucide="music"></i> <span>${total} 首</span>`;
  if (current > 0 && total > 0) {
    elAlbumProgress.innerHTML = `<i data-lucide="download"></i> <span>${current}/${total}</span>`;
  } else if (downloaded > 0) {
    elAlbumProgress.innerHTML = `<i data-lucide="check"></i> <span>已下载 ${downloaded} 首</span>`;
  } else {
    elAlbumProgress.innerHTML = `<i data-lucide="loader"></i> <span>准备中</span>`;
  }
  refreshIcons();
}

function updateProgress(percent) {
  const p = Math.max(0, Math.min(100, percent || 0));
  elProgressBar.style.width = `${p}%`;
  elProgressValue.textContent = `${p.toFixed(1)}%`;
  elProgressSection.style.display = 'block';
}

function updateStatus(status, downloaded = 0) {
  elStatusBar.style.display = 'flex';
  elStatusText.textContent = getStatusText(status);
  elDownloadedCount.textContent = downloaded;
  elStatusDot.className = 'status-dot';
  if (status === 'running' || status === 'canceling') elStatusDot.classList.add('running');
  else if (status === 'error') elStatusDot.classList.add('error');
  else if (status === 'done') elStatusDot.classList.add('done');
}

function getStatusText(status) {
  const map = { queued: '排队中', running: '下载中', done: '已完成', error: '出错', canceled: '已取消', canceling: '取消中' };
  return map[status] || status || '-';
}

function resetDownloadUI() {
  elUrlInput.value = '';
  elAlbumPreview.classList.remove('visible');
  elProgressSection.style.display = 'none';
  elProgressBar.style.width = '0%';
  elProgressValue.textContent = '0%';
  elStatusBar.style.display = 'none';
  elDownloadListCard.style.display = 'none';
  elDownloadZipBtn.style.display = 'none';
  elJobTrackList.innerHTML = '';
  elJobPlayer.removeAttribute('src');
  elDownloadItemsCard.style.display = 'none';
  elDownloadItemsList.innerHTML = '';
  currentJobTrackId = null;
  updateButtonStates(false);
}

// ========== 下载项列表渲染 ==========

function renderDownloadItems(items) {
  if (!items || items.length === 0) {
    elDownloadItemsCard.style.display = 'none';
    return;
  }
  
  elDownloadItemsCard.style.display = 'block';
  
  // 统计
  const doneCount = items.filter(i => i.status === 'done').length;
  elDownloadItemsCount.textContent = `${doneCount}/${items.length}`;
  
  elDownloadItemsList.innerHTML = '';
  
  items.forEach((item) => {
    const el = document.createElement('div');
    el.className = `download-item ${item.status}`;
    
    const statusText = {
      pending: '等待中',
      downloading: `${item.progress?.toFixed(0) || 0}%`,
      done: '完成',
      error: '失败',
      skipped: '跳过'
    }[item.status] || item.status;
    
    const showProgress = item.status === 'downloading';
    
    el.innerHTML = `
      <div class="download-item-index">${item.index}</div>
      <div class="download-item-info">
        <div class="download-item-title">${item.title || `Track ${item.index}`}</div>
        ${showProgress ? `
          <div class="download-item-progress">
            <div class="download-item-progress-bar" style="width: ${item.progress || 0}%"></div>
          </div>
        ` : ''}
      </div>
      <span class="download-item-status">${statusText}</span>
    `;
    
    elDownloadItemsList.appendChild(el);
  });
  
  // 滚动到当前下载项
  const downloadingItem = elDownloadItemsList.querySelector('.download-item.downloading');
  if (downloadingItem) {
    downloadingItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

// ========== 曲目列表渲染 ==========

function renderTrackList({ container, tracks, playingId, onPlay, onDelete }) {
  container.innerHTML = '';
  if (!tracks || tracks.length === 0) {
    container.innerHTML = `<div class="empty-state"><i data-lucide="music"></i><p>暂无曲目</p></div>`;
    refreshIcons();
    return;
  }
  tracks.forEach((track, index) => {
    const isPlaying = track.id === playingId;
    const el = document.createElement('div');
    el.className = `track-item${isPlaying ? ' playing' : ''}`;
    el.innerHTML = `
      <img class="track-cover" src="${track.cover_url || ''}" alt="" onerror="this.style.display='none'" />
      <div class="track-info">
        <div class="track-title">${track.title || `Track ${index + 1}`}</div>
        <div class="track-duration">${formatDuration(track.duration_seconds)}</div>
      </div>
      ${isPlaying ? '<span class="track-status">播放中</span>' : ''}
      <div class="track-actions">
        <button class="track-btn delete" title="删除"><i data-lucide="trash-2"></i></button>
      </div>
    `;
    el.onclick = (e) => {
      if (e.target.closest('.track-btn')) return;
      if (onPlay) onPlay(track, index);
    };
    const deleteBtn = el.querySelector('.track-btn.delete');
    deleteBtn.onclick = async (e) => {
      e.stopPropagation();
      const ok = await confirm({ title: '删除歌曲', text: `确定要删除「${track.title}」吗？`, okText: '删除' });
      if (ok && onDelete) await onDelete(track, index);
    };
    container.appendChild(el);
  });
  refreshIcons();
}

// ========== 下载任务管理 ==========

async function fetchJobTracks() {
  if (!currentJobId) return [];
  try {
    const res = await fetch(`/api/jobs/${currentJobId}/tracks`);
    const data = await res.json();
    return res.ok ? (data.tracks || []) : [];
  } catch { return []; }
}

async function updateJobTracks() {
  const tracks = await fetchJobTracks();
  if (tracks.length > 0) elDownloadListCard.style.display = 'block';
  renderTrackList({
    container: elJobTrackList,
    tracks,
    playingId: currentJobTrackId,
    onPlay: (track) => {
      currentJobTrackId = track.id;
      elJobPlayer.src = track.stream_url;
      elJobPlayer.play();
      updateJobTracks();
    },
    onDelete: async (track) => {
      await fetch(`/api/jobs/${currentJobId}/tracks/${track.id}/delete`, { method: 'POST' });
      toast('已删除', 'success');
      await updateJobTracks();
      await pollJob();
    }
  });
}

async function pollJob() {
  if (!currentJobId) return;
  try {
    const res = await fetch(`/api/jobs/${currentJobId}`);
    const data = await res.json();
    if (!res.ok) {
      clearInterval(pollTimer);
      pollTimer = null;
      updateButtonStates(false);
      return;
    }
    updateAlbumPreview(data.meta);
    updateProgress(data.progress);
    updateStatus(data.status, data.meta?.downloaded_count || 0);
    
    // 渲染下载项列表
    renderDownloadItems(data.download_items);
    
    await updateJobTracks();
    const isRunning = ['running', 'queued', 'canceling'].includes(data.status);
    updateButtonStates(isRunning);
    if (data.status === 'done') {
      clearInterval(pollTimer);
      pollTimer = null;
      if (data.download_url) {
        elDownloadZipBtn.href = data.download_url;
        elDownloadZipBtn.style.display = 'inline-flex';
      }
      toast('下载完成！', 'success');
      refreshLibrary();
    }
    if (data.status === 'error') {
      clearInterval(pollTimer);
      pollTimer = null;
      toast(data.message || '下载失败', 'error');
    }
    if (data.status === 'canceled') {
      clearInterval(pollTimer);
      pollTimer = null;
      if (data.download_url) {
        elDownloadZipBtn.href = data.download_url;
        elDownloadZipBtn.style.display = 'inline-flex';
      }
      toast('已取消下载', 'info');
    }
  } catch (err) {
    console.error('Poll error:', err);
  }
}

async function startDownload() {
  const url = elUrlInput.value.trim();
  if (!url) { toast('请输入 YouTube 链接', 'error'); return; }

  elDownloadZipBtn.style.display = 'none';
  elDownloadListCard.style.display = 'none';
  elDownloadItemsCard.style.display = 'none';
  updateAlbumPreview(null);
  updateProgress(0);
  updateButtonStates(true);
  setButtonLoading(elStartBtn, true, '解析中...');

  try {
    // 解析链接
    const resolveRes = await fetch('/api/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const resolveData = await resolveRes.json();
    if (!resolveRes.ok) throw new Error(resolveData.error || '解析链接失败');

    let targetUrl = resolveData.url;
    let videoUrls = null;
    let videoTitles = null;

    // 播放列表模式 - 显示曲目选择
    if (resolveData.mode === 'playlist' && resolveData.playlist) {
      setButtonLoading(elStartBtn, false);
      updateButtonStates(false);
      
      const selection = await showTrackSelectModal(resolveData.playlist);
      if (!selection || !selection.urls || selection.urls.length === 0) return;
      
      videoUrls = selection.urls;
      videoTitles = selection.titles;
      updateButtonStates(true);
      setButtonLoading(elStartBtn, true, '创建任务...');
    }
    // 多专辑选择模式
    else if (resolveData.mode === 'choose' && resolveData.choices?.length > 0) {
      setButtonLoading(elStartBtn, false);
      updateButtonStates(false);
      
      targetUrl = await showChoiceModal(resolveData.choices);
      if (!targetUrl) return;
      
      // 选择专辑后，再获取曲目列表
      updateButtonStates(true);
      setButtonLoading(elStartBtn, true, '获取曲目...');
      
      const playlistRes = await fetch('/api/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: targetUrl })
      });
      const playlistData = await playlistRes.json();
      
      if (playlistRes.ok && playlistData.mode === 'playlist' && playlistData.playlist) {
        setButtonLoading(elStartBtn, false);
        updateButtonStates(false);
        
        const selection = await showTrackSelectModal(playlistData.playlist);
        if (!selection || !selection.urls || selection.urls.length === 0) return;
        
        videoUrls = selection.urls;
        videoTitles = selection.titles;
        updateButtonStates(true);
        setButtonLoading(elStartBtn, true, '创建任务...');
      }
    }

    // 创建下载任务
    const jobBody = { url: targetUrl || url };
    if (videoUrls && videoUrls.length > 0) {
      jobBody.video_urls = videoUrls;
      jobBody.video_titles = videoTitles;
    }
    
    const jobRes = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(jobBody)
    });
    const jobData = await jobRes.json();
    if (!jobRes.ok) throw new Error(jobData.error || '创建任务失败');

    currentJobId = jobData.job_id;
    toast('开始下载', 'success');
    pollTimer = setInterval(pollJob, 1000);
    await pollJob();
  } catch (err) {
    toast(err.message || '操作失败', 'error');
    updateButtonStates(false);
  } finally {
    setButtonLoading(elStartBtn, false);
  }
}

async function cancelDownload() {
  if (!currentJobId) return;
  setButtonLoading(elCancelBtn, true, '取消中...');
  try {
    await fetch(`/api/jobs/${currentJobId}/cancel`, { method: 'POST' });
    toast('正在取消...', 'info');
    await pollJob();
  } catch (err) {
    toast('取消失败', 'error');
  } finally {
    setButtonLoading(elCancelBtn, false);
  }
}

async function deleteJob() {
  if (!currentJobId) { resetDownloadUI(); return; }
  const ok = await confirm({ title: '删除任务', text: '确定要删除此任务及其所有已下载文件吗？', okText: '删除' });
  if (!ok) return;
  setButtonLoading(elResetBtn, true, '删除中...');
  try {
    await fetch(`/api/jobs/${currentJobId}/delete`, { method: 'POST' });
    toast('任务已删除', 'success');
    currentJobId = null;
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    resetDownloadUI();
    refreshLibrary();
  } catch (err) {
    toast('删除失败', 'error');
  } finally {
    setButtonLoading(elResetBtn, false);
  }
}

// ========== 音乐库管理 ==========

async function refreshLibrary() {
  try {
    const res = await fetch('/api/library/tracks');
    const data = await res.json();
    if (!res.ok) { toast(data.error || '加载音乐库失败', 'error'); return; }
    libTracks = data.tracks || [];
    
    // 应用搜索过滤
    filterLibraryTracks();
    
    elLibCount.textContent = `${libTracks.length} 首歌曲`;
    if (libTracks.length > 0) {
      elLibBadge.textContent = libTracks.length;
      elLibBadge.style.display = 'inline';
    } else {
      elLibBadge.style.display = 'none';
    }
    
    renderLibraryList();
  } catch (err) {
    console.error('Refresh library error:', err);
  }
}

function filterLibraryTracks() {
  const query = libSearchQuery.toLowerCase().trim();
  
  if (!query) {
    libFilteredTracks = [...libTracks];
  } else {
    libFilteredTracks = libTracks.filter(track => {
      const title = (track.title || '').toLowerCase();
      return title.includes(query);
    });
  }
}

function renderLibraryList() {
  const tracks = libFilteredTracks;
  const isSearching = libSearchQuery.trim().length > 0;
  
  // 显示/隐藏空状态
  elLibEmpty.style.display = libTracks.length === 0 ? 'block' : 'none';
  elLibTrackList.style.display = tracks.length > 0 || isSearching ? 'flex' : 'none';
  
  // 检查当前播放索引
  if (libCurrentIndex >= libTracks.length) {
    libCurrentIndex = -1;
    elLibPlayer.removeAttribute('src');
    updatePlayButton(false);
  }
  
  // 搜索结果提示
  let searchInfo = elLibTrackList.previousElementSibling;
  if (searchInfo?.classList.contains('search-result-info')) {
    searchInfo.remove();
  }
  
  if (isSearching) {
    const info = document.createElement('div');
    info.className = 'search-result-info';
    info.textContent = `找到 ${tracks.length} 首匹配的歌曲`;
    elLibTrackList.parentNode.insertBefore(info, elLibTrackList);
  }
  
  // 渲染列表
  renderTrackList({
    container: elLibTrackList,
    tracks,
    playingId: libTracks[libCurrentIndex]?.id,
    onPlay: (track) => {
      // 找到在原始列表中的索引
      const originalIndex = libTracks.findIndex(t => t.id === track.id);
      if (originalIndex >= 0) playLibTrack(originalIndex);
    },
    onDelete: async (track) => {
      await fetch(`/api/library/tracks/${track.id}/delete`, { method: 'POST' });
      toast('已删除', 'success');
      await refreshLibrary();
    }
  });
}

function handleLibrarySearch() {
  libSearchQuery = elLibSearchInput.value;
  elLibSearchClearBtn.style.display = libSearchQuery ? 'flex' : 'none';
  filterLibraryTracks();
  renderLibraryList();
}

function clearLibrarySearch() {
  libSearchQuery = '';
  elLibSearchInput.value = '';
  elLibSearchClearBtn.style.display = 'none';
  filterLibraryTracks();
  renderLibraryList();
}

function playLibTrack(index) {
  if (!libTracks.length || index < 0 || index >= libTracks.length) return;
  libCurrentIndex = index;
  elLibPlayer.src = libTracks[index].stream_url;
  elLibPlayer.play();
  updatePlayButton(true);
  renderLibraryList();
}

function getNextIndex() {
  if (!libTracks.length) return -1;
  if (libShuffle) {
    if (libTracks.length === 1) return 0;
    let next;
    do { next = Math.floor(Math.random() * libTracks.length); } while (next === libCurrentIndex);
    return next;
  }
  return (libCurrentIndex + 1) % libTracks.length;
}

function getPrevIndex() {
  if (!libTracks.length) return -1;
  if (libShuffle) return getNextIndex();
  return (libCurrentIndex - 1 + libTracks.length) % libTracks.length;
}

function updatePlayButton(isPlaying) {
  elLibPlayBtn.innerHTML = `<i data-lucide="${isPlaying ? 'pause' : 'play'}"></i>`;
  refreshIcons();
}

function updateShuffleButton() {
  elLibShuffleBtn.classList.toggle('active', libShuffle);
}

function switchTab(tab) {
  const isDownload = tab === 'download';
  elTabDownload.style.display = isDownload ? 'block' : 'none';
  elTabLibrary.style.display = isDownload ? 'none' : 'block';
  elTabDownloadBtn.classList.toggle('active', isDownload);
  elTabLibraryBtn.classList.toggle('active', !isDownload);
  if (!isDownload) refreshLibrary();
}

// ========== 事件绑定 ==========

// 标签页切换
elTabDownloadBtn.onclick = () => switchTab('download');
elTabLibraryBtn.onclick = () => switchTab('library');

// 下载操作
elStartBtn.onclick = startDownload;
elCancelBtn.onclick = cancelDownload;
elResetBtn.onclick = deleteJob;

// 专辑选择模态框
elChoiceBackdrop.onclick = hideChoiceModal;
elChoiceCloseBtn.onclick = hideChoiceModal;
elChoiceCancelBtn.onclick = hideChoiceModal;

// 曲目选择模态框
elTrackSelectBackdrop.onclick = hideTrackSelectModal;
elTrackSelectCloseBtn.onclick = hideTrackSelectModal;
elTrackSelectCancelBtn.onclick = hideTrackSelectModal;
elTrackSelectConfirmBtn.onclick = confirmTrackSelection;
elTrackSelectAllBtn.onclick = selectAllTracks;
elTrackSelectNoneBtn.onclick = selectNoTracks;

// 音乐库搜索
elLibSearchInput.oninput = handleLibrarySearch;
elLibSearchClearBtn.onclick = clearLibrarySearch;

// 音乐库播放控制
elLibPrevBtn.onclick = () => { const idx = getPrevIndex(); if (idx >= 0) playLibTrack(idx); };
elLibNextBtn.onclick = () => { const idx = getNextIndex(); if (idx >= 0) playLibTrack(idx); };
elLibPlayBtn.onclick = async () => {
  if (!libTracks.length) await refreshLibrary();
  if (!libTracks.length) return;
  if (elLibPlayer.paused) {
    if (!elLibPlayer.src || libCurrentIndex < 0) playLibTrack(0);
    else { elLibPlayer.play(); updatePlayButton(true); }
  } else {
    elLibPlayer.pause();
    updatePlayButton(false);
  }
};
elLibShuffleBtn.onclick = () => {
  libShuffle = !libShuffle;
  updateShuffleButton();
  toast(libShuffle ? '随机播放已开启' : '随机播放已关闭', 'info');
};

// 播放器事件
elLibPlayer.onended = () => { const idx = getNextIndex(); if (idx >= 0) playLibTrack(idx); };
elLibPlayer.onplay = () => updatePlayButton(true);
elLibPlayer.onpause = () => updatePlayButton(false);

// ========== 初始化 ==========

function init() {
  updateButtonStates(false);
  updateShuffleButton();
  updatePlayButton(false);
  refreshIcons();
  switchTab('download');
  refreshLibrary();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}