#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import platform
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# ================== Configuration ==================
APP_NAME = "GitCommitHelper"
ENTRY_FILE = "git_commit_gui.py"
REQUIRED_PACKAGES = ["customtkinter", "pyinstaller"]

# Windows: hide subprocess window
CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0


def print_info(msg):
    print(f"[INFO] {msg}")


def print_success(msg):
    print(f"[OK] {msg}")


def print_error(msg):
    print(f"[ERROR] {msg}")


def print_step(msg):
    print(f"\n[STEP] {msg}")


def run_cmd(cmd, hide_window=True):
    """Run command and return result"""
    try:
        kwargs = {
            "text": True,
            "encoding": "utf-8",
            "errors": "replace"
        }
        if platform.system() == "Windows" and hide_window:
            kwargs["creationflags"] = CREATE_NO_WINDOW

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **kwargs
        )
        out, err = proc.communicate()
        return out.strip(), err.strip(), proc.returncode
    except Exception as e:
        return "", str(e), -1


def check_python():
    """Check Python version"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required, current: {version.major}.{version.minor}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro}")
    return True


def install_package(package):
    """Install Python package"""
    print_info(f"Installing {package}...")
    out, err, code = run_cmd([sys.executable, "-m", "pip", "install", package])
    if code == 0:
        print_success(f"{package} installed")
        return True
    else:
        print_error(f"{package} install failed: {err}")
        return False


def check_dependencies():
    """Check and install dependencies"""
    print_step("Checking dependencies...")
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
            print_success(f"{pkg} OK")
        except ImportError:
            missing.append(pkg)
            print_info(f"{pkg} not found")

    if missing:
        print_info(f"Installing: {', '.join(missing)}")
        for pkg in missing:
            if not install_package(pkg):
                return False
    return True


def clean_build():
    """Clean old build directories"""
    print_step("Cleaning old builds...")
    for dir_name in ["build", "dist"]:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print_success(f"Removed {dir_name}/")
            except Exception as e:
                print_error(f"Failed to remove {dir_name}/: {e}")
                return False
    return True


def build_exe():
    """Build exe with PyInstaller"""
    print_step("Building exe...")

    if not os.path.exists(ENTRY_FILE):
        print_error(f"Entry file not found: {ENTRY_FILE}")
        return False

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--add-data", f"{ENTRY_FILE};.",
        ENTRY_FILE
    ]

    print_info(f"Running: {' '.join(cmd)}")
    print_info("Please wait, this may take 1-3 minutes...")

    out, err, code = run_cmd(cmd)

    if code == 0:
        print_success("Build successful!")
        exe_path = os.path.join("dist", f"{APP_NAME}.exe")
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path) / (1024 * 1024)
            print_success(f"File: {exe_path} ({size:.2f} MB)")
        return True
    else:
        print_error(f"Build failed: {err}")
        if out:
            print_info(f"Output: {out}")
        return False


def main():
    print("=" * 50)
    print("   Git Commit Helper - Build Tool")
    print("=" * 50)

    if not check_python():
        sys.exit(1)

    if not check_dependencies():
        sys.exit(1)

    if not clean_build():
        sys.exit(1)

    if not build_exe():
        sys.exit(1)

    print("\n" + "=" * 50)
    print_success("Build completed!")
    print_success(f"EXE location: dist\\{APP_NAME}.exe")
    print("=" * 50)


if __name__ == "__main__":
    main()