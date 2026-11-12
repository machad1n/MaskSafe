const goToUploadBtn = document.getElementById('goToUploadBtn');
const docsList = document.getElementById('docsList');
const docsEmptyState = document.getElementById('docsEmptyState');
const docsCountPill = document.getElementById('docsCountPill');
const currentUserLabel = document.getElementById('currentUserLabel');
const detailEmptyState = document.getElementById('detailEmptyState');
const detailShell = document.getElementById('detailShell');
const detailTitle = document.getElementById('detailTitle');
const detailTeam = document.getElementById('detailTeam');
const detailDate = document.getElementById('detailDate');
const detailSecurity = document.getElementById('detailSecurity');
const detailCryptoKey = document.getElementById('detailCryptoKey');
const detailPreviewFrame = document.getElementById('detailPreviewFrame');
const detailPreviewFallback = document.getElementById('detailPreviewFallback');
const undoRedactionBtn = document.getElementById('undoRedactionBtn');
const closeDetailsBtn = document.getElementById('closeDetailsBtn');
const loadingStep = document.getElementById('loadingStep');
const loadingStepLabel = document.getElementById('loadingStepLabel');
const loadingFileName = document.getElementById('loadingFileName');
const loadingBadgeRedaction = document.getElementById('loadingBadgeRedaction');
const loadingBadgeTeams = document.getElementById('loadingBadgeTeams');
const docsActionMessage = document.getElementById('docsActionMessage');
const deleteDocModal = document.getElementById('deleteDocModal');
const deleteDocName = document.getElementById('deleteDocName');
const deleteDocError = document.getElementById('deleteDocError');
const confirmDeleteDocBtn = document.getElementById('confirmDeleteDocBtn');
const cancelDeleteDocBtn = document.getElementById('cancelDeleteDocBtn');

const API_DOCUMENTS = `${API_ROOT}/documentos/censurados`;
const initialDocId = Number(new URLSearchParams(window.location.search).get('doc_id'));

const storedName = localStorage.getItem('userName') || 'Usuario';currentUserLabel.textContent = storedName;

const state = {
    documentos: [],
    selectedDoc: null,
    previewObjectUrl: null,
    loadingTimeoutId: null,
    previewRequestId: 0,
    selectionRequestId: 0,
    pendingDeleteDoc: null,
};

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDate(value) {
    if (!value) {
        return 'data indisponivel';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return 'data invalida';
    }

    return date.toLocaleString('pt-BR');
}

function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes <= 0) {
        return '0 KB';
    }

    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex += 1;
    }

    return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function securityLabel(level) {
    const map = {
        1: 'Basico',
        2: 'Protecao media',
        3: 'Protecao alta',
        4: 'Protecao maxima',
    };

    return map[Number(level)] || 'Desconhecido';
}

function toggleDetailState(hasDocument) {
    detailEmptyState.hidden = hasDocument;
    detailShell.hidden = !hasDocument;
}

function clearPreviewUrl() {
    if (state.previewObjectUrl) {
        URL.revokeObjectURL(state.previewObjectUrl);
        state.previewObjectUrl = null;
    }
}

function handleUnauthorized() {
    if (window.AppShell?.Sessao?.limpar) {
        window.AppShell.Sessao.limpar();
    } else {
        localStorage.removeItem('token');
    }
    window.location.href = '../auth/login.html';
}

function showDocsMessage(message, kind = 'success') {
    docsActionMessage.textContent = message;
    docsActionMessage.className = `docs-action-message ${kind}`;
    docsActionMessage.hidden = false;
}

