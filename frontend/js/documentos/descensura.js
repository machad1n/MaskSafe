const backToDocumentsBtn = document.getElementById('backToDocumentsBtn');
const docTitle = document.getElementById('docTitle');
const docSubtitle = document.getElementById('docSubtitle');
const docAccessLabel = document.getElementById('docAccessLabel');
const docTeamLabel = document.getElementById('docTeamLabel');
const docPreviewFrame = document.getElementById('docPreviewFrame');
const docPreviewFallback = document.getElementById('docPreviewFallback');
const metaTeam = document.getElementById('metaTeam');
const metaAuthor = document.getElementById('metaAuthor');
const metaDate = document.getElementById('metaDate');
const metaSize = document.getElementById('metaSize');
const metaLevel = document.getElementById('metaLevel');
const metaStatus = document.getElementById('metaStatus');
const metaKey = document.getElementById('metaKey');
const openCensoredBtn = document.getElementById('openCensoredBtn');
const startRedactionBtn = document.getElementById('startRedactionBtn');
const viewOriginalBtn = document.getElementById('viewOriginalBtn');

const API_DOCUMENT = `${API_ROOT}/documentos/censurados`;
const docId = Number(new URLSearchParams(window.location.search).get('doc_id'));

const storedName = localStorage.getItem('userName') || 'Usuario';
let previewObjectUrl = null;
let previewTimeoutId = null;
let previewGeneration = 0;
let podeDescensurar = false;
let cargoNivelAtual = 0;
let previewUrlCensurado = null;
let visualizandoOriginal = false;

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
        return '-';
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '-';
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

