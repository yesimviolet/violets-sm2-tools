import os
import sys
import json
import yaml
import urllib.request
import subprocess
import numpy as np
from PIL import Image

# ---------------- Paths ----------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(SCRIPT_DIR, "project", "bin")
ASSET_PCT_DIR = os.path.join(SCRIPT_DIR, "project", "assets", "pct")
TGA_OUT_DIR = os.path.join(SCRIPT_DIR, "project", "resources", "tga")
TEXCONV_EXE = os.path.join(BIN_DIR, "texconv.exe")

# -------------- Format Map --------------
# 34: BC1/DXT1, 35: BC2/DXT3, 36: BC5/ATI2 (normals/spec),
# 37: emissive stored as one-channel (we decode as BC4 gray -> RGB),
# 51: BC7 UNORM, 52: BC7 UNORM SRGB
FORMAT_MAP = {
    34: ("FOURCC", b"DXT1", None),
    35: ("FOURCC", b"DXT3", None),
    36: ("FOURCC", b"ATI2", None),
    37: ("FOURCC", b"DXT5", None),      # we won't use texconv for this; treat as BC4
    51: ("DX10",   b"DX10", 98),        # DXGI_FORMAT_BC7_UNORM
    52: ("DX10",   b"DX10", 99),        # DXGI_FORMAT_BC7_UNORM_SRGB
}

# ------------- Helpers: I/O -------------
def fetch_latest_texconv_exe_url():
    with urllib.request.urlopen("https://api.github.com/repos/microsoft/DirectXTex/releases") as resp:
        releases = json.loads(resp.read().decode("utf-8"))
    for rel in releases:
        for asset in rel.get("assets", []):
            if asset.get("name", "").lower() == "texconv.exe":
                return asset["browser_download_url"]
    raise RuntimeError("No texconv.exe asset found in DirectXTex releases")

def ensure_texconv(debug=False):
    os.makedirs(BIN_DIR, exist_ok=True)
    if os.path.isfile(TEXCONV_EXE):
        return
    url = fetch_latest_texconv_exe_url()
    if debug:
        print("[DEBUG] Downloading texconv.exe …")
    urllib.request.urlretrieve(url, TEXCONV_EXE)

