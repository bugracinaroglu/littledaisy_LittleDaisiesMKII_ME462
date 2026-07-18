import subprocess

def restore_file(filename):
    # Try to get the file from HEAD~1
    result = subprocess.run(["git", "show", f"HEAD~1:{filename}"], capture_output=True, text=True)
    if result.returncode == 0:
        with open(filename, "w") as f:
            f.write(result.stdout)
        print(f"Restored {filename} from HEAD~1")
    else:
        print(f"Failed to restore {filename}: {result.stderr}")

restore_file("main.py")
restore_file("main_colored.py")
