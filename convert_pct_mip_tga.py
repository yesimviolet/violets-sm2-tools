import os
import sys
import yaml
import warnings
from PIL import Image
import numpy as np
import subprocess
import urllib.request
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(SCRIPT_DIR, "project", "bin")
ASSET_PCT_DIR = os.path.join(SCRIPT_DIR, "project", "assets", "pct")
TGA_OUT_DIR = os.path.join(SCRIPT_DIR, "project", "resources", "tga")
TEXCONV_EXE = os.path.join(BIN_DIR, "texconv.exe")

FORMAT_MAP = {
    36: ("FOURCC", b'ATI2', None),      # BC5/ATI2N/DXN
    37: ("FOURCC", b'DXT5', None),      # BC3/DXT5 (used for emission, actually BC4 here)
    51: ("DX10",   b'DX10', 98),        # BC7 (DX10+)
}

def fetch_latest_texconv_exe_url():
    with urllib.request.urlopen("https://api.github.com/repos/microsoft/DirectXTex/releases") as resp:
        releases = json.loads(resp.read().decode("utf-8"))
    for release in releases:
        assets = release.get("assets", [])
        for asset in assets:
            name = asset["name"].lower()
            if name == "texconv.exe":
                return asset["browser_download_url"], asset["name"]
    raise RuntimeError("Could not find a suitable texconv.exe in any release.")

def download_texconv_exe():
    os.makedirs(BIN_DIR, exist_ok=True)
    if os.path.isfile(TEXCONV_EXE):
        return
    url, exe_name = fetch_latest_texconv_exe_url()
    urllib.request.urlretrieve(url, TEXCONV_EXE)

