// O frontend não tem etapa de build. Para uma instalação com domínio próprio,
// pode-se definir `window.MASKSAFE_API_URL` antes deste arquivo ser carregado.
// Em Vercel/Render, a URL pública do backend continua sendo o fallback.
const configuredApiUrl = typeof window.MASKSAFE_API_URL === 'string'
    ? window.MASKSAFE_API_URL.trim()
    : '';
const isLocalhost = window.location.hostname === 'localhost'
    || window.location.hostname === '127.0.0.1';
const API_ROOT = (configuredApiUrl || (isLocalhost
    ? 'http://localhost:8000'
    : 'https://masksafe-backend-q8y4.onrender.com')).replace(/\/+$/, '');

// Respostas da API podem trazer caminhos relativos ("/documentos/...") ou
// URLs absolutas (quando o backend está atrás de um proxy). Concatenar as duas
// formas produzia URLs inválidas e, em alguns ambientes, 404 no preview.
function apiUrl(path) {
    if (!path) return API_ROOT;
    try {
        return new URL(String(path), `${API_ROOT}/`).toString();
    } catch (_) {
        return `${API_ROOT}/${String(path).replace(/^\/+/, '')}`;
    }
}
