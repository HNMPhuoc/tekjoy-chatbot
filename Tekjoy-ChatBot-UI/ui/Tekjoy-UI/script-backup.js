// --- API CLIENT ---
// const BASE_URL = 'https://sv.tekjoy.io.vn/api';
const BASE_URL = 'http://127.0.0.1:8001/api';
// --- REQUEST QUEUE MANAGER ---
class RequestQueueManager {
    constructor() {
        this.queue = [];
        this.activeRequests = 0;
        this.maxConcurrentRequests = 2;
        this.isProcessing = false;
    }

    async addRequest(requestFn, priority = 'normal') {
        return new Promise((resolve, reject) => {
            const requestItem = {
                requestFn,
                priority,
                resolve,
                reject,
                timestamp: Date.now()
            };

            // Add to queue based on priority
            if (priority === 'high') {
                this.queue.unshift(requestItem);
            } else {
                this.queue.push(requestItem);
            }

            this.processQueue();
        });
    }

    async processQueue() {
        if (this.isProcessing || this.activeRequests >= this.maxConcurrentRequests || this.queue.length === 0) {
            return;
        }

        this.isProcessing = true;

        while (this.queue.length > 0 && this.activeRequests < this.maxConcurrentRequests) {
            const requestItem = this.queue.shift();
            this.activeRequests++;

            this.executeRequest(requestItem);
        }

        this.isProcessing = false;
    }

    async executeRequest(requestItem) {
        try {
            const result = await requestItem.requestFn();
            requestItem.resolve(result);
        } catch (error) {
            requestItem.reject(error);
        } finally {
            this.activeRequests--;
            // Continue processing queue
            setTimeout(() => this.processQueue(), 10);
        }
    }
}

const requestQueue = new RequestQueueManager();

const api = {
    async request(endpoint, method = 'GET', body = null, options = {}) {
        const priority = options.priority || 'normal';

        return requestQueue.addRequest(async () => {
            const url = `${BASE_URL}${endpoint}`;
            const token = localStorage.getItem('authToken');
            const headers = {
                'Content-Type': 'application/json'
            };

            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const config = {
                method,
                headers,
                ...options // Allow passing additional options like signal for AbortController
            };

            // Remove priority from config to avoid sending it to fetch
            delete config.priority;

            if (body) {
                config.body = JSON.stringify(body);
            }

            try {
                const response = await fetch(url, config);
                if (!response.ok) {
                    if (response.status === 401) {
                        showLogin();
                    }
                    const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                    throw new Error(errorData.detail || 'Có lỗi xảy ra');
                }
                if (response.status === 204 || response.headers.get("content-length") === "0") {
                    return { message: "Success" };
                }
                return await response.json();
            } catch (error) {
                // Don't show error alert for aborted requests
                if (error.name === 'AbortError') {
                    console.log('Request was aborted');
                    throw error;
                }
                console.error(`API Error (${method} ${endpoint}):`, error);
                showCustomAlert(`Lỗi API: ${error.message}`, 'error');
                throw error;
            }
        }, priority);
    },

    login(email, password) {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);
        return fetch(`${BASE_URL}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData,
        });
    },

    get(endpoint, options = {}) { return this.request(endpoint, 'GET', null, options); },
    post(endpoint, body, options = {}) { return this.request(endpoint, 'POST', body, options); },
    put(endpoint, body, options = {}) { return this.request(endpoint, 'PUT', body, options); },
    delete(endpoint, body, options = {}) { return this.request(endpoint, 'DELETE', body, options); },
};

// --- APPLICATION STATE ---
const state = {
    currentPage: localStorage.getItem('currentPage') || 'manage-folders', // Nhớ tab trước đó
    currentUser: null,
    currentFolderId: localStorage.getItem('currentFolderId') ? JSON.parse(localStorage.getItem('currentFolderId')) : null, // Nhớ folder hiện tại
    folderHistory: localStorage.getItem('folderHistory') ? JSON.parse(localStorage.getItem('folderHistory')) : [], // Nhớ lịch sử folder
    activeUploads: new Map(), // Theo dõi các upload đang diễn ra
    uploadQueue: [], // Hàng đợi upload
    requestQueue: [], // Hàng đợi request
    isProcessingQueue: false, // Đang xử lý queue
    maxConcurrentRequests: 2, // Giới hạn số request đồng thời
    activeRequests: 0, // Số request đang active
    allFilesPage: 1, // Track current page for the "All Files" view
    searchParams: {
        name: '',
        file_extension: '',
        upload_from: '',
        upload_to: '',
        uploader_only: false,
    },

};

// --- DOM ELEMENTS ---
const mainContent = document.getElementById('main-content');
const mainNav = document.getElementById('main-nav');
const loginScreen = document.getElementById('login-screen');
const appScreen = document.getElementById('app');
const loginForm = document.getElementById('login-form');
const modalBackdrop = document.getElementById('modal-backdrop');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');
const modalCloseBtn = document.getElementById('modal-close-btn');
const userFullNameDisplay = document.getElementById('user-fullname');
const userAvatar = document.getElementById('user-avatar');
const rootFolderId = "a0a00953-72d4-4422-84b0-882a0938112b"; // Root folder ID

// --- NAVIGATION ---
const navItems = [
    { id: 'manage-folders', label: 'Quản lý Folder', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>` },
    { id: 'view-files', label: 'Tất cả File', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>` },
    { id: 'manage-users', label: 'Quản lý User', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M15 21a6 6 0 00-9-5.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-3-5.197m0 0A4 4 0 0012 4.354a4 4 0 00-3 5.197z" /></svg>`, role: 'admin' },
    { id: 'manage-groups', label: 'Quản lý Group', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>`, role: 'admin' },
    { id: 'manage-access-levels', label: 'Quản lý Access Level', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H5v-2H3v-2H1v-4a6 6 0 017.743-5.743z" /></svg>`, role: 'admin' },
    { id: 'manage-settings', label: 'Cài đặt', icon: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>`, role: 'admin' }
];

function renderNav() {
    const visibleNavItems = navItems.filter(item => {
        if (item.role) {
            return state.currentUser && state.currentUser.role === item.role;
        }
        return true;
    });

    mainNav.innerHTML = visibleNavItems.map(item => `
         <a href="#" data-page="${item.id}" class="nav-link flex items-center px-4 py-3 rounded-xl transition-all duration-200 ${state.currentPage === item.id ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-lg' : 'hover:bg-gray-200 text-black-900 hover:text-black-900'}">
             ${item.icon}
             <span class="ml-3 font-medium">${item.label}</span>
         </a>
     `).join('');
}

// --- UTILITIES ---
// Lưu state vào localStorage
function saveState() {
    localStorage.setItem('currentPage', state.currentPage);
    localStorage.setItem('currentFolderId', JSON.stringify(state.currentFolderId));
    localStorage.setItem('folderHistory', JSON.stringify(state.folderHistory));
    console.log('State saved:', {
        currentPage: state.currentPage,
        currentFolderId: state.currentFolderId,
        folderHistory: state.folderHistory
    });
}

// Xóa state khỏi localStorage (khi logout)
function clearState() {
    localStorage.removeItem('currentPage');
    localStorage.removeItem('currentFolderId');
    localStorage.removeItem('folderHistory');
    console.log('State cleared');
}

function showCustomAlert(message, type = 'success') {
    const alertContainer = document.createElement('div');
    const alertClass = type === 'error' ? 'alert-error' : 'alert-success';
    alertContainer.className = `alert ${alertClass}`;
    alertContainer.innerHTML = `
         <div class="flex items-center">
             <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                 ${type === 'error'
            ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
            : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
        }
             </svg>
             <span>${message}</span>
         </div>
     `;
    document.body.appendChild(alertContainer);
    setTimeout(() => {
        alertContainer.style.animation = 'slideInRight 0.3s ease-out reverse';
        setTimeout(() => alertContainer.remove(), 300);
    }, 3000);
}

// --- UPLOAD MANAGER ---
class UploadManager {
    constructor() {
        this.uploads = new Map();
        this.container = null;
        this.isVisible = false;
        this.initContainer();
    }

    initContainer() {
        // Create container if it doesn't exist
        this.container = document.getElementById('upload-manager');

        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'upload-manager';
            this.container.className = 'fixed bottom-4 right-4 w-96 max-w-full z-50 bg-white rounded-lg shadow-xl overflow-hidden transition-all duration-300 transform translate-y-4 opacity-0 border border-gray-200 pointer-events-auto';
            this.container.innerHTML = `
                <div class="p-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                    <h3 class="font-medium text-black-900 dark:text-white text-sm font-medium">Đang tải lên (0)</h3>
                    <div class="flex items-center space-x-2">
                        <button id="minimize-uploads" class="text-black-500 hover:text-black-700 dark:text-balck-400 dark:hover:text-black-200 p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"></path>
                            </svg>
                        </button>
                        <button id="close-uploads" class="text-black-500 hover:text-black-700 dark:text-black-900 dark:hover:text-black-200 p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                </div>
                <div id="upload-list" class="max-h-96 overflow-y-auto bg-white">
                    <div class="p-4 text-center text-black-500 dark:text-black-900 text-sm">Không có file nào đang tải lên</div>
                </div>
                <div class="p-3 border-t border-gray-200 bg-gray-50 text-right">
                    <button id="hide-completed" class="text-xs text-blue-600 dark:text-blue-400 hover:underline">Ẩn đã hoàn thành</button>
                </div>
            `;
            document.body.appendChild(this.container);

            // Add event listeners
            document.getElementById('minimize-uploads').addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleMinimize();
            });
            document.getElementById('close-uploads').addEventListener('click', (e) => {
                e.stopPropagation();
                this.hide();
            });
            document.getElementById('hide-completed')?.addEventListener('click', () => this.hideCompleted());
        }
    }

    show() {
        if (!this.isVisible) {
            this.container.classList.remove('opacity-0', 'translate-y-4');
            this.container.classList.add('opacity-100', 'translate-y-0');
            this.isVisible = true;
        }
    }

    hide() {
        if (this.isVisible) {
            this.container.classList.add('opacity-0', 'translate-y-4');
            this.container.classList.remove('opacity-100', 'translate-y-0');
            this.isVisible = false;
        }
    }

    toggleMinimize() {
        const list = this.container.querySelector('#upload-list');
        const btn = this.container.querySelector('#minimize-uploads svg');

        if (list.style.display === 'none') {
            list.style.display = 'block';
            btn.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"></path>';
        } else {
            list.style.display = 'none';
            btn.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>';
        }
    }

    addUpload(uploadId, file, folderId) {
        const upload = {
            id: uploadId,
            file,
            folderId,
            progress: 0,
            status: 'pending',
            xhr: null, // Store xhr for cancellation
            startTime: Date.now(),
            loaded: 0,
            total: file.size,
            element: null
        };

        this.uploads.set(uploadId, upload);
        this.updateUI();
        this.show();
        return upload;
    }

    updateProgress(uploadId, progress, status) {
        const upload = this.uploads.get(uploadId);
        if (!upload) return;

        upload.progress = progress;
        upload.status = status || upload.status;

        // Update progress in UI
        const progressBar = upload.element?.querySelector('.upload-progress-bar');
        const statusText = upload.element?.querySelector('.upload-status');
        const progressText = upload.element?.querySelector('.upload-progress-text');

        if (progressBar) progressBar.style.width = `${progress}%`;
        if (statusText) statusText.textContent = this.getStatusText(status || upload.status);
        if (progressText) progressText.textContent = `${Math.round(progress)}%`;
    }

    completeUpload(uploadId, success = true, message = '') {
        const upload = this.uploads.get(uploadId);
        if (!upload) return;

        upload.status = success ? 'completed' : 'failed';
        upload.message = message;
        upload.completedAt = new Date();

        // Update UI
        const statusIcon = upload.element?.querySelector('.status-icon');
        const statusText = upload.element?.querySelector('.upload-status');
        const progressBar = upload.element?.querySelector('.upload-progress-bar');
        const progressText = upload.element?.querySelector('.upload-progress-text');

        if (success) {
            upload.progress = 100;
            if (progressBar) progressBar.style.width = '100%';
            if (progressText) progressText.textContent = '100%';
        }

        if (statusIcon) {
            statusIcon.className = 'status-icon mt-0.5';
            statusIcon.innerHTML = success
                ? '<svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
                : '<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
        }

        if (statusText) {
            statusText.textContent = success ? 'Tải lên thành công' : 'Tải lên thất bại';
            statusText.className = `text-xs font-medium ${success ? 'text-green-500' : 'text-red-500'}`;
        }

        // Remove cancel button
        const cancelBtn = upload.element?.querySelector('.cancel-upload-btn');
        if (cancelBtn) cancelBtn.remove();

        // Auto-remove after delay if successful
        if (success) {
            setTimeout(() => {
                this.removeUpload(uploadId);
            }, 5000);
        } else if (upload.element) {
            // For failed uploads, show retry button
            const retryBtn = document.createElement('button');
            retryBtn.className = 'text-xs text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 font-medium';
            retryBtn.textContent = 'Thử lại';
            retryBtn.addEventListener('click', async () => {
                await performAsyncUpload(upload.file, upload.folderId, uploadId);
            });

            const actions = document.createElement('div');
            actions.className = 'mt-2 flex justify-end';
            actions.appendChild(retryBtn);

            upload.element.querySelector('.flex-1')?.appendChild(actions);
        }

        // Update title with completed count
        this.updateTitle();
    }

    removeUpload(uploadId) {
        const upload = this.uploads.get(uploadId);
        if (!upload) return;

        upload.element?.remove();
        this.uploads.delete(uploadId);

        // Update UI
        if (this.uploads.size === 0) {
            this.hide();
        } else {
            this.updateEmptyState();
            this.updateTitle();
        }
    }

    hideCompleted() {
        const completedUploads = Array.from(this.uploads.entries())
            .filter(([id, upload]) => upload.status === 'completed');

        completedUploads.forEach(([id, upload]) => {
            this.removeUpload(id);
        });
    }

    updateTitle() {
        const title = this.container?.querySelector('h3');
        if (!title) return;

        const inProgressCount = Array.from(this.uploads.values())
            .filter(upload => upload.status === 'uploading').length;

        title.textContent = `Đang tải lên (${inProgressCount}/${this.uploads.size})`;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    cancelUpload(uploadId) {
        const upload = this.uploads.get(uploadId);
        if (!upload || !upload.xhr) return;

        upload.xhr.abort();
        this.completeUpload(uploadId, false, 'Đã hủy');
        showCustomAlert('Đã hủy tải lên', 'error');
    }

    getStatusText(status) {
        switch (status) {
            case 'pending': return 'Đang chờ...';
            case 'uploading': return 'Đang tải lên...';
            case 'processing': return 'Đang xử lý...';
            case 'completed': return 'Hoàn thành';
            case 'failed': return 'Thất bại';
            default: return status;
        }
    }

    updateUI() {
        const uploadList = this.container.querySelector('#upload-list');
        if (!uploadList) return;

        // Clear and rebuild the list
        uploadList.innerHTML = '';

        if (this.uploads.size === 0) {
            uploadList.innerHTML = '<div class="p-4 text-center text-black-500 dark:text-black-900 text-sm">Không có file nào đang tải lên</div>';
            return;
        }

        // Sort uploads: in-progress first, then completed/failed
        const sortedUploads = Array.from(this.uploads.entries())
            .sort(([id1, a], [id2, b]) => {
                if (a.status === 'uploading' && b.status !== 'uploading') return -1;
                if (a.status !== 'uploading' && b.status === 'uploading') return 1;
                return (a.completedAt || 0) - (b.completedAt || 0);
            });

        sortedUploads.forEach(([uploadId, upload]) => {
            if (!upload.element) {
                upload.element = this.createUploadElement(upload, uploadId);
            }
            uploadList.appendChild(upload.element);
        });

        this.updateTitle();
    }

    createUploadElement(upload, uploadId) {
        const element = document.createElement('div');
        element.className = 'p-3 border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors duration-150';
        element.innerHTML = `
            <div class="flex items-start gap-3">
                <div class="status-icon mt-0.5 text-blue-500">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                    </svg>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-2">
                        <div class="text-sm font-medium text-black-900 dark:text-black-100 truncate" title="${upload.file.name}">
                            ${upload.file.name}
                        </div>
                        <div class="flex items-center space-x-2">
                            <span class="text-xs text-black-500 dark:text-black-900 upload-progress-text">0%</span>
                            <button class="cancel-upload-btn text-black-900 hover:text-red-500 transition-colors p-1 -mr-1" data-upload-id="${uploadId}" title="Hủy tải lên">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <div class="mt-1 flex items-center justify-between">
                        <span class="text-xs text-black-500 dark:text-black-900 upload-status">${this.getStatusText(upload.status)}</span>
                        <span class="text-xs text-black-900">${this.formatFileSize(upload.file.size)}</span>
                    </div>
                    <div class="mt-2 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                        <div class="upload-progress-bar bg-blue-500 h-full rounded-full transition-all duration-300 ease-out" style="width: 0%"></div>
                    </div>
                </div>
            </div>
        `;

        // Add cancel button handler
        element.querySelector('.cancel-upload-btn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.cancelUpload(uploadId);
        });

        return element;
    }

    updateEmptyState() {
        const uploadList = this.container.querySelector('#upload-list');
        if (!uploadList) return;

        if (this.uploads.size === 0) {
            uploadList.innerHTML = '<div class="p-4 text-center text-black-900 text-sm">Không có file nào đang tải lên</div>';
        }
    }
}

// Initialize upload manager
const uploadManager = new UploadManager();

// --- UPLOAD NOTIFICATION SYSTEM (Legacy compatibility) ---
function createUploadNotification(uploadId, fileName) {
    // This is now handled by the UploadManager
    return null;
}

function updateUploadProgress(uploadId, progress, status) {
    uploadManager.updateProgress(uploadId, progress, status);
}

function completeUploadNotification(uploadId, success = true, message = '') {
    uploadManager.completeUpload(uploadId, success, message);

    // Thông báo cho các tab khác biết có file mới được upload
    if (success) {
        localStorage.setItem('file_uploaded', Date.now().toString());
        // Xóa sự kiện sau một khoảng thời gian ngắn
        setTimeout(() => localStorage.removeItem('file_uploaded'), 100);
    }
}

function cancelUpload(uploadId) {
    uploadManager.cancelUpload(uploadId);
}

function setupSearchFilter(containerId, itemSelector) {
    const searchInput = document.getElementById(containerId);
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase().trim();
        const items = mainContent.querySelectorAll(itemSelector);
        items.forEach(item => {
            const textContent = item.textContent.toLowerCase();
            if (textContent.includes(searchTerm)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    });
}

const searchBarHtml = `
     <div class="relative w-full max-w-xs">
         <input type="search" id="search-input" placeholder="Tìm kiếm..." class="form-input w-full bg-white border border-gray-300 text-black-900 rounded-xl px-4 py-3 pl-10 focus:ring-2 focus:ring-indigo-500 focus:outline-none">
         <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
             <svg class="w-5 h-5 text-black-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
             </svg>
         </div>
     </div>
 `;

function getFileIcon(extension) {
    const ext = (extension || '').toLowerCase().replace('.', '');
    switch (ext) {
        case 'pdf': return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>`;
        case 'doc':
        case 'docx': return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>`;
        case 'xls':
        case 'xlsx': return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>`;
        default: return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0011.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>`;
    }
}

function getGroupTagColor(name) {
    let hash = 0;
    if (!name || name.length === 0) return 'bg-gray-200 text-black-700';
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
        hash = hash & hash;
    }
    const colors = [
        'bg-blue-500/20 text-blue-300', 'bg-green-500/20 text-green-300',
        'bg-yellow-500/20 text-yellow-300', 'bg-purple-500/20 text-purple-300',
        'bg-red-500/20 text-red-300', 'bg-indigo-500/20 text-indigo-300',
        'bg-pink-500/20 text-pink-300', 'bg-teal-500/20 text-teal-300'
    ];
    const index = Math.abs(hash % colors.length);
    return colors[index];
}


// --- UTILITIES ---
function saveState() {
    localStorage.setItem('currentPage', state.currentPage);
    localStorage.setItem('currentFolderId', JSON.stringify(state.currentFolderId));
    localStorage.setItem('folderHistory', JSON.stringify(state.folderHistory));
}

function clearState() {
    localStorage.removeItem('currentPage');
    localStorage.removeItem('currentFolderId');
    localStorage.removeItem('folderHistory');
}

function showCustomAlert(message, type = 'success') {
    const alertContainer = document.createElement('div');
    const alertClass = type === 'error' ? 'alert-error' : 'alert-success';
    alertContainer.className = `alert ${alertClass}`;
    alertContainer.innerHTML = `
         <div class="flex items-center">
             <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                 ${type === 'error'
            ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
            : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>'
        }
             </svg>
             <span>${message}</span>
         </div>
     `;
    document.body.appendChild(alertContainer);
    setTimeout(() => {
        alertContainer.style.animation = 'slideInRight 0.3s ease-out reverse';
        setTimeout(() => alertContainer.remove(), 300);
    }, 3000);
}

// [THAY ĐỔI]: Hàm debounce để tránh gọi API liên tục.
function debounce(func, delay = 500) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
}

function getFileIcon(extension) {
    const ext = (extension || '').toLowerCase().replace('.', '');
    switch (ext) {
        case 'pdf': return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>`;
        case 'doc':
        case 'docx': return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>`;
        case 'xls':
        case 'xlsx': return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>`;
        default: return `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0011.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>`;
    }
}

