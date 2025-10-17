// --- CONFIG & STATE ---
// const API_BASE_URL = 'https://sv.tekjoy.io.vn/api';
const API_BASE_URL = 'http://127.0.0.1:8001/api';
let state = {
    accessToken: localStorage.getItem('accessToken'),
    currentUser: null,
    sessions: [],
    currentSessionId: null,
    keywords: [],
    isAutocompleteActive: false,
    activeKeyword: null,
    autocompleteTriggerRange: null,
    autocompleteSelectedIndex: -1,
    activeFiles: [],
    isAwaitingResponse: false, // [THÊM MỚI] Trạng thái chờ phản hồi từ AI

};

// --- DOM ELEMENTS ---
const dom = {
    loginView: document.getElementById('login-view'),
    appView: document.getElementById('app-view'),
    loginForm: document.getElementById('login-form'),
    loginError: document.getElementById('login-error'),
    logoutBtn: document.getElementById('logout-btn'),
    userInfo: {
        fullname: document.getElementById('user-fullname'),
        email: document.getElementById('user-email')
    },
    newChatBtn: document.getElementById('new-chat-btn'),
    sessionList: document.getElementById('session-list'),
    sessionTitle: document.getElementById('session-title'),
    chatContainer: document.getElementById('chat-container'),
    chatForm: document.getElementById('chat-form'),
    messageInput: document.getElementById('message-input'),
    suggestionBox: document.getElementById('suggestion-box'),
    activeFiles: {
        wrapper: document.getElementById('active-files-wrapper'),
        container: document.getElementById('active-files-container'),
    },
    settings: {
        btn: document.getElementById('settings-btn'),
        modal: document.getElementById('settings-modal'),
        closeBtn: document.getElementById('close-settings-btn'),
        saveBtn: document.getElementById('save-settings-btn'),
        form: document.getElementById('settings-form'),
        maxTokensSlider: document.getElementById('max_tokens'),
        maxTokensValue: document.getElementById('max_tokens_value'),
    },
    fileDetails: {
        modal: document.getElementById('file-details-modal'),
        content: document.getElementById('file-details-content'),
        closeBtn: document.getElementById('close-file-details-btn')
    }
};

// --- UTILS ---
function generateUUID() {
    return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
}

async function fetchAPI(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (state.accessToken) {
        headers['Authorization'] = `Bearer ${state.accessToken}`;
    }
    const response = await fetch(`${API_BASE_URL}${endpoint}`, { ...options, headers });

    if (!response.ok) {
        if (response.status === 401) handleLogout();
        const error = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(error.detail || error.message || 'Đã có lỗi xảy ra');
    }
    if (response.status === 204) return null;
    return response.json();
}

function expandAttachments(element, allFiles) {
    const container = element.parentNode;
    const fullHtml = allFiles.map(file => `
        <div class="attachment-item" onclick="showFileDetails('${file.file_id}')" title="Xem chi tiết file ${file.file_name}">
            <i data-lucide="file-text" class="w-4 h-4 mr-2 flex-shrink-0"></i>
            <span class="truncate">${file.file_name}</span>
        </div>
    `).join('');
    container.innerHTML = fullHtml;
    lucide.createIcons();
}

// --- UI RENDERING ---
function showThinkingIndicator() {
    // Xóa chỉ báo cũ nếu có để tránh trùng lặp
    removeThinkingIndicator();

    const indicatorHtml = `
        <div id="thinking-indicator" class="w-full flex flex-col items-start">
            <div class="flex items-start gap-3 w-full justify-start">
                <div class="w-8 h-8 flex-shrink-0 bg-indigo-600 rounded-full flex items-center justify-center font-bold">A</div>
                <div class="p-4 rounded-lg max-w-full w-auto text-black bg-white-800">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        </div>
    `;
    dom.chatContainer.insertAdjacentHTML('beforeend', indicatorHtml);
    dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
}

