const userNameElement = document.getElementById('userName');
const userIcon = document.getElementById('userIcon');

const teamNameHeader = document.getElementById('teamNameHeader');
const teamSubtitle = document.getElementById('teamSubtitle');
const detailTeamName = document.getElementById('detailTeamName');
const detailTeamDescription = document.getElementById('detailTeamDescription');
const detailCreatedAt = document.getElementById('detailCreatedAt');
const detailTotalMembers = document.getElementById('detailTotalMembers');
const detailTotalDocs = document.getElementById('detailTotalDocs');
const detailMemberList = document.getElementById('detailMemberList');
const detailDocumentList = document.getElementById('detailDocumentList');
const teamDocsCount = document.getElementById('teamDocsCount');

const API_BASE = `${API_ROOT}/equipes`;
const storedName = localStorage.getItem('userName') || 'Usuario';
let currentTeam = null;
const selectedTeamMembers = new Map();
let teamMemberCandidates = [];
let teamMemberSearchTimer = null;
let teamActionMessageTimer = null;
let teamRoles = [];
let pendingMemberAction = null;
function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function roleLabel(role) {
    if (!role) {
        return { label: 'Sem cargo', css: 'wait' };
    }

    if (role.toLowerCase() === 'lider') {
        return { label: 'Lider', css: 'ok' };
    }

    return { label: role, css: 'wait' };
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

function documentAccessLabel(canAccess) {
    return canAccess
        ? { label: 'Com acesso', css: 'ok', action: 'Descensurar' }
        : { label: 'Sem acesso', css: 'alert', action: 'Bloqueado' };
}

function openDocumentRedaction(docId) {
    window.location.href = `../documentos/descensura.html?doc_id=${docId}`;
}

function getTeamId() {
    const params = new URLSearchParams(window.location.search);
    const teamId = Number(params.get('team_id'));
    return Number.isFinite(teamId) ? teamId : null;
}

function renderTeam(team) {
    currentTeam = team;
    if (!team) {
        teamNameHeader.textContent = 'Equipe nao encontrada';
        teamSubtitle.textContent = 'Nao foi possivel carregar a equipe solicitada';
        detailTeamName.textContent = 'Equipe nao encontrada';
        detailTeamDescription.textContent = 'Verifique se voce tem acesso a esta equipe.';
        detailCreatedAt.textContent = '-';
        detailTotalMembers.textContent = '0';
        detailTotalDocs.textContent = '0';
        detailMemberList.innerHTML = `
            <li class="empty-state">
                <strong>Sem membros</strong>
                <span>A equipe nao pode ser exibida.</span>
            </li>
        `;
        detailDocumentList.innerHTML = `
            <li class="empty-state">
                <strong>Sem documentos</strong>
                <span>Os documentos desta equipe nao puderam ser exibidos.</span>
            </li>
        `;
        teamDocsCount.textContent = '0 documentos';
        return;
    }

    teamNameHeader.textContent = team.nome;
    teamSubtitle.textContent = `${team.membros} membro(s) · ${team.documentos} documento(s)`;
    detailTeamName.textContent = team.nome;
    detailTeamDescription.textContent = team.descricao || 'Sem descricao cadastrada.';
    detailCreatedAt.textContent = formatDate(team.criado_em);
    detailTotalMembers.textContent = team.membros ?? 0;
    detailTotalDocs.textContent = team.documentos ?? 0;

    const members = (team.membros_lista || []).slice().sort((a, b) => {
        const cargoDiff = (b.cargo_nivel || 0) - (a.cargo_nivel || 0);
        if (cargoDiff !== 0) {
            return cargoDiff;
        }
        return String(a.nome || '').localeCompare(String(b.nome || ''), 'pt-BR');
    });

    if (!members.length) {
        detailMemberList.innerHTML = `
            <li class="empty-state">
                <strong>Nenhum membro encontrado</strong>
                <span>Essa equipe ainda nao possui integrantes vinculados.</span>
            </li>
        `;
    } else {
        detailMemberList.innerHTML = members
            .map((member) => {
                const role = roleLabel(member.cargo_nome);
                return `
                    <li>
                        <div class="member-body">
                            <strong>${escapeHtml(member.nome)}</strong>
                            <p class="member-email">${escapeHtml(member.email)}</p>
                            <p>${escapeHtml(role.label)}</p>
                        </div>
                            <div class="member-actions"><span class="pill ${role.css} member-role">${escapeHtml(role.label)}</span><button class="member-action-button member-action-edit" type="button" data-edit-member="${member.user_team_id}"><span aria-hidden="true">✎</span> Alterar cargo</button><button class="member-action-button member-action-remove" type="button" data-remove-member="${member.user_team_id}"><span aria-hidden="true">×</span> Remover</button></div>
                    </li>
                `;
            })
            .join('');
    }

    const documentos = Array.isArray(team.documentos_lista) ? team.documentos_lista : [];
    teamDocsCount.textContent = `${documentos.length} documento(s)`;

    if (!documentos.length) {
        detailDocumentList.innerHTML = `
            <li class="empty-state">
                <strong>Nenhum documento encontrado</strong>
                <span>Esta equipe ainda nao possui documentos cadastrados.</span>
            </li>
        `;
        return;
    }

    detailDocumentList.innerHTML = documentos
        .map((documento) => {
            const access = documentAccessLabel(Boolean(documento.tem_acesso));
            const docClasses = `team-doc-item ${documento.tem_acesso ? 'allowed' : 'denied'}`;
            const actionMarkup = documento.tem_acesso
                ? `<button type="button" class="team-doc-action" data-doc-redaction="${documento.doc_id}">${access.action}</button>`
                : `<button type="button" class="team-doc-action disabled" disabled>${access.action}</button>`;

            return `
                <li class="${docClasses}">
                    <div class="team-doc-top">
                        <div>
                            <strong>${escapeHtml(documento.nome_original)}</strong>
                            <p>${escapeHtml(documento.autor_nome || 'Autor desconhecido')} · ${escapeHtml(formatDate(documento.criado_em))}</p>
                        </div>
                        <span class="pill ${access.css}">${escapeHtml(access.label)}</span>
                    </div>

                    <div class="team-doc-meta">
                        <span class="pill wait">Extensao ${escapeHtml(documento.extensao || '-')}</span>
                        <span class="pill wait">${escapeHtml(formatBytes(documento.tamanho_bytes))}</span>
                        <span class="pill wait">Nivel ${escapeHtml(String(documento.nivel_seguranca ?? '-'))}</span>
                    </div>

                    <div class="team-doc-footer">
                        <span>${escapeHtml(documento.status_processamento || 'status indisponivel')}</span>
                        ${actionMarkup}
                    </div>
                </li>
            `;
        })
        .join('');
}

detailDocumentList.addEventListener('click', (event) => {
    const target = event.target.closest('[data-doc-redaction]');
    if (target) {
        openDocumentRedaction(target.dataset.docRedaction);
        return;
    }

    const docCard = event.target.closest('.team-doc-item');
    if (!docCard) {
        return;
    }

    const docId = docCard.querySelector('[data-doc-redaction]')?.dataset.docRedaction || null;
    const isAllowed = docCard.classList.contains('allowed');

    if (!isAllowed) {
        showTeamMessage('Você não tem permissão para descensurar este documento.', 'error');
        return;
    }

    if (docId) {
        openDocumentRedaction(docId);
    }
});

async function loadTeam() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '../auth/login.html';
        return;
    }

    const teamId = getTeamId();
    if (!teamId) {
        renderTeam(null);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/${teamId}`, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        if (response.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '../auth/login.html';
            return;
        }

        if (!response.ok) {
            throw new Error('Falha ao carregar equipe.');
        }

        const data = await response.json();
        const backendUser = data?.usuario;
        if (backendUser?.nome) {
            localStorage.setItem('userName', backendUser.nome);
            localStorage.setItem('userId', String(backendUser.user_id));
            userNameElement.textContent = backendUser.nome;
            userIcon.textContent = backendUser.nome.charAt(0).toUpperCase();
        }

        renderTeam(data);
    } catch (error) {
        console.error(error);
        renderTeam(null);
    }
}

loadTeam();

// Operações administrativas: o servidor revalida tenant, vínculo e cargo em cada chamada.
async function teamAction(path, method, body) {
    const response = await fetch(`${API_BASE}/${getTeamId()}${path}`, {method, headers:{Authorization:`Bearer ${localStorage.getItem('token')}`,'Content-Type':'application/json'}, body:body ? JSON.stringify(body) : undefined});
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(data.detail || 'Operação não autorizada.');
    return data;
}
function showTeamMessage(message, type = 'success') {
    const element = document.getElementById('teamActionMessage');
    if (!element) return;
    clearTimeout(teamActionMessageTimer);
    element.textContent = message;
    element.className = `team-action-message ${type}`;
    element.hidden = false;
    teamActionMessageTimer = setTimeout(() => { element.hidden = true; }, 5000);
}

function openTeamModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
}

function closeTeamModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal-overlay.open')) {
        document.body.classList.remove('modal-open');
    }
}

document.querySelectorAll('[data-close-team-modal]').forEach((button) => {
    button.addEventListener('click', () => closeTeamModal(button.dataset.closeTeamModal));
});
document.querySelectorAll('.modal-overlay').forEach((modal) => {
    modal.addEventListener('click', (event) => {
        if (event.target === modal) closeTeamModal(modal.id);
    });
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.open').forEach((modal) => closeTeamModal(modal.id));
    }
});

document.getElementById('editTeam')?.addEventListener('click', () => {
    if (!currentTeam) return;
    document.getElementById('editTeamName').value = currentTeam.nome || '';
    openTeamModal('editTeamModal');
    document.getElementById('editTeamName').focus();
});
document.getElementById('editTeamForm')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = document.getElementById('editTeamName').value.trim();
    if (!name) {
        showTeamMessage('Informe o nome da equipe.', 'error');
        return;
    }
    const submitButton = event.currentTarget.querySelector('[type="submit"]');
    submitButton.disabled = true;
    try {
        await teamAction('', 'PATCH', { nome: name });
        closeTeamModal('editTeamModal');
        await loadTeam();
        showTeamMessage('Nome da equipe atualizado.');
    } catch (error) {
        showTeamMessage(error.message || 'Não foi possível atualizar a equipe.', 'error');
    } finally {
        submitButton.disabled = false;
    }
});

function renderTeamMemberCandidates(users) {
    const container = document.getElementById('teamMemberCandidates');
    teamMemberCandidates = users;
    if (!users.length) {
        container.innerHTML = '<li class="empty-state small"><strong>Nenhum usuário disponível</strong><span>Altere a pesquisa ou verifique os usuários da organização.</span></li>';
        return;
    }
    container.innerHTML = users.map((user) => {
        const selected = selectedTeamMembers.has(Number(user.user_id));
        return `<li class="candidate-item ${selected ? 'selected' : ''}"><div><strong>${escapeHtml(user.nome)}</strong><p>${escapeHtml(user.email)}</p></div><button class="candidate-action" type="button" data-select-team-member="${Number(user.user_id)}" aria-pressed="${selected}">${selected ? 'Selecionado' : 'Selecionar'}</button></li>`;
    }).join('');
}

function renderSelectedTeamMembers() {
    const container = document.getElementById('teamSelectedMembers');
    const count = document.getElementById('teamSelectedCount');
    const submit = document.getElementById('confirmAddTeamMembers');
    const selected = Array.from(selectedTeamMembers.values());
    count.textContent = String(selected.length);
    submit.disabled = selected.length === 0;
    container.innerHTML = selected.length
        ? selected.map((user) => `<button type="button" class="selected-chip" data-remove-team-member="${Number(user.user_id)}">${escapeHtml(user.nome)} <span aria-hidden="true">×</span></button>`).join('')
        : '<span class="empty-chip">Nenhum usuário selecionado</span>';
}

async function loadTeamMemberCandidates(query = '') {
    const container = document.getElementById('teamMemberCandidates');
    container.innerHTML = '<li class="empty-state small"><strong>Buscando usuários</strong><span>Aguarde um instante.</span></li>';
    const endpoint = new URL(`${API_BASE}/form-data`);
    endpoint.searchParams.set('team_id', String(getTeamId()));
    if (query.trim()) endpoint.searchParams.set('query', query.trim());
    try {
        const response = await fetch(endpoint.toString(), {
            headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Não foi possível carregar os usuários.');
        const availableUsers = data.usuarios_disponiveis || [];
        teamRoles = data.cargos_disponiveis || [];
        renderTeamMemberCandidates(availableUsers);
        // Mantém em estado os usuários escolhidos mesmo quando a busca muda.
        availableUsers.forEach((user) => {
            if (selectedTeamMembers.has(Number(user.user_id))) {
                selectedTeamMembers.set(Number(user.user_id), user);
            }
        });
        renderSelectedTeamMembers();
    } catch (error) {
        container.innerHTML = `<li class="empty-state small"><strong>Falha ao carregar</strong><span>${escapeHtml(error.message)}</span></li>`;
    }
}

document.getElementById('addTeamMember')?.addEventListener('click', () => {
    if (!currentTeam) return;
    selectedTeamMembers.clear();
    document.getElementById('teamMemberSearch').value = '';
    renderSelectedTeamMembers();
    openTeamModal('addTeamMemberModal');
    loadTeamMemberCandidates();
    document.getElementById('teamMemberSearch').focus();
});
document.getElementById('teamMemberSearch')?.addEventListener('input', (event) => {
    clearTimeout(teamMemberSearchTimer);
    teamMemberSearchTimer = setTimeout(() => loadTeamMemberCandidates(event.target.value), 250);
});
document.getElementById('teamMemberCandidates')?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-select-team-member]');
    if (!button) return;
    const userId = Number(button.dataset.selectTeamMember);
        const user = teamMemberCandidates.find((candidate) => Number(candidate.user_id) === userId);
    if (user) selectedTeamMembers.set(userId, user);
    renderSelectedTeamMembers();
    renderTeamMemberCandidates(teamMemberCandidates);
});
document.getElementById('teamSelectedMembers')?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-remove-team-member]');
    if (!button) return;
    selectedTeamMembers.delete(Number(button.dataset.removeTeamMember));
    renderSelectedTeamMembers();
    renderTeamMemberCandidates(teamMemberCandidates);
});

document.getElementById('confirmAddTeamMembers')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const selected = Array.from(selectedTeamMembers.values());
    if (!selected.length) return;
    button.disabled = true;
    let added = 0;
    try {
        for (const user of selected) {
            await teamAction('/membros', 'POST', { user_id: Number(user.user_id) });
            added += 1;
        }
        closeTeamModal('addTeamMemberModal');
        selectedTeamMembers.clear();
        await loadTeam();
        showTeamMessage(`${added} membro(s) adicionado(s) à equipe.`);
    } catch (error) {
        if (added > 0) {
            closeTeamModal('addTeamMemberModal');
            selectedTeamMembers.clear();
            await loadTeam();
        }
        showTeamMessage(added
            ? `${added} membro(s) adicionado(s); não foi possível concluir os demais. ${error.message}`
            : error.message || 'Não foi possível adicionar os membros.', 'error');
    } finally {
        button.disabled = selectedTeamMembers.size === 0;
    }
});

document.getElementById('deleteTeam')?.addEventListener('click', () => {
    if (!currentTeam) return;
    document.getElementById('deleteTeamName').textContent = currentTeam.nome;
    openTeamModal('deleteTeamModal');
});
document.getElementById('confirmDeleteTeam')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
        await teamAction('', 'DELETE');
        showTeamMessage('Equipe excluída.');
        closeTeamModal('deleteTeamModal');
        setTimeout(() => { window.location.href = 'equipes.html'; }, 1600);
    } catch (error) {
        showTeamMessage(error.message || 'Não foi possível excluir a equipe.', 'error');
    } finally {
        button.disabled = false;
    }
});

function showModalError(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = message || '';
    element.hidden = !message;
}

function openEditMemberModal(member) {
    pendingMemberAction = { type: 'edit', userTeamId: member.user_team_id };
    document.getElementById('editMemberName').textContent = `${member.nome} · ${member.email}`;
    const select = document.getElementById('editMemberRole');
    select.innerHTML = teamRoles.map((role) => `<option value="${Number(role.cargo_id)}">${escapeHtml(role.nome)}</option>`).join('');
    select.value = String(member.cargo_id || '');
    showModalError('editMemberError', '');
    openTeamModal('editMemberModal');
    select.focus();
}

function openRemoveMemberModal(member) {
    pendingMemberAction = { type: 'remove', userTeamId: member.user_team_id };
    document.getElementById('removeMemberName').textContent = member.nome;
    showModalError('removeMemberError', '');
    openTeamModal('removeMemberModal');
}

detailMemberList.addEventListener('click', (event) => {
    const edit = event.target.closest('[data-edit-member]');
    const remove = event.target.closest('[data-remove-member]');
    if (!edit && !remove) return;
    const userTeamId = Number((edit || remove).dataset.editMember || (edit || remove).dataset.removeMember);
    const member = (currentTeam?.membros_lista || []).find((item) => Number(item.user_team_id) === userTeamId);
    if (!member) return;
    if (edit) openEditMemberModal(member);
    else openRemoveMemberModal(member);
});

document.getElementById('confirmEditMember')?.addEventListener('click', async (event) => {
    if (!pendingMemberAction || pendingMemberAction.type !== 'edit') return;
    const button = event.currentTarget;
    const cargoId = Number(document.getElementById('editMemberRole').value);
    if (!cargoId) { showModalError('editMemberError', 'Selecione um cargo.'); return; }
    button.disabled = true;
    try {
        await teamAction(`/membros/${pendingMemberAction.userTeamId}`, 'PATCH', { cargo_id: cargoId });
        closeTeamModal('editMemberModal');
        await loadTeam();
        showTeamMessage('Cargo atualizado.');
    } catch (error) {
        showModalError('editMemberError', error.message || 'Não foi possível atualizar o cargo.');
    } finally { button.disabled = false; }
});

document.getElementById('confirmRemoveMember')?.addEventListener('click', async (event) => {
    if (!pendingMemberAction || pendingMemberAction.type !== 'remove') return;
    const button = event.currentTarget;
    button.disabled = true;
    try {
        await teamAction(`/membros/${pendingMemberAction.userTeamId}`, 'DELETE');
        closeTeamModal('removeMemberModal');
        await loadTeam();
        showTeamMessage('Membro removido.');
    } catch (error) {
        showModalError('removeMemberError', error.message || 'Não foi possível remover o membro.');
    } finally { button.disabled = false; }
});