function getGroupTagColor(name) {
    let hash = 0;
    if (!name || name.length === 0) return 'bg-gray-200 text-black-700';
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
        hash = hash & hash;
    }
    const colors = ['bg-blue-500/20 text-blue-300', 'bg-green-500/20 text-green-300', 'bg-yellow-500/20 text-yellow-300', 'bg-purple-500/20 text-purple-300', 'bg-red-500/20 text-red-300', 'bg-indigo-500/20 text-indigo-300', 'bg-pink-500/20 text-pink-300', 'bg-teal-500/20 text-teal-300'];
    const index = Math.abs(hash % colors.length);
    return colors[index];
}

function createFileCard(file) {
    const canManage = state.currentUser && (file.uploaded_by_user_id === state.currentUser.id || state.currentUser.role === 'admin');
    return `
     <div class="file-item relative bg-white rounded-2xl p-6 border border-gray-200 hover:border-indigo-500 transition-all duration-300 group card-hover shadow-sm hover:shadow-md">
         <div data-action="view-file-details" data-id="${file.id}" class="cursor-pointer">
             <div class="w-16 h-16 bg-gradient-to-br from-indigo-400 to-purple-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
                 ${getFileIcon(file.file_extension)}
             </div>
             <h4 class="font-semibold text-black text-center truncate mb-2" title="${file.original_file_name}">${file.original_file_name}</h4>
             <p class="text-sm text-black-900 text-center">${(file.file_size_bytes / 1024).toFixed(2)} KB</p>
         </div>
         ${canManage ? `
         <div class="item-actions space-x-1">
             <button data-action="manage-file-access" data-id="${file.id}" title="Phân quyền" class="p-2 rounded-lg hover:bg-green-500/20 transition-colors"><svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg></button>
             <button data-action="edit-file" data-id="${file.id}" title="Sửa" class="p-2 rounded-lg hover:bg-blue-500/20 transition-colors"><svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L14.732 3.732z"></path></svg></button>
             <button data-action="delete-file" data-id="${file.id}" title="Xóa" class="p-2 rounded-lg hover:bg-red-500/20 transition-colors"><svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg></button>
         </div>
         ` : ''}
     </div>`;
}

// --- PAGINATION ---
function renderPaginationControls(currentPage, totalPages) {
    if (totalPages <= 1) return '';

    const prevDisabled = currentPage === 1;
    const nextDisabled = currentPage === totalPages;

    const prevButton = `
        <a href="#"
           data-page="${currentPage - 1}"
           class="pagination-link ${prevDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-indigo-500/30'
        } relative inline-flex items-center rounded-l-md px-3 py-2 text-black-300 ring-1 ring-inset ring-gray-600 focus:z-20 focus:outline-offset-0">
            <span class="sr-only">Previous</span>
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" /></svg>
        </a>`;

    const nextButton = `
         <a href="#"
            data-page="${currentPage + 1}"
            class="pagination-link ${nextDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-indigo-500/30'
        } relative inline-flex items-center rounded-r-md px-3 py-2 text-black-300 ring-1 ring-inset ring-gray-600 focus:z-20 focus:outline-offset-0">
            <span class="sr-only">Next</span>
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
         </a>`;

    // Logic to create page number buttons with ellipses
    let pageButtons = '';
    const maxPagesToShow = 7;
    if (totalPages <= maxPagesToShow) {
        for (let i = 1; i <= totalPages; i++) {
            pageButtons += createPageButton(i, currentPage);
        }
    } else {
        pageButtons += createPageButton(1, currentPage);
        if (currentPage > 4) {
            pageButtons += `<span class="relative inline-flex items-center px-4 py-2 text-sm font-semibold text-black-900 ring-1 ring-inset ring-gray-600">...</span>`;
        }
        let start = Math.max(2, currentPage - 2);
        let end = Math.min(totalPages - 1, currentPage + 2);

        if (currentPage <= 4) {
            end = 5;
        }
        if (currentPage >= totalPages - 3) {
            start = totalPages - 4;
        }

        for (let i = start; i <= end; i++) {
            pageButtons += createPageButton(i, currentPage);
        }
        if (currentPage < totalPages - 3) {
            pageButtons += `<span class="relative inline-flex items-center px-4 py-2 text-sm font-semibold text-black-900 ring-1 ring-inset ring-gray-600">...</span>`;
        }
        pageButtons += createPageButton(totalPages, currentPage);
    }


    return `
        <div class="flex items-center justify-center py-6">
            <nav class="isolate inline-flex -space-x-px rounded-md shadow-sm" aria-label="Pagination">
                ${prevButton}
                ${pageButtons}
                ${nextButton}
            </nav>
        </div>`;
}