def read_resource_yaml(resource_path):
    with open(resource_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def make_dds_header(width, height, header_type, fourcc, dxgi_fmt=None):
    header = bytearray(128+20 if header_type == "DX10" else 128)
    header[0:4] = b'DDS '
    header[4:8] = (124).to_bytes(4, 'little')
    header[8:12] = (0x00021007).to_bytes(4, 'little')
    header[12:16] = height.to_bytes(4, 'little')
    header[16:20] = width.to_bytes(4, 'little')
    linear_size = max(1, ((width+3)//4)) * max(1, ((height+3)//4)) * 16
    header[20:24] = linear_size.to_bytes(4, 'little')
    header[24:28] = (0).to_bytes(4, 'little')
    header[28:32] = (1).to_bytes(4, 'little')
    header[32:76] = (0).to_bytes(44, 'little')
    header[76:80] = (32).to_bytes(4, 'little')
    header[80:84] = (0x00000004).to_bytes(4, 'little')
    header[84:88] = fourcc
    header[88:92] = (0).to_bytes(4, 'little')
    header[92:108] = (0).to_bytes(16, 'little')
    header[108:112] = (0x1000).to_bytes(4, 'little')
    header[112:116] = (0).to_bytes(4, 'little')
    header[116:120] = (0).to_bytes(4, 'little')
    header[120:124] = (0).to_bytes(4, 'little')
    header[124:128] = (0).to_bytes(4, 'little')
    if header_type == "DX10":
        header[128:132] = dxgi_fmt.to_bytes(4, 'little')
        header[132:136] = (3).to_bytes(4, 'little')
        header[136:140] = (0).to_bytes(4, 'little')
        header[140:144] = (1).to_bytes(4, 'little')
        header[144:148] = (0).to_bytes(4, 'little')
    return header

def decode_bc4_block(block):
    c0, c1 = block[0], block[1]
    bits = int.from_bytes(block[2:8], 'little')
    palette = [c0, c1]
    if c0 > c1:
        for i in range(1, 7):
            palette.append(((7 - i) * c0 + i * c1) // 7)
    else:
        for i in range(1, 5):
            palette.append(((5 - i) * c0 + i * c1) // 5)
        palette.extend([0, 255])
    out = []
    for i in range(16):
        idx = (bits >> (3 * i)) & 0x7
        if idx >= len(palette):
            out.append(palette[-1])
        else:
            out.append(palette[idx])
    return out

def bc4_to_img(raw, width, height):
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    arr = np.zeros((height, width), dtype=np.uint8)
    i = 0
    for by in range(blocks_y):
        for bx in range(blocks_x):
            block = raw[i:i+8]
            if len(block) < 8:
                continue
            vals = decode_bc4_block(block)
            for yb in range(4):
                for xb in range(4):
                    x = bx * 4 + xb
                    y = by * 4 + yb
                    if x < width and y < height:
                        arr[y, x] = vals[yb * 4 + xb]
            i += 8
    return arr

def decode_bc5_block(data):
    def decompress_channel(block):
        c0, c1 = block[0], block[1]
        codes = list(block[2:8])
        code_bytes = codes[0] | (codes[1]<<8) | (codes[2]<<16) | (codes[3]<<24) | (codes[4]<<32) | (codes[5]<<40)
        palette = [c0, c1]
        if c0 > c1:
            palette += [
                (6*c0 + 1*c1)//7, (5*c0 + 2*c1)//7, (4*c0 + 3*c1)//7,
                (3*c0 + 4*c1)//7, (2*c0 + 5*c1)//7, (1*c0 + 6*c1)//7
            ]
        else:
            palette += [
                (4*c0 + 1*c1)//5, (3*c0 + 2*c1)//5, (2*c0 + 3*c1)//5, (1*c0 + 4*c1)//5,
                0, 255
            ]
        out = []
        for i in range(16):
            idx = (code_bytes >> (3*i)) & 0x7
            out.append(palette[idx])
        return out
    r_block = data[:8]
    g_block = data[8:]
    r = decompress_channel(r_block)
    g = decompress_channel(g_block)
    b = [0]*16
    return r, g, b

def decode_bc5_data(raw_data, width, height):
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    i = 0
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            block = raw_data[i:i+16]
            if len(block) < 16:
                break
            r, g, b = decode_bc5_block(block)
            for j in range(4):
                for k in range(4):
                    y = by + j
                    x = bx + k
                    if x < width and y < height:
                        arr[y, x, 0] = r[j*4+k]
                        arr[y, x, 1] = g[j*4+k]
                        arr[y, x, 2] = 0
            i += 16
    return arr

def bc5_raw_to_tga(raw_data, width, height, tga_path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        arr = decode_bc5_data(raw_data, width, height)
        img = Image.fromarray(arr).convert("RGB")
        img.save(tga_path)

def emission_bc4_to_tga(raw_data, width, height, tga_path):
    arr = bc4_to_img(raw_data, width, height)
    rgb = np.stack([arr, arr, arr], axis=2)
    Image.fromarray(rgb, mode='RGB').save(tga_path)

def convert_one(mip_path, debug=False):
    if not mip_path.endswith('_1.pct_mip'):
        if debug:
            print(f"Skipping {mip_path}: not a '_1.pct_mip' file.")
        return False
    base_name = os.path.basename(mip_path)
    res_base = base_name.replace('_1.pct_mip', '.pct.resource')
    res_path = os.path.join(ASSET_PCT_DIR, res_base)
    if not os.path.isfile(res_path):
        if debug:
            print(f"Resource not found for {mip_path}. Skipping.")
        return False
    os.makedirs(TGA_OUT_DIR, exist_ok=True)
    tga_name = base_name.replace('_1.pct_mip', '.tga')
    tga_path = os.path.join(TGA_OUT_DIR, tga_name)
    temp_dds_path = os.path.join(TGA_OUT_DIR, tga_name.replace('.tga', '.dds'))
    resource = read_resource_yaml(res_path)
    fmt_code = resource["header"]["format"]
    mip_levels = resource["header"]["mipLevel"]
    sx, sy = resource["header"]["sx"], resource["header"]["sy"]
    top_mip = None
    for mip in mip_levels:
        w = mip.get('width', sx)
        h = mip.get('height', sy)
        if w == sx and h == sy:
            top_mip = mip
            break
    if top_mip is None:
        top_mip = max(mip_levels, key=lambda m: m.get('size', 0))
    with open(mip_path, "rb") as inf:
        inf.seek(top_mip['offset'])
        raw_data = inf.read(top_mip['size'])

    try:
        if debug:
            print(f"----\n{mip_path}: format={fmt_code}, size=({sx}x{sy}), mips={len(mip_levels)}")
            for idx, mip in enumerate(mip_levels):
                print(f"  Mip {idx+1}: offset={mip['offset']}, size={mip['size']}")
        if fmt_code == 37:
            emission_bc4_to_tga(raw_data, sx, sy, tga_path)
            print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
            # Only delete DDS in non-debug mode
            if not debug and os.path.exists(temp_dds_path):
                os.remove(temp_dds_path)
            return True

        if fmt_code == 36:
            header_type, fourcc, dxgi_fmt = FORMAT_MAP[fmt_code]
            with open(temp_dds_path, "wb") as outf:
                dds_header = make_dds_header(sx, sy, header_type, fourcc, dxgi_fmt)
                outf.write(dds_header)
                outf.write(raw_data)
            try:
                download_texconv_exe()
                subprocess.run([
                    TEXCONV_EXE,
                    "-ft", "tga",
                    "-o", TGA_OUT_DIR,
                    temp_dds_path
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
                if not debug and os.path.exists(temp_dds_path):
                    os.remove(temp_dds_path)
                return True
            except Exception:
                bc5_raw_to_tga(raw_data, sx, sy, tga_path)
                print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
                if not debug and os.path.exists(temp_dds_path):
                    os.remove(temp_dds_path)
                return True

        if fmt_code == 51:
            header_type, fourcc, dxgi_fmt = FORMAT_MAP[fmt_code]
            with open(temp_dds_path, "wb") as outf:
                dds_header = make_dds_header(sx, sy, header_type, fourcc, dxgi_fmt)
                outf.write(dds_header)
                outf.write(raw_data)
            try:
                download_texconv_exe()
                subprocess.run([
                    TEXCONV_EXE,
                    "-ft", "tga",
                    "-o", TGA_OUT_DIR,
                    temp_dds_path
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
                if not debug and os.path.exists(temp_dds_path):
                    os.remove(temp_dds_path)
                return True
            except Exception:
                if len(raw_data) == sx * sy * 4:
                    arr = np.frombuffer(raw_data, dtype=np.uint8).reshape((sy, sx, 4))[:, :, :3]
                    Image.fromarray(arr, mode='RGB').save(tga_path)
                    print(f"{'[DEBUG] ' if debug else ''}Successfully converted: {tga_path}")
                    if not debug and os.path.exists(temp_dds_path):
                        os.remove(temp_dds_path)
                    return True
                else:
                    print(f"{'[DEBUG] ' if debug else ''}Failed to convert (unknown BC7 layout): {tga_path}")
                    if not debug and os.path.exists(temp_dds_path):
                        os.remove(temp_dds_path)
                    return False

        print(f"{'[DEBUG] ' if debug else ''}Format code {fmt_code} not supported for {mip_path}. Skipping.")
        if not debug and os.path.exists(temp_dds_path):
            os.remove(temp_dds_path)
        return False
    finally:
        if not debug and os.path.exists(temp_dds_path):
            try:
                os.remove(temp_dds_path)
            except Exception:
                pass

if __name__ == "__main__":
    debug = False
    files = []
    for arg in sys.argv[1:]:
        if arg == "-debug":
            debug = True
        else:
            files.append(arg)
    if not files:
        print("Drag one or more _1.pct_mip files onto this script to convert.")
        sys.exit(1)
    for mip_path in files:
        convert_one(mip_path, debug=debug)
