const API_ACCOUNT = `${API_ROOT}/conta`;
const profileForm = document.getElementById('profileForm');
const profileName = document.getElementById('profileName');
const profileEmail = document.getElementById('profileEmail');
const profilePhoto = document.getElementById('profilePhoto');
const avatarPreview = document.getElementById('avatarPreview');
const avatarInitial = document.getElementById('avatarInitial');
const photoFileName = document.getElementById('photoFileName');
const profileFeedback = document.getElementById('profileFeedback');
const passwordForm = document.getElementById('passwordForm');
const newPassword = document.getElementById('newPassword');
const confirmPassword = document.getElementById('confirmPassword');
const passwordFeedback = document.getElementById('passwordFeedback');
const deleteFeedback = document.getElementById('deleteFeedback');
const deleteModalFeedback = document.getElementById('deleteModalFeedback');
const deleteModal = document.getElementById('deleteAccountModal');
const deleteForm = document.getElementById('deleteAccountForm');
const deletePassword = document.getElementById('deletePassword');
const confirmDeleteCheck = document.getElementById('confirmDeleteCheck');
const openDeleteModalBtn = document.getElementById('openDeleteModalBtn');
const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

let currentUserId = null;
let currentPhotoUrl = null;
let selectedPhotoUrl = null;

function showFeedback(element, message, kind = 'success') {
    element.textContent = message;
    element.className = `account-feedback ${kind}`;
    element.hidden = false;
}

function hideFeedback(element) {
    element.textContent = '';
    element.hidden = true;
}

async function parseError(response, fallback) {
    try {
        const data = await response.json();
        if (Array.isArray(data.detail)) {
            return data.detail.map((item) => item.msg).filter(Boolean).join(' ');
        }
        return data.detail || fallback;
    } catch (_) {
        return fallback;
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

async function apiFetch(path, options = {}) {
    const token = localStorage.getItem('token');
    if (!token) {
        handleUnauthorized();
        throw new Error('Sua sessão expirou. Entre novamente.');
    }
    const response = await fetch(`${API_ACCOUNT}${path}`, {
        cache: 'no-store',
        ...options,
        headers: {
            Authorization: `Bearer ${token}`,
            ...(options.headers || {}),
        },
    });
    if (response.status === 401) {
        handleUnauthorized();
        throw new Error('Sua sessão expirou. Entre novamente.');
    }
    return response;
}

function setAvatarImage(url) {
    avatarPreview.replaceChildren();
    const image = document.createElement('img');
    image.src = url;
    image.alt = 'Foto de perfil selecionada';
    avatarPreview.appendChild(image);
}

function setAvatarInitial(name) {
    avatarPreview.replaceChildren(avatarInitial);
    avatarInitial.textContent = (name || 'U').trim().charAt(0).toUpperCase() || 'U';
}

async function loadProfile() {
    try {
        const response = await apiFetch('/perfil');
        if (!response.ok) throw new Error(await parseError(response, 'Não foi possível carregar o perfil.'));
        const profile = await response.json();
        currentUserId = profile.user_id;
        profileName.value = profile.nome || '';
        profileEmail.value = profile.email || '';
        setAvatarInitial(profile.nome);
        if (profile.foto_url) {
            const photoResponse = await apiFetch(`/foto/${profile.user_id}`);
            if (photoResponse.ok) {
                const blob = await photoResponse.blob();
                currentPhotoUrl = URL.createObjectURL(blob);
                setAvatarImage(currentPhotoUrl);
            }
        }
    } catch (error) {
        showFeedback(profileFeedback, error.message || 'Não foi possível carregar o perfil.', 'error');
    }
}

profileName.addEventListener('input', () => {
    if (!currentPhotoUrl && !selectedPhotoUrl) setAvatarInitial(profileName.value);
});

profilePhoto.addEventListener('change', () => {
    hideFeedback(profileFeedback);
    const file = profilePhoto.files?.[0];
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        profilePhoto.value = '';
        showFeedback(profileFeedback, 'Selecione uma imagem JPEG, PNG ou WebP.', 'error');
        return;
    }
    if (file.size > 5 * 1024 * 1024) {
        profilePhoto.value = '';
        showFeedback(profileFeedback, 'A imagem deve ter no máximo 5 MB.', 'error');
        return;
    }
    if (selectedPhotoUrl) URL.revokeObjectURL(selectedPhotoUrl);
    selectedPhotoUrl = URL.createObjectURL(file);
    photoFileName.textContent = file.name;
    setAvatarImage(selectedPhotoUrl);
});

profileForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideFeedback(profileFeedback);
    const button = document.getElementById('saveProfileBtn');
    button.disabled = true;
    button.textContent = 'Salvando...';
    try {
        const form = new FormData();
        form.append('nome', profileName.value.trim());
        form.append('email', profileEmail.value.trim());
        if (profilePhoto.files?.[0]) form.append('foto', profilePhoto.files[0]);
        const response = await apiFetch('/perfil', { method: 'PUT', body: form });
        if (!response.ok) throw new Error(await parseError(response, 'Não foi possível salvar o perfil.'));
        const data = await response.json();
        const profile = data.perfil;
        if (data.access_token) {
            window.AppShell.Sessao.salvar({ token: data.access_token, nome: profile.nome });
        }
        profileName.value = profile.nome;
        profileEmail.value = profile.email;
        setAvatarInitial(profile.nome);
        if (selectedPhotoUrl) URL.revokeObjectURL(selectedPhotoUrl);
        selectedPhotoUrl = null;
        profilePhoto.value = '';
        photoFileName.textContent = 'Nenhuma nova imagem selecionada';
        if (currentPhotoUrl) URL.revokeObjectURL(currentPhotoUrl);
        currentPhotoUrl = null;
        if (profile.foto_url) {
            const photoResponse = await apiFetch(`/foto/${profile.user_id}`);
            if (photoResponse.ok) {
                currentPhotoUrl = URL.createObjectURL(await photoResponse.blob());
                setAvatarImage(currentPhotoUrl);
            }
        }
        const headerName = document.getElementById('userName');
        const headerIcon = document.getElementById('userIcon');
        if (headerName) headerName.textContent = profile.nome;
        if (headerIcon) headerIcon.textContent = profile.nome.charAt(0).toUpperCase();
        showFeedback(profileFeedback, 'Perfil atualizado com sucesso.');
    } catch (error) {
        showFeedback(profileFeedback, error.message || 'Não foi possível salvar o perfil.', 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Salvar perfil';
    }
});