function createPageButton(page, currentPage) {
    const isActive = page === currentPage;
    return `
        <a href="#"
           data-page="${page}"
           class="pagination-link ${isActive
            ? 'bg-indigo-600 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600'
            : 'text-black-300 ring-1 ring-inset ring-gray-600 hover:bg-indigo-500/30'
        } relative inline-flex items-center px-4 py-2 text-sm font-semibold focus:z-20">
            ${page}
        </a>`;
}

// --- SEARCH & FILTER LOGIC ---
// [THAY ĐỔI]: Biến HTML cho thanh tìm kiếm và bộ lọc mới.
const searchAndFilterHtml = `
<div class="w-full bg-white shadow-xl rounded-2xl p-6 border border-gray-200">
    <form id="search-form" class="flex flex-col md:flex-row gap-4 items-center">
        <div class="relative w-full md:flex-grow">
            <input type="search" id="search-input" name="name" placeholder="Tìm kiếm theo tên file..." class="form-input w-full bg-white border border-gray-300 text-black-900 rounded-xl px-4 py-3 pl-10 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none shadow-sm" value="${state.searchParams.name || ''}">
            <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <svg class="w-5 h-5 text-black-900" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
            </div>
        </div>
        <button type="submit" id="search-btn" class="btn bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-semibold flex items-center shadow transition-all">
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
            Tìm kiếm
        </button>
        <button type="button" id="toggle-filter-btn" class="btn bg-gray-100 text-black-700 hover:bg-gray-200 p-3 rounded-xl flex items-center transition-colors md:hidden w-full justify-center border border-gray-300" title="Bộ lọc nâng cao">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L12 14.414V19a1 1 0 01-1.447.894L9 18v-3.586l-8.707-8.707A1 1 0 010 5V4z" /></svg>
            <span>Bộ lọc</span>
        </button>
    </form>
    <div id="filter-panel" class="hidden md:grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 pt-4 mt-4 border-t border-gray-200">
        <div>
            <label for="filter-ext" class="block text-sm font-medium text-black-700 mb-2">Loại file</label>
            <select id="filter-ext" name="file_extension" class="form-input-filter bg-white border border-gray-300 text-black-900 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
                <option value="">Tất cả</option>
                <option value="pdf" ${state.searchParams.file_extension === 'pdf' ? 'selected' : ''}>PDF</option>
                <option value="docx" ${state.searchParams.file_extension === 'docx' ? 'selected' : ''}>DOCX</option>
                <option value="doc" ${state.searchParams.file_extension === 'doc' ? 'selected' : ''}>DOC</option>
                <option value="xlsx" ${state.searchParams.file_extension === 'xlsx' ? 'selected' : ''}>XLSX</option>
                <option value="xls" ${state.searchParams.file_extension === 'xls' ? 'selected' : ''}>XLS</option>
                <option value="pptx" ${state.searchParams.file_extension === 'pptx' ? 'selected' : ''}>PPTX</option>
                <option value="jpg" ${state.searchParams.file_extension === 'jpg' ? 'selected' : ''}>JPG</option>
                <option value="png" ${state.searchParams.file_extension === 'png' ? 'selected' : ''}>PNG</option>
            </select>
        </div>
        <!-- Các filter khác giữ nguyên -->
        <div>
            <label for="filter-upload-from" class="block text-sm font-medium text-black-700 mb-2">Upload từ ngày</label>
            <input type="date" id="filter-upload-from" name="upload_from" class="form-input-filter bg-white border border-gray-300 text-black-900 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" value="${state.searchParams.upload_from || ''}">
        </div>
        <div>
            <label for="filter-upload-to" class="block text-sm font-medium text-black-700 mb-2">Upload đến ngày</label>
            <input type="date" id="filter-upload-to" name="upload_to" class="form-input-filter bg-white border border-gray-300 text-black-900 rounded-xl px-4 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" value="${state.searchParams.upload_to || ''}">
        </div>
        <div class="flex items-end pb-1">
            <label class="flex items-center space-x-3 cursor-pointer">
                <input type="checkbox" id="filter-uploader-only" name="uploader_only" class="form-checkbox-filter accent-indigo-500 w-5 h-5" ${state.searchParams.uploader_only ? 'checked' : ''}>
                <span class="text-sm text-black-700 whitespace-nowrap">Chỉ file của bạn</span>
            </label>
        </div>
        <div class="flex items-end">
            <button type="button" id="reset-filter-btn" class="btn bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 w-full py-2 rounded-lg flex items-center justify-center transition-colors text-sm" title="Xóa bộ lọc">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                Xóa bộ lọc
            </button>
        </div>
    </div>
</div>
`;

// [THAY ĐỔI]: Hàm mới để xử lý sự kiện cho tìm kiếm và bộ lọc.
function setupSearchEventListeners() {
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-input');
    const toggleFilterBtn = document.getElementById('toggle-filter-btn');
    const filterPanel = document.getElementById('filter-panel');
    const resetFilterBtn = document.getElementById('reset-filter-btn');
    const uploaderOnlyCheckbox = document.getElementById('filter-uploader-only');
    const fileExtSelect = document.getElementById('filter-ext');
    const uploadFromInput = document.getElementById('filter-upload-from');
    const uploadToInput = document.getElementById('filter-upload-to');

    if (!searchForm) return;

    // Gỡ event cũ trước khi gán mới
    searchForm.onsubmit = null;
    if (uploaderOnlyCheckbox) uploaderOnlyCheckbox.onchange = null;
    if (fileExtSelect) fileExtSelect.onchange = null;
    if (uploadFromInput) uploadFromInput.onchange = null;
    if (uploadToInput) uploadToInput.onchange = null;
    if (resetFilterBtn) resetFilterBtn.onclick = null;
    if (toggleFilterBtn) toggleFilterBtn.onclick = null;

    // Chỉ gọi API khi submit form (ấn nút Tìm kiếm)
    searchForm.onsubmit = (e) => {
        e.preventDefault();
        state.searchParams.name = searchInput.value.trim();
        state.searchParams.file_extension = fileExtSelect?.value || '';
        state.searchParams.upload_from = uploadFromInput?.value || '';
        state.searchParams.upload_to = uploadToInput?.value || '';
        state.searchParams.uploader_only = uploaderOnlyCheckbox?.checked || false;
        renderAllFilesPage({ isSearch: true, searchParams: state.searchParams, page: 1 });
    };

    // Khi click vào checkbox "Chỉ file của bạn" thì submit luôn form (chỉ gọi 1 lần)
    if (uploaderOnlyCheckbox) {
        uploaderOnlyCheckbox.onchange = () => {
            searchForm.requestSubmit();
        };
    }

    // Nếu muốn tự động lọc khi đổi loại file hoặc ngày, có thể mở comment dưới:
    // if (fileExtSelect) fileExtSelect.onchange = () => searchForm.requestSubmit();
    // if (uploadFromInput) uploadFromInput.onchange = () => searchForm.requestSubmit();
    // if (uploadToInput) uploadToInput.onchange = () => searchForm.requestSubmit();

    // Toggle filter panel
    if (toggleFilterBtn) {
        toggleFilterBtn.onclick = () => {
            filterPanel.classList.toggle('hidden');
        };
    }

    // Xóa bộ lọc
    if (resetFilterBtn) {
        resetFilterBtn.onclick = () => {
            // Reset state
            state.searchParams = { name: '', file_extension: '', upload_from: '', upload_to: '', uploader_only: false };
            // Reset UI
            searchInput.value = '';
            if (fileExtSelect) fileExtSelect.value = '';
            if (uploadFromInput) uploadFromInput.value = '';
            if (uploadToInput) uploadToInput.value = '';
            if (uploaderOnlyCheckbox) uploaderOnlyCheckbox.checked = false;
            renderAllFilesPage({ page: 1 });
        };
    }
}
// [THAY ĐỔI]: Hàm tìm kiếm client-side cũ được đổi tên để tránh xung đột
function setupLocalItemFilter(containerId, itemSelector) {
    const searchInput = document.getElementById(containerId);
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase().trim();
        const items = mainContent.querySelectorAll(itemSelector);
        items.forEach(item => {
            const textContent = item.textContent.toLowerCase();
            item.style.display = textContent.includes(searchTerm) ? '' : 'none';
        });
    });
}
// kết thúc search & filter logic

// --- PAGE RENDERERS ---

async function renderFolderManager(folderId = null) {
    state.currentFolderId = folderId;
    const url = folderId ? `/file/folders/content?folder_id=${folderId}` : '/file/folders/content';
    const { folders, files } = await api.get(url);

    if (!folderId) {
        state.folderHistory = [];
    } else {
        const currentFolderInHistory = state.folderHistory.find(f => f.id === folderId);
        if (!currentFolderInHistory) {
            try {
                const folderInfo = await api.get(`/file/folders/${folderId}`);
                if (folderInfo && folderInfo.name) {
                    state.folderHistory.push({ id: folderId, name: folderInfo.name });
                }
            } catch (e) {
                // If fetching fails, add a placeholder
                const folderName = `Folder ${folderId.substring(0, 8)}`;
                state.folderHistory.push({ id: folderId, name: folderName });
            }
        }
    }
    saveState();
    const localSearchBarHtml = `
    <div class="relative w-full max-w-xs">
        <input type="search" id="local-search-input" placeholder="Tìm kiếm..." class="form-input w-full bg-white border border-gray-300 text-black-900 rounded-xl px-4 py-3 pl-10 focus:ring-2 focus:ring-indigo-500 focus:outline-none">
        <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
            <svg class="w-5 h-5 text-black-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
        </div>
    </div>
    `;
    const breadcrumbHtml = `
         <nav class="flex items-center space-x-2 text-sm text-black-900">
             <a href="#" class="folder-link hover:text-indigo-400 transition-colors" data-folder-id="">
                 <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
                 Root
             </a>
             ${state.folderHistory.map(f => `
                 <svg class="w-4 h-4 text-black-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                 <a href="#" class="folder-link hover:text-indigo-400 transition-colors" data-folder-id="${f.id}">${f.name}</a>
             `).join('')}
         </nav>
     `;

    mainContent.innerHTML = `
         <div class="flex justify-between items-center mb-4">
             <div>
                 <h2 class="text-4xl font-bold text-white mb-2">Quản lý File</h2>
                 <p class="text-black-900">Quản lý thư mục và tệp tin của bạn</p>
             </div>
             <div class="flex space-x-3">
                 <button data-action="add-folder" class="btn btn-primary text-white font-semibold py-3 px-6 rounded-xl flex items-center">
                     <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" /></svg>
                     Tạo thư mục
                 </button>
                 <button data-action="upload-file" class="btn bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white font-semibold py-3 px-6 rounded-xl flex items-center transition-all">
                     <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                     Upload File
                 </button>
             </div>
         </div>
         <div class="mb-6 flex justify-between items-center">
             ${breadcrumbHtml}
             ${localSearchBarHtml}
         </div>
         <div id="file-list" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-6">
             ${folders.map(folder => `
                 <div class="folder-item relative bg-white-800/50 backdrop-blur-sm rounded-2xl p-6 border border-gray-700/50 hover:border-indigo-500/50 transition-all duration-300 group card-hover">
                     <div data-folder-id="${folder.id}" class="folder-link cursor-pointer">
                         <div class="w-16 h-16 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
                             <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>
                             </svg>
                         </div>
                         <h4 class="font-semibold text-black text-center truncate" title="${folder.name}">${folder.name}</h4>
                     </div>
                     <div class="item-actions space-x-2">
                         <button data-action="edit-folder" data-id="${folder.id}" data-name="${folder.name}" title="Sửa" class="p-2 rounded-lg hover:bg-blue-500/20 transition-colors">
                             <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L14.732 3.732z"></path>
                             </svg>
                         </button>
                         <button data-action="delete-folder" data-id="${folder.id}" title="Xóa" class="p-2 rounded-lg hover:bg-red-500/20 transition-colors">
                             <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                             </svg>
                         </button>
                     </div>
                 </div>
             `).join('')}
             ${files.map(file => {
        const canManage = state.currentUser && (file.uploaded_by_user_id === state.currentUser.id || state.currentUser.role === 'admin');
        return `
                 <div class="file-item relative bg-white rounded-2xl p-6 border border-gray-200 hover:border-indigo-500 transition-all duration-300 group card-hover shadow-sm hover:shadow-md">
                     <div data-action="view-file-details" data-id="${file.id}" class="cursor-pointer">
                         <div class="w-16 h-16 bg-gradient-to-br from-indigo-400 to-purple-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
                             ${getFileIcon(file.file_extension)}
                         </div>
                         <h4 class="font-semibold text-black text-center truncate mb-2" title="${file.original_file_name}">${file.original_file_name}</h4>
                         <p class="text-sm text-black-900 text-center">${(file.file_size_bytes / 1024).toFixed(2)} KB</p>
                     </div>
                     ${canManage ? `
                     <div class="item-actions space-x-1">
                         <button data-action="manage-file-access" data-id="${file.id}" title="Phân quyền" class="p-2 rounded-lg hover:bg-green-500/20 transition-colors">
                             <svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
                             </svg>
                         </button>
                         <button data-action="edit-file" data-id="${file.id}" title="Sửa" class="p-2 rounded-lg hover:bg-blue-500/20 transition-colors">
                             <svg class="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L14.732 3.732z"></path>
                             </svg>
                         </button>
                         <button data-action="delete-file" data-id="${file.id}" title="Xóa" class="p-2 rounded-lg hover:bg-red-500/20 transition-colors">
                             <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                             </svg>
                         </button>
                     </div>
                     ` : ''}
                 </div>
                 `}).join('')}
         </div>
     `;
    setupLocalItemFilter('local-search-input', '.folder-item, .file-item');
}

