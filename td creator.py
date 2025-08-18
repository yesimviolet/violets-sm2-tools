#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import sys
from pathlib import Path

BASE_TD = """convert_settings = {
   resample = 0
   mipmap_level = 12
   format_name = "MD"
   format_descr = "Diff(rgb)"
   uncompressed_flag = false
   fade_flag = false
   fade_begin = 0
   fade_end = 0
   color = {
      R = 127.000000
      G = 127.000000
      B = 127.000000
      A = 0.000000
   }
   filter = 0
   sharpen = 1
   compressionQuality = 3
   force_use_oxt1_flag = false
   fp16 = false
}
usage = "MD"
version = 1
"""

EM_TD = """mapping = {
   lod_bias = 0.000000
   anisotropy = 0.000000
   address_u = "wrap"
   address_v = "wrap"
}
rendering = {
   use_akill = false
   akill_ref = 127
   linear_rgb = false
   sm_hi = false
   detail_density = 0.000000
   detail_scale = 1.000000
   hdr_scale = -1.000000
}
isUltraHiRes = false
version = 1
usage = "MEM"
convert_settings = {
   resample = 0
   mipmap_level = 11
   format_name = "MEM"
   format_descr = "RGBEm(rgb)"
   uncompressed_flag = false
   force_use_oxt1_flag = false
   fp16 = false
   fade_flag = false
   fade_begin = 0
   fade_end = 0
   fade_mask = {
      R = true
      G = true
      B = true
      A = false
   }
   color = {
      R = 127.000000
      G = 127.000000
      B = 127.000000
      A = 0.000000
   }
   fade_rough_flag = false
   fade_rough_mip_bot = 0.000000
   fade_rough_mip_top = 1.000000
   fade_rough_top_min = 0.500000
   filter = 0
   sharpen = 1
   compressionQuality = 3
   m_akill_ref = 127
   m_akill_thick = 0
   auto_mipmap_brightness_param = 127
}
"""

SPEC_TD = """mapping = {
   lod_bias = 0.000000
   anisotropy = 0.000000
   address_u = "wrap"
   address_v = "wrap"
}
rendering = {
   use_akill = false
   akill_ref = 127
   linear_rgb = false
   sm_hi = false
   detail_density = 0.000000
   detail_scale = 1.000000
   hdr_scale = -1.000000
}
isUltraHiRes = false
version = 1
usage = "MSCRGHAO"
convert_settings = {
   resample = 0
   mipmap_level = 10
   format_name = "MSCRGHAO"
   format_descr = "Metalness(r)+Roughness(g)+AO(b)"
   uncompressed_flag = false
   force_use_oxt1_flag = false
   fp16 = false
   fade_flag = false
   fade_begin = 0
   fade_end = 0
   fade_mask = {
      R = true
      G = true
      B = true
      A = false
   }
   color = {
      R = 127.000000
      G = 127.000000
      B = 127.000000
      A = 0.000000
   }
   fade_rough_flag = false
   fade_rough_mip_bot = 0.000000
   fade_rough_mip_top = 1.000000
   fade_rough_top_min = 0.500000
   filter = 4
   sharpen = 3
   compressionQuality = 3
   m_akill_ref = 127
   m_akill_thick = 0
   auto_mipmap_brightness_param = 127
}
"""

NM_TD = """mapping = {
   lod_bias = 0.000000
   anisotropy = 0.000000
   address_u = "wrap"
   address_v = "wrap"
}
rendering = {
   use_akill = false
   akill_ref = 127
   linear_rgb = false
   sm_hi = false
   detail_density = 0.000000
   detail_scale = 1.000000
   hdr_scale = -1.000000
}
isUltraHiRes = false
version = 1
usage = "MNM"
convert_settings = {
   resample = 0
   mipmap_level = 10
   format_name = "MNM"
   format_descr = "Normalmap(rgb)"
   uncompressed_flag = false
   force_use_oxt1_flag = false
   fp16 = false
   fade_flag = false
   fade_begin = 0
   fade_end = 0
   fade_mask = {
      R = true
      G = true
      B = true
      A = false
   }
   color = {
      R = 127.000000
      G = 127.000000
      B = 127.000000
      A = 0.000000
   }
   fade_rough_flag = false
   fade_rough_mip_bot = 0.000000
   fade_rough_mip_top = 1.000000
   fade_rough_top_min = 0.500000
   filter = 0
   sharpen = 1
   compressionQuality = 3
   m_akill_ref = 127
   m_akill_thick = 0
   auto_mipmap_brightness_param = 127
}
"""

