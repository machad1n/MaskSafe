import re

EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._%+-]{0,62}[A-Za-z0-9])?@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
)

PHONE_PATTERN = re.compile(
    r"(?:\+55[\s-]?)?(?:\([1-9]\d\)|[1-9]\d)[\s-]?"
    r"(?:9?\d{4})[-\s]?\d{4}"
)

CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CNS_PATTERN = re.compile(r"\b\d{15}\b")
CID10_PATTERN = re.compile(r"\b[A-TV-Z]\d{2}(?:\.\d{1,4})?\b", re.IGNORECASE)
CRM_PATTERN = re.compile(r"CRM(?:\s*[-/]\s*[A-Z]{2})?\s+\d{4,6}", re.IGNORECASE)

# Cartao de credito/debito: 13 a 19 digitos, em blocos separados por espaco ou
# hifen ("4111 1111 1111 1111", "4111-1111-1111-1111") ou corridos. A
# validacao de verdade e o Luhn em `cartao_valido`: sem ela, qualquer
# sequencia longa de numeros viraria "cartao".
CARTAO_PATTERN = re.compile(r"(?<![\d.,/-])\d{4}(?:[ -]?\d{3,4}){2}[ -]?\d{1,7}(?![\d.,/-]?\d)")

# Os campos curtos de pagamento só são sensíveis quando acompanhados de um
# rótulo explícito. Não procurar CVV ou validade como números isolados reduz
# falsos positivos em datas, códigos postais, telefones e identificadores.
CARTAO_CVV_PATTERN = re.compile(
    r"(?i)(?:\bCVV2?\b|\bCVC2?\b|\bCSC\b|c[oó]digo\s+(?:de\s+)?seguran[cç]a)"
    r"\s*[:#-]?\s*\d{3,4}\b"
)
CARTAO_VALIDADE_PATTERN = re.compile(
    r"(?i)(?:\bvalidade\b|\bv[aá]lido\s+at[eé]\b|\bvalid\s+thru\b|"
    r"\bexp(?:ira[cç][aã]o|iry|iration)?\b)\s*[:#-]?\s*"
    r"(?P<mes>0[1-9]|1[0-2])\s*[/.-]\s*(?P<ano>\d{2}|\d{4})\b"
)
CARTAO_TITULAR_PATTERN = re.compile(
    r"(?i)(?:\bnome\s+(?:do\s+)?titular\b|\btitular\s+(?:do\s+)?cart[aã]o\b|"
    r"\bcardholder(?:\s+name)?\b|\bname\s+on\s+card\b)\s*[:#-]?\s*"
    r"[A-ZÀ-ÖØ-öø-ÿ][A-ZÀ-ÖØ-öø-ÿ'’. -]{1,59}"
)


def cartao_valido(numero: str) -> bool:
    """Número sintaticamente válido de uma bandeira comum, validado por Luhn."""
    digitos = [int(c) for c in numero if c.isdigit()]
    if not 13 <= len(digitos) <= 19:
        return False
    soma = 0
    for i, d in enumerate(reversed(digitos)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        soma += d
    return soma % 10 == 0 and bandeira_cartao(numero) is not None


def bandeira_cartao(numero: str) -> str | None:
    """Reconhece faixas IIN e comprimentos usuais das principais bandeiras."""
    digits = re.sub(r"\D", "", numero)
    length = len(digits)
    prefix2 = int(digits[:2]) if len(digits) >= 2 else -1
    prefix3 = int(digits[:3]) if len(digits) >= 3 else -1
    prefix4 = int(digits[:4]) if len(digits) >= 4 else -1

    # Inclui as faixas brasileiras mais comuns antes de Visa, pois alguns IIN
    # Elo também começam por 4. Os campos continuam sujeitos ao Luhn em
    # `cartao_valido`.
    elo_iins = (
        "401178", "401179", "431274", "438935", "451416", "457393",
        "457631", "457632", "504175", "506699", "5067", "5090",
        "627780", "636297", "636368", "650031", "650033", "650035",
        "6504", "6505", "6507", "6509", "6516", "6517", "6550",
    )
    if any(digits.startswith(prefix) for prefix in elo_iins) and length in {16, 19}:
        return "ELO"
    if digits.startswith("6062") and length == 16:
        return "HIPERCARD"
    if digits.startswith("4") and length in {13, 16, 19}:
        return "VISA"
    if (51 <= prefix2 <= 55 or 2221 <= prefix4 <= 2720) and length == 16:
        return "MASTERCARD"
    if digits[:2] in {"34", "37"} and length == 15:
        return "AMEX"
    if (digits.startswith(("6011", "65")) or 644 <= prefix3 <= 649
            or 622126 <= int(digits[:6] or -1) <= 622925) and length in {16, 19}:
        return "DISCOVER"
    if (300 <= prefix3 <= 305 or digits[:2] in {"36", "38", "39"}) and length == 14:
        return "DINERS"
    if 3528 <= prefix4 <= 3589 and 16 <= length <= 19:
        return "JCB"
    if digits.startswith("62") and 16 <= length <= 19:
        return "UNIONPAY"
    if (digits.startswith("50") or 56 <= prefix2 <= 69) and 12 <= length <= 19:
        return "MAESTRO"
    return None


def normalize_phone(phone: str) -> str | None:
    normalized_phone = phone.strip()
    if not PHONE_PATTERN.fullmatch(normalized_phone):
        return None

    digits = re.sub(r"\D", "", normalized_phone)
    return digits[2:] if normalized_phone.startswith("+55") else digits


def mask_phone(phone: str) -> str | None:
    """Oculta o miolo do telefone sem alterar sua formatação original."""
    normalized_phone = phone.strip()
    if not PHONE_PATTERN.fullmatch(normalized_phone):
        return None

    digit_positions = [
        index for index, character in enumerate(normalized_phone) if character.isdigit()
    ]
    prefix_length = 4 if normalized_phone.startswith("+55") else 2
    visible_positions = set(digit_positions[:prefix_length] + digit_positions[-4:])

    return "".join(
        character
        if not character.isdigit() or index in visible_positions
        else "*"
        for index, character in enumerate(normalized_phone)
    )


def mask_cpf(cpf: str) -> str | None:
    if not CPF_PATTERN.fullmatch(cpf):
        return None

    return "***.***.***-**"


def increment_cpf_count(current_count: int, entity_type: str, occurrences: int) -> int:
    return current_count + occurrences if entity_type == "CPF" else current_count