// async function renderAllFilesPage({ page = 1, isSearch = false, searchParams = state.searchParams } = {}) {
//     state.allFilesPage = page;
//     const pageSize = 12;
//     let data;
//     let pageType;
//     let title = "Tất cả File";
//     let subTitle = "Danh sách các file bạn đã upload và các file được chia sẻ với bạn";

//     // Show loading spinner
//     mainContent.innerHTML = `<div class="flex items-center justify-center h-full"><div class="loading-spinner"></div></div>`;

//     try {
//         if (isSearch) {
//             pageType = 'search';
//             const params = new URLSearchParams({ page, page_size: pageSize });
//             for (const key in searchParams) {
//                 if (searchParams[key]) {
//                     params.append(key, searchParams[key]);
//                 }
//             }
//             data = await api.get(`/file/files/search/scr?${params.toString()}`);
//             title = "Kết quả tìm kiếm";
//             subTitle = `Tìm thấy ${data.total} file khớp với tiêu chí của bạn.`;
//         } else {
//             pageType = 'all-files';
//             data = await api.get(`/file/files/accessibleV2/?page=${page}&page_size=${pageSize}`);
//         }

//         const { items, total } = data;
//         const totalPages = Math.ceil(total / pageSize);

//         const myFiles = items.filter(f => f.uploaded_by_user_id === state.currentUser.id);
//         const accessibleFiles = items.filter(f => f.uploaded_by_user_id !== state.currentUser.id);

//         mainContent.innerHTML = `
//             <div class="flex justify-between items-center mb-4">
//                 <div>
//                     <h2 class="text-4xl font-bold text-white mb-2">${title}</h2>
//                     <p class="text-black-900 font-medium">${subTitle}</p>
//                 </div>
//                 <div class="flex items-center space-x-4">
//                     <button data-action="refresh-access" class="btn bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 p-3 rounded-xl flex items-center transition-colors" title="Làm mới quyền truy cập file">
//                         <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h5m11 2a9 9 0 01-18 0 9 9 0 0118 0z"></path></svg>
//                     </button>
//                 </div>
//             </div>

//             <div class="mb-8">
//                 ${searchAndFilterHtml}
//             </div>

//             <div class="mb-8">
//                 ${renderPaginationControls(page, totalPages, pageType)}
//             </div>

//             <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
//                 <div>
//                      <h3 class="text-2xl font-bold text-white mb-6">File của bạn</h3>
//                      <div class="bg-gray-800/50 backdrop-blur-sm rounded-2xl p-6 border border-gray-700/50 min-h-[300px]">
//                          ${myFiles.length > 0 ? `<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 card-container">${myFiles.map(createFileCard).join('')}</div>` : `<div class="empty-state">Không có file nào.</div>`}
//                      </div>
//                 </div>
//                 <div>
//                      <h3 class="text-2xl font-bold text-white mb-6">File được chia sẻ</h3>
//                      <div class="bg-gray-800/50 backdrop-blur-sm rounded-2xl p-6 border border-gray-700/50 min-h-[300px]">
//                          ${accessibleFiles.length > 0 ? `<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 card-container">${accessibleFiles.map(createFileCard).join('')}</div>` : `<div class="empty-state">Không có file nào.</div>`}
//                      </div>
//                 </div>
//             </div>
//         `;

//         setupSearchEventListeners();
//     } catch (error) {
//         console.error("Error rendering files page:", error);
//         mainContent.innerHTML = `<div class="text-center text-red-400">Không thể tải dữ liệu file.</div>`;
//     }
// }

async function renderAllFilesPage({ page = 1, isSearch = false, searchParams = state.searchParams } = {}) {
    state.allFilesPage = page;
    const pageSize = 12;
    let data;
    let pageType;
    let title = "Tất cả File";
    let subTitle = "Danh sách các file bạn đã upload và các file được chia sẻ với bạn";

    // Nếu chưa có khung ngoài, render khung ngoài
    if (!document.getElementById('files-content')) {
        mainContent.innerHTML = `
            <div class="flex justify-between items-center mb-4">
                <div>
                    <h2 class="text-4xl font-bold text-white mb-2">${title}</h2>
                    <p class="text-black-900 font-medium">${subTitle}</p>
                </div>
                <div class="flex items-center space-x-4">
                    <button data-action="refresh-access" class="btn bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 p-3 rounded-xl flex items-center transition-colors" title="Làm mới quyền truy cập file">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h5m11 2a9 9 0 01-18 0 9 9 0 0118 0z"></path></svg>
                    </button>
                </div>
            </div>
            <div class="mb-8">${searchAndFilterHtml}</div>
            <div class="mb-8" id="pagination-controls"></div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8" id="files-content">
                <div>
                    <h3 class="text-2xl font-bold text-white mb-6">File của bạn</h3>
                    <div class="bg-white rounded-2xl p-6 border border-gray-200 min-h-[300px] shadow-sm" id="my-files-list">
                        <div class="flex items-center justify-center h-40"><div class="loading-spinner"></div></div>
                    </div>
                </div>
                <div>
                    <h3 class="text-2xl font-bold text-white mb-6">File được chia sẻ</h3>
                    <div class="bg-white rounded-2xl p-6 border border-gray-200 min-h-[300px] shadow-sm" id="shared-files-list">
                        <div class="flex items-center justify-center h-40"><div class="loading-spinner"></div></div>
                    </div>
                </div>
            </div>
        `;
    } else {
        // Nếu đã có khung ngoài, chỉ show spinner ở vùng file-list
        document.getElementById('my-files-list').innerHTML = `<div class="flex items-center justify-center h-40"><div class="loading-spinner"></div></div>`;
        document.getElementById('shared-files-list').innerHTML = `<div class="flex items-center justify-center h-40"><div class="loading-spinner"></div></div>`;
    }

    try {
        // ...fetch data như cũ...
        if (isSearch) {
            pageType = 'search';
            const params = new URLSearchParams({ page, page_size: pageSize });
            for (const key in searchParams) {
                if (searchParams[key]) {
                    params.append(key, searchParams[key]);
                }
            }
            data = await api.get(`/file/files/search/scr?${params.toString()}`);
            title = "Kết quả tìm kiếm";
            subTitle = `Tìm thấy ${data.total} file khớp với tiêu chí của bạn.`;
        } else {
            pageType = 'all-files';
            data = await api.get(`/file/files/accessibleV2/?page=${page}&page_size=${pageSize}`);
        }

        const { items, total } = data;
        const totalPages = Math.ceil(total / pageSize);

        const myFiles = items.filter(f => f.uploaded_by_user_id === state.currentUser.id);
        const accessibleFiles = items.filter(f => f.uploaded_by_user_id !== state.currentUser.id);

        // Cập nhật pagination
        document.getElementById('pagination-controls').innerHTML = renderPaginationControls(page, totalPages, pageType);

        // Cập nhật danh sách file
        document.getElementById('my-files-list').innerHTML =
            myFiles.length > 0
                ? `<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 card-container">${myFiles.map(createFileCard).join('')}</div>`
                : `<div class="empty-state">Không có file nào.</div>`;

        document.getElementById('shared-files-list').innerHTML =
            accessibleFiles.length > 0
                ? `<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 card-container">${accessibleFiles.map(createFileCard).join('')}</div>`
                : `<div class="empty-state">Không có file nào.</div>`;

        setupSearchEventListeners();
    } catch (error) {
        document.getElementById('my-files-list').innerHTML = `<div class="text-center text-red-400">Không thể tải dữ liệu file.</div>`;
        document.getElementById('shared-files-list').innerHTML = `<div class="text-center text-red-400">Không thể tải dữ liệu file.</div>`;
    }
}
async function renderManagementPage({ resource, title, columns, formFields, addEndpoint, hasDetails = false }, viewOptions = {}) {
    const isUserGroupView = resource === 'users' && viewOptions.withGroups;
    const isUserFileView = resource === 'users' && viewOptions.withFiles;

    let endpoint = `/${resource}`;
    if (isUserGroupView) endpoint = '/users/with_groups';
    if (isUserFileView) endpoint = '/users/with_files';

    const items = await api.get(endpoint);

    let viewTitle = title;
    if (isUserGroupView) viewTitle += ' theo Group';
    if (isUserFileView) viewTitle += ' và File truy cập';

    mainContent.innerHTML = `
         <div class="flex justify-between items-center mb-8">
             <div>
                 <h2 class="text-4xl font-bold text-white mb-2">${viewTitle}</h2>
                 <p class="text-black-900">Quản lý ${resource.replace(/_/g, ' ')}</p>
             </div>
             <div class="flex items-center space-x-3">
                 ${isUserGroupView || isUserFileView ? `
                     <button data-action="view-default-users" class="btn bg-gray-600/50 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-xl flex items-center">
                         Quay lại
                     </button>
                 ` : `
                     ${resource === 'users' ? `
                         <button data-action="view-user-files" class="btn bg-sky-500/80 hover:bg-sky-500 text-white font-semibold py-3 px-6 rounded-xl flex items-center">
                             Xem User Access File
                         </button>
                         <button data-action="view-user-groups" class="btn bg-teal-500/80 hover:bg-teal-500 text-white font-semibold py-3 px-6 rounded-xl flex items-center">
                             Xem User Group
                         </button>
                     ` : ''}
                     <button data-action="add" data-resource="${resource}" class="btn btn-primary text-white font-semibold py-3 px-6 rounded-xl flex items-center">
                         <svg class="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
                             <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
                         </svg>
                         Thêm mới
                     </button>
                 `}
             </div>
         </div>
         <div class="mb-6">${searchBarHtml}</div>
         <div class="bg-white-800/50 backdrop-blur-sm rounded-2xl shadow-xl overflow-hidden border border-gray-700/50">
             <div class="overflow-x-auto">
                 <table class="w-full text-left">
                     <thead class="bg-gray-50">
                         <tr>
                             ${(() => {
            if (isUserGroupView) {
                return `<th class="p-6 uppercase text-sm font-semibold text-black-900">Tên</th>
                                             <th class="p-6 uppercase text-sm font-semibold text-black-900">Email</th>
                                             <th class="p-6 uppercase text-sm font-semibold text-black-900">Vai trò</th>
                                             <th class="p-6 uppercase text-sm font-semibold text-black-900">Groups</th>`;
            }
            if (isUserFileView) {
                return `<th class="p-6 uppercase text-sm font-semibold text-black-300">Tên</th>
                                             <th class="p-6 uppercase text-sm font-semibold text-black-900">Email</th>
                                             <th class="p-6 uppercase text-sm font-semibold text-black-300" style="width: 50%;">Files được phép truy cập</th>`;
            }
            return `${columns.map(col => `<th class="p-6 uppercase text-sm font-semibold text-black-300">${col.header}</th>`).join('')}
                                         <th class="p-6 uppercase text-sm font-semibold text-black-300 text-right">Hành động</th>`;
        })()}
                         </tr>
                     </thead>
                     <tbody class="divide-y divide-gray-700/50">
                         ${items.length > 0 ? items.map(item => {
            let rowContent;
            if (isUserGroupView) {
                rowContent = `
                                     <td class="p-6 whitespace-nowrap text-black-200">${item.full_name || item.username || 'N/A'}</td>
                                     <td class="p-6 whitespace-nowrap text-black-200">${item.email || 'N/A'}</td>
                                     <td class="p-6 whitespace-nowrap text-black-200">${item.role || 'N/A'}</td>
                                     <td class="p-6 whitespace-nowrap text-black-200">
                                         <div class="flex flex-wrap gap-2">
                                             ${item.groups.length > 0 ? item.groups.map(g => `<span class="px-3 py-1 rounded-full text-xs font-medium ${getGroupTagColor(g.name)}">${g.name}</span>`).join('') : '<span class="text-black-500">No groups</span>'}
                                         </div>
                                     </td>`;
            } else if (isUserFileView) {
                const files = item.files || [];
                const visibleFiles = files.slice(0, 4);
                const hiddenFiles = files.slice(4);
                rowContent = `
                                     <td class="p-6 whitespace-nowrap text-black-200">${item.full_name || item.username || 'N/A'}</td>
                                     <td class="p-6 whitespace-nowrap text-black-200">${item.email || 'N/A'}</td>
                                     <td class="p-6 text-black-200">
                                         <div class="flex flex-wrap gap-2 items-center">
                                             ${files.length > 0 ? visibleFiles.map(f => `<span title="${f.original_file_name}" class="px-3 py-1 rounded-full text-xs font-medium ${getGroupTagColor(f.file_extension)} truncate max-w-[150px] inline-block">${f.original_file_name}</span>`).join('') : '<span class="text-black-500">Không có file</span>'}
                                             ${hiddenFiles.length > 0 ? `
                                                 <div class="hidden-tags hidden flex-wrap gap-2">
                                                     ${hiddenFiles.map(f => `<span title="${f.original_file_name}" class="px-3 py-1 rounded-full text-xs font-medium ${getGroupTagColor(f.file_extension)} truncate max-w-[150px] inline-block">${f.original_file_name}</span>`).join('')}
                                                 </div>
                                                 <button data-action="toggle-file-tags" class="text-indigo-400 hover:text-indigo-300 text-xs font-bold ml-2 whitespace-nowrap">
                                                     +${hiddenFiles.length} xem thêm
                                                 </button>
                                             ` : ''}
                                         </div>
                                     </td>`;
            } else {
                rowContent = `
                                     ${columns.map(col => `<td class="p-6 whitespace-nowrap text-black-200">${item[col.key] || 'N/A'}</td>`).join('')}
                                     <td class="p-6 text-right whitespace-nowrap">
                                         <div class="flex justify-end space-x-2">
                                             ${hasDetails ? `<button data-action="manage-details" data-resource="${resource}" data-id="${item.id}" data-name="${item.name}" class="btn px-4 py-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 font-medium text-sm">Quản lý</button>` : ''}
                                             <button data-action="edit" data-resource="${resource}" data-id="${item.id}" class="btn px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 font-medium text-sm">Sửa</button>
                                             ${resource === 'access_levels' && item.name.toLowerCase() === 'public' ? '' : `
                                             <button data-action="delete" data-resource="${resource}" data-id="${item.id}" class="btn px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 font-medium text-sm">Xóa</button>
                                             `}
                                         </div>
                                     </td>`;
            }
            return `<tr class="table-row" data-id="${item.id}">${rowContent}</tr>`;
        }).join('') : `<tr><td colspan="100%" class="text-center p-8 text-black-500">Không có dữ liệu.</td></tr>`}
                     </tbody>
                 </table>
             </div>
         </div>
     `;
    setupSearchFilter('search-input', '.table-row');
}

