import os
import shutil

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mods_source = os.path.join(base_dir, 'mods_source')
    local = os.path.join(base_dir, 'local')

    if not os.path.isdir(mods_source):
        print(f"'mods_source' folder not found in {base_dir}")
        return
    if not os.path.isdir(local):
        print(f"'local' folder not found in {base_dir}")
        return

    for root, dirs, files in os.walk(mods_source):
        for file in files:
            if file.lower().endswith('.link'):
                continue  # Skip .link files

            source_path = os.path.join(root, file)
            rel_path = os.path.relpath(source_path, mods_source)
            dest_path = os.path.join(local, rel_path)

            copy_file = False
            if not os.path.exists(dest_path):
                copy_file = True
            else:
                src_mtime = os.path.getmtime(source_path)
                dst_mtime = os.path.getmtime(dest_path)
                if src_mtime > dst_mtime:
                    copy_file = True

            if copy_file:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(source_path, dest_path)
                print(f"Copied: {rel_path}")
            else:
                print(f"Up to date: {rel_path}")

if __name__ == "__main__":
    main()
