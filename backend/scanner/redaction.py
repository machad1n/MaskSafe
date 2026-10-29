from PIL import Image, ImageDraw, ImageFont

CPF_MASK = "***.***.***-**"


def _fonte_que_cabe(drawer: ImageDraw.ImageDraw, mask: str, box_w: int, box_h: int):
    """Maior fonte default que deixa `mask` inteira dentro da caixa.

    Sem isto os asteriscos usavam a fonte bitmap fixa do PIL e sumiam numa
    caixa de 150 dpi: a regiao ficava so branca, sem mascara visivel.

    Deixa uma folga em volta: a mascara encostada na borda some no preto.
    """
    fonte = ImageFont.load_default()
    limite_w = max(1, box_w - 4)
    limite_h = max(1, int(box_h * 0.8))
    tamanho = 1
    while tamanho <= 200:
        candidata = ImageFont.load_default(size=tamanho)
        bb = drawer.textbbox((0, 0), mask, font=candidata)
        if (bb[2] - bb[0]) > limite_w or (bb[3] - bb[1]) > limite_h:
            break
        fonte = candidata
        tamanho += 1
    return fonte


def draw_structured_mask(
    image: Image.Image,
    bounds: tuple[float, float, float, float],
    mask: str,
) -> None:
    left, top, right, bottom = (round(value) for value in bounds)
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((left, top, right, bottom), fill="black")

    box_w = max(1, right - left)
    box_h = max(1, bottom - top)
    fonte = _fonte_que_cabe(drawer, mask, box_w, box_h)
    # Centraliza pela caixa real dos glifos (do topo do "*" ao pe do "."), e
    # nao pela posicao de desenho: o PIL desenha a partir do topo da linha da
    # fonte, que fica acima dos glifos, e a mascara saia deslocada para baixo,
    # com os pontos e tracos cortados pela borda inferior da tarja.
    bb = drawer.textbbox((0, 0), mask, font=fonte)
    x = left + (box_w - (bb[2] - bb[0])) / 2 - bb[0]
    y = top + (box_h - (bb[3] - bb[1])) / 2 - bb[1]
    drawer.text((x, y), mask, fill="white", font=fonte)


def draw_cpf_mask(image: Image.Image, bounds: tuple[float, float, float, float]) -> None:
    draw_structured_mask(image, bounds, CPF_MASK)