async function renderSettingsPage() {
    mainContent.innerHTML = `
         <div class="flex justify-between items-center mb-8">
             <div>
                 <h2 class="text-4xl font-bold text-black mb-2">Cài đặt</h2>
                 <p class="text-black-900">Quản lý cài đặt hệ thống</p>
             </div>
         </div>

         <div class="space-y-12">
             <!-- Keyword Settings -->
             <div>
                 <div class="flex items-center mb-4 border-b border-gray-700 pb-3">
                     <h3 class="text-2xl font-bold text-black flex-1">Keyword Autocomplete</h3>
                     <button data-action="toggle-settings-view" data-target="#keyword-settings-table" class="ml-4 p-2 rounded-full hover:bg-gray-200 transition-colors">
                         <svg class="w-6 h-6 text-black-900 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7 7" /></svg>
                     </button>
                 </div>
                 <div id="keyword-settings-table" class="hidden transition-all duration-500 ease-in-out">
                      <!-- Content will be loaded here -->
                      <div class="flex items-center justify-center py-12"><div class="loading-spinner"></div></div>
                 </div>
             </div>
         </div>
     `;

    const keywords = await api.get('/autoc/autocomplete/keywords');
    document.querySelector('#keyword-settings-table').innerHTML = `
         <div class="mb-6">${searchBarHtml}</div>
          <div class="bg-white-800/50 backdrop-blur-sm rounded-2xl shadow-xl overflow-hidden border border-gray-700/50">
             <div class="overflow-x-auto">
                 <table class="w-full text-left">
                     <thead class="bg-black-50">
                         <tr>
                             <th class="p-6 uppercase text-sm font-semibold text-black-300">Tên Thư mục</th>
                             <th class="p-6 uppercase text-sm font-semibold text-black-300">Keyword</th>
                             <th class="p-6 uppercase text-sm font-semibold text-black-300 text-right">Hành động</th>
                         </tr>
                     </thead>
                     <tbody class="divide-y divide-gray-700/50">
                         ${keywords.map(item => `
                             <tr class="table-row">
                                 <td class="p-6 whitespace-nowrap text-black-900">${item.folder_name}</td>
                                 <td class="p-6 whitespace-nowrap text-black-200 font-mono bg-white-700/30 rounded">${item.keyword}</td>
                                 <td class="p-6 text-right whitespace-nowrap">
                                     <button data-action="edit-keyword" data-id="${item.folder_id}" data-name="${item.folder_name}" data-keyword="${item.keyword}" class="btn px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 font-medium text-sm">Sửa</button>
                                 </td>
                             </tr>
                         `).join('')}
                     </tbody>
                 </table>
             </div>
         </div>
     `;
    setupSearchFilter('search-input', '.table-row');
}

// --- MODAL & FORM HANDLING ---
function openModal(title, bodyHtml) {
    modalTitle.textContent = title;
    modalBody.innerHTML = bodyHtml;
    modalBackdrop.style.display = 'flex';
}

function closeModal() {
    modalBackdrop.style.display = 'none';
    modalBody.innerHTML = ''; // Clear content to prevent old event listeners
}

function showConfirmationModal(title, message, onConfirm) {
    openModal(title, `
         <p class="text-black-700 mb-8">${message}</p>
         <div class="flex justify-end space-x-3">
             <button type="button" id="modal-cancel-btn" class="btn bg-gray-600/50 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-xl">Hủy</button>
             <button type="button" id="confirm-action-btn" class="btn bg-red-600 hover:bg-red-700 text-white font-semibold py-3 px-6 rounded-xl">Xác nhận</button>
         </div>
     `);
    const confirmBtn = document.getElementById('confirm-action-btn');
    confirmBtn.addEventListener('click', () => {
        onConfirm();
    }, { once: true });
}


function createFormHtml(fields, data = {}, isEdit = false) {
    return `
         <form id="modal-form" class="space-y-6" novalidate>
             ${fields.map(field => {
        const value = data[field.id] || '';
        switch (field.type) {
            case 'select':
                return `<div>
                             <label for="${field.id}" class="block text-sm font-medium text-black-700 mb-2">${field.label}</label>
                             <select id="${field.id}" name="${field.id}" ${field.required ? 'required' : ''} class="form-input w-full bg-white-700/50 border border-gray-600/50 text-black rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                                 <option value="">Chọn ${field.label.toLowerCase()}</option>
                                 ${field.options.map(opt => `<option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>${opt.label}</option>`).join('')}
                             </select>
                         </div>`;
            case 'multiselect':
                return `<div>
                             <label class="block text-sm font-medium text-black-700 mb-3">${field.label}</label>
                             <div class="bg-gray-50 border border-gray-200 rounded-xl p-4 max-h-60 overflow-y-auto">
                             ${field.options.map(opt => `
                                 <label class="flex items-center space-x-3 p-3 rounded-lg hover:bg-gray-600/50 transition-colors cursor-pointer">
                                     <input type="checkbox" name="${field.id}" value="${opt.value}" ${opt.checked ? 'checked' : ''} class="rounded bg-gray-800 border-gray-500 text-indigo-600 focus:ring-indigo-500 focus:ring-2">
                                     <span class="text-black-800">${opt.label}</span>
                                 </label>
                             `).join('')}
                             </div>
                         </div>`;
            case 'file':
                return `<div>
                             <label for="${field.id}" class="block text-sm font-medium text-black-700 mb-2">${field.label}</label>
                             <input type="file" id="${field.id}" name="${field.id}" ${field.required ? 'required' : ''} class="form-input w-full bg-white-700/50 border border-gray-600/50 text-black rounded-xl px-4 py-3 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-500 file:text-white hover:file:bg-indigo-600">
                         </div>`;
            case 'textarea':
                return `<div>
                             <label for="${field.id}" class="block text-sm font-medium text-black-700 mb-2">${field.label}</label>
                             <textarea id="${field.id}" name="${field.id}" rows="3" ${field.required ? 'required' : ''} class="form-input w-full bg-white-700/50 border border-gray-600/50 text-black rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:outline-none transition-all">${value}</textarea>
                         </div>`;
            default:
                if (isEdit && field.type === 'password' && field.id === 'password') {
                    return `<div>
                                 <label for="${field.id}" class="block text-sm font-medium text-black-300 mb-2">${field.label} (Để trống nếu không đổi)</label>
                                 <input type="${field.type}" id="${field.id}" name="${field.id}" class="form-input w-full bg-white-700/50 border border-white-600/50 text-black rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:outline-none transition-all">
                             </div>`;
                }
                return `<div>
                             <label for="${field.id}" class="block text-sm font-medium text-black-700 mb-2">${field.label}</label>
                             <input type="${field.type}" id="${field.id}" name="${field.id}" value="${value}" ${field.required ? 'required' : ''} class="form-input w-full bg-white-700/50 border border-gray-600/50 text-black rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 focus:outline-none transition-all">
                         </div>`;
        }
    }).join('')}
             <div class="pt-6 flex justify-end space-x-3">
                 <button type="button" id="modal-cancel-btn" class="btn bg-gray-600/50 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-xl transition-all">Hủy</button>
                 <button type="submit" class="btn btn-primary text-white font-semibold py-3 px-6 rounded-xl flex items-center justify-center">
                     <span class="btn-text">Lưu</span>
                     <div class="loading-spinner hidden ml-2"></div>
                 </button>
             </div>
         </form>
     `;
}


// --- ROUTING ---
const pageConfigs = {
    'manage-users': {
        resource: 'users',
        title: 'Quản lý User',
        addEndpoint: '/users/register',
        columns: [{ header: 'ID', key: 'id' }, { header: 'Tên', key: 'full_name' }, { header: 'Email', key: 'email' }, { header: 'Vai trò', key: 'role' }],
        formFields: [
            { id: 'full_name', label: 'Họ và Tên', type: 'text', required: true },
            { id: 'email', label: 'Email', type: 'email', required: true },
            { id: 'username', label: 'Tên đăng nhập', type: 'text', required: true },
            {
                id: 'role',
                label: 'Vai trò',
                type: 'select',
                required: true,
                options: [
                    { value: 'user', label: 'User' },
                    { value: 'admin', label: 'Admin' }
                ]
            },
            { id: 'password', label: 'Mật khẩu', type: 'password', required: true },
        ]
    },
    'manage-groups': {
        resource: 'groups',
        title: 'Quản lý Group',
        columns: [{ header: 'ID', key: 'id' }, { header: 'Tên Group', key: 'name' }, { header: 'Mô tả', key: 'description' }],
        formFields: [
            { id: 'name', label: 'Tên Group', type: 'text', required: true },
            { id: 'description', label: 'Mô tả', type: 'textarea', required: false },
        ],
        hasDetails: true,
    },
    'manage-access-levels': {
        resource: 'access_levels',
        title: 'Quản lý Cấp độ Truy cập',
        columns: [{ header: 'ID', key: 'id' }, { header: 'Tên Cấp độ', key: 'name' }, { header: 'Mô tả', key: 'description' }],
        formFields: [
            { id: 'name', label: 'Tên Cấp độ', type: 'text', required: true },
            { id: 'description', label: 'Mô tả', type: 'textarea', required: false },
        ]
    }
};

