import io, os, math, numpy as np, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
Z = 8; N = 2 ** Z
def tx(lon): return int((lon + 180) / 360 * N)
def ty(lat): return int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * N)
X0, X1, Y0, Y1 = tx(-125), tx(-66), ty(50), ty(24)
os.makedirs('dem_tiles', exist_ok=True)
def get(xy):
    x, y = xy; p = f'dem_tiles/{x}_{y}.png'
    if not os.path.exists(p):
        urllib.request.urlretrieve(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png', p)
    a = np.asarray(Image.open(p).convert('RGB')).astype(np.float32)
    return xy, (a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768)
tiles = [(x, y) for x in range(X0, X1 + 1) for y in range(Y0, Y1 + 1)]
M = np.zeros(((Y1 - Y0 + 1) * 256, (X1 - X0 + 1) * 256), np.float32)
with ThreadPoolExecutor(16) as ex:
    for (x, y), a in ex.map(get, tiles):
        M[(y - Y0) * 256:(y - Y0 + 1) * 256, (x - X0) * 256:(x - X0 + 1) * 256] = a
np.savez_compressed('dem_conus.npz', M=M.astype(np.int16), Z=Z, X0=X0, Y0=Y0)
print(M.shape, len(tiles), M.min(), M.max())