function showPreviewFallback(title, message) {
    detailPreviewFallback.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p>`;
    detailPreviewFallback.hidden = false;
}

function renderDocumentsList() {
    docsCountPill.textContent = `${state.documentos.length} documento(s)`;

    if (!state.documentos.length) {
        docsEmptyState.innerHTML = `
            <strong>Nenhum documento encontrado</strong>
            <span>Você ainda não possui documentos censurados vinculados ao seu usuário.</span>
        `;
        docsList.innerHTML = '';
        toggleDetailState(false);
        return;
    }

    docsEmptyState.hidden = true;
    docsList.innerHTML = state.documentos
        .map((documento) => `
            <article class="doc-card ${state.selectedDoc && state.selectedDoc.doc_id === documento.doc_id ? 'active' : ''}" data-doc-id="${documento.doc_id}">
                <div class="doc-card-top">
                    <div>
                        <strong>${escapeHtml(documento.nome_original)}</strong>
                        <p>${escapeHtml(formatDate(documento.criado_em))}</p>
                    </div>
                    <span class="doc-tag">${escapeHtml(securityLabel(documento.nivel_seguranca))}</span>
                </div>
                <div class="doc-card-meta">
                    <span class="doc-tag">Equipe: ${escapeHtml(documento.equipe_nome || 'Sem equipe')}</span>
                    <span class="doc-tag">Tamanho: ${escapeHtml(formatBytes(documento.tamanho_bytes))}</span>
                </div>
                <div class="doc-actions">
                    <button type="button" class="cta-censor" data-action="redact" data-doc-id="${documento.doc_id}">Visualizar documento</button>
                    <button type="button" class="ghost-button" data-action="details" data-doc-id="${documento.doc_id}">Detalhes</button>
                    ${documento.pode_excluir ? `<button type="button" class="danger-button" data-action="delete" data-doc-id="${documento.doc_id}">Excluir</button>` : ''}
                </div>
            </article>
        `)
        .join('');
}

function renderDocumentDetails(documento) {
    const previewRequestId = ++state.previewRequestId;
    clearTimeout(state.loadingTimeoutId);
    if (!documento) {
        clearPreviewUrl();
        detailPreviewFrame.src = 'about:blank';
        detailPreviewFrame.onload = null;
        state.selectedDoc = null;
        showPreviewFallback('Selecione um documento', 'Escolha um item na lista para ver o PDF censurado e os dados do documento.');
        toggleDetailState(false);
        return;
    }

    state.selectedDoc = documento;
    detailTitle.textContent = documento.nome_original || '-';
    detailTeam.textContent = documento.equipe_nome || '-';
    detailDate.textContent = formatDate(documento.criado_em);
    detailSecurity.textContent = securityLabel(documento.nivel_seguranca);
    detailCryptoKey.textContent = documento.doc_id || '-';

    clearPreviewUrl();
    showPreviewFallback('Carregando preview', 'Buscando o PDF censurado para exibição.');
    detailPreviewFrame.src = 'about:blank';
    detailPreviewFrame.onload = null;
    toggleDetailState(true);
    renderDocumentsList();

    if (documento.preview_url) {
        const token = localStorage.getItem('token');
        if (!token) {
            handleUnauthorized();
            return;
        }
        fetch(apiUrl(documento.preview_url), {
            cache: 'no-store',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        })
            .then(async (response) => {
                if (response.status === 401) {
                    handleUnauthorized();
                    throw new Error('Sessão expirada. Entre novamente.');
                }
                if (!response.ok) {
                    throw new Error(`O servidor não conseguiu carregar o PDF (HTTP ${response.status}).`);
                }
                const blob = await response.blob();
                if (!blob.size || !(await blob.slice(0, 5).text()).startsWith('%PDF-')) {
                    throw new Error('A resposta recebida não é um PDF válido.');
                }
                return blob;
            })
            .then((blob) => {
                if (previewRequestId !== state.previewRequestId) return;
                state.previewObjectUrl = URL.createObjectURL(blob);
                detailPreviewFrame.onload = () => {
                    if (previewRequestId !== state.previewRequestId) return;
                    clearTimeout(state.loadingTimeoutId);
                    detailPreviewFallback.hidden = true;
                };
                detailPreviewFrame.onerror = () => {
                    if (previewRequestId === state.previewRequestId) {
                        clearTimeout(state.loadingTimeoutId);
                        showPreviewFallback('Preview indisponível', 'O navegador não conseguiu renderizar este PDF.');
                    }
                };
                detailPreviewFrame.src = state.previewObjectUrl;
                // O visualizador nativo de PDF pode não disparar `iframe.onload`
                // quando a origem é uma Blob URL. O blob já foi validado acima
                // como PDF, portanto não devemos manter o overlay sobre um
                // documento que o navegador já está renderizando.
                detailPreviewFallback.hidden = true;
            })
            .catch((error) => {
                if (previewRequestId !== state.previewRequestId) return;
                console.error(error);
                if (localStorage.getItem('token')) {
                    showPreviewFallback('Preview indisponível', error.message || 'Não foi possível carregar o PDF autorizado.');
                }
            });
    } else {
        showPreviewFallback('Preview indisponível', 'Este documento não possui um endereço de arquivo para exibição.');
    }
}

async function loadDocumentDetails(docId) {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '../auth/login.html';
        return;
    }

    const response = await fetch(apiUrl(`/documentos/censurados/${docId}`), {
        cache: 'no-store',
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });

    if (response.status === 401) {
        handleUnauthorized();
        return;
    }

    if (!response.ok) {
        throw new Error('Falha ao carregar detalhes do documento.');
    }

    return response.json();
}

async function loadDocuments() {
    const selectionRequestId = ++state.selectionRequestId;
    const token = localStorage.getItem('token');
    if (!token) {
        handleUnauthorized();
        return false;
    }

    try {
        const response = await fetch(apiUrl('/documentos/censurados'), {
            cache: 'no-store',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (response.status === 401) {
            handleUnauthorized();
            return false;
        }

        if (!response.ok) {
            throw new Error('Falha ao carregar documentos censurados.');
        }

        const data = await response.json();
        state.documentos = Array.isArray(data.documentos) ? data.documentos : [];
        docsCountPill.textContent = `${data.total || state.documentos.length} documento(s)`;
        currentUserLabel.textContent = `#${data.usuario?.user_id || '-'} ${data.usuario?.nome || storedName}`;
        renderDocumentsList();

        if (state.documentos.length) {
            const initialDocument = state.documentos.find((documento) => Number(documento.doc_id) === initialDocId) || state.documentos[0];
            const detalheInicial = await loadDocumentDetails(initialDocument.doc_id);
            if (selectionRequestId === state.selectionRequestId && detalheInicial) {
                renderDocumentDetails(detalheInicial);
            }
        } else {
            renderDocumentDetails(null);
        }
        return true;
    } catch (error) {
        console.error(error);
        docsEmptyState.innerHTML = `
            <strong>Erro ao carregar documentos</strong>
            <span>Verifique se o backend está ativo e se sua sessão continua válida.</span>
        `;
        docsList.innerHTML = '';
        toggleDetailState(false);
        return false;
    }
}