const routes = {
    'manage-folders': () => renderFolderManager(state.currentFolderId), // Giữ nguyên folder hiện tại
    'view-files': () => renderAllFilesPage(state.allFilesPage),
    'manage-users': () => renderManagementPage(pageConfigs['manage-users']),
    'manage-groups': () => renderManagementPage(pageConfigs['manage-groups']),
    'manage-access-levels': () => renderManagementPage(pageConfigs['manage-access-levels']),
    'manage-settings': renderSettingsPage,
};

async function navigate(page, params = null) {
    console.log(`Navigating to page: ${page}, params:`, params);
    state.currentPage = page;

    // Khi chuyển trang manage-folders lần đầu (không phải refresh), reset về root
    if (page === 'manage-folders' && params !== 'refresh') {
        console.log('Navigating to manage-folders - resetting to root');
        state.currentFolderId = null;
        state.folderHistory = [];
    }

    // Lưu state sau khi thay đổi
    saveState();

    const renderer = routes[page];
    if (renderer) {
        // Show loading immediately
        mainContent.innerHTML = `
             <div class="flex items-center justify-center h-full">
                 <div class="text-center">
                     <div class="loading-spinner mx-auto mb-4" style="width: 48px; height: 48px; border-width: 4px;"></div>
                     <p class="text-black-900 text-lg">Đang tải dữ liệu...</p>
                 </div>
             </div>
         `;

        // Update navigation immediately to show active state
        renderNav();

        // Use requestAnimationFrame to ensure UI updates before starting async operation
        requestAnimationFrame(() => {
            setTimeout(async () => {
                try {
                    await renderer(params);
                } catch (e) {
                    console.error('Navigation error:', e);
                    mainContent.innerHTML = `<div class="text-center text-red-400 p-8 bg-red-500/10 rounded-lg">Không thể tải nội dung trang. Vui lòng thử lại.</div>`;
                }
            }, 10); // Small delay to ensure UI is responsive
        });
    } else {
        mainContent.innerHTML = `<h2 class="text-2xl">Page not found</h2>`;
        renderNav();
    }
}

// Helper function to refresh current page content without changing navigation
async function refreshCurrentPage(params = null) {
    console.log(`Refreshing current page: ${state.currentPage}`);
    const renderer = routes[state.currentPage];
    if (renderer) {
        try {
            // Đối với trang manage-folders, đảm bảo giữ nguyên folder hiện tại
            if (state.currentPage === 'manage-folders') {
                await renderFolderManager(state.currentFolderId);
            } else {
                await renderer(params);
            }
        } catch (e) {
            console.error('Error refreshing page:', e);
            mainContent.innerHTML = `<div class="text-center text-red-400 p-8 bg-red-500/10 rounded-lg">Không thể tải nội dung trang. Vui lòng thử lại.</div>`
        }
    }
}

// --- EVENT LISTENERS ---
mainNav.addEventListener('click', (e) => {
    e.preventDefault();
    const link = e.target.closest('.nav-link');
    if (link && link.dataset.page && state.currentPage !== link.dataset.page) {
        navigate(link.dataset.page);
    }
});

mainContent.addEventListener('click', async (e) => {
    const folderLink = e.target.closest('.folder-link');
    if (folderLink) {
        e.preventDefault();
        const folderIdAttr = folderLink.dataset.folderId;
        const targetFolderId = (folderIdAttr === "" || folderIdAttr === null || folderIdAttr === undefined) ? null : folderIdAttr;

        if (state.currentFolderId === targetFolderId) return;

        if (targetFolderId) {
            const existingIndex = state.folderHistory.findIndex(f => f.id === targetFolderId);
            if (existingIndex > -1) {
                state.folderHistory.splice(existingIndex + 1);
            } else {
                const folderName = folderLink.querySelector('h4')?.textContent || folderLink.textContent.trim();
                state.folderHistory.push({ id: targetFolderId, name: folderName });
            }
        } else {
            console.log('Navigating to root - clearing folderHistory');
            state.folderHistory = [];
        }

        // Lưu state khi thay đổi folder
        saveState();
        console.log('Folder navigation - new state:', {
            currentFolderId: targetFolderId,
            folderHistory: state.folderHistory
        });
        renderFolderManager(targetFolderId);
        return;
    }

    const paginationLink = e.target.closest('.pagination-link');
    if (paginationLink) {
        e.preventDefault();
        const page = parseInt(paginationLink.dataset.page, 10);
        if (!isNaN(page) && page !== state.allFilesPage && !paginationLink.classList.contains('opacity-50')) {
            await renderAllFilesPage({ page });
        }
        return; // Stop further execution
    }


    const target = e.target.closest('[data-action]');
    if (!target) return;

    const action = target.dataset.action;
    const resource = target.dataset.resource;
    const id = target.dataset.id;
    const name = target.dataset.name;

    try {
        switch (action) {
            case 'add':
                const addKey = `manage-${resource.replace(/_/g, '-')}`;
                const addConfig = pageConfigs[addKey];
                openModal(`Thêm mới ${addConfig.title.replace('Quản lý ', '')}`, createFormHtml(addConfig.formFields, {}, false));
                handleCrudFormSubmit(resource);
                break;
            case 'edit':
                const editKey = `manage-${resource.replace(/_/g, '-')}`;
                const editConfig = pageConfigs[editKey];
                const itemData = await api.get(`/${resource}/${id}`);
                const editFormFields = JSON.parse(JSON.stringify(editConfig.formFields));
                if (resource === 'users') {
                    const passField = editFormFields.find(f => f.id === 'password');
                    if (passField) passField.required = false;
                }
                openModal(`Chỉnh sửa ${editConfig.title.replace('Quản lý ', '')}`, createFormHtml(editFormFields, itemData, true));
                handleCrudFormSubmit(resource, id);
                break;
            case 'delete':
                showConfirmationModal('Xác nhận xóa', 'Bạn có chắc chắn muốn xóa mục này? Hành động này không thể hoàn tác.', async () => {
                    await api.delete(`/${resource}/${id}`);
                    showCustomAlert('Xóa thành công!', 'success');
                    closeModal();
                    await refreshCurrentPage();
                });
                break;
            case 'view-user-groups':
                await renderManagementPage(pageConfigs['manage-users'], { withGroups: true });
                break;
            case 'view-user-files':
                await renderManagementPage(pageConfigs['manage-users'], { withFiles: true });
                break;
            case 'view-default-users':
                await renderManagementPage(pageConfigs['manage-users']);
                break;
            case 'toggle-file-tags':
                const container = target.previousElementSibling;
                container.classList.toggle('hidden');
                container.classList.toggle('flex');
                if (container.classList.contains('hidden')) {
                    target.textContent = `+${container.children.length} xem thêm`;
                } else {
                    target.textContent = 'ẩn bớt';
                }
                break;
            case 'toggle-settings-view':
                const settingsTarget = document.querySelector(target.dataset.target);
                const icon = target.querySelector('svg');
                if (settingsTarget) {
                    settingsTarget.classList.toggle('hidden');
                    icon.classList.toggle('rotate-180');
                }
                break;
            case 'refresh-access':
                target.disabled = true;
                const refreshIcon = target.querySelector('svg');
                refreshIcon.classList.add('animate-spin');
                try {
                    await api.post('/file/me/refresh-access');
                    showCustomAlert('Làm mới quyền truy cập thành công!', 'success');
                    await renderAllFilesPage();
                } catch (e) {
                    console.error('Làm mới quyền truy cập thất bại:', e);
                    showCustomAlert('Có lỗi xảy ra khi làm mới quyền truy cập', 'error');
                } finally {
                    // Always re-enable the button and remove spinner, whether successful or not
                    target.disabled = false;
                    refreshIcon.classList.remove('animate-spin');
                }
                break;
            case 'manage-details':
                await openManageGroupModal(id, name);
                break;
            case 'edit-keyword':
                openModal(`Sửa Keyword cho: ${name}`, createFormHtml([
                    { id: 'keyword', label: 'Keyword mới', type: 'text', required: true }
                ], { keyword: target.dataset.keyword }));
                handleKeywordEditFormSubmit(id);
                break;
            case 'add-folder':
                openModal('Tạo thư mục mới', createFormHtml([{ id: 'name', label: 'Tên thư mục', type: 'text', required: true }], { parent_id: state.currentFolderId }));
                handleFolderFormSubmit();
                break;
            case 'edit-folder':
                openModal('Sửa tên thư mục', createFormHtml([{ id: 'name', label: 'Tên thư mục mới', type: 'text', required: true }], { name }));
                handleFolderFormSubmit(id);
                break;
            case 'delete-folder':
                showConfirmationModal('Xác nhận xóa thư mục', 'Bạn có chắc chắn muốn xóa thư mục này và tất cả nội dung bên trong?', async () => {
                    await api.delete(`/file/folders/${id}`);
                    showCustomAlert('Xóa thư mục thành công!', 'success');
                    closeModal();
                    await refreshCurrentPage();
                });
                break;
            case 'upload-file':
                const uploadFolderId = target.dataset.folderId || state.currentFolderId || rootFolderId;
                const currentFolderName = state.folderHistory.length > 0 ? state.folderHistory[state.folderHistory.length - 1].name : 'Root';

                openModal(`Upload file vào: ${currentFolderName}`, `
                     <form id="upload-form" class="space-y-4">
                         <input type="hidden" name="folder_id" value="${uploadFolderId}">

                         <!-- File List Area - Always visible -->
                         <div class="file-list-area">
                             <div class="bg-gray-50 rounded-xl p-4 border border-gray-200">
                                 <h4 class="text-sm font-medium text-black-700 dark:text-black-300 mb-3">Danh sách file đã chọn</h4>
                                 <div class="file-list mt-2 space-y-2 max-h-60 overflow-y-auto">
                                     <div class="text-sm text-black-500 dark:text-black-900 text-center py-8">
                                         Chưa có file nào được chọn
                                     </div>
                                 </div>
                             </div>
                         </div>

                         <div id="upload-status" class="hidden">
                             <div class="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
                                 <div class="flex items-center">
                                     <div class="loading-spinner mr-3"></div>
                                     <div>
                                         <p class="text-blue-300 font-medium">Đang xử lý file...</p>
                                         <p class="text-blue-200 text-sm">Vui lòng đợi trong khi hệ thống xử lý OCR và phân tích nội dung</p>
                                     </div>
                                 </div>
                             </div>
                         </div>
                         <div class="pt-4 flex justify-end space-x-3">
                             <button type="button" id="modal-cancel-btn" class="btn bg-gray-600/50 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-xl">Hủy</button>
                             <button type="submit" class="btn btn-primary text-white font-semibold py-3 px-6 rounded-xl flex items-center justify-center">
                                 <span class="btn-text">Upload</span>
                                 <div class="loading-spinner hidden ml-2"></div>
                             </button>
                         </div>
                     </form>
                 `);
                handleUploadFormSubmit();
                break;
            case 'manage-file-access':
                await openManageFileAccessModal(id);
                break;
            case 'edit-file':
                const fileData = await api.get(`/file/files/${id}`);
                openModal('Sửa thông tin file', createFormHtml([{ id: 'original_file_name', label: 'Tên file', type: 'text', required: true }], fileData));
                handleFileEditFormSubmit(id);
                break;
            case 'delete-file':
                showConfirmationModal('Xác nhận xóa file', 'Bạn có chắc chắn muốn xóa file này?', async () => {
                    try {
                        await api.delete(`/file/files/${id}`);
                        showCustomAlert('Xóa file thành công!', 'success');
                        closeModal();
                        // Refresh current page to stay in current tab
                        await refreshCurrentPage();
                    } catch (error) {
                        showCustomAlert(error.message || 'Xóa file thất bại', 'error');
                    }
                });
                break;
            case 'view-file-details':
                if (state.currentPage === 'manage-folders' && state.currentUser && state.currentUser.role === 'user') {
                    return;
                }

                const details = await api.get(`/file/files/${id}`); // Giả sử đã có dữ liệu trong biến `details`

                // --- Bắt đầu phần hiển thị Chi tiết file đã tùy chỉnh ---

                let detailsHtml = '<div class="space-y-3 text-black-300 max-h-[60vh] overflow-y-auto">';



                // 2. Định nghĩa thứ tự các key cần hiển thị ở cuối
                const final_keys = [
                    'folder_id',
                    'id',
                    'original_file_name',
                    'file_extension',
                    'file_size_bytes',
                    'storage_path',
                    'upload_timestamp',
                    'last_modified_timestamp',
                    'uploaded_by_user_id',
                ];

                // Tạo một Map để dễ dàng lấy các giá trị của các key còn lại
                // const other_details = new Map(Object.entries(details).filter(([key]) => !final_keys.includes(key) && key !== 'extracted_text'));

                // 3. Hiển thị các trường thông tin còn lại không nằm trong danh sách cuối cùng (nếu có)
                // for (const [key, value] of other_details) {
                //     const display_key = key.replace(/_/g, ' ');
                //     const display_value = value || 'N/A';
                //     // Sử dụng text-sm cho các chi tiết khác để tiết kiệm không gian
                //     detailsHtml += `<div class="flex justify-between py-1 border-b border-gray-700/50 text-sm"><strong class="text-white capitalize pr-4">${display_key}:</strong> <span class="text-black-300 text-right truncate" title="${display_value}">${display_value}</span></div>`;
                // }

                // 4. Hiển thị các trường cố định theo thứ tự yêu cầu
                detailsHtml += '<div class="pt-4 border-t border-gray-700/50 mt-4">'; // Tạo một section riêng cho các chi tiết cuối cùng
                for (const key of final_keys) {
                    const value = details[key] !== undefined ? details[key] : 'N/A';
                    const display_key = key.replace(/_/g, ' ');
                    const display_value = value || 'N/A';
                    // Vẫn sử dụng text-sm và định dạng tương tự
                    detailsHtml += `<div class="flex justify-between py-1 border-b border-gray-700/50 text-sm"><strong class="text-black capitalize pr-4">${display_key}:</strong> <span class="text-black-300 text-right truncate" title="${display_value}">${display_value}</span></div>`;
                }
                detailsHtml += '</div>';
                // 1. Hiển thị Extracted Text trong khung riêng, lớn
                if (details.extracted_text) {
                    detailsHtml += `
                        <div class="py-2 border-b border-gray-700/50">
                            <strong class="text-white capitalize pr-4">Nội dung trích xuất (Extracted Text):</strong>
                            <div class="mt-2 p-3 bg-white-800 rounded-lg border border-gray-700 max-h-60vh overflow-auto text-sm whitespace-pre-wrap">
                                ${details.extracted_text || 'N/A'}
                            </div>
                        </div>
                    `;
                }
                detailsHtml += '</div>'; // Đóng thẻ div max-h-[60vh] overflow-y-auto

                openModal(`Chi tiết file: ${details.original_file_name}`, detailsHtml);
                break;
        }
    } catch (error) {
        console.error('Action error:', error);
    }
});