function clearPreviewUrl() {
    clearTimeout(previewTimeoutId);
    previewTimeoutId = null;
    if (previewObjectUrl) {
        URL.revokeObjectURL(previewObjectUrl);
        previewObjectUrl = null;
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

function showPreviewFallback(title, message) {
    docPreviewFallback.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p>`;
    docPreviewFallback.hidden = false;
}

async function loadPdfPreview(url, label) {
    const generation = ++previewGeneration;
    const token = localStorage.getItem('token');
    clearPreviewUrl();
    docPreviewFrame.onload = null;
    docPreviewFrame.onerror = null;
    docPreviewFrame.src = 'about:blank';
    showPreviewFallback('Carregando preview', `Carregando ${label}.`);
    if (!token) {
        handleUnauthorized();
        return;
    }

    try {
        const response = await fetch(apiUrl(url), {
            cache: 'no-store',
            headers: { Authorization: `Bearer ${token}` },
        });
        if (response.status === 401) {
            handleUnauthorized();
            return;
        }
        if (!response.ok) {
            throw new Error(`Não foi possível carregar ${label} (HTTP ${response.status}).`);
        }
        const blob = await response.blob();
        if (!blob.size || !(await blob.slice(0, 5).text()).startsWith('%PDF-')) {
            throw new Error('A resposta recebida não é um PDF válido.');
        }
        if (generation !== previewGeneration) return;

        previewObjectUrl = URL.createObjectURL(blob);
        docPreviewFrame.onload = () => {
            if (generation !== previewGeneration) return;
            clearTimeout(previewTimeoutId);
            docPreviewFallback.hidden = true;
        };
        docPreviewFrame.onerror = () => {
            if (generation === previewGeneration) {
                showPreviewFallback('Preview indisponível', 'O navegador não conseguiu renderizar este PDF.');
            }
        };
        docPreviewFrame.src = previewObjectUrl;
        // O visualizador nativo de PDF pode não disparar `iframe.onload`
        // para Blob URLs. Como o conteúdo já foi validado como PDF acima,
        // remova o overlay imediatamente após entregar o blob ao iframe.
        docPreviewFallback.hidden = true;
    } catch (error) {
        if (generation !== previewGeneration) return;
        console.error(error);
        showPreviewFallback('Preview indisponível', error.message || 'Não foi possível carregar o documento autorizado.');
    }
}

function resetPage(message = 'Selecione um documento permitido para iniciar a descensura.') {
    previewGeneration += 1;
    docTitle.textContent = 'Documento indisponivel';
    docSubtitle.textContent = message;
    docAccessLabel.textContent = 'Sem dados';
    docTeamLabel.textContent = 'Equipe';
    metaTeam.textContent = '-';
    metaAuthor.textContent = '-';
    metaDate.textContent = '-';
    metaSize.textContent = '-';
    metaLevel.textContent = '-';
    metaStatus.textContent = '-';
    metaKey.textContent = '-';
    clearPreviewUrl();
    docPreviewFrame.src = 'about:blank';
    viewOriginalBtn.hidden = true;
    viewOriginalBtn.setAttribute('aria-pressed', 'false');
    visualizandoOriginal = false;
    docPreviewFallback.hidden = false;
    docPreviewFallback.innerHTML = `
        <strong>Documento indisponível</strong>
        <p>${escapeHtml(message)}</p>
    `;
}

async function loadDocument() {
    const token = localStorage.getItem('token');
    if (!token) {
        handleUnauthorized();
        return;
    }

    if (!docId) {
        resetPage('Nenhum documento foi informado na URL.');
        return;
    }

    try {
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

        if (response.status === 404) {
            resetPage('Este documento não existe ou sua equipe não tem acesso.');
            window.location.href = 'censurados.html';
            return;
        }

        if (!response.ok) {
            throw new Error('Falha ao carregar o documento.');
        }

        const documento = await response.json();
        docTitle.textContent = documento.nome_original || 'Documento';
        docSubtitle.textContent = `${documento.equipe?.nome || 'Sem equipe'} · pronto para descensura`;
        docAccessLabel.textContent = 'Com acesso';
        docTeamLabel.textContent = documento.equipe?.nome || 'Sem equipe';
        metaTeam.textContent = documento.equipe?.nome || '-';
        metaAuthor.textContent = documento.autor_nome || storedName;
        metaDate.textContent = formatDate(documento.criado_em);
        metaSize.textContent = formatBytes(documento.tamanho_bytes);
        metaLevel.textContent = securityLabel(documento.nivel_seguranca);
        metaStatus.textContent = documento.status_processamento || '-';
        metaKey.textContent = documento.chave_criptografica || '-';

        podeDescensurar = Boolean(documento.pode_descensurar || documento.pode_descensura_parcial);
        startRedactionBtn.disabled = !podeDescensurar;
        cargoNivelAtual = Number(documento.cargo_usuario?.nivel || 0);
        previewUrlCensurado = documento.preview_url || null;
        visualizandoOriginal = false;
        viewOriginalBtn.hidden = cargoNivelAtual < 3;
        viewOriginalBtn.textContent = 'Ver arquivo original';
        viewOriginalBtn.setAttribute('aria-pressed', 'false');
        if (podeDescensurar) {
            const cargo = documento.cargo_usuario?.nome || 'lider';
            if (cargoNivelAtual >= 3) {
                startRedactionBtn.textContent = 'Baixar versão original';
            } else {
                startRedactionBtn.textContent = 'Baixar descensura parcial';
            }
            docAccessLabel.textContent = `Com acesso (${cargo})`;
        } else {
            startRedactionBtn.textContent = 'Sem permissão para descensura';
        }

        if (previewUrlCensurado) {
            docPreviewFrame.title = 'Preview do documento censurado';
            await loadPdfPreview(previewUrlCensurado, 'o documento censurado');
        } else {
            showPreviewFallback('Preview indisponível', 'Este documento não possui um endereço de arquivo para exibição.');
        }
    } catch (error) {
        console.error(error);
        resetPage('Não foi possível carregar o documento selecionado.');
    }
}

backToDocumentsBtn.addEventListener('click', () => {
    window.location.href = 'censurados.html';
});

openCensoredBtn.addEventListener('click', () => {
    window.location.href = `censurados.html?doc_id=${docId}`;
});

viewOriginalBtn.addEventListener('click', async () => {
    if (cargoNivelAtual < 3 || !previewUrlCensurado) return;
    visualizandoOriginal = !visualizandoOriginal;
    viewOriginalBtn.textContent = visualizandoOriginal ? 'Voltar ao documento censurado' : 'Ver arquivo original';
    viewOriginalBtn.setAttribute('aria-pressed', String(visualizandoOriginal));
    const url = visualizandoOriginal ? `/documentos/${docId}/original` : previewUrlCensurado;
    docPreviewFrame.title = visualizandoOriginal ? 'Preview do arquivo original' : 'Preview do documento censurado';
    await loadPdfPreview(url, visualizandoOriginal ? 'o arquivo original' : 'o documento censurado');
});

startRedactionBtn.addEventListener('click', async () => {
    const token = localStorage.getItem('token');
    if (!token) {
        handleUnauthorized();
        return;
    }

    if (!podeDescensurar) {
        showPreviewFallback('Acesso não permitido', 'Seu cargo não permite descensurar este documento.');
        return;
    }

    try {
        startRedactionBtn.disabled = true;
        startRedactionBtn.textContent = 'Baixando...';

        const rota = cargoNivelAtual >= 3 ? 'original' : 'parcial';
        const response = await fetch(apiUrl(`/documentos/${docId}/${rota}`), {
            cache: 'no-store',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (response.status === 403) {
            showPreviewFallback('Acesso não permitido', 'Seu cargo não permite acessar esta versão do documento.');
            return;
        }

        if (response.status === 401) {
            handleUnauthorized();
            return;
        }

        if (!response.ok) {
            throw new Error('Falha ao baixar o documento.');
        }

        const blob = await response.blob();
        if (!blob.size || !(await blob.slice(0, 5).text()).startsWith('%PDF-')) {
            throw new Error('A resposta recebida não é um PDF válido.');
        }
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = cargoNivelAtual >= 3
            ? `${docTitle.textContent}_original.pdf`
            : `${docTitle.textContent}_descensurado_parcial.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error(error);
        showPreviewFallback('Falha ao baixar o documento', error.message || 'Não foi possível baixar esta versão.');
    } finally {
        startRedactionBtn.disabled = !podeDescensurar;
        startRedactionBtn.textContent = !podeDescensurar ? 'Sem permissão para descensura'
            : (cargoNivelAtual >= 3 ? 'Baixar versão original' : 'Baixar descensura parcial');
    }
});

window.addEventListener('pagehide', () => {
    previewGeneration += 1;
    clearPreviewUrl();
    docPreviewFrame.onload = null;
    docPreviewFrame.onerror = null;
    docPreviewFrame.src = 'about:blank';
});
window.addEventListener('pageshow', (event) => {
    if (event.persisted) loadDocument();
});
window.addEventListener('storage', (event) => {
    if (event.key !== 'token') return;
    if (!event.newValue) {
        previewGeneration += 1;
        clearPreviewUrl();
        docPreviewFrame.src = 'about:blank';
        handleUnauthorized();
        return;
    }
    loadDocument();
});

loadDocument();