function updatePasswordRequirements() {
    const value = newPassword.value;
    const checks = {
        length: value.length >= 8 && new TextEncoder().encode(value).length <= 72,
        lower: /[a-z]/.test(value),
        upper: /[A-Z]/.test(value),
        number: /\d/.test(value),
    };
    document.querySelectorAll('[data-requirement]').forEach((item) => {
        item.classList.toggle('valid', Boolean(checks[item.dataset.requirement]));
    });
}

newPassword.addEventListener('input', updatePasswordRequirements);

passwordForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideFeedback(passwordFeedback);
    if (newPassword.value !== confirmPassword.value) {
        showFeedback(passwordFeedback, 'A confirmação da nova senha não corresponde.', 'error');
        confirmPassword.focus();
        return;
    }
    updatePasswordRequirements();
    if (!Object.values({
        length: newPassword.value.length >= 8 && new TextEncoder().encode(newPassword.value).length <= 72,
        lower: /[a-z]/.test(newPassword.value),
        upper: /[A-Z]/.test(newPassword.value),
        number: /\d/.test(newPassword.value),
    }).every(Boolean)) {
        showFeedback(passwordFeedback, 'A nova senha não atende a todos os requisitos.', 'error');
        return;
    }

    const button = document.getElementById('savePasswordBtn');
    button.disabled = true;
    button.textContent = 'Atualizando...';
    try {
        const response = await apiFetch('/senha', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                senha_atual: document.getElementById('currentPassword').value,
                nova_senha: newPassword.value,
                confirmar_senha: confirmPassword.value,
            }),
        });
        if (!response.ok) throw new Error(await parseError(response, 'Não foi possível alterar a senha.'));
        const data = await response.json();
        if (data.access_token) window.AppShell.Sessao.salvar({ token: data.access_token });
        passwordForm.reset();
        updatePasswordRequirements();
        showFeedback(passwordFeedback, data.mensagem || 'Senha alterada com sucesso.');
    } catch (error) {
        showFeedback(passwordFeedback, error.message || 'Não foi possível alterar a senha.', 'error');
    } finally {
        button.disabled = false;
        button.textContent = 'Alterar senha';
    }
});

function closeDeleteModal() {
    deleteModal.classList.remove('open');
    deleteModal.hidden = true;
    deleteForm.reset();
    hideFeedback(deleteModalFeedback);
    openDeleteModalBtn.focus();
}

openDeleteModalBtn.addEventListener('click', () => {
    hideFeedback(deleteFeedback);
    deleteModal.hidden = false;
    requestAnimationFrame(() => deleteModal.classList.add('open'));
    deletePassword.focus();
});

cancelDeleteBtn.addEventListener('click', closeDeleteModal);
deleteModal.addEventListener('click', (event) => {
    if (event.target === deleteModal) closeDeleteModal();
});
window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !deleteModal.hidden) closeDeleteModal();
});

deleteForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideFeedback(deleteModalFeedback);
    if (!confirmDeleteCheck.checked) {
        showFeedback(deleteModalFeedback, 'Marque a confirmação para continuar.', 'error');
        return;
    }
    confirmDeleteBtn.disabled = true;
    confirmDeleteBtn.textContent = 'Excluindo...';
    try {
        const response = await apiFetch('', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ senha_atual: deletePassword.value, confirmar: true }),
        });
        if (!response.ok) throw new Error(await parseError(response, 'Não foi possível excluir a conta.'));
        const data = await response.json();
        showFeedback(deleteModalFeedback, data.mensagem || 'Conta excluída.', 'success');
        confirmDeleteBtn.disabled = true;
        window.AppShell.Sessao.limpar();
        setTimeout(() => { window.location.href = '../auth/login.html'; }, 1800);
    } catch (error) {
        showFeedback(deleteModalFeedback, error.message || 'Não foi possível excluir a conta.', 'error');
        confirmDeleteBtn.disabled = false;
        confirmDeleteBtn.textContent = 'Excluir definitivamente';
    }
});

document.querySelectorAll('.account-nav-link').forEach((link) => {
    link.addEventListener('click', () => {
        document.querySelectorAll('.account-nav-link').forEach((item) => item.classList.remove('active'));
        link.classList.add('active');
    });
});

window.addEventListener('beforeunload', () => {
    if (currentPhotoUrl) URL.revokeObjectURL(currentPhotoUrl);
    if (selectedPhotoUrl) URL.revokeObjectURL(selectedPhotoUrl);
});

loadProfile();