// [THÊM MỚI] Hàm ẩn chỉ báo
function removeThinkingIndicator() {
    const indicator = document.getElementById('thinking-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function switchView(view) {
    dom.loginView.classList.toggle('hidden', view !== 'login');
    dom.appView.classList.toggle('hidden', view !== 'app');
    if (view === 'app') dom.appView.classList.add('flex');
}

function displayMessage(sender, data, isHistory = false) {
    const isUser = sender === 'user';
    const payload = typeof data === 'string' ? { text: data, files: [] } : data;
    const messageText = isHistory ? data.message_text : payload.text;
    if (!messageText && (!payload.files || payload.files.length === 0)) return;

    const messageWrapper = document.createElement('div');
    messageWrapper.className = `w-full flex flex-col ${isUser ? 'items-end' : 'items-start'}`;

    if (messageText) {
        const messageElement = document.createElement('div');
        messageElement.className = `flex items-start gap-3 w-full ${isUser ? 'justify-end' : 'justify-start'}`;

        const avatar = isUser
            ? `<div class="w-8 h-8 flex-shrink-0 bg-gray-200 rounded-full flex items-center justify-center font-bold">U</div>`
            : `<div class="w-8 h-8 flex-shrink-0 bg-indigo-600 rounded-full flex items-center justify-center font-bold">A</div>`;

        // Process markdown and highlight code
        let htmlText = messageText;
        if (!isUser && window.marked) {
            htmlText = marked.parse(messageText, {
                breaks: true,
                gfm: true,
                highlight: function (code, lang) {
                    if (window.hljs && lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang }).value;
                    }
                    return code;
                }
            });
            htmlText = htmlText.replace(/<table>/g, '<div class="table-wrapper"><table>').replace(/<\/table>/g, '</table></div>');
        } else {
            // For user messages, just escape HTML and handle newlines
            htmlText = messageText.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
        }

        const messageBubble = `<div class="p-4 rounded-lg max-w-full w-auto text-black break-words whitespace-pre-line prose prose-invert prose-pre:bg-white-900 prose-pre:text-white prose-code:text-pink-400 ${isUser ? 'bg-[rgb(244,244,244)]' : 'bg-white-800]'}">${htmlText}</div>`;

        messageElement.innerHTML = isUser ? `${messageBubble}${avatar}` : `${avatar}${messageBubble}`;
        messageWrapper.appendChild(messageElement);

        // Activate highlighting after inserting into the DOM
        setTimeout(() => {
            if (window.hljs) {
                messageWrapper.querySelectorAll('pre code').forEach(block => {
                    hljs.highlightElement(block);
                });
            }
        }, 0);
    }

    // Handle attachments
    if (!isUser && payload.files && payload.files.length > 0) {
        const attachmentsContainer = document.createElement('div');
        attachmentsContainer.className = 'attachments-container';
        attachmentsContainer.style.marginRight = isUser ? '2.75rem' : '0';
        attachmentsContainer.style.marginLeft = isUser ? '0' : '2.75rem';

        const MAX_VISIBLE_FILES = 2;
        const files = payload.files;
        let attachmentsHtml = '';

        if (files.length <= MAX_VISIBLE_FILES) {
            attachmentsHtml = files.map(file => `
                <div class="attachment-item" onclick="showFileDetails('${file.file_id}')" title="Xem chi tiết file ${file.file_name}">
                    <i data-lucide="file-text" class="w-4 h-4 mr-1 flex-shrink-0"></i>
                    <span class="truncate">${file.file_name}</span>
                </div>
            `).join('');
        } else {
            attachmentsHtml = files.slice(0, MAX_VISIBLE_FILES).map(file => `
                <div class="attachment-item" onclick="showFileDetails('${file.file_id}')" title="Xem chi tiết file ${file.file_name}">
                    <i data-lucide="file-text" class="w-4 h-4 mr-1 flex-shrink-0"></i>
                    <span class="truncate">${file.file_name}</span>
                </div>
            `).join('');

            const remainingCount = files.length - MAX_VISIBLE_FILES;
            const allFilesJson = JSON.stringify(files.map(f => ({ file_id: f.file_id, file_name: f.file_name }))).replace(/"/g, "'");
            attachmentsHtml += `
                <div class="attachment-item" style="background-color: #4a5568;" onclick="expandAttachments(this, ${allFilesJson})">
                    <span class="font-semibold">+${remainingCount}</span>
                </div>
            `;
        }
        attachmentsContainer.innerHTML = attachmentsHtml;
        messageWrapper.appendChild(attachmentsContainer);
    }

    dom.chatContainer.appendChild(messageWrapper);
    lucide.createIcons();
    if (!isHistory) {
        dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
    }
}

