const API_URL = `${API_ROOT}/auth`;

const params = new URLSearchParams(window.location.hash.slice(1));
const resetToken = params.get('token') || '';
// Remove o segredo do histórico/barra assim que a página o captura.
if (window.location.hash) {
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
}

const form = document.getElementById('resetPasswordForm');
const emailInput = document.getElementById('email');
const senhaInput = document.getElementById('senha');
const confirmarInput = document.getElementById('confirmar_senha');
const feedback = document.getElementById('reset-feedback');

// Email não é necessário para redefinir: o token identifica a conta.
emailInput?.remove();

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const senha = senhaInput.value.trim();
    const confirmar = confirmarInput.value.trim();

    feedback.textContent = '';

    if (!senha || !confirmar) {
        feedback.textContent = 'Preencha os campos de senha.';
        return;
    }
    if (senha !== confirmar) {
        feedback.textContent = 'As senhas não coincidem.';
        return;
    }

    if (!resetToken) {
        feedback.textContent = 'Token de redefinição ausente.';
        return;
    }

    try {
        const resp = await fetch(`${API_URL}/reset-senha`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: resetToken, senha }),
        });

        const data = await resp.json();
        if (!resp.ok) {
            feedback.textContent = data.detail || data.mensagem || 'Erro ao redefinir senha.';
            return;
        }

        feedback.textContent = data.mensagem || 'Senha alterada com sucesso.';
        // Caminho relativo: funciona servindo da raiz (Vercel) ou so de frontend/.
        setTimeout(() => { window.location.href = 'login.html'; }, 1500);
    } catch (err) {
        console.error(err);
        feedback.textContent = 'Erro ao comunicar com o servidor.';
    }
});
