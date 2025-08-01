import os
import sys
import subprocess
from dataclasses import dataclass

CWD = os.path.dirname(os.path.realpath(__file__))

PROJECT_DIR = os.path.join(CWD, 'project')
PCT_DIR = os.path.join(PROJECT_DIR, 'resources', 'pct')
TGA_DIR = os.path.join(PROJECT_DIR, 'resources', 'tga')

BINARIES_DIR = os.path.join(PROJECT_DIR, 'bin')
TEXTURE_CONVERTER_EXE = os.path.join(BINARIES_DIR, 'TextureConverter.exe')

@dataclass(frozen=True)
class TextureDeconversionContext:
    src: str
    dst: str

def _execute_subprocess(cmd_args):
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    print(' '.join(cmd_args))

    process = subprocess.Popen(
        cmd_args,
        startupinfo=startupinfo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_DIR
    )

    stdout, stderr = process.communicate()
    print(stdout.decode())
    if stderr:
        print(stderr.decode())

    return process.wait()

def reverse_convert(ctx: TextureDeconversionContext):
    cmd = [
        TEXTURE_CONVERTER_EXE,
        ctx.src,
        ctx.dst
    ]
    return _execute_subprocess(cmd)

def main(file_paths):
    os.makedirs(TGA_DIR, exist_ok=True)

    for arg in file_paths:
        base_name = os.path.splitext(os.path.basename(arg))[0]
        src_pct = os.path.join(PCT_DIR, base_name + '.pct')
        dst_tga = os.path.join(TGA_DIR, base_name + '.tga')

        if not os.path.exists(src_pct):
            print(f'Error: {src_pct} not found, skipping.')
            continue

        print(f'Converting: {src_pct} → {dst_tga}')
        reverse_convert(TextureDeconversionContext(
            src=src_pct,
            dst=dst_tga
        ))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Drag and drop .pct file(s) onto this script to convert them.")
        sys.exit(1)
    main(sys.argv[1:])
