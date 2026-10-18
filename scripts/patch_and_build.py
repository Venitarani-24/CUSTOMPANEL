#!/usr/bin/env python3
"""
Auto Custom Panel Maker - Patch & Customization Script
Used by GitHub Actions (and locally) to inject custom branding, logo, and KeyAuth credentials
into the C/C++ project before compiling.
"""

import os
import sys
import argparse
import urllib.request
import zipfile
import shutil
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def log(msg: str):
    print(f"[AutoPanelMaker] {msg}", flush=True)


def download_icon(icon_url: str, dest_path: Path) -> bool:
    """Download image from URL and save to destination."""
    try:
        log(f"Downloading custom logo from: {icon_url}")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        req = urllib.request.Request(icon_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        log(f"Custom logo downloaded ({dest_path.stat().st_size} bytes)")
        return True
    except Exception as e:
        log(f"Warning: Failed to download icon from {icon_url}: {e}")
        return False


def convert_image_to_ico(source_img: Path, output_ico: Path) -> bool:
    """Convert any PNG/JPEG image to multi-size Windows .ico file."""
    if not HAS_PIL:
        log("Pillow not installed; copying source image directly if already .ico")
        if source_img.suffix.lower() == ".ico":
            shutil.copy(source_img, output_ico)
            return True
        return False

    try:
        log(f"Converting image {source_img} to high-resolution Windows ICO...")
        img = Image.open(source_img)
        # Convert to RGBA for clean transparency
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Standard Windows icon sizes
        icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        img.save(output_ico, format="ICO", sizes=icon_sizes)
        log(f"Icon successfully generated at: {output_ico}")
        return True
    except Exception as e:
        log(f"Error converting image to ICO: {e}")
        return False


def sanitize_input(value: str) -> str:
    """Escape quotes and backslashes for C/C++ string literals."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def patch_file_content(file_path: Path, replacements: dict):
    """Replace placeholder tokens in a target source file."""
    if not file_path.exists():
        log(f"Warning: file {file_path} does not exist, skipping patch.")
        return

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    modified = False
    for token, val in replacements.items():
        if token in content:
            content = content.replace(token, val)
            modified = True
            log(f"Injected: {token} -> {val} in {file_path.name}")

    if modified:
        file_path.write_text(content, encoding="utf-8")
        log(f"Successfully updated {file_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Auto Panel Patch & Customizer")
    parser.add_argument("--project-dir", required=True, help="Directory of the C/C++ project")
    parser.add_argument("--panel-name", required=True, help="Custom Panel Name")
    parser.add_argument("--dev-name", required=True, help="Developer / Brand Name")
    parser.add_argument("--keyauth-name", required=True, help="KeyAuth Application Name")
    parser.add_argument("--keyauth-ownerid", required=True, help="KeyAuth Owner ID")
    parser.add_argument("--keyauth-secret", required=True, help="KeyAuth Application Secret")
    parser.add_argument("--keyauth-version", default="1.0", help="KeyAuth Application Version")
    parser.add_argument("--icon-url", default="", help="Direct URL to logo image")
    parser.add_argument("--icon-file", default="", help="Local path to custom logo")
    parser.add_argument("--zip-template", default="", help="Path to zip archive containing custom project")

    args = parser.parse_args()
    proj_dir = Path(args.project_dir).resolve()

    log(f"Starting customization for Panel: '{args.panel_name}' | Dev: '{args.dev_name}'")

    # 1. If custom zip template is provided, extract it over the project dir
    if args.zip_template and os.path.exists(args.zip_template):
        log(f"Extracting user project zip template: {args.zip_template}")
        with zipfile.ZipFile(args.zip_template, "r") as z:
            z.extractall(proj_dir)
        log("Project template extracted successfully.")

    proj_dir.mkdir(parents=True, exist_ok=True)

    # 2. Handle Custom Logo / Icon
    temp_download = proj_dir / "_temp_download_icon"
    target_ico = proj_dir / "app.ico"

    icon_source = None
    if args.icon_url and args.icon_url.strip():
        if download_icon(args.icon_url.strip(), temp_download):
            icon_source = temp_download
    elif args.icon_file and os.path.exists(args.icon_file):
        icon_source = Path(args.icon_file)

    if icon_source:
        convert_image_to_ico(icon_source, target_ico)
        if temp_download.exists():
            temp_download.unlink()

    # 3. Build replacement dictionary
    replacements = {
        "__PLACEHOLDER_PANEL_NAME__": sanitize_input(args.panel_name),
        "__PLACEHOLDER_DEV_NAME__": sanitize_input(args.dev_name),
        "__PLACEHOLDER_KEYAUTH_NAME__": sanitize_input(args.keyauth_name),
        "__PLACEHOLDER_KEYAUTH_OWNERID__": sanitize_input(args.keyauth_ownerid),
        "__PLACEHOLDER_KEYAUTH_SECRET__": sanitize_input(args.keyauth_secret),
        "__PLACEHOLDER_KEYAUTH_VERSION__": sanitize_input(args.keyauth_version),
    }

    # 4. Patch source files (config.h, resource.rc, main.cpp, or any .h/.cpp files)
    extensions_to_check = [".h", ".hpp", ".c", ".cpp", ".rc", ".cs", ".vcxproj"]
    for root, _, files in os.walk(proj_dir):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in extensions_to_check:
                patch_file_content(p, replacements)

    log("Customization complete! Source code is ready for compilation.")


if __name__ == "__main__":
    main()