function renderSessions() {
    dom.sessionList.innerHTML = '';
    if (!state.sessions || state.sessions.length === 0) {
        dom.sessionList.innerHTML = '<p class="text-sm text-black-400 px-2">Chưa có cuộc trò chuyện nào.</p>';
        return;
    }

    state.sessions.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    state.sessions.forEach(session => {
        const isActive = session.id === state.currentSessionId;
        const item = document.createElement('div');
        item.className = `session-item flex items-center justify-between p-2 rounded-lg cursor-pointer ${isActive ? 'bg-white-800' : 'hover:bg-indigo-600/50'}`;
        item.dataset.sessionId = session.id;

        item.innerHTML = `
            <div class="flex-1 truncate pr-2">
                <span class="session-title-text text-sm text-black-200">${session.title}</span>
                <input type="text" class="session-title-input hidden w-full bg-white-600 text-sm rounded px-1" value="${session.title}" />
            </div>
            <div class="session-actions flex items-center gap-1">
                <button class="edit-title-btn p-1 text-gray-400 hover:text-white"><i data-lucide="pencil" class="w-3 h-3"></i></button>
            </div>
        `;

        item.addEventListener('click', () => {
            if (!item.querySelector('.session-title-input').classList.contains('hidden')) return;
            handleSessionClick(session.id);
        });

        const editBtn = item.querySelector('.edit-title-btn');
        const titleText = item.querySelector('.session-title-text');
        const titleInput = item.querySelector('.session-title-input');

        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            titleText.classList.add('hidden');
            titleInput.classList.remove('hidden');
            titleInput.focus();
            titleInput.select();
        });

        const saveTitle = async () => {
            const newTitle = titleInput.value.trim();
            if (newTitle && newTitle !== session.title) {
                try {
                    const updatedSessionData = await updateSessionTitle(session.id, newTitle);
                    session.title = updatedSessionData.session.title;
                    titleText.textContent = session.title;
                    if (session.id === state.currentSessionId) {
                        dom.sessionTitle.textContent = session.title;
                    }
                } catch (error) {
                    console.error("Failed to update title:", error);
                    titleInput.value = session.title; // Revert on failure
                }
            }
            titleInput.classList.add('hidden');
            titleText.classList.remove('hidden');
        }

        titleInput.addEventListener('blur', saveTitle);
        titleInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') saveTitle();
            if (e.key === 'Escape') {
                titleInput.value = session.title;
                titleInput.classList.add('hidden');
                titleText.classList.remove('hidden');
            }
        });


        dom.sessionList.appendChild(item);
    });
    lucide.createIcons();
}

function renderActiveFiles() {
    const wrapper = dom.activeFiles.wrapper;
    const container = dom.activeFiles.container;
    container.innerHTML = '';

    if (state.activeFiles.length === 0) {
        wrapper.classList.add('hidden');
        return;
    }

    wrapper.classList.remove('hidden');
    state.activeFiles.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'active-file-item';
        fileItem.innerHTML = `
            <span class="truncate max-w-[150px] cursor-pointer hover:underline" title="${file.file_name}" onclick="showFileDetails('${file.file_id}')">${file.file_name}</span>
            <button class="remove-file-btn" onclick="removeActiveFile('${file.file_id}')" title="Bỏ chọn tệp này">
                <i data-lucide="x" class="w-3 h-3"></i>
            </button>
        `;
        container.appendChild(fileItem);
    });
    lucide.createIcons();
}

function updateUserInfo() {
    if (state.currentUser) {
        dom.userInfo.fullname.textContent = state.currentUser.full_name;
        dom.userInfo.email.textContent = state.currentUser.email;
    }
}

// --- API & DATA ---

async function fetchSessions() {
    if (!state.currentUser) return;
    try {
        state.sessions = await fetchAPI(`/chatbot/sessions/${state.currentUser.id}`);
        renderSessions();
    } catch (error) {
        console.error('Failed to fetch sessions:', error);
        dom.sessionList.innerHTML = '<p class="text-sm text-red-400 px-2">Lỗi tải lịch sử.</p>';
    }
}

async function fetchHistory(sessionId) {
    dom.chatContainer.innerHTML = '<p class="text-center text-gray-400">Đang tải lịch sử trò chuyện...</p>';
    try {
        const historyData = await fetchAPI(`/chatbot/history/${sessionId}`);
        dom.chatContainer.innerHTML = ''; // Clear loading message
        if (historyData.messages && historyData.messages.length > 0) {
            historyData.messages.forEach(msg => {
                displayMessage(msg.sender_type, msg, true);
            });
        } else {
            displayMessage('assistant', { text: 'Bắt đầu cuộc trò chuyện. Tôi có thể giúp gì cho bạn?' }, true);
        }
        setTimeout(() => dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight, 0);
    } catch (error) {
        console.error('Failed to fetch history:', error);
        dom.chatContainer.innerHTML = `<p class="text-center text-red-400">Lỗi khi tải lịch sử: ${error.message}</p>`;
    }
}

