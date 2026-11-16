r"""Arma el video (GIF animado) del transitorio de G025 a partir de los fotogramas de video.java.

    python armar_video.py   → baja frames\ de la .245 y deja en PAT_PAT1_resultados\transitorio_G025\:
                              G025_transitorio_vectores.gif (las dos escenas una sobre otra, 1 vuelta del rotor)

Recorta cada fotograma a la voluta, el rotor y la tubería y pega la escala de color debajo. Sin ffmpeg: Pillow (GIF)."""
import pathlib, sys, tempfile

from PIL import Image, ImageDraw, ImageFont

AQUI = pathlib.Path(__file__).parent
sys.path.insert(0, str(AQUI.parent.parent / "doe"))
import doe   # noqa: E402

IP, OUT = "172.17.76.245", "C:/trabajo/TRANSITORIO_G025"
DESTINO = pathlib.Path(r"C:\Users\investigacion\Desktop\Geometrias_Prueba\PAT_PAT1_resultados\transitorio_G025")
ZONA, ESCALA = (330, 300, 1270, 700), (1110, 820, 1510, 930)   # en el PNG de 1600 × 1000
TITULO = {"vectores_medio": "Velocidad relativa al rotor (plano medio)", "plano_vectores": "Velocidad absoluta (plano medio)"}


def cuadro(png: pathlib.Path, nombre: str, grados: float) -> Image.Image:
    im = Image.open(png).convert("RGB")
    z, e = im.crop(ZONA), im.crop(ESCALA)
    c = Image.new("RGB", (z.width, z.height + e.height + 30), "white")
    c.paste(z, (0, 30)); c.paste(e, ((z.width - e.width) // 2, z.height + 30))
    d = ImageDraw.Draw(c)
    try:
        f = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        f = ImageFont.load_default()
    d.text((10, 5), f"{TITULO[nombre]} · rotor a {grados:5.0f}°", fill="black", font=f)
    return c


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        doe.scp(t, IP, OUT + "/frames", bajar=True)
        fr = pathlib.Path(t) / "frames"
        n = len(list(fr.glob("vectores_medio_*.png")))
        cuadros = []
        for k in range(n):
            a = cuadro(fr / f"vectores_medio_{k:04d}.png", "vectores_medio", k * 4)
            b = cuadro(fr / f"plano_vectores_{k:04d}.png", "plano_vectores", k * 4)
            c = Image.new("RGB", (a.width, a.height + b.height), "white")
            c.paste(a, (0, 0)); c.paste(b, (0, a.height))
            cuadros.append(c.resize((c.width * 3 // 4, c.height * 3 // 4)).quantize(colors=128, method=Image.Quantize.MEDIANCUT))
        gif = DESTINO / "G025_transitorio_vectores.gif"
        cuadros[0].save(gif, save_all=True, append_images=cuadros[1:], duration=110, loop=0, optimize=True)
        cuadros[0].convert("RGB").save(DESTINO / "G025_transitorio_vectores_cuadro0.png")
    print(n, "cuadros →", gif, f"{gif.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