async function openManageGroupModal(groupId, groupName) {
    try {
        const modalContent = `<div class="flex items-center justify-center py-12"><div class="loading-spinner"></div></div>`;
        openModal(`Quản lý Group: ${groupName}`, modalContent);

        const [allUsers, allLevels, groupUsers, groupLevels] = await Promise.all([
            api.get('/users'),
            api.get('/access_levels'),
            api.get(`/groups/${groupId}/users`).catch(() => []),
            api.get(`/groups/${groupId}/access_levels`).catch(() => [])
        ]);

        const groupUserIds = new Set(groupUsers.map(u => u.id));
        const groupLevelIds = new Set(groupLevels.map(l => l.id));

        const usersField = { id: 'user_ids', label: 'Thành viên', type: 'multiselect', options: allUsers.map(u => ({ value: u.id, label: `${u.full_name} (${u.email})`, checked: groupUserIds.has(u.id) })) };
        const levelsField = { id: 'access_level_ids', label: 'Cấp độ truy cập', type: 'multiselect', options: allLevels.map(l => ({ value: l.id, label: l.name, checked: groupLevelIds.has(l.id) })) };

        modalBody.innerHTML = createFormHtml([usersField, levelsField]);

        document.getElementById('modal-form').onsubmit = async (e) => {
            e.preventDefault();
            const form = e.target;
            const btn = form.querySelector('button[type="submit"]');
            const btnText = btn.querySelector('.btn-text');
            const spinner = btn.querySelector('.loading-spinner');

            btn.disabled = true;
            btnText.textContent = 'Đang lưu...';
            spinner.classList.remove('hidden');

            try {
                const formData = new FormData(form);
                const selectedUserIds = Array.from(new Set(formData.getAll('user_ids')));
                const selectedLevelIds = formData.getAll('access_level_ids');

                // Update users in the group
                await api.put(`/groups/${groupId}/update_users`, {
                    user_ids: selectedUserIds
                });

                // Update access levels for the group
                await api.post(`/groups/${groupId}/assign_access_levels`, {
                    access_level_ids: selectedLevelIds
                });

                showCustomAlert('Cập nhật group thành công!', 'success');
                closeModal();
                await refreshCurrentPage();
            } catch (error) {
                // Error is already shown by the API client
            } finally {
                btn.disabled = false;
                btnText.textContent = 'Lưu';
                spinner.classList.add('hidden');
            }
        };
    } catch (error) {
        showCustomAlert(`Không thể tải thông tin group: ${error.message}`, 'error');
        closeModal();
    }
}

async function openManageFileAccessModal(fileId) {
    try {
        openModal(`Phân quyền cho File`, `<div class="flex items-center justify-center py-12"><div class="loading-spinner"></div></div>`);
        const [allLevels, fileLevels] = await Promise.all([
            api.get('/access_levels'),
            api.get(`/access_levels/files/${fileId}/access-levels`).catch(() => [])
        ]);

        const fileLevelIds = new Set(fileLevels.map(l => l.id));
        const levelsField = { id: 'access_level_ids', label: 'Chọn cấp độ truy cập', type: 'multiselect', options: allLevels.map(l => ({ value: l.id, label: l.name, checked: fileLevelIds.has(l.id) })) };

        modalBody.innerHTML = createFormHtml([levelsField]);

        document.getElementById('modal-form').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const selectedLevelIds = formData.getAll('access_level_ids');

            try {
                await api.post(`/access_levels/files/${fileId}/access-levels`, { access_level_ids: selectedLevelIds });
                showCustomAlert('Cập nhật quyền file thành công!', 'success');
                closeModal();
                await refreshCurrentPage();
            } catch (error) {
                // error shown by api client
            }
        };
    } catch (error) {
        showCustomAlert(`Không thể tải thông tin phân quyền: ${error.message}`, 'error');
        closeModal();
    }
}

function handleCrudFormSubmit(resource, id = null) {
    const form = document.getElementById('modal-form');
    if (!form) return;
    form.onsubmit = async (e) => {
        e.preventDefault();
        const btn = form.querySelector('button[type="submit"]');
        const btnText = btn.querySelector('.btn-text');
        const spinner = btn.querySelector('.loading-spinner');

        btn.disabled = true;
        btnText.textContent = 'Đang lưu...';
        spinner.classList.remove('hidden');

        const formData = new FormData(form);
        let data = Object.fromEntries(formData.entries());

        if (resource === 'users' && !data.password) {
            delete data.password;
        }

        try {
            const configKey = `manage-${resource.replace(/_/g, '-')}`;
            const config = pageConfigs[configKey];
            if (id) {
                await api.put(`/${resource}/${id}`, data);
            } else {
                const endpoint = config.addEndpoint || `/${resource}`;
                await api.post(endpoint, data);
            }
            showCustomAlert('Thao tác thành công!', 'success');
            closeModal();
            await refreshCurrentPage();
        } catch (error) {
            // Error is already shown by api client
        } finally {
            btn.disabled = false;
            btnText.textContent = 'Lưu';
            spinner.classList.add('hidden');
        }
    };
}

function handleKeywordEditFormSubmit(folderId) {
    const form = document.getElementById('modal-form');
    if (!form) return;
    form.onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = {
            keyword: formData.get('keyword')
        };
        try {
            await api.put(`/file/folders/${folderId}`, data);
            showCustomAlert('Cập nhật keyword thành công!', 'success');
            closeModal();
            await refreshCurrentPage();
        } catch (error) { /* error handled by api client */ }
    };
}

function handleFolderFormSubmit(id = null) {
    const form = document.getElementById('modal-form');
    if (!form) return;
    form.onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = { name: formData.get('name') };
        try {
            if (id) {
                await api.put(`/file/folders/${id}`, data);
            } else {
                data.parent_id = state.currentFolderId || null;
                await api.post('/file/folders', data);
            }
            showCustomAlert('Thao tác thư mục thành công!', 'success');
            closeModal();
            await refreshCurrentPage();
        } catch (error) {
            // Error already shown
        }
    }
}

function handleFileEditFormSubmit(id) {
    const form = document.getElementById('modal-form');
    if (!form) return;
    form.onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = { original_file_name: formData.get('original_file_name') };
        try {
            await api.put(`/file/files/${id}`, data);
            showCustomAlert('Cập nhật file thành công!', 'success');
            closeModal();
            await refreshCurrentPage();
        } catch (error) {
            // Error already shown by api client
        }
    }
}

// --- ASYNC UPLOAD SYSTEM ---
async function performAsyncUpload(file, folderId, uploadId) {
    const controller = new AbortController();
    let uploadSuccessful = false;

    try {
        // Add to upload manager
        const upload = uploadManager.addUpload(uploadId, file, folderId);

        const formData = new FormData();
        formData.append('file', file);

        if (folderId && folderId !== 'null') {
            formData.append('folder_id', folderId);
        }

        updateUploadProgress(uploadId, 10, 'Đang chuẩn bị...');

        // Use XMLHttpRequest for better progress tracking
        const xhr = new XMLHttpRequest();
        upload.xhr = xhr; // Assign xhr for cancellation
        xhr.open('POST', `${BASE_URL}/file/files`, true);
        const token = localStorage.getItem('authToken');
        console.log('Auth token exists:', !!token);
        console.log('Auth token length:', token ? token.length : 0);
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);

        // Track upload progress
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                // Scale upload to 70% of total progress
                const uploadPercentage = Math.round((e.loaded / e.total) * 70);
                updateUploadProgress(uploadId, uploadPercentage, 'Đang tải lên...');
            }
        };

        // Handle response
        xhr.onload = async () => {
            console.log('Upload response status:', xhr.status);
            console.log('Upload response text:', xhr.responseText);

            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const newFile = JSON.parse(xhr.responseText);
                    console.log('Upload successful, file data:', newFile);
                    if (newFile && newFile.id) {
                        // Update to 80% when starting to process
                        updateUploadProgress(uploadId, 80, 'Đang xử lý...');

                        // Handle permissions if needed
                        const ROOT_FOLDER_ID = '860ff0c7-73d9-4003-95f3-5d47ca3a95ed';
                        if (folderId === null || folderId !== ROOT_FOLDER_ID) {
                            // Update to 90% when starting permission handling
                            updateUploadProgress(uploadId, 90, 'Đang phân quyền...');

                            try {
                                // Use the api client instead of fetch directly
                                console.log('Attempting to assign permissions for file:', newFile.id);
                                console.log('Access level ID:', '0c31fdb4-d4b1-4665-8568-e8da1f2e50cf');
                                await api.post(`/access_levels/files/${newFile.id}/access-levels`, {
                                    access_level_ids: ['0c31fdb4-d4b1-4665-8568-e8da1f2e50cf']
                                }, { priority: 'high' });
                                console.log('Permission assignment successful for file:', newFile.id);

                            } catch (permError) {
                                console.warn('Permission assignment error for file:', newFile.id, permError);
                                console.warn('Error details:', permError.message, permError.status);
                                // Don't fail the upload for permission errors
                            }
                        } else {
                            // For root folder, skip permission assignment
                            console.log('Skipping permission assignment for root folder file:', newFile.id);
                        }

                        uploadSuccessful = true;
                        completeUploadNotification(uploadId, true, `File "${file.name}" đã được upload thành công`);

                        // Only refresh if user is still on manage-folders or view-files page
                        // Update to 100% when fully completed
                        updateUploadProgress(uploadId, 100, 'Hoàn thành');

                        setTimeout(() => {
                            if (state.currentPage === 'manage-folders' || state.currentPage === 'view-files') {
                                refreshCurrentPage();
                            }
                        }, 1500);
                    } else {
                        throw new Error('Upload thành công nhưng không nhận được thông tin file');
                    }
                } catch (error) {
                    completeUploadNotification(uploadId, false, error.message || 'Lỗi khi xử lý phản hồi');
                    console.error('Error processing upload response:', error);
                }
            } else {
                console.log('Upload failed with status:', xhr.status);
                console.log('Upload failed response:', xhr.responseText);
                let errorMessage = 'Upload thất bại';
                try {
                    const errorData = JSON.parse(xhr.responseText);
                    console.log('Parsed error data:', errorData);
                    errorMessage = errorData.detail || errorMessage;
                } catch (e) {
                    console.error('Error parsing error response:', e);
                }
                completeUploadNotification(uploadId, false, errorMessage);
            }
        };

        xhr.onerror = () => {
            completeUploadNotification(uploadId, false, 'Lỗi kết nối');
        };

        xhr.send(formData);

        // Wait for the upload to complete or be canceled
        await new Promise((resolve) => {
            const checkComplete = setInterval(() => {
                const upload = uploadManager.uploads.get(uploadId);
                if (!upload || upload.status === 'completed' || upload.status === 'failed') {
                    clearInterval(checkComplete);
                    resolve();
                }
            }, 100);
        });

    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Upload was cancelled');
            return;
        }

        console.error('Upload error:', error);
        if (!uploadSuccessful) {
            completeUploadNotification(uploadId, false, error.message || 'Upload thất bại');
        }
    } finally {
        // Clean up after a delay to show completion status
        setTimeout(() => {
            state.activeUploads.delete(uploadId);
        }, 3000);
    }
}

