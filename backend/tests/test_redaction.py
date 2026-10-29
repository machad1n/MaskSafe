import unittest

from PIL import Image

from scanner.redaction import draw_cpf_mask, draw_structured_mask


class CpfMaskRenderingTests(unittest.TestCase):
    def test_draws_structured_mask_over_detected_area(self):
        image = Image.new("RGB", (180, 50), "gray")

        draw_cpf_mask(image, (10, 10, 170, 35))

        masked_area = image.crop((10, 10, 170, 35))
        self.assertEqual(image.getpixel((10, 10)), (0, 0, 0))
        self.assertTrue(
            any(
                masked_area.getpixel((x, y))[0] > 200
                for x in range(masked_area.width)
                for y in range(masked_area.height)
            )
        )

    def test_draws_any_structured_mask_over_detected_area(self):
        image = Image.new("RGB", (180, 50), "gray")

        draw_structured_mask(image, (10, 10, 170, 35), "(11) *****-5432")

        self.assertEqual(image.getpixel((10, 10)), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()


def test_mascara_fica_dentro_da_tarja():
    """A mascara branca nao pode vazar pela borda de baixo da tarja."""
    image = Image.new("RGB", (400, 80), "gray")
    caixa = (20, 20, 380, 50)

    draw_cpf_mask(image, caixa)

    for x in range(image.width):
        for y in list(range(0, 20)) + list(range(51, 80)):
            assert image.getpixel((x, y)) == (128, 128, 128), (x, y)
    # e o texto branco aparece nas metades de cima e de baixo (centralizado)
    def branco(y0, y1):
        return any(image.getpixel((x, y))[0] > 200
                   for x in range(20, 380) for y in range(y0, y1))
    assert branco(20, 35) and branco(35, 51)