async function updateSessionTitle(sessionId, newTitle) {
    return await fetchAPI(`/chatbot/sessions/${sessionId}/edit-title`, {
        method: 'PUT',
        body: JSON.stringify({ new_title: newTitle })
    });
}

async function loadKeywords() {
    try {
        state.keywords = await fetchAPI('/autoc/autocomplete/keywords');
    } catch (error) {
        console.error("Failed to load keywords:", error);
    }
}

// --- AUTHENTICATION ---

async function refreshAccess() {
    try {
        const response = await fetch(`${API_BASE_URL}/file/me/refresh-access`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${state.accessToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Failed to refresh access');
        }

        const data = await response.json();
        console.log('Access refreshed successfully');
        return data;
    } catch (error) {
        console.error('Error refreshing access:', error);
        throw error;
    }
}

// Listen for file upload events from other tabs
window.addEventListener('storage', (event) => {
    if (event.key === 'file_uploaded' && event.newValue) {
        console.log('Detected file upload, refreshing access...');
        refreshAccess().catch(console.error);
    }
});

async function handleLogin(event) {
    event.preventDefault();
    dom.loginError.textContent = '';
    const formData = new FormData(dom.loginForm);
    const body = new URLSearchParams(formData);

    try {
        const response = await fetch(`${API_BASE_URL}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString()
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Invalid credentials' }));
            throw new Error(errorData.detail);
        }
        const data = await response.json();
        state.accessToken = data.access_token;
        localStorage.setItem('accessToken', state.accessToken);

        // Làm mới quyền truy cập file ngay sau khi đăng nhập
        try {
            await refreshAccess();
            console.log('Đã cập nhật quyền truy cập file sau khi đăng nhập');
        } catch (error) {
            console.error('Lỗi khi làm mới quyền truy cập:', error);
        }

        await initializeApp();
    } catch (error) {
        dom.loginError.textContent = 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.';
        console.error('Login failed:', error);
    }
}

function handleLogout() {
    state.accessToken = null;
    state.currentUser = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('currentSessionId');
    switchView('login');
}

// --- CHAT & AUTOCOMPLETE LOGIC ---
function addActiveFile(file) {
    const exists = state.activeFiles.some(f => f.file_id === file.file_id);
    if (!exists) {
        state.activeFiles.push(file);
        renderActiveFiles();
        saveActiveFilesForSession(state.currentSessionId); // <-- Dòng được thêm vào

    }
}

function removeActiveFile(fileId) {
    state.activeFiles = state.activeFiles.filter(f => f.file_id !== fileId);
    renderActiveFiles();
    saveActiveFilesForSession(state.currentSessionId); // <-- Dòng được thêm vào

}

function resetAutocomplete() {
    state.isAutocompleteActive = false;
    state.activeKeyword = null;
    state.autocompleteTriggerRange = null;
    state.autocompleteSelectedIndex = -1;
    if (dom.suggestionBox) {
        dom.suggestionBox.classList.add('hidden');
        dom.suggestionBox.innerHTML = '';
    }
}

// [CẬP NHẬT] hàm handleMessageKeyDown
async function handleMessageKeyDown(event) {
    // Handle Enter key for submission or selection
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();

        // [THÊM MỚI] Nếu đang chờ AI, không làm gì cả
        if (state.isAwaitingResponse) {
            return;
        }

        if (state.isAutocompleteActive && state.autocompleteSelectedIndex !== -1) {
            const selectedItem = dom.suggestionBox.querySelector('.suggestion-item-selected');
            if (selectedItem) selectSuggestionItem(selectedItem);
        } else {
            dom.chatForm.requestSubmit();
        }
        return;
    }

    // ... phần còn lại của hàm giữ nguyên
    if (state.isAutocompleteActive) {
        const items = dom.suggestionBox.querySelectorAll('[data-file-id]');
        if (items.length === 0) return;

        if (['ArrowDown', 'ArrowUp', 'Tab'].includes(event.key)) {
            event.preventDefault();
            if (event.key === 'ArrowDown' || event.key === 'Tab') {
                state.autocompleteSelectedIndex = (state.autocompleteSelectedIndex + 1) % items.length;
            } else if (event.key === 'ArrowUp') {
                state.autocompleteSelectedIndex = (state.autocompleteSelectedIndex - 1 + items.length) % items.length;
            }
            updateSuggestionSelection();
        } else if (event.key === 'Escape') {
            resetAutocomplete();
        }
        return;
    }
}

/**
 * [IMPROVED] Handles user input in the message box to trigger and update autocomplete suggestions.
 * This version uses a more robust method of tracking the text to be replaced and allows spaces in the search prefix.
 * It also exits autocomplete on a double space.
 */
async function handleMessageInput() {
    const selection = window.getSelection();
    if (!selection.rangeCount) {
        if (state.isAutocompleteActive) resetAutocomplete();
        return;
    }
    const range = selection.getRangeAt(0);
    const textContent = range.startContainer.textContent || '';
    const cursorPosition = range.startOffset;

    if (state.isAutocompleteActive) {
        // --- Currently in autocomplete mode ---
        const startOffset = state.autocompleteTriggerRange.startOffset;

        // Reset if the text node is gone or cursor moves before the keyword.
        if (!document.body.contains(state.autocompleteTriggerRange.commonAncestorContainer) || cursorPosition < startOffset) {
            return resetAutocomplete();
        }

        // Dynamically update the end of our replacement range to the current cursor.
        state.autocompleteTriggerRange.setEnd(range.startContainer, cursorPosition);

        const fullSearchText = state.autocompleteTriggerRange.toString();

        // Check if the keyword is still at the beginning. If not, reset.
        if (!fullSearchText.startsWith(state.activeKeyword.keyword)) {
            return resetAutocomplete();
        }

        // If user types two consecutive spaces, exit autocomplete mode.
        if (/[\s\u00A0]{2,}$/.test(fullSearchText)) {
            return resetAutocomplete();
        }

        // The prefix is everything after the keyword and the first space.
        const firstSpaceIndex = fullSearchText.indexOf(' ');
        if (firstSpaceIndex === -1) {
            // This should not happen if autocomplete is active but is a safeguard.
            return resetAutocomplete();
        }
        const prefix = fullSearchText.substring(firstSpaceIndex + 1);

        await updateSuggestions(prefix);

    } else {
        // --- Not in autocomplete, check for a trigger ---
        // A trigger is a keyword followed by a space.
        const lastChar = textContent.substring(cursorPosition - 1, cursorPosition);
        if (lastChar === ' ' || lastChar === '\u00A0') {
            const textBeforeCursor = textContent.substring(0, cursorPosition);
            const textWithoutTrailingSpace = textBeforeCursor.replace(/[\s\u00A0]+$/, '');
            const lastWord = textWithoutTrailingSpace.split(/[\s\u00A0]+/).pop();

            if (!lastWord) return;

            const matchingKeyword = state.keywords.find(k => k.keyword === lastWord);
            if (matchingKeyword) {
                state.isAutocompleteActive = true;
                state.activeKeyword = matchingKeyword;

                // Create a range starting at the keyword. It will expand as the user types.
                const triggerRange = document.createRange();
                const keywordStartPos = textWithoutTrailingSpace.length - lastWord.length;
                triggerRange.setStart(range.startContainer, keywordStartPos);
                triggerRange.setEnd(range.startContainer, cursorPosition);
                state.autocompleteTriggerRange = triggerRange;

                await updateSuggestions(''); // Initial search
            }
        }
    }
}


async function updateSuggestions(prefix) {
    if (!state.isAutocompleteActive) return;
    try {
        // The API call is correct, the issue was in the logic calling it.
        const files = await fetchAPI(`/autoc/autocomplete/files?keyword=${state.activeKeyword.keyword}&file_prefix=${encodeURIComponent(prefix)}`);
        if (files.length > 0) {
            dom.suggestionBox.innerHTML = files.map(file =>
                `<div class="p-3 hover:bg-gray-600 cursor-pointer text-sm" data-file-id="${file.id}" data-file-name="${file.original_file_name}">
                    ${file.original_file_name}
                 </div>`
            ).join('');
            dom.suggestionBox.classList.remove('hidden');
            state.autocompleteSelectedIndex = 0;
            updateSuggestionSelection();
        } else {
            dom.suggestionBox.classList.add('hidden');
        }
    } catch (error) {
        console.error("Failed to fetch file suggestions:", error);
        dom.suggestionBox.classList.add('hidden');
    }
}

function updateSuggestionSelection() {
    const items = dom.suggestionBox.querySelectorAll('[data-file-id]');
    items.forEach((item, index) => {
        item.classList.toggle('suggestion-item-selected', index === state.autocompleteSelectedIndex);
        if (index === state.autocompleteSelectedIndex) {
            item.scrollIntoView({ block: 'nearest' });
        }
    });
}

/**
 * [IMPROVED] Replaces the trigger text (e.g., "file my-doc") with a non-editable file span.
 * This version uses a simpler replacement method based on the improved `handleMessageInput`.
 */
function selectSuggestionItem(itemElement) {
    if (!itemElement || !state.isAutocompleteActive) return;

    const fileId = itemElement.dataset.fileId;
    const fileName = itemElement.dataset.fileName;

    // Create the new element to insert
    const newSpan = document.createElement('span');
    newSpan.className = 'highlighted-file';
    newSpan.contentEditable = 'false';
    newSpan.textContent = fileName;
    newSpan.dataset.fileId = fileId;

    const spaceNode = document.createTextNode('\u00A0'); // Non-breaking space
    const selection = window.getSelection();

    // The triggerRange already covers everything we need to replace ("keyword prefix").
    state.autocompleteTriggerRange.deleteContents();
    state.autocompleteTriggerRange.insertNode(newSpan);

    // Position the cursor after the newly inserted file span
    const newRange = document.createRange();
    newRange.setStartAfter(newSpan);
    newRange.collapse(true);

    // Insert a space after the span for better UX
    newRange.insertNode(spaceNode);
    newRange.setStartAfter(spaceNode); // Move cursor after the space

    // Apply the new cursor position
    selection.removeAllRanges();
    selection.addRange(newRange);

    addActiveFile({ file_id: fileId, file_name: fileName });

    resetAutocomplete();
    dom.messageInput.focus();
}
// lưu các file đang sử dụng  reload 
function saveActiveFilesForSession(sessionId) {
    if (!sessionId) return;
    localStorage.setItem(`activeFiles_${sessionId}`, JSON.stringify(state.activeFiles));
}

function getMessagePayload() {
    let textContent = '';
    dom.messageInput.childNodes.forEach(node => {
        textContent += node.textContent;
    });
    return { apiMessage: textContent.trim() };
}

// [CẬP NHẬT] Toàn bộ hàm handleSendMessage
async function handleSendMessage(event) {
    event.preventDefault();

    // Ngăn gửi nếu AI đang phản hồi
    if (state.isAwaitingResponse) {
        // Có thể thêm một thông báo nhỏ ở đây nếu muốn
        console.warn("AI is currently responding. Please wait.");
        return;
    }

    const { apiMessage } = getMessagePayload();

    if (!apiMessage && state.activeFiles.length === 0) return;

    const userMessageText = dom.messageInput.innerText.trim();
    displayMessage('user', { text: userMessageText });
    dom.messageInput.innerHTML = '';
    resetAutocomplete();

    // ---- BẮT ĐẦU TRẠNG THÁI CHỜ ----
    state.isAwaitingResponse = true;
    dom.messageInput.contentEditable = 'false'; // Khóa ô chat
    dom.messageInput.classList.add('cursor-not-allowed', 'opacity-60');
    showThinkingIndicator();
    // ---------------------------------

    try {
        const apiPayload = {
            user_id: state.currentUser.id,
            session_id: state.currentSessionId,
            message: apiMessage,
            files: state.activeFiles
        };

        const response = await fetchAPI('/chatbot/chatV2', {
            method: 'POST',
            body: JSON.stringify(apiPayload)
        });

        // Xóa chỉ báo "đang gõ" TRƯỚC KHI hiển thị tin nhắn thật
        removeThinkingIndicator();

        const responseData = {
            text: response.message || response.response,
            files: response.files || []
        };
        displayMessage('assistant', responseData);

        const currentSession = state.sessions.find(s => s.id === state.currentSessionId);
        if (currentSession && currentSession.title.startsWith("Cuộc trò chuyện mới")) {
            await fetchSessions();
            const updatedSession = state.sessions.find(s => s.id === state.currentSessionId);
            if (updatedSession) {
                dom.sessionTitle.textContent = updatedSession.title;
            }
        }
    } catch (error) {
        console.error("Chat API error:", error);
        removeThinkingIndicator(); // Xóa chỉ báo khi có lỗi
        displayMessage('assistant', { text: `Lỗi: ${error.message}` });
    } finally {
        // ---- KẾT THÚC TRẠNG THÁI CHỜ (luôn chạy) ----
        state.isAwaitingResponse = false;
        dom.messageInput.contentEditable = 'true'; // Mở lại ô chat
        dom.messageInput.classList.remove('cursor-not-allowed', 'opacity-60');
        dom.messageInput.focus(); // Focus lại vào ô chat để người dùng tiện gõ tiếp
        // ------------------------------------------
    }
}

function handleNewChat() {
    const newSessionId = `${generateUUID()}`;
    const newSession = {
        id: newSessionId,
        title: `Cuộc trò chuyện mới`,
        created_at: new Date().toISOString(),
        user_id: state.currentUser.id,
        isNew: true
    };

    state.sessions.push(newSession);
    handleSessionClick(newSessionId, true);
}

// async function handleSessionClick(sessionId, isNew = false) {
//     if (state.currentSessionId === sessionId && !isNew) return;

//     state.currentSessionId = sessionId;
//     localStorage.setItem('currentSessionId', sessionId);
//     state.activeFiles = []; // Reset active files for the new session
//     renderActiveFiles(); // Update UI to remove active files

//     const sessionData = state.sessions.find(s => s.id === sessionId);
//     dom.sessionTitle.textContent = sessionData ? sessionData.title : 'Chat';

//     if (!isNew) {
//         await fetchHistory(sessionId);
//     } else {
//         dom.chatContainer.innerHTML = '';
//         displayMessage('assistant', {text: 'Bắt đầu cuộc trò chuyện mới. Tôi có thể giúp gì cho bạn?'});
//     }
//     renderSessions();
// }

// Thay thế toàn bộ hàm handleSessionClick cũ bằng hàm này
async function handleSessionClick(sessionId, isNew = false) {
    if (state.currentSessionId === sessionId && !isNew) return;

    state.currentSessionId = sessionId;
    localStorage.setItem('currentSessionId', sessionId);

    // [FIX] Tải danh sách tệp từ localStorage cho session này
    const savedFiles = localStorage.getItem(`activeFiles_${sessionId}`);
    state.activeFiles = savedFiles ? JSON.parse(savedFiles) : [];
    renderActiveFiles(); // Cập nhật UI ngay lập tức với các tệp đã tải

    const sessionData = state.sessions.find(s => s.id === sessionId);
    dom.sessionTitle.textContent = sessionData ? sessionData.title : 'Chat';

    if (!isNew) {
        await fetchHistory(sessionId);
    } else {
        dom.chatContainer.innerHTML = '';
        displayMessage('assistant', { text: 'Bắt đầu cuộc trò chuyện mới. Tôi có thể giúp gì cho bạn?' });
        // Đảm bảo session mới không có tệp nào được lưu
        saveActiveFilesForSession(sessionId);
    }
    renderSessions();
}

// --- FILE DETAILS ---
async function showFileDetails(fileId) {
    const modal = dom.fileDetails.modal;
    const content = dom.fileDetails.content;
    content.innerHTML = '<p>Đang tải chi tiết tệp...</p>';
    modal.classList.remove('hidden');

    try {
        const fileData = await fetchAPI(`/file/files/${fileId}`);
        const { original_file_name, folder_path, extracted_text, ...otherDetails } = fileData;

        content.innerHTML = `
            <div class="space-y-4 text-gray-200">
                <div class="pb-2 border-b border-gray-700">
                    <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Tên file</p>
                    <p class="mt-1 text-base">${original_file_name || 'N/A'}</p>
                </div>
                 <div class="pb-2">
                    <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Nội dung trích xuất</p>
                    <p class="mt-1 text-sm bg-gray-900 p-2 rounded-md max-h-48 overflow-y-auto font-mono">${extracted_text || 'Chưa có nội dung.'}</p>
                </div>
                <div>
                   <button id="expand-details-btn" class="text-sm text-indigo-400 hover:underline">Xem thêm chi tiết</button>
                   <div id="extra-details" class="hidden mt-2 bg-gray-900 p-2 rounded-md">
                        <pre class="whitespace-pre-wrap text-xs">${JSON.stringify(otherDetails, null, 2)}</pre>
                   </div>
                </div>
            </div>
        `;
        document.getElementById('expand-details-btn').addEventListener('click', (e) => {
            document.getElementById('extra-details').classList.toggle('hidden');
            e.target.textContent = document.getElementById('extra-details').classList.contains('hidden')
                ? 'Xem thêm chi tiết'
                : 'Ẩn bớt';
        });

    } catch (error) {
        content.innerHTML = `<p class="text-red-400">Không thể tải chi tiết tệp: ${error.message}</p>`;
        console.error("Failed to fetch file details:", error);
    }
}

// --- SETTINGS ---
async function loadSettings() {
    if (!state.currentUser) return;
    try {
        const settings = await fetchAPI('/chat-settings/getV2', {
            method: 'POST',
            body: JSON.stringify({ user_id: state.currentUser.id })
        });

        const form = dom.settings.form;
        form.model.value = settings.model;
        form.max_tokens.value = settings.max_tokens;
        dom.settings.maxTokensValue.textContent = settings.max_tokens;
        form.system_prompt.value = settings.system_prompt;
        form.is_history.checked = settings.is_history;
        form.using_document.checked = settings.using_document;
        form.free_chat.checked = settings.free_chat;
        form.show_sources.checked = settings.show_sources;

        // nếu backend trả api_key (hoặc null)
        if (form.api_key) {
            form.api_key.value = settings.api_key || "";
        }
    } catch (error) {
        console.error("Failed to load settings:", error);
    }
}

// thêm note
async function handleSaveSettings() {
    if (!state.currentUser) return;
    const form = dom.settings.form;
    const payload = {
        user_id: state.currentUser.id,
        payload: {
            model: form.model.value,
            max_tokens: parseInt(form.max_tokens.value, 10),
            system_prompt: form.system_prompt.value,
            is_history: form.is_history.checked,
            using_document: form.using_document.checked,
            free_chat: form.free_chat.checked,
            show_sources: form.show_sources.checked,
            api_key: form.api_key?.value || null  // thêm api_key
        }
    };

    try {
        await fetchAPI('/chat-settings/editV2', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        dom.settings.modal.classList.add('hidden');
    } catch (error) {
        console.error("Failed to save settings:", error);
        alert(`Lưu cài đặt thất bại: ${error.message}`);
    }
}

// --- INITIALIZATION ---
async function initializeApp() {
    if (!state.accessToken) {
        switchView('login');
        return;
    }

    // Làm mới quyền truy cập file mỗi khi tải lại trang
    try {
        await refreshAccess();
        console.log('Đã cập nhật quyền truy cập file khi tải lại trang');
    } catch (error) {
        console.error('Lỗi khi làm mới quyền truy cập:', error);
    }
    try {
        state.currentUser = await fetchAPI('/users/me');
        updateUserInfo();
        await loadKeywords();
        await fetchSessions();

        const lastSessionId = localStorage.getItem('currentSessionId');
        const lastSessionExists = state.sessions.some(s => s.id === lastSessionId);

        if (lastSessionId && lastSessionExists) {
            await handleSessionClick(lastSessionId);
        } else if (state.sessions.length > 0) {
            await handleSessionClick(state.sessions[0].id);
        } else {
            handleNewChat();
        }

        switchView('app');
    } catch (error) {
        console.error('Initialization failed:', error);
        handleLogout();
    }
}

// --- EVENT LISTENERS ---
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initializeApp();
});

dom.loginForm.addEventListener('submit', handleLogin);
dom.logoutBtn.addEventListener('click', handleLogout);
dom.chatForm.addEventListener('submit', handleSendMessage);
dom.messageInput.addEventListener('keydown', handleMessageKeyDown);
dom.messageInput.addEventListener('input', handleMessageInput);
dom.suggestionBox.addEventListener('click', (e) => selectSuggestionItem(e.target.closest('[data-file-id]')));
dom.newChatBtn.addEventListener('click', handleNewChat);

// Settings Modal Listeners
dom.settings.btn.addEventListener('click', async () => {
    await loadSettings();
    dom.settings.modal.classList.remove('hidden');
});
dom.settings.closeBtn.addEventListener('click', () => dom.settings.modal.classList.add('hidden'));
dom.settings.saveBtn.addEventListener('click', handleSaveSettings);
dom.settings.maxTokensSlider.addEventListener('input', (e) => dom.settings.maxTokensValue.textContent = e.target.value);

// File Details Modal Listeners
dom.fileDetails.closeBtn.addEventListener('click', () => dom.fileDetails.modal.classList.add('hidden'));

// Make functions globally available for inline onclick handlers
window.showFileDetails = showFileDetails;
window.expandAttachments = expandAttachments;
window.removeActiveFile = removeActiveFile;

