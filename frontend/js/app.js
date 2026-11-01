// Bklit YouTube Downloader - Pure Native JavaScript Core
// Zero external framework dependencies, 100% stable & offline-ready

(function () {
  'use strict';

  // Application State
  const state = {
    tasks: [],
    stats: { total: 0, downloading: 0, queued: 0, completed: 0, failed: 0, total_downloaded_str: "0 B" },
    libraryFiles: [],
    activeFilter: 'all', // 'all', 'downloading', 'queued', 'completed', 'failed', 'library'
    searchQuery: '',
    nextIndex: 1,
    downloadDir: '',
    proxy: '',
    isDark: true,
  };

  // DOM Elements
  const el = {
    urlInput: document.getElementById('urlInput'),
    urlCountBadge: document.getElementById('urlCountBadge'),
    qualitySelect: document.getElementById('qualitySelect'),
    formatSelect: document.getElementById('formatSelect'),
    startIndexInput: document.getElementById('startIndexInput'),
    expandPlaylistsCheck: document.getElementById('expandPlaylistsCheck'),
    startDownloadBtn: document.getElementById('startDownloadBtn'),
    taskList: document.getElementById('taskList'),
    librarySection: document.getElementById('librarySection'),
    libraryList: document.getElementById('libraryList'),
    tasksSection: document.getElementById('tasksSection'),
    searchFilter: document.getElementById('searchFilter'),
    toast: document.getElementById('toast'),
    toastMsg: document.getElementById('toastMsg'),
    themeToggleBtn: document.getElementById('themeToggleBtn'),
    openFolderBtn: document.getElementById('openFolderBtn'),
    sidebarOpenFolderBtn: document.getElementById('sidebarOpenFolderBtn'),
    clearCompletedBtn: document.getElementById('clearCompletedBtn'),
    topClearCompletedBtn: document.getElementById('topClearCompletedBtn'),
    pasteBtn: document.getElementById('pasteBtn'),
    sampleBtn: document.getElementById('sampleBtn'),
    clearInputBtn: document.getElementById('clearInputBtn'),
    refreshLibraryBtn: document.getElementById('refreshLibraryBtn'),
    nextIndexBadge: document.getElementById('nextIndexBadge'),
    statDownloading: document.getElementById('statDownloading'),
    statQueued: document.getElementById('statQueued'),
    statCompleted: document.getElementById('statCompleted'),
    statLibraryCount: document.getElementById('statLibraryCount'),
    countAll: document.getElementById('countAll'),
    countDownloading: document.getElementById('countDownloading'),
    countQueued: document.getElementById('countQueued'),
    countCompleted: document.getElementById('countCompleted'),
    countFailed: document.getElementById('countFailed'),
    countLibrary: document.getElementById('countLibrary'),
    activeFilterTitle: document.getElementById('activeFilterTitle'),
    proxyStatusBadge: document.getElementById('proxyStatusBadge'),
  };

  // --- Theme Management ---
  function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) {
      state.isDark = saved === 'dark';
    } else {
      state.isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    applyTheme();
  }

  function applyTheme() {
    if (state.isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }

  function toggleTheme() {
    state.isDark = !state.isDark;
    applyTheme();
  }

  // --- Toast Notifications ---
  let toastTimer = null;
  function showToast(message, type = 'info') {
    if (!el.toast) return;
    clearTimeout(toastTimer);
    el.toastMsg.textContent = message;

    // Reset colors
    el.toast.className = 'fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-xl text-xs font-semibold transition-all duration-300';
    if (type === 'success') {
      el.toast.classList.add('bg-emerald-600', 'text-white', 'border-emerald-500');
    } else if (type === 'warning') {
      el.toast.classList.add('bg-amber-600', 'text-white', 'border-amber-500');
    } else if (type === 'danger') {
      el.toast.classList.add('bg-rose-600', 'text-white', 'border-rose-500');
    } else {
      el.toast.classList.add('bg-card', 'border-border', 'text-textPrimary');
    }

    el.toast.style.display = 'flex';
    toastTimer = setTimeout(() => {
      el.toast.style.display = 'none';
    }, 3500);
  }

  // --- API Requests ---
  async function fetchTasks() {
    try {
      const res = await fetch('/api/tasks');
      if (res.ok) {
        const data = await res.json();
        state.tasks = data.tasks || [];
        state.stats = data.stats || state.stats;
        renderStats();
        renderTasks();
      }
    } catch (e) {
      console.warn('fetchTasks failed:', e);
    }
  }

  async function fetchConfig() {
    try {
      const res = await fetch('/api/config');
      if (res.ok) {
        const data = await res.json();
        state.downloadDir = data.config.download_dir;
        state.proxy = data.config.proxy || '';
        if (data.system && data.system.next_index) {
          state.nextIndex = data.system.next_index;
          updateNextIndexUI();
        }
        if (el.proxyStatusBadge) {
          if (state.proxy) {
            el.proxyStatusBadge.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-500 border border-blue-500/20';
            el.proxyStatusBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span> 代理: ${escapeHtml(state.proxy)}`;
          } else {
            el.proxyStatusBadge.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted text-textMuted border border-border';
            el.proxyStatusBadge.innerHTML = '直连模式';
          }
        }
      }
    } catch (e) {
      console.warn('fetchConfig failed:', e);
    }
  }

  async function fetchLibrary() {
    try {
      const res = await fetch('/api/library');
      if (res.ok) {
        const data = await res.json();
        state.libraryFiles = data.files || [];
        renderLibrary();
        if (el.statLibraryCount) el.statLibraryCount.textContent = `${state.libraryFiles.length} 部`;
        if (el.countLibrary) el.countLibrary.textContent = state.libraryFiles.length;
      }
    } catch (e) {
      console.warn('fetchLibrary failed:', e);
    }
  }

  async function startDownload() {
    const raw = el.urlInput.value.trim();
    const urls = raw.split('\n').map(u => u.trim()).filter(u => u.length > 0);

    if (urls.length === 0) {
      showToast('请在输入框中粘贴 YouTube 视频链接', 'warning');
      el.urlInput.focus();
      return;
    }

    const sVal = el.startIndexInput.value.trim();
    const startIndex = sVal ? parseInt(sVal, 10) : null;

    el.startDownloadBtn.disabled = true;
    el.startDownloadBtn.innerHTML = `
      <svg class="w-4 h-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      正在提交任务...
    `;

    try {
      const res = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          urls: urls,
          quality: el.qualitySelect.value,
          format: el.formatSelect.value,
          expand_playlists: el.expandPlaylistsCheck.checked,
          start_index: startIndex,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        showToast(data.message || `成功创建 ${data.tasks.length} 个下载任务`, 'success');
        el.urlInput.value = '';
        el.startIndexInput.value = '';
        updateUrlCount();
        fetchTasks();
        fetchConfig();
        // Switch to all tasks tab
        setActiveFilter('all');
      } else {
        showToast(data.detail || '添加下载任务失败', 'danger');
      }
    } catch (e) {
      showToast('请求失败: ' + e.message, 'danger');
    } finally {
      el.startDownloadBtn.disabled = false;
      el.startDownloadBtn.innerHTML = `
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        立即开始批量下载
      `;
    }
  }

  async function cancelTask(taskId) {
    try {
      const res = await fetch(`/api/tasks/${taskId}/cancel`, { method: 'POST' });
      if (res.ok) {
        showToast('已取消下载任务', 'info');
      }
    } catch (e) {
      showToast('取消失败: ' + e.message, 'danger');
    }
  }

  async function retryTask(taskId) {
    try {
      const res = await fetch(`/api/tasks/${taskId}/retry`, { method: 'POST' });
      if (res.ok) {
        showToast('任务已重新排队', 'success');
      }
    } catch (e) {
      showToast('重试失败: ' + e.message, 'danger');
    }
  }

  async function deleteTask(taskId) {
    try {
      const res = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
      if (res.ok) {
        state.tasks = state.tasks.filter(t => t.id !== taskId);
        renderStats();
        renderTasks();
        showToast('任务已删除', 'info');
      }
    } catch (e) {
      showToast('删除失败: ' + e.message, 'danger');
    }
  }

  async function clearCompleted() {
    try {
      const res = await fetch('/api/tasks/clear-completed', { method: 'POST' });
      if (res.ok) {
        state.tasks = state.tasks.filter(t => !['completed', 'failed', 'cancelled'].includes(t.status));
        renderStats();
        renderTasks();
        showToast('已清理所有完成及停止的任务', 'info');
      }
    } catch (e) {
      showToast('清理失败: ' + e.message, 'danger');
    }
  }

  async function openTaskLocation(taskId) {
    try {
      const res = await fetch(`/api/tasks/${taskId}/open`, { method: 'POST' });
      if (res.ok) {
        showToast('已在 Windows 资源管理器中定位', 'success');
      } else {
        showToast('定位失败，请确保文件存在', 'danger');
      }
    } catch (e) {
      showToast('打开失败: ' + e.message, 'danger');
    }
  }

  async function openFile(filePath) {
    try {
      const res = await fetch('/api/open-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath }),
      });
      if (res.ok) {
        showToast('已在资源管理器中定位文件', 'success');
      }
    } catch (e) {
      showToast('操作失败: ' + e.message, 'danger');
    }
  }

  async function openDownloadFolder() {
    try {
      const res = await fetch('/api/open-folder', { method: 'POST' });
      if (res.ok) {
        showToast('已打开下载目录', 'success');
      }
    } catch (e) {
      showToast('无法打开目录: ' + e.message, 'danger');
    }
  }

  // --- Real-time SSE Connection ---
  function setupSSE() {
    try {
      const es = new EventSource('/api/events');
      es.addEventListener('task_update', (e) => {
        try {
          const updated = JSON.parse(e.data);
          const idx = state.tasks.findIndex(t => t.id === updated.id);
          if (idx !== -1) {
            state.tasks[idx] = updated;
          } else {
            state.tasks.unshift(updated);
          }
          renderStats();
          renderTasks();
          if (updated.status === 'completed') {
            fetchLibrary();
            fetchConfig();
          }
        } catch (err) {
          console.warn('SSE parse error:', err);
        }
      });
    } catch (err) {
      console.warn('SSE init error:', err);
    }
  }

  // --- UI Renderers ---
  function updateNextIndexUI() {
    const formatted = String(state.nextIndex).padStart(3, '0');
    if (el.nextIndexBadge) el.nextIndexBadge.textContent = `#${formatted}`;
    if (el.startIndexInput) el.startIndexInput.placeholder = `留空自动接续 #${formatted}`;
  }

  function updateUrlCount() {
    const raw = el.urlInput.value.trim();
    const count = raw.split('\n').filter(u => u.trim().length > 0).length;
    if (el.urlCountBadge) {
      if (count > 0) {
        el.urlCountBadge.textContent = `${count} 个链接`;
        el.urlCountBadge.style.display = 'inline-block';
      } else {
        el.urlCountBadge.style.display = 'none';
      }
    }
  }

  function renderStats() {
    const tasks = state.tasks;
    const queued = tasks.filter(t => t.status === 'queued').length;
    const downloading = tasks.filter(t => ['downloading', 'extracting', 'processing'].includes(t.status)).length;
    const completed = tasks.filter(t => t.status === 'completed').length;
    const failed = tasks.filter(t => ['failed', 'cancelled'].includes(t.status)).length;

    if (el.statDownloading) el.statDownloading.textContent = downloading;
    if (el.statQueued) el.statQueued.textContent = queued;
    if (el.statCompleted) el.statCompleted.textContent = completed;

    if (el.countAll) el.countAll.textContent = tasks.length;
    if (el.countDownloading) el.countDownloading.textContent = downloading;
    if (el.countQueued) el.countQueued.textContent = queued;
    if (el.countCompleted) el.countCompleted.textContent = completed;
    if (el.countFailed) el.countFailed.textContent = failed;
  }

  function setActiveFilter(filter) {
    state.activeFilter = filter;
    
    // Update navigation active styles
    document.querySelectorAll('.filter-nav-btn').forEach(btn => {
      const f = btn.getAttribute('data-filter');
      if (f === filter) {
        btn.classList.add('bg-blue-500/10', 'text-blue-500', 'font-semibold');
        btn.classList.remove('text-textSecondary');
      } else {
        btn.classList.remove('bg-blue-500/10', 'text-blue-500', 'font-semibold');
        btn.classList.add('text-textSecondary');
      }
    });

    if (filter === 'library') {
      el.tasksSection.style.display = 'none';
      el.librarySection.style.display = 'block';
      fetchLibrary();
    } else {
      el.tasksSection.style.display = 'block';
      el.librarySection.style.display = 'none';
      renderTasks();
    }
  }

  function renderTasks() {
    if (!el.taskList) return;
    let list = state.tasks;

    // Filter by tab
    if (state.activeFilter === 'downloading') {
      list = list.filter(t => ['downloading', 'extracting', 'processing'].includes(t.status));
    } else if (state.activeFilter === 'queued') {
      list = list.filter(t => t.status === 'queued');
    } else if (state.activeFilter === 'completed') {
      list = list.filter(t => t.status === 'completed');
    } else if (state.activeFilter === 'failed') {
      list = list.filter(t => ['failed', 'cancelled'].includes(t.status));
    }

    // Filter by search query
    const q = state.searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter(t => 
        (t.title && t.title.toLowerCase().includes(q)) ||
        (t.uploader && t.uploader.toLowerCase().includes(q)) ||
        (t.index_str && t.index_str.includes(q))
      );
    }

    if (list.length === 0) {
      el.taskList.innerHTML = `
        <div class="py-16 text-center rounded-xl border border-dashed border-border bg-card/50">
          <div class="w-12 h-12 mx-auto rounded-full bg-muted flex items-center justify-center text-textMuted mb-3">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
            </svg>
          </div>
          <h3 class="text-sm font-semibold text-textPrimary">暂无下载任务</h3>
          <p class="text-xs text-textMuted mt-1 max-w-sm mx-auto">
            在上方输入框粘贴 YouTube 视频链接，点击“立即开始批量下载”即可添加任务。
          </p>
        </div>
      `;
      return;
    }

    el.taskList.innerHTML = list.map(t => {
      let badgeClass = 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20';
      let statusText = t.status;
      let isDownloading = false;

      if (t.status === 'completed') {
        badgeClass = 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
        statusText = '已完成';
      } else if (t.status === 'downloading') {
        badgeClass = 'bg-blue-500/10 text-blue-500 border-blue-500/20 animate-pulse';
        statusText = '下载中';
        isDownloading = true;
      } else if (t.status === 'extracting') {
        badgeClass = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
        statusText = '解析元数据';
        isDownloading = true;
      } else if (t.status === 'processing') {
        badgeClass = 'bg-purple-500/10 text-purple-400 border-purple-500/20';
        statusText = '混流转码中';
        isDownloading = true;
      } else if (t.status === 'queued') {
        badgeClass = 'bg-amber-500/10 text-amber-500 border-amber-500/20';
        statusText = '队列等待中';
      } else if (t.status === 'failed') {
        badgeClass = 'bg-rose-500/10 text-rose-500 border-rose-500/20';
        statusText = '下载失败';
      } else if (t.status === 'cancelled') {
        badgeClass = 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20';
        statusText = '已取消';
      }

      const percent = t.percent || 0;
      const progressBg = t.status === 'completed' ? 'bg-emerald-500' : t.status === 'failed' ? 'bg-rose-500' : 'bg-blue-600 progress-shimmer';

      return `
        <div class="rounded-xl border border-border bg-card p-4 shadow-xs hover:border-blue-500/30 transition">
          <div class="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            
            <!-- Thumbnail -->
            <div class="relative w-full sm:w-36 h-20 shrink-0 bg-muted rounded-lg overflow-hidden border border-border/60">
              ${t.thumbnail ? `<img src="${escapeHtml(t.thumbnail)}" class="w-full h-full object-cover">` : `
                <div class="w-full h-full flex items-center justify-center text-textMuted">
                  <svg class="w-6 h-6 opacity-40" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
                  </svg>
                </div>
              `}
              <span class="absolute top-1 left-1 px-1.5 py-0.2 rounded bg-blue-600 font-mono font-extrabold text-[10px] text-white shadow-xs">
                #${escapeHtml(t.index_str || '001')}
              </span>
              ${t.duration_str && t.duration_str !== '--:--' ? `
                <span class="absolute bottom-1 right-1 px-1.5 py-0.2 rounded bg-black/80 text-[10px] font-mono text-white">
                  ${escapeHtml(t.duration_str)}
                </span>
              ` : ''}
              <span class="absolute top-1 right-1 px-1.5 py-0.2 rounded bg-black/80 text-[9px] font-mono font-bold text-white uppercase">
                ${escapeHtml(t.format || 'mp4')}
              </span>
            </div>

            <!-- Details & Progress -->
            <div class="flex-1 min-w-0 w-full space-y-2">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-500 font-mono font-bold text-xs shrink-0">
                      #${escapeHtml(t.index_str || '001')}
                    </span>
                    <h4 class="text-xs sm:text-sm font-bold text-textPrimary truncate" title="${escapeHtml(t.title)}">
                      ${escapeHtml(t.title)}
                    </h4>
                  </div>
                  <div class="flex items-center gap-2 text-[11px] text-textMuted mt-0.5">
                    ${t.uploader ? `<span class="truncate max-w-[200px]">${escapeHtml(t.uploader)}</span> <span>•</span>` : ''}
                    <span class="font-mono uppercase">${escapeHtml(t.quality || 'best')}</span>
                    ${t.error_message ? `<span class="text-rose-500 truncate max-w-sm">• ${escapeHtml(t.error_message)}</span>` : ''}
                  </div>
                </div>

                <span class="${badgeClass} shrink-0 px-2.5 py-1 text-[11px] font-semibold rounded-md border flex items-center gap-1.5">
                  ${statusText}
                </span>
              </div>

              <!-- Progress Bar -->
              <div class="w-full bg-muted rounded-full h-2 overflow-hidden relative">
                <div class="h-full transition-all duration-300 ${progressBg}" style="width: ${percent}%"></div>
              </div>

              <!-- Speed and ETA -->
              <div class="flex items-center justify-between text-[11px] font-mono text-textMuted">
                <div>
                  <span class="font-semibold text-textPrimary">${percent}%</span>
                  <span class="mx-1.5">•</span>
                  <span>${t.downloaded_str || '0 B'} / ${t.total_str || '0 B'}</span>
                </div>
                <div class="flex items-center gap-3">
                  ${t.speed_str && isDownloading ? `<span class="text-blue-500 font-semibold">${escapeHtml(t.speed_str)}</span>` : ''}
                  ${t.eta_str && isDownloading && t.eta_str !== '--:--' ? `<span>剩余: ${escapeHtml(t.eta_str)}</span>` : ''}
                </div>
              </div>
            </div>

            <!-- Action Buttons -->
            <div class="flex sm:flex-col items-center gap-1.5 shrink-0 w-full sm:w-auto justify-end pt-2 sm:pt-0 border-t sm:border-t-0 border-border">
              <button 
                onclick="window.appOpenLocation('${t.id}')"
                title="在 Windows 资源管理器中定位" 
                class="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-border bg-card hover:bg-muted text-textSecondary hover:text-textPrimary transition">
                <svg class="w-3.5 h-3.5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                定位
              </button>

              ${['failed', 'cancelled'].includes(t.status) ? `
                <button 
                  onclick="window.appRetry('${t.id}')"
                  class="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-border bg-card hover:bg-muted text-blue-500 hover:text-blue-600 transition">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  重试
                </button>
              ` : ''}

              ${isDownloading || t.status === 'queued' ? `
                <button 
                  onclick="window.appCancel('${t.id}')"
                  class="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-border bg-card hover:bg-muted text-amber-500 hover:text-amber-600 transition">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  取消
                </button>
              ` : ''}

              <button 
                onclick="window.appDelete('${t.id}')"
                title="删除记录"
                class="p-1.5 text-textMuted hover:text-rose-500 rounded-md hover:bg-rose-500/10 transition">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>

          </div>
        </div>
      `;
    }).join('');
  }

  function renderLibrary() {
    if (!el.libraryList) return;
    const files = state.libraryFiles;

    if (files.length === 0) {
      el.libraryList.innerHTML = `
        <div class="py-12 text-center rounded-xl border border-dashed border-border bg-card/50">
          <p class="text-xs text-textMuted">暂无已下载完成的媒体文件</p>
        </div>
      `;
      return;
    }

    el.libraryList.innerHTML = files.map(f => `
      <div class="flex items-center justify-between p-3 rounded-lg border border-border bg-card hover:border-blue-500/40 transition">
        <div class="flex items-center gap-3 min-w-0">
          <span class="px-2 py-1 rounded bg-blue-500/10 text-blue-500 font-mono font-bold text-xs shrink-0">
            #${escapeHtml(f.index_str || '--')}
          </span>
          <div class="min-w-0">
            <div class="text-xs font-semibold text-textPrimary truncate" title="${escapeHtml(f.filename)}">
              ${escapeHtml(f.filename)}
            </div>
            <div class="text-[11px] text-textMuted mt-0.5 flex items-center gap-2">
              <span class="uppercase font-mono font-medium">${escapeHtml(f.ext)}</span>
              <span>•</span>
              <span>${escapeHtml(f.size_str)}</span>
            </div>
          </div>
        </div>

        <button 
          onclick="window.appOpenFile('${encodeURIComponent(f.file_path)}')"
          class="px-2.5 py-1 text-xs border border-border rounded-md hover:bg-muted text-textSecondary hover:text-textPrimary shrink-0 flex items-center gap-1">
          <svg class="w-3.5 h-3.5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          定位文件
        </button>
      </div>
    `).join('');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Global Window Hooks for Inline Handlers ---
  window.appOpenLocation = (id) => openTaskLocation(id);
  window.appRetry = (id) => retryTask(id);
  window.appCancel = (id) => cancelTask(id);
  window.appDelete = (id) => deleteTask(id);
  window.appOpenFile = (encodedPath) => openFile(decodeURIComponent(encodedPath));

  // --- Event Listeners Setup ---
  function setupEvents() {
    if (el.themeToggleBtn) el.themeToggleBtn.addEventListener('click', toggleTheme);
    if (el.openFolderBtn) el.openFolderBtn.addEventListener('click', openDownloadFolder);
    if (el.sidebarOpenFolderBtn) el.sidebarOpenFolderBtn.addEventListener('click', openDownloadFolder);
    if (el.clearCompletedBtn) el.clearCompletedBtn.addEventListener('click', clearCompleted);
    if (el.topClearCompletedBtn) el.topClearCompletedBtn.addEventListener('click', clearCompleted);
    if (el.refreshLibraryBtn) el.refreshLibraryBtn.addEventListener('click', fetchLibrary);

    if (el.startDownloadBtn) el.startDownloadBtn.addEventListener('click', startDownload);

    if (el.urlInput) {
      el.urlInput.addEventListener('input', updateUrlCount);
    }

    if (el.pasteBtn) {
      el.pasteBtn.addEventListener('click', async () => {
        try {
          const text = await navigator.clipboard.readText();
          if (text) {
            if (el.urlInput.value && !el.urlInput.value.endsWith('\n')) {
              el.urlInput.value += '\n' + text.trim();
            } else {
              el.urlInput.value += text.trim();
            }
            updateUrlCount();
            showToast('已从剪贴板粘贴', 'info');
          }
        } catch (e) {
          showToast('无法读取剪贴板，请使用 Ctrl+V 粘贴', 'warning');
        }
      });
    }

    if (el.sampleBtn) {
      el.sampleBtn.addEventListener('click', () => {
        el.urlInput.value = [
          'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
          'https://www.youtube.com/shorts/5GL9t_vX980',
          'https://www.youtube.com/watch?v=jNQXAC9IVRw',
        ].join('\n');
        updateUrlCount();
        showToast('已载入测试链接', 'info');
      });
    }

    if (el.clearInputBtn) {
      el.clearInputBtn.addEventListener('click', () => {
        el.urlInput.value = '';
        updateUrlCount();
      });
    }

    if (el.searchFilter) {
      el.searchFilter.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        renderTasks();
      });
    }

    // Sidebar filter buttons
    document.querySelectorAll('.filter-nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const f = btn.getAttribute('data-filter');
        setActiveFilter(f);
      });
    });
  }

  // --- Initialize App ---
  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    setupEvents();
    fetchTasks();
    fetchConfig();
    fetchLibrary();
    setupSSE();

    // Periodic polling every 5s
    setInterval(() => {
      fetchTasks();
    }, 5000);
  });

})();
