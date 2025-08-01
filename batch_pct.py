import sys
import subprocess
import os

def process_files(files):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    convert_script = os.path.join(script_dir, "convert_pct.py")
    
    if not os.path.exists(convert_script):
        print(f"Error: {convert_script} not found.")
        return
    
    for file in files:
        if os.path.exists(file):
            print(f"Processing: {file}")
            try:
                subprocess.run([sys.executable, convert_script, file], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error processing {file}: {e}")
        else:
            print(f"File not found: {file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_files(sys.argv[1:])
    else:
        print("Drag and drop files onto this script to process them.")