function handleUploadFormSubmit() {
    const form = document.getElementById('upload-form');
    if (!form) return;

    // Create or get the file input
    let fileInput = form.querySelector('input[type="file"]');
    if (!fileInput) {
        fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.multiple = true;
        fileInput.className = 'hidden';
        form.appendChild(fileInput);
    }
    fileInput.multiple = true;

    // Create the drop zone if it doesn't exist
    let dropZone = form.querySelector('.upload-drop-zone');
    if (!dropZone) {
        dropZone = document.createElement('div');
        form.appendChild(dropZone);
        dropZone.className = 'upload-drop-zone border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 text-center cursor-pointer hover:border-blue-500 hover:bg-blue-50/50 dark:hover:bg-gray-700/50 transition-colors duration-200 mb-6';
        dropZone.innerHTML = `
            <div class="upload-content">
                <div class="flex flex-col items-center justify-center space-y-3">
                    <div class="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center text-blue-500 dark:text-blue-400">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                        </svg>
                    </div>
                    <div>
                        <p class="text-sm font-medium text-black-700 dark:text-black-200">Kéo và thả nhiều file vào đây hoặc <span class="text-blue-600 dark:text-blue-400 hover:underline">chọn nhiều file</span></p>
                        <p class="text-xs text-black-500 dark:text-black-900 mt-1">Hỗ trợ: PDF, DOCX, XLSX, PPTX, JPG, PNG (tối đa 100MB mỗi file)</p>
                    </div>
                </div>
            </div>
        `;
        form.insertBefore(dropZone, form.firstChild);
    }

    // Add drag and drop support
    let isDragging = false;
    let dragCounter = 0;
    let currentFiles = []; // Track current selected files

    const preventDefaults = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const highlight = () => {
        dropZone.classList.add('border-blue-500', 'bg-blue-50/70', 'dark:bg-blue-900/20');
        dropZone.querySelector('.upload-content').classList.add('opacity-50');
    };

    const unhighlight = () => {
        dropZone.classList.remove('border-blue-500', 'bg-blue-50/70', 'dark:bg-blue-900/20');
        dropZone.querySelector('.upload-content').classList.remove('opacity-50');
    };

    // Handle all drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dragCounter++;
            highlight();
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dragCounter--;
            if (dragCounter === 0) {
                unhighlight();
            }
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const newFiles = dt.files;
        if (newFiles.length > 0) {
            // Combine existing files with new ones, avoid duplicates
            const existingFileNames = currentFiles.map(f => f.name);
            const uniqueNewFiles = Array.from(newFiles).filter(file => !existingFileNames.includes(file.name));
            const allFiles = [...currentFiles, ...uniqueNewFiles];

            // Create new FileList
            const dataTransfer = new DataTransfer();
            allFiles.forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;

            // Update current files and UI
            currentFiles = allFiles;
            updateFileList(dataTransfer.files);

            // Show message if some files were skipped
            if (uniqueNewFiles.length < newFiles.length) {
                showCustomAlert('Một số file đã được chọn trước đó và đã được bỏ qua.', 'info');
            }
        }
    });

    // Click to select files
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file input change - combine with existing files
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            // Combine existing files with newly selected files, avoid duplicates
            const newFiles = Array.from(fileInput.files);
            const existingFileNames = currentFiles.map(f => f.name);
            const uniqueNewFiles = newFiles.filter(file => !existingFileNames.includes(file.name));
            const allFiles = [...currentFiles, ...uniqueNewFiles];

            // Create new FileList with all files
            const dataTransfer = new DataTransfer();
            allFiles.forEach(file => dataTransfer.items.add(file));
            fileInput.files = dataTransfer.files;

            // Update current files and UI
            currentFiles = allFiles;
            updateFileList(dataTransfer.files);

            // Show message if some files were skipped
            if (uniqueNewFiles.length < newFiles.length) {
                showCustomAlert('Một số file đã được chọn trước đó và đã được bỏ qua.', 'info');
            }
        }
    });

    // Update the form submission
    form.onsubmit = async (e) => {
        e.preventDefault();

        const files = fileInput.files;
        if (!files || files.length === 0) {
            showCustomAlert('Vui lòng chọn ít nhất một file.', 'error');
            return;
        }

        // Check file sizes (max 100MB per file)
        const maxSize = 500 * 1024 * 1024; // 500MB
        const oversizedFiles = Array.from(files).filter(file => file.size > maxSize);
        if (oversizedFiles.length > 0) {
            const fileNames = oversizedFiles.map(f => `• ${f.name} (${formatFileSize(f.size)})`).join('\n');
            showCustomAlert(`Các file sau vượt quá giới hạn 100MB:\n${fileNames}`, 'error');
            return;
        }

        // Get folder info
        const folderId = form.querySelector('input[name="folder_id"]')?.value || null;

        // Close modal
        closeModal();

        // Start async upload for each file
        Array.from(files).forEach((file, index) => {
            const uploadId = `upload-${Date.now()}-${index}`;
            performAsyncUpload(file, folderId, uploadId);
        });
    };

    // Helper function to update file list display
    function updateFileList(files) {
        const fileList = form.querySelector('.file-list');
        if (!fileList) return;

        fileList.innerHTML = '';

        if (files.length === 0) {
            fileList.innerHTML = '<div class="text-sm text-black-600 text-center py-8">Chưa có file nào được chọn.<br>Click vào vùng trên để chọn file hoặc kéo thả file vào đây.</div>';
            return;
        }

        // Show file count
        const fileCount = document.createElement('div');
        fileCount.className = 'text-sm text-black-700 dark:text-black-300 mb-2';
        fileCount.textContent = `Đã chọn ${files.length} ${files.length > 1 ? 'files' : 'file'}`;
        fileList.appendChild(fileCount);

        // Add each file
        Array.from(files).forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200';
            fileItem.innerHTML = `
                <div class="flex items-center gap-3 flex-1 min-w-0">
                    <div class="flex-shrink-0 w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center text-blue-500">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                    </div>
                    <div class="min-w-0">
                        <div class="text-sm font-medium text-black-900 dark:text-black-100 truncate" title="${file.name}">${file.name}</div>
                        <div class="text-xs text-black-500 dark:text-black-900">${formatFileSize(file.size)}</div>
                    </div>
                </div>
                <button type="button" class="text-black-900 hover:text-red-500 transition-colors p-1 -mr-1" data-index="${index}" title="Xóa">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            `;

            // Add remove file handler
            const removeBtn = fileItem.querySelector('button');
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const index = parseInt(removeBtn.dataset.index);

                // Remove file from currentFiles array
                const newFiles = [...currentFiles];
                newFiles.splice(index, 1);

                // Create new FileList
                const dataTransfer = new DataTransfer();
                newFiles.forEach(file => dataTransfer.items.add(file));
                fileInput.files = dataTransfer.files;

                // Update current files and UI
                currentFiles = newFiles;
                updateFileList(dataTransfer.files);
            });

            fileList.appendChild(fileItem);
        });
    }

    // Helper function to format file size
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

// Thêm sự kiện click cho nút đóng modal
modalCloseBtn.addEventListener('click', closeModal);

// Thêm sự kiện click ra ngoài modal để đóng
modalBackdrop.addEventListener('click', (e) => {
    if (e.target === modalBackdrop) {
        closeModal();
    }
});

document.body.addEventListener('click', (e) => {
    if (e.target.id === 'modal-cancel-btn') closeModal();
});


// --- AUTHENTICATION & THEME LOGIC ---
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const loginError = document.getElementById('login-error');
    const loginBtnText = document.getElementById('login-btn-text');
    const loginSpinner = document.getElementById('login-spinner');

    loginError.classList.add('hidden');
    loginBtnText.textContent = 'Đang đăng nhập...';
    loginSpinner.classList.remove('hidden');

    try {
        const response = await api.login(email, password);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Email hoặc mật khẩu không đúng');
        }
        const data = await response.json();
        localStorage.setItem('authToken', data.access_token);
        await showApp();
    } catch (error) {
        loginError.textContent = error.message;
        loginError.classList.remove('hidden');
    } finally {
        loginBtnText.textContent = 'Đăng nhập';
        loginSpinner.classList.add('hidden');
    }
});

// Logout button event listener is handled in the init function

async function showApp() {
    const app = document.getElementById('app');
    if (app) app.classList.remove('hidden');
    hideLoginModal();

    // Load user data
    if (localStorage.getItem('currentUser')) {
        state.currentUser = JSON.parse(localStorage.getItem('currentUser'));
    }

    // Initialize the app
    renderNav();

    // Sau khi login, luôn bắt đầu từ trang "Quản lý Folder"
    console.log('Login successful - navigating to manage-folders');
    console.log('Clearing previous session state');

    // Reset state về mặc định sau login
    state.currentPage = 'manage-folders';
    state.currentFolderId = null;
    state.folderHistory = [];

    // Lưu state mới và navigate đến manage-folders
    saveState();
    navigate('manage-folders');

    // Update user info in the UI
    if (state.currentUser) {
        const name = state.currentUser.full_name || state.currentUser.email.split('@')[0];
        const userFullNameDisplay = document.getElementById('user-fullname');
        const userAvatar = document.getElementById('user-avatar');

        if (userFullNameDisplay) userFullNameDisplay.textContent = name;
        if (userAvatar) userAvatar.textContent = name.charAt(0).toUpperCase();
    }
}

function showLogin() {
    showLoginModal();
}

// --- MODAL FUNCTIONS ---
function showLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.classList.remove('hidden');
}

function hideLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.classList.add('hidden');
}

// Lắng nghe sự kiện upload file từ các tab khác
window.addEventListener('storage', (event) => {
    if (event.key === 'file_uploaded' && event.newValue) {
        console.log('Phát hiện file mới được upload, đang làm mới quyền truy cập...');
        refreshAccess().catch(console.error);
    }
});

// --- INITIALIZATION ---
function init() {
    // Theme is now permanently dark, clean up old setting
    localStorage.removeItem('theme');

    // Set up modal close button
    const closeModalBtn = document.getElementById('close-login-modal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', hideLoginModal);
    }

    // Check authentication state on page load
    checkAuthState();
}

function checkAuthState() {
    if (localStorage.getItem('authToken')) {
        showApp();
    } else {
        showLoginModal();
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Initialize the app
    init();

    // Set up login form if it exists
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const loginError = document.getElementById('login-error');
            const loginBtnText = document.getElementById('login-btn-text');
            const loginSpinner = document.getElementById('login-spinner');

            loginError.classList.add('hidden');
            loginBtnText.textContent = 'Đang đăng nhập...';
            loginSpinner.classList.remove('hidden');

            try {
                const response = await api.login(email, password);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Email hoặc mật khẩu không đúng');
                }

                localStorage.setItem('authToken', data.access_token);

                // Get and store user data
                const userResponse = await api.get('/users/me');
                localStorage.setItem('currentUser', JSON.stringify(userResponse));
                state.currentUser = userResponse;

                // Show the main app and hide login modal
                showApp();
            } catch (error) {
                loginError.textContent = error.message;
                loginError.classList.remove('hidden');
            } finally {
                loginBtnText.textContent = 'Đăng nhập';
                loginSpinner.classList.add('hidden');
            }
        });
    }

    // Set up logout button if it exists
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            localStorage.removeItem('authToken');
            localStorage.removeItem('currentUser');

            // Xóa state đã lưu khi logout
            clearState();

            state.currentUser = null;
            showLoginModal();
            const app = document.getElementById('app');
            if (app) app.classList.add('hidden');
            showLogin();
        });
    }
});