goToUploadBtn.addEventListener('click', () => {
    window.location.href = 'censurar.html';
});

function closeDeleteDocModal() {
    deleteDocModal.classList.remove('open');
    deleteDocModal.hidden = true;
    state.pendingDeleteDoc = null;
    deleteDocError.textContent = '';
    confirmDeleteDocBtn.disabled = false;
}

function openDeleteDocModal(documento) {
    state.pendingDeleteDoc = documento;
    deleteDocName.textContent = documento.nome_original || 'Documento selecionado';
    deleteDocError.textContent = '';
    deleteDocModal.hidden = false;
    requestAnimationFrame(() => deleteDocModal.classList.add('open'));
    cancelDeleteDocBtn.focus();
}

async function confirmDeleteDocument() {
    if (!state.pendingDeleteDoc) return;
    const documento = state.pendingDeleteDoc;
    const token = localStorage.getItem('token');
    if (!token) {
        handleUnauthorized();
        return;
    }

    confirmDeleteDocBtn.disabled = true;
    deleteDocError.textContent = '';
    try {
        const response = await fetch(apiUrl(`/documentos/${documento.doc_id}`), {
            method: 'DELETE',
            cache: 'no-store',
            headers: { Authorization: `Bearer ${token}` },
        });
        if (response.status === 401) {
            handleUnauthorized();
            return;
        }
        if (!response.ok) {
            let message = 'Não foi possível excluir o documento.';
            try {
                const data = await response.json();
                message = data.detail || message;
            } catch (_) {
                // Respostas não JSON mantêm a mensagem segura e legível.
            }
            throw new Error(message);
        }

        closeDeleteDocModal();
        state.selectedDoc = null;
        const listaAtualizada = await loadDocuments();
        showDocsMessage(
            listaAtualizada
                ? 'Documento excluído com sucesso.'
                : 'Documento excluído, mas a listagem não pôde ser atualizada. Atualize a página para recarregar os dados.',
            listaAtualizada ? 'success' : 'error',
        );
    } catch (error) {
        console.error(error);
        deleteDocError.textContent = error.message || 'Não foi possível excluir o documento.';
        confirmDeleteDocBtn.disabled = false;
    }
}