def read_resource_yaml(resource_path):
    with open(resource_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# -------- DDS Header for compressed data --------
def make_dds_header(width, height, header_type, fourcc, dxgi_fmt=None):
    hdr = bytearray(128 + (20 if header_type == "DX10" else 0))
    # DDS magic + header size/flags
    hdr[0:4] = b"DDS "
    hdr[4:8] = (124).to_bytes(4, "little")
    hdr[8:12] = (0x00021007).to_bytes(4, "little")  # CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE
    hdr[12:16] = height.to_bytes(4, "little")
    hdr[16:20] = width.to_bytes(4, "little")
    lin = max(1, (width+3)//4) * max(1, (height+3)//4) * 16
    hdr[20:24] = lin.to_bytes(4, "little")
    hdr[24:28] = (0).to_bytes(4, "little")          # depth
    hdr[28:32] = (1).to_bytes(4, "little")          # mipMapCount=1
    hdr[32:76] = (0).to_bytes(44, "little")         # reserved
    # PIXELFORMAT (FOURCC)
    hdr[76:80] = (32).to_bytes(4, "little")
    hdr[80:84] = (0x00000004).to_bytes(4, "little")
    hdr[84:88] = fourcc
    hdr[88:92] = (0).to_bytes(4, "little")
    hdr[92:108] = (0).to_bytes(16, "little")
    # CAPS
    hdr[108:112] = (0x1000).to_bytes(4, "little")   # TEXTURE
    hdr[112:128] = (0).to_bytes(16, "little")
    if header_type == "DX10":
        hdr.extend(bytearray(20))
        hdr[128:132] = dxgi_fmt.to_bytes(4, "little")
        hdr[132:136] = (3).to_bytes(4, "little")    # D3D11_RESOURCE_DIMENSION_TEXTURE2D
        hdr[136:140] = (0).to_bytes(4, "little")    # misc
        hdr[140:144] = (1).to_bytes(4, "little")    # array size
        hdr[144:148] = (0).to_bytes(4, "little")    # misc2
    return hdr

# ------------- BC4/BC5 Decoders -------------
def decode_bc4_block(block):
    c0, c1 = block[0], block[1]
    bits = int.from_bytes(block[2:8], "little")
    pal = [c0, c1]
    if c0 > c1:
        for i in range(1, 7):
            pal.append(((7 - i)*c0 + i*c1)//7)
    else:
        for i in range(1, 5):
            pal.append(((5 - i)*c0 + i*c1)//5)
        pal.extend([0, 255])
    out = []
    for i in range(16):
        idx = (bits >> (3*i)) & 0x7
        out.append(pal[idx] if idx < len(pal) else pal[-1])
    return out

def bc4_to_img(raw, w, h):
    bx, by = (w+3)//4, (h+3)//4
    arr = np.zeros((h, w), dtype=np.uint8)
    i = 0
    for yb in range(by):
        for xb in range(bx):
            blk = raw[i:i+8]
            if len(blk) < 8: continue
            vals = decode_bc4_block(blk)
            for yy in range(4):
                for xx in range(4):
                    x, y = xb*4+xx, yb*4+yy
                    if x < w and y < h:
                        arr[y, x] = vals[yy*4+xx]
            i += 8
    return arr

def decode_bc5_block(block):
    def chan(b):
        c0, c1 = b[0], b[1]
        bits = int.from_bytes(b[2:8], "little")
        pal = [c0, c1]
        if c0 > c1:
            for i in range(1, 7):
                pal.append(((7 - i)*c0 + i*c1)//7)
        else:
            for i in range(1, 5):
                pal.append(((5 - i)*c0 + i*c1)//5)
            pal.extend([0, 255])
        vals = []
        for i in range(16):
            idx = (bits >> (3*i)) & 0x7
            vals.append(pal[idx] if idx < len(pal) else pal[-1])
        return vals
    return chan(block[:8]), chan(block[8:])

def bc5_raw_to_rgb(raw, w, h):
    bx, by = (w+3)//4, (h+3)//4
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    i = 0
    for yb in range(by):
        for xb in range(bx):
            blk = raw[i:i+16]
            if len(blk) < 16: continue
            R, G = decode_bc5_block(blk)
            for yy in range(4):
                for xx in range(4):
                    x, y = xb*4+xx, yb*4+yy
                    if x < w and y < h:
                        arr[y, x, 0] = R[yy*4+xx]
                        arr[y, x, 1] = G[yy*4+xx]
                        arr[y, x, 2] = 0
            i += 16
    return arr

# ------------- TexConv wrappers -------------
def texconv_to_tga(dds_path, out_dir, debug=False):
    # Force to RGBA first to avoid TGA writer oddities, overwrite allowed
    cmd = [TEXCONV_EXE, "-f", "R8G8B8A8_UNORM", "-ft", "tga", "-y", "-o", out_dir, dds_path]
    if debug:
        print("[DEBUG] texconv TGA cmd:", " ".join(cmd))
        return subprocess.run(cmd)  # show exit code in debug
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def texconv_to_bmp(dds_path, out_dir, debug=False):
    # Fallback path: make BMP, then we resave as TGA via Pillow
    cmd = [TEXCONV_EXE, "-f", "R8G8B8A8_UNORM", "-ft", "bmp", "-y", "-o", out_dir, dds_path]
    if debug:
        print("[DEBUG] texconv BMP cmd:", " ".join(cmd))
        return subprocess.run(cmd)  # show exit code in debug
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ------------- Main Convert -------------
def convert_one(mip_path, debug=False):
    if not mip_path.endswith("_1.pct_mip"):
        if debug: print(f"[DEBUG] Skipping {mip_path}: not a _1.pct_mip")
        return False

    base = os.path.basename(mip_path)
    name = base[:-len("_1.pct_mip")]
    res_path = os.path.join(ASSET_PCT_DIR, f"{name}.pct.resource")
    if not os.path.isfile(res_path):
        if debug: print(f"[DEBUG] Resource not found: {res_path}")
        return False

    os.makedirs(TGA_OUT_DIR, exist_ok=True)
    tga_path = os.path.join(TGA_OUT_DIR, f"{name}.tga")
    dds_path = os.path.join(TGA_OUT_DIR, f"{name}.dds")
    bmp_path = os.path.join(TGA_OUT_DIR, f"{name}.bmp")  # used only if tga conversion fails

    res = read_resource_yaml(res_path)
    header = res.get("header", {})
    fmt = header.get("format")
    sx, sy = header.get("sx"), header.get("sy")
    mips = header.get("mipLevel") or []

    # pick top mip (match sx/sy first; else largest size)
    top = None
    for m in mips:
        if m.get("width", sx) == sx and m.get("height", sy) == sy:
            top = m; break
    if top is None and mips:
        top = max(mips, key=lambda mm: mm.get("size", 0))
    if top is None:
        if debug: print("[DEBUG] No mip levels in resource")
        return False

    with open(mip_path, "rb") as f:
        f.seek(top["offset"])
        raw = f.read(top["size"])

    if debug:
        print(f"----\n{mip_path}: format={fmt}, size=({sx}x{sy}), mips={len(mips)}")
        for i, m in enumerate(mips):
            print(f"  Mip {i+1}: offset={m['offset']}, size={m['size']}")

    try:
        # Emissive (engine uses 37; behaves like BC4 one-channel)
        if fmt == 37:
            gray = bc4_to_img(raw, sx, sy)
            rgb = np.stack([gray, gray, gray], axis=2)
            Image.fromarray(rgb, mode="RGB").save(tga_path)
            print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
            return True

        if fmt not in FORMAT_MAP:
            # last resort: raw RGBA try
            if len(raw) == sx * sy * 4:
                arr = np.frombuffer(raw, dtype=np.uint8).reshape((sy, sx, 4))[:, :, :3]
                Image.fromarray(arr, mode="RGB").save(tga_path)
                print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
                return True
            print(f"{'[DEBUG] ' if debug else ''}Format {fmt} not supported for {mip_path}")
            return False

        typ, fourcc, dxgi = FORMAT_MAP[fmt]
        # Write a minimal 1-mip compressed DDS and let texconv decompress to RGBA & write image
        with open(dds_path, "wb") as out:
            out.write(make_dds_header(sx, sy, typ, fourcc, dxgi))
            out.write(raw)

        # Try direct TGA first (force RGBA)
        ensure_texconv(debug)
        r = texconv_to_tga(dds_path, TGA_OUT_DIR, debug=debug)
        if r.returncode != 0:
            # Fallback to BMP, then re-save as TGA via Pillow
            if debug: print("[DEBUG] texconv TGA failed, trying BMP route…")
            rb = texconv_to_bmp(dds_path, TGA_OUT_DIR, debug=debug)
            if rb.returncode != 0:
                if debug: print("[DEBUG] texconv BMP also failed")
                return False
            # bmp should now exist; load & save as tga
            if os.path.exists(bmp_path):
                img = Image.open(bmp_path).convert("RGB")
                img.save(tga_path)
            else:
                # texconv names outputs based on input; ensure path
                # If for some reason it emitted a different name, find any .bmp and use it:
                found = None
                for fn in os.listdir(TGA_OUT_DIR):
                    if fn.lower().endswith(".bmp") and fn.lower().startswith(name.lower()):
                        found = os.path.join(TGA_OUT_DIR, fn); break
                if not found:
                    return False
                Image.open(found).convert("RGB").save(tga_path)
                if not debug:
                    try: os.remove(found)
                    except: pass
            print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
        else:
            # TexConv wrote TGA into the output dir (named <name>.tga)
            # Nothing else needed.
            print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")

        # Cleanup (keep intermediates if -debug)
        if debug:
            # hide intermediates in debug
            for p in (dds_path, bmp_path):
                if os.path.exists(p):
                    try:
                        os.system(f'attrib +h "{p}"')
                    except:
                        pass
        else:
            for p in (dds_path, bmp_path):
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass

        return True

    except Exception as e:
        if debug:
            print("[DEBUG] Exception:", repr(e))
        return False

def main():
    debug = False
    files = []
    for a in sys.argv[1:]:
        if a == "-debug":
            debug = True
        else:
            files.append(a)
    if not files:
        print("Drag one or more _1.pct_mip files onto this script to convert.")
        sys.exit(1)

    os.makedirs(TGA_OUT_DIR, exist_ok=True)
    for p in files:
        convert_one(p, debug=debug)

if __name__ == "__main__":
    main()