BASE_RES = """__type: res_desc_td
descType: ''
linksPct:
- res://pct/(image name)_nm.pct.resource
- res://pct/(image name)_spec.pct.resource
- res://pct/(image name).pct.resource
- res://pct/part_nm_03_nm.pct.resource
- res://pct/part_nm_06_nm.pct.resource
- res://pct/phantom_hands.pct.resource
materialTemplates: res://material_templates/material_templates.resource
name: (image name)
sdrPresets:
- res://sdr_presets/glt_sdr_preset_default.sd.resource
- res://sdr_presets/mtl_fill_sdr_preset_default.sd.resource
- res://sdr_presets/sfx_sdr_preset_default.sd.resource
td: (image name).td
tdDefaults: res://td_defaults/td_defaults.resource
"""

EM_RES = """__type: res_desc_td
descType: ''
linksPct:
- res://pct/(image name).pct.resource
materialTemplates: res://material_templates/material_templates.resource
name: (image name)
sdrPresets: []
td: (image name).td
tdDefaults: res://td_defaults/td_defaults.resource
"""

SPEC_RES = """__type: res_desc_td
descType: spec
linksPct:
- res://pct/(image name).pct.resource
materialTemplates: res://material_templates/material_templates.resource
name: (image name)
sdrPresets: []
td: (image name).td
tdDefaults: res://td_defaults/td_defaults.resource
"""

NM_RES = """__type: res_desc_td
descType: nm
linksPct:
- res://pct/(image name).pct.resource
materialTemplates: res://material_templates/material_templates.resource
name: (image name)
sdrPresets: []
td: (image name).td
tdDefaults: res://td_defaults/td_defaults.resource
"""

SUFFIX_MAP = [
    ("_nm", "nm"),
    ("_em", "em"),
    ("_spec", "spec"),
    ("_cc", "cc"),
    ("_a", "a"),
]

IMAGE_EXTS = {".png", ".tga", ".dds", ".jpg", ".jpeg", ".exr", ".bmp", ".tiff", ".tif"}

BUILTINS = {
    "base": (BASE_TD, BASE_RES),
    "cc":   (BASE_TD, BASE_RES),
    "a":    (BASE_TD, BASE_RES),
    "em":   (EM_TD, EM_RES),
    "spec": (SPEC_TD, SPEC_RES),
    "nm":   (NM_TD, NM_RES),
}

def detect_kind(stem: str) -> str:
    s = stem.lower()
    for suffix, kind in SUFFIX_MAP:
        if s.endswith(suffix):
            return kind
    return "base"

def fill_tokens(template_text: str, image_base: str) -> str:
    return template_text.replace("(image name)", image_base)

def write_text(path: Path, text: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        print(f"Skip (exists): {path}")
        return
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Created: {path}")

def process_image(img: Path, overwrite: bool) -> None:
    if not img.exists():
        print(f"Not found: {img}")
        return
    if img.suffix.lower() not in IMAGE_EXTS:
        print(f"Skip (not an image): {img.name}")
        return
    base = img.stem
    kind = detect_kind(base)
    td_tmpl, res_tmpl = BUILTINS[kind]
    td_text = fill_tokens(td_tmpl, base)
    res_text = fill_tokens(res_tmpl, base)
    out_td = img.with_name(f"{base}.td")
    out_res = img.with_name(f"{base}.td.resource")
    write_text(out_td, td_text, overwrite)
    write_text(out_res, res_text, overwrite)

def main(argv: list[str]) -> int:
    if not argv:
        return 1
    overwrite = False
    paths: list[str] = []
    for a in argv:
        if a == "--force":
            overwrite = True
        else:
            paths.append(a)
    if not paths:
        return 1
    for p in paths:
        try:
            process_image(Path(p), overwrite)
        except Exception as e:
            print(f"[ERROR] {p}: {e}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