docsList.addEventListener('click', (event) => {
    const redactionButton = event.target.closest('[data-action="redact"]');
    if (redactionButton) {
        const docId = Number(redactionButton.dataset.docId);
        window.location.href = `descensura.html?doc_id=${docId}`;
        return;
    }

    const deleteButton = event.target.closest('[data-action="delete"]');
    if (deleteButton) {
        const docId = Number(deleteButton.dataset.docId);
        const selected = state.documentos.find((documento) => Number(documento.doc_id) === docId);
        if (selected?.pode_excluir) openDeleteDocModal(selected);
        return;
    }

    const button = event.target.closest('[data-action="details"]');
    if (!button) {
        return;
    }

    const docId = Number(button.dataset.docId);
    const selected = state.documentos.find((documento) => Number(documento.doc_id) === docId);
    if (selected) {
        const selectionRequestId = ++state.selectionRequestId;
        loadDocumentDetails(docId)
            .then((detalhe) => {
                if (selectionRequestId === state.selectionRequestId && detalhe) {
                    renderDocumentDetails(detalhe);
                }
            })
            .catch((error) => {
                console.error(error);
                showDocsMessage(error.message || 'Não foi possível carregar os detalhes do documento.', 'error');
            });
    }
});

undoRedactionBtn.addEventListener('click', () => {
    if (!state.selectedDoc) {
        showDocsMessage('Selecione um documento antes de abrir as opções de acesso.', 'error');
        return;
    }
    window.location.href = `descensura.html?doc_id=${state.selectedDoc.doc_id}`;
});

closeDetailsBtn.addEventListener('click', () => {
    state.selectionRequestId += 1;
    state.previewRequestId += 1;
    clearTimeout(state.loadingTimeoutId);
    clearPreviewUrl();
    detailPreviewFrame.onload = null;
    detailPreviewFrame.onerror = null;
    detailPreviewFrame.src = 'about:blank';
    toggleDetailState(false);
    state.selectedDoc = null;
    renderDocumentsList();
});

confirmDeleteDocBtn.addEventListener('click', confirmDeleteDocument);
cancelDeleteDocBtn.addEventListener('click', closeDeleteDocModal);
deleteDocModal.addEventListener('click', (event) => {
    if (event.target === deleteDocModal) closeDeleteDocModal();
});
window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !deleteDocModal.hidden) closeDeleteDocModal();
});

window.addEventListener('pagehide', () => {
    clearTimeout(state.loadingTimeoutId);
    clearPreviewUrl();
    detailPreviewFrame.onload = null;
    detailPreviewFrame.onerror = null;
    detailPreviewFrame.src = 'about:blank';
});
window.addEventListener('pageshow', (event) => {
    if (event.persisted) loadDocuments();
});
window.addEventListener('storage', (event) => {
    if (event.key !== 'token') return;
    if (!event.newValue) {
        clearPreviewUrl();
        detailPreviewFrame.src = 'about:blank';
        handleUnauthorized();
        return;
    }
    loadDocuments();
});

loadDocuments();


