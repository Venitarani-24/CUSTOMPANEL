#!/usr/bin/env python3
"""
Auto Custom Panel Maker - Patch & Customization Script
Used by GitHub Actions (and locally) to inject custom branding, logo, and KeyAuth credentials
directly into the DirectX 11 Panel C/C++ project before compiling.
"""

import os
import sys
import argparse
import urllib.request
import zipfile
import shutil
import re
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
    """Escape quotes/backslashes and strip newlines to prevent C2001 newline in constant."""
    val = value.replace("\r", "").replace("\n", "").strip()
    return val.replace("\\", "\\\\").replace('"', '\\"')


def patch_file_content(file_path: Path, replacements: dict, regex_replacements: list):
    """Replace placeholder tokens and patterns in a target source file."""
    if not file_path.exists():
        log(f"Warning: file {file_path} does not exist, skipping patch.")
        return

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    modified = False

    # 1. Exact token replacements
    for token, val in replacements.items():
        if token in content:
            content = content.replace(token, val)
            modified = True
            log(f"Injected exact match: '{token}' -> '{val}' in {file_path.name}")

    # 2. Regex replacements
    for pattern, repl in regex_replacements:
        new_content, count = pattern.subn(repl, content)
        if count > 0:
            content = new_content
            modified = True
            log(f"Injected regex match ({count}x) in {file_path.name}")

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
    parser.add_argument("--keyauth-url", default="https://keyauth.win/api/1.2/", help="KeyAuth API URL")
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

    has_custom_ico = False
    if icon_source:
        if convert_image_to_ico(icon_source, target_ico):
            has_custom_ico = True
        if temp_download.exists():
            temp_download.unlink()

    # 3. Build replacement dictionaries
    safe_panel_name = sanitize_input(args.panel_name)
    safe_dev_name = sanitize_input(args.dev_name)
    safe_auth_name = sanitize_input(args.keyauth_name)
    safe_auth_owner = sanitize_input(args.keyauth_ownerid)
    safe_auth_secret = sanitize_input(args.keyauth_secret)
    safe_auth_version = sanitize_input(args.keyauth_version)
    safe_auth_url = sanitize_input(args.keyauth_url.strip() or "https://keyauth.win/api/1.2/")

    # Parse host & path from URL
    from urllib.parse import urlparse
    parsed = urlparse(safe_auth_url)
    auth_host = parsed.netloc or "keyauth.win"
    auth_path = parsed.path or "/api/1.2/"
    if not auth_path.endswith("/"):
        auth_path += "/"

    log(f"KeyAuth config: App='{safe_auth_name}', Owner='{safe_auth_owner}', URL='{safe_auth_url}', Host='{auth_host}'")

    replacements = {
        "__PLACEHOLDER_PANEL_NAME__": safe_panel_name,
        "__PLACEHOLDER_DEV_NAME__": safe_dev_name,
        "__PLACEHOLDER_KEYAUTH_NAME__": safe_auth_name,
        "__PLACEHOLDER_KEYAUTH_OWNERID__": safe_auth_owner,
        "__PLACEHOLDER_KEYAUTH_SECRET__": safe_auth_secret,
        "__PLACEHOLDER_KEYAUTH_VERSION__": safe_auth_version,
        "__PLACEHOLDER_KEYAUTH_URL__": safe_auth_url,

        # KeyAuth patterns in Red X Cheats / ImGui panels
        'g_name = "EXTERNAL"': f'g_name = "{safe_auth_name}"',
        'g_ownerid = "6862743278"': f'g_ownerid = "{safe_auth_owner}"',
        'g_secret = "bda5ce36ddc610adc203a9f904103ae13eaf4b20f3aacff9b8cd505fe916d301"': f'g_secret = "{safe_auth_secret}"',
        'g_version = "1.0"': f'g_version = "{safe_auth_version}"',
        'g_host = L"www.keyauth-manager.online"': f'g_host = L"{auth_host}"',
        'g_path = L"/api/1.2/"': f'g_path = L"{auth_path}"',

        'OBF("EXTERNAL")': f'OBF("{safe_auth_name}")',
        'OBF("6862743278")': f'OBF("{safe_auth_owner}")',
        'OBF("bda5ce36ddc610adc203a9f904103ae13eaf4b20f3aacff9b8cd505fe916d301")': f'OBF("{safe_auth_secret}")',
        'OBF("RED X CHEATS")': f'OBF("{safe_panel_name}")',
        'OBF("https://www.keyauth-manager.online/api/1.2/")': f'OBF("{safe_auth_url}")',
        'OBF("https://keyauth.win/api/1.2/")': f'OBF("{safe_auth_url}")',

        # Panel Name & Branding
        '"RED X CHEATS"': f'"{safe_panel_name}"',
        '"WELCOME TO RED X CHEATS"': f'"WELCOME TO {safe_panel_name}"',
        '"Welcome To RED X CHEATS': f'"Welcome To {safe_panel_name}',
        '<ProjectName>RED X CHEATS</ProjectName>': f'<ProjectName>{safe_panel_name}</ProjectName>',

        # URL and Host string replacements
        "https://www.keyauth-manager.online/api/1.2/": safe_auth_url,
        "https://keyauth.win/api/1.2/": safe_auth_url,
        '"www.keyauth-manager.online"': f'"{auth_host}"',
        '"keyauth.win"': f'"{auth_host}"',

        # Remove missing ATL header dependencies on standard Windows CI runners
        '#include "atlsecurity.h"': '// #include "atlsecurity.h"',
        '#include <atlsecurity.h>': '// #include <atlsecurity.h>',
        '#include <atlbase.h>': '// #include <atlbase.h>',
        '#include <atlimage.h>': '// #include <atlimage.h>',
    }

    regex_replacements = [
        # CustomKeyAuth.hpp
        (re.compile(r'inline\s+std::string\s+g_name\s*=\s*"[^"]*";'), f'inline std::string g_name = "{safe_auth_name}";'),
        (re.compile(r'inline\s+std::string\s+g_ownerid\s*=\s*"[^"]*";'), f'inline std::string g_ownerid = "{safe_auth_owner}";'),
        (re.compile(r'inline\s+std::string\s+g_secret\s*=\s*"[^"]*";'), f'inline std::string g_secret = "{safe_auth_secret}";'),
        (re.compile(r'inline\s+std::string\s+g_version\s*=\s*"[^"]*";'), f'inline std::string g_version = "{safe_auth_version}";'),
        (re.compile(r'inline\s+std::wstring\s+g_host\s*=\s*L"[^"]*";'), f'inline std::wstring g_host = L"{auth_host}";'),
        (re.compile(r'inline\s+std::wstring\s+g_path\s*=\s*L"[^"]*";'), f'inline std::wstring g_path = L"{auth_path}";'),

        # main.cpp KeyAuth initialization
        (re.compile(r'std::string\s+name\s*=\s*std::string\(OBF\("[^"]*"\)\);'), f'std::string name = std::string(OBF("{safe_auth_name}"));'),
        (re.compile(r'std::string\s+ownerid\s*=\s*std::string\(OBF\("[^"]*"\)\);'), f'std::string ownerid = std::string(OBF("{safe_auth_owner}"));'),
        (re.compile(r'std::string\s+secret\s*=\s*std::string\(OBF\("[^"]*"\)\);'), f'std::string secret = std::string(OBF("{safe_auth_secret}"));'),
        (re.compile(r'std::string\s+version\s*=\s*std::string\(OBF\("[^"]*"\)\);'), f'std::string version = std::string(OBF("{safe_auth_version}"));'),
        (re.compile(r'std::string\s+url\s*=\s*std::string\(OBF\("[^"]*"\)\);'), f'std::string url = std::string(OBF("{safe_auth_url}"));'),

        # ProjectName in .vcxproj
        (re.compile(r'<ProjectName>[^<]*</ProjectName>'), f'<ProjectName>{safe_panel_name}</ProjectName>'),

        # ATL HWID in AntiLogin.h -> Win32 GetCurrentHwProfileA
        (re.compile(r'ATL::CAccessToken\s+accessToken;[\s\S]*?return\s+std::string\(CT2A\(currentUserSid\.Sid\(\)\)\);[\s\S]*?else[\s\S]*?\{[\s\S]*?return\s+"DEFAULT_HWID";[\s\S]*?\}'),
         'HW_PROFILE_INFOA hwInfo; if (GetCurrentHwProfileA(&hwInfo)) return std::string(hwInfo.szHwProfileGuid); else return "DEFAULT_HWID";'),
    ]

    # 4. Patch source files (config.h, resource.rc, main.cpp, or any .h/.cpp files)
    extensions_to_check = [".h", ".hpp", ".c", ".cpp", ".rc", ".cs", ".vcxproj"]
    for root, _, files in os.walk(proj_dir):
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in extensions_to_check:
                patch_file_content(p, replacements, regex_replacements)

            # If an existing icon file is found, replace it with the new custom icon
            if p.suffix.lower() == ".ico" and has_custom_ico and p != target_ico:
                try:
                    shutil.copy(target_ico, p)
                    log(f"Replaced project icon: {p.name}")
                except Exception:
                    pass

            # If resources.rc is found and we have a custom icon, embed it
            if p.name.lower() in ["resources.rc", "resource.rc"] and has_custom_ico:
                try:
                    rc_content = p.read_text(encoding="utf-8", errors="ignore")
                    if "app.ico" not in rc_content:
                        rc_content += '\n1 ICON "app.ico"\n'
                        p.write_text(rc_content, encoding="utf-8")
                        # Copy app.ico to the same directory as the .rc file
                    shutil.copy(target_ico, p.parent / "app.ico")
                except Exception as e:
                    log(f"Warning: could not inject icon into {p.name}: {e}")

    # 5. Ensure DirectX Lib/x64 directory and d3dx11.lib exist
    deps_dx = Path(__file__).resolve().parent.parent / "deps" / "DirectX" / "Lib" / "x64"
    if deps_dx.exists():
        target_dx_dirs = [
            proj_dir / "examples" / "example_win32_directx11" / "ext" / "DirectX" / "Lib" / "x64",
            proj_dir / "ext" / "DirectX" / "Lib" / "x64",
        ]
        for dx_target_dir in target_dx_dirs:
            dx_target_dir.mkdir(parents=True, exist_ok=True)
            for lib_file in deps_dx.glob("*.lib"):
                dest = dx_target_dir / lib_file.name
                if not dest.exists():
                    shutil.copy(lib_file, dest)
            log(f"Verified DirectX x64 libraries at: {dx_target_dir}")

    log("Customization complete! Source code is ready for compilation.")


if __name__ == "__main__":
    main()
