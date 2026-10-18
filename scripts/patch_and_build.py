#!/usr/bin/env python3
"""
Auto Custom Panel Maker - Patch & Customization Script
Used by GitHub Actions (and locally) to inject custom branding, logo, developer name,
and KeyAuth credentials directly into the DirectX 11 Panel C/C++ project before compiling.
"""

import os
import sys
import argparse
import urllib.request
import zipfile
import shutil
import re
import struct
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


def create_default_ico(dest_ico: Path) -> bool:
    """Generate a clean default 32x32 RGBA Windows .ico file if none is provided."""
    try:
        if HAS_PIL:
            img = Image.new("RGBA", (64, 64), color=(20, 24, 32, 255))
            icon_sizes = [(64, 64), (48, 48), (32, 32), (16, 16)]
            img.save(dest_ico, format="ICO", sizes=icon_sizes)
            log(f"Default Windows ICO generated with Pillow at: {dest_ico}")
            return True

        # Raw binary ICO fallback (32x32 32-bit BGRA with alpha)
        width, height = 32, 32
        bmp_header_size = 40
        img_data_size = width * height * 4
        mask_data_size = ((width + 31) // 32) * 4 * height
        bytes_in_res = bmp_header_size + img_data_size + mask_data_size

        header = struct.pack("<HHH", 0, 1, 1)  # Reserved, ICO type, 1 image
        entry = struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, bytes_in_res, 22)
        bih = struct.pack("<IIIHHIIIIII", bmp_header_size, width, height * 2, 1, 32, 0, img_data_size + mask_data_size, 0, 0, 0, 0)
        pixel = bytes([235, 120, 30, 255]) * (width * height)
        mask = bytes(mask_data_size)

        dest_ico.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_ico, "wb") as f:
            f.write(header + entry + bih + pixel + mask)
        log(f"Default raw ICO generated at: {dest_ico}")
        return True
    except Exception as e:
        log(f"Warning: could not create default icon: {e}")
        return False


def update_resources_rc(rc_path: Path, panel_name: str, dev_name: str, has_icon: bool):
    """Ensure resources.rc contains icon and Windows VERSIONINFO metadata (Details tab / Task Manager)."""
    icon_entry = '1 ICON "app.ico"\n\n' if has_icon else ''
    content = f"""// Auto Custom Panel Maker - Generated Resource File
{icon_entry}1 VERSIONINFO
FILEVERSION 1,0,0,0
PRODUCTVERSION 1,0,0,0
FILEFLAGSMASK 0x3fL
FILEFLAGS 0x0L
FILEOS 0x40004L
FILETYPE 0x1L
FILESUBTYPE 0x0L
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0"
        BEGIN
            VALUE "CompanyName", "{dev_name}"
            VALUE "FileDescription", "{panel_name}"
            VALUE "FileVersion", "1.0.0.0"
            VALUE "InternalName", "{panel_name}"
            VALUE "LegalCopyright", "Copyright (C) 2026 {dev_name}"
            VALUE "OriginalFilename", "{panel_name}.exe"
            VALUE "ProductName", "{panel_name}"
            VALUE "ProductVersion", "1.0.0.0"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x0409, 1200
    END
END
"""
    try:
        rc_path.write_text(content, encoding="utf-8")
        log(f"Injected Windows Version Info & Branding into {rc_path.name}")
    except Exception as e:
        log(f"Warning: could not write version info to {rc_path.name}: {e}")


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

    has_ico = False
    if icon_source:
        if convert_image_to_ico(icon_source, target_ico):
            has_ico = True
        if temp_download.exists():
            temp_download.unlink()

    # If no custom icon or conversion failed, generate default modern icon
    if not has_ico and not target_ico.exists():
        has_ico = create_default_ico(target_ico)
    elif target_ico.exists():
        has_ico = True

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

    # Compute dual-tone title split for ImGui animated wave headers
    # Example: "Phantom Loader" -> title1 = "Phantom ", title2 = "Loader"
    # Example: "Red X Cheats" -> title1 = "Red X ", title2 = "Cheats"
    # Example: "Apex" -> title1 = "Apex ", title2 = ""
    panel_words = safe_panel_name.split()
    if len(panel_words) > 1:
        safe_title1 = " ".join(panel_words[:-1]) + " "
        safe_title2 = panel_words[-1]
    else:
        safe_title1 = safe_panel_name + " "
        safe_title2 = ""

    # Safe folder name for AppData directory (without spaces or invalid path chars)
    safe_folder_name = re.sub(r'[^a-zA-Z0-9_-]', '', safe_panel_name) or "CustomPanel"

    log(f"Branding: Panel='{safe_panel_name}' (Title1='{safe_title1}', Title2='{safe_title2}'), Dev='{safe_dev_name}'")
    log(f"KeyAuth config: App='{safe_auth_name}', Owner='{safe_auth_owner}', URL='{safe_auth_url}', Host='{auth_host}'")

    replacements = {
        "__PLACEHOLDER_PANEL_NAME__": safe_panel_name,
        "__PLACEHOLDER_DEV_NAME__": safe_dev_name,
        "__PLACEHOLDER_KEYAUTH_NAME__": safe_auth_name,
        "__PLACEHOLDER_KEYAUTH_OWNERID__": safe_auth_owner,
        "__PLACEHOLDER_KEYAUTH_SECRET__": safe_auth_secret,
        "__PLACEHOLDER_KEYAUTH_VERSION__": safe_auth_version,
        "__PLACEHOLDER_KEYAUTH_URL__": safe_auth_url,

        # -------------------------------------------------------------
        # 1. Dual-Tone Header Titles (Login Screen & Main Menu)
        # -------------------------------------------------------------
        'const char* title1 = "RED X ";': f'const char* title1 = "{safe_title1}";',
        'const char* title2 = "CHEATS";': f'const char* title2 = "{safe_title2}";',
        'const char* title1 = OBF("RED X ");': f'const char* title1 = OBF("{safe_title1}");',
        'const char* title2 = OBF("CHEATS");': f'const char* title2 = OBF("{safe_title2}");',
        'OBF("RED X ")': f'OBF("{safe_title1}")',
        'OBF("CHEATS")': f'OBF("{safe_title2}")',

        # -------------------------------------------------------------
        # 2. Developer / Brand Name Replacements
        # -------------------------------------------------------------
        '"DEVELOPED BY Red Corporation"': f'"DEVELOPED BY {safe_dev_name}"',
        '"DEVELOPED BY RED CORPORATION"': f'"DEVELOPED BY {safe_dev_name}"',
        '"Developer: (Red Corporation)"': f'"Developer: ({safe_dev_name})"',
        'OBF("Dev</>Red Corporation")': f'OBF("Dev</>{safe_dev_name}")',
        '"Dev</>Red Corporation"': f'"Dev</>{safe_dev_name}"',
        '"Red Corporation"': f'"{safe_dev_name}"',
        'OBF("Red Corporation")': f'OBF("{safe_dev_name}")',

        # -------------------------------------------------------------
        # 3. Panel Name, Watermark, ESP Overlay, & Notifications
        # -------------------------------------------------------------
        'const char* watermarkLabel = "RED X CHEATS";': f'const char* watermarkLabel = "{safe_panel_name}";',
        'const char* titleText = "RED X CHEATS";': f'const char* titleText = "{safe_panel_name}";',
        'OBF("RED X CHEATS")': f'OBF("{safe_panel_name}")',
        '"RED X CHEATS"': f'"{safe_panel_name}"',
        '"REDX CHEATS"': f'"{safe_panel_name}"',
        'OBF("REDX CHEATS")': f'OBF("{safe_panel_name}")',
        '"WELCOME TO RED X CHEATS"': f'"WELCOME TO {safe_panel_name}"',
        '"Welcome To RED X CHEATS': f'"Welcome To {safe_panel_name}',
        '<ProjectName>RED X CHEATS</ProjectName>': f'<ProjectName>{safe_panel_name}</ProjectName>',

        # -------------------------------------------------------------
        # 4. Discord Rich Presence (RPC) & Status
        # -------------------------------------------------------------
        '"RED X CHEATS • Connecting"': f'"{safe_panel_name} • Connecting"',
        '"RED X CHEATS • Lobby • "': f'"{safe_panel_name} • Lobby • "',
        '"RED X CHEATS • "': f'"{safe_panel_name} • "',
        'rpc.smallImageText = "Developer: (Red Corporation)";': f'rpc.smallImageText = "Developer: ({safe_dev_name})";',

        # -------------------------------------------------------------
        # 5. Win32 Window Title & Class Name
        # -------------------------------------------------------------
        'CreateWindowExW(NULL, wc.lpszClassName, L"PP",': f'CreateWindowExW(NULL, wc.lpszClassName, L"{safe_panel_name}",',
        'wc.lpszMenuName = L"PP";': f'wc.lpszMenuName = L"{safe_panel_name}";',
        'wc.lpszClassName = L"PP";': f'wc.lpszClassName = L"{safe_panel_name}";',

        # -------------------------------------------------------------
        # 6. AppData Folder Name
        # -------------------------------------------------------------
        '\\ArmoraaExternal': f'\\{safe_folder_name}',

        # -------------------------------------------------------------
        # 7. KeyAuth Credentials & Endpoints
        # -------------------------------------------------------------
        'g_name = "EXTERNAL"': f'g_name = "{safe_auth_name}"',
        'g_ownerid = "6862743278"': f'g_ownerid = "{safe_auth_owner}"',
        'g_secret = "bda5ce36ddc610adc203a9f904103ae13eaf4b20f3aacff9b8cd505fe916d301"': f'g_secret = "{safe_auth_secret}"',
        'g_version = "1.0"': f'g_version = "{safe_auth_version}"',
        'g_host = L"www.keyauth-manager.online"': f'g_host = L"{auth_host}"',
        'g_path = L"/api/1.2/"': f'g_path = L"{auth_path}"',

        'OBF("EXTERNAL")': f'OBF("{safe_auth_name}")',
        'OBF("6862743278")': f'OBF("{safe_auth_owner}")',
        'OBF("bda5ce36ddc610adc203a9f904103ae13eaf4b20f3aacff9b8cd505fe916d301")': f'OBF("{safe_auth_secret}")',
        'OBF("https://www.keyauth-manager.online/api/1.2/")': f'OBF("{safe_auth_url}")',
        'OBF("https://keyauth.win/api/1.2/")': f'OBF("{safe_auth_url}")',

        "https://www.keyauth-manager.online/api/1.2/": safe_auth_url,
        "https://keyauth.win/api/1.2/": safe_auth_url,
        '"www.keyauth-manager.online"': f'"{auth_host}"',
        '"keyauth.win"': f'"{auth_host}"',

        # -------------------------------------------------------------
        # 8. Build Fixes for CI Runners
        # -------------------------------------------------------------
        '#include "atlsecurity.h"': '// #include "atlsecurity.h"',
        '#include <atlsecurity.h>': '// #include <atlsecurity.h>',
        '#include <atlbase.h>': '// #include <atlbase.h>',
        '#include <atlimage.h>': '// #include <atlimage.h>',
    }

    regex_replacements = [
        # Dual-tone title headers in main.cpp
        (re.compile(r'const\s+char\*\s+title1\s*=\s*"[^"]*";'), f'const char* title1 = "{safe_title1}";'),
        (re.compile(r'const\s+char\*\s+title2\s*=\s*"[^"]*";'), f'const char* title2 = "{safe_title2}";'),
        (re.compile(r'const\s+char\*\s+title1\s*=\s*OBF\("[^"]*"\);'), f'const char* title1 = OBF("{safe_title1}");'),
        (re.compile(r'const\s+char\*\s+title2\s*=\s*OBF\("[^"]*"\);'), f'const char* title2 = OBF("{safe_title2}");'),

        # Developer Name replacements
        (re.compile(r'"DEVELOPED\s+BY\s+[^"]*"', re.IGNORECASE), f'"DEVELOPED BY {safe_dev_name}"'),
        (re.compile(r'"Developer:\s*\([^)]*\)"', re.IGNORECASE), f'"Developer: ({safe_dev_name})"'),
        (re.compile(r'OBF\("Dev</>[^"]*"\)'), f'OBF("Dev</>{safe_dev_name}")'),
        (re.compile(r'"Dev</>[^"]*"'), f'"Dev</>{safe_dev_name}"'),
        (re.compile(r'OBF\("Red Corporation"\)'), f'OBF("{safe_dev_name}")'),
        (re.compile(r'"Red Corporation"'), f'"{safe_dev_name}"'),

        # Watermark & Visual.cpp Title & Notifications
        (re.compile(r'const\s+char\*\s+watermarkLabel\s*=\s*(?:OBF\()?"[^"]*"\)?;'), f'const char* watermarkLabel = "{safe_panel_name}";'),
        (re.compile(r'const\s+char\*\s+titleText\s*=\s*(?:OBF\()?"[^"]*"\)?;'), f'const char* titleText = "{safe_panel_name}";'),
        (re.compile(r'"WELCOME\s+TO\s+[^"]*"', re.IGNORECASE), f'"WELCOME TO {safe_panel_name}"'),
        (re.compile(r'OBF\("Welcome\s+To\s+[^"(]+\('), f'OBF("Welcome To {safe_panel_name} ('),
        (re.compile(r'"Welcome\s+To\s+[^"(]+\('), f'"Welcome To {safe_panel_name} ('),
        (re.compile(r'OBF\("RED\s*X\s*CHEATS"\)', re.IGNORECASE), f'OBF("{safe_panel_name}")'),
        (re.compile(r'"RED\s*X\s*CHEATS"', re.IGNORECASE), f'"{safe_panel_name}"'),
        (re.compile(r'"RED\s*X\s*CHEATS\s*•'), f'"{safe_panel_name} •'),

        # Window creation
        (re.compile(r'CreateWindowExW\(NULL,\s*wc\.lpszClassName,\s*L"[^"]*",'), f'CreateWindowExW(NULL, wc.lpszClassName, L"{safe_panel_name}",'),

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

        # ProjectName in .vcxproj & AssemblyName in .csproj
        (re.compile(r'<ProjectName>[^<]*</ProjectName>'), f'<ProjectName>{safe_panel_name}</ProjectName>'),
        (re.compile(r'<AssemblyName>[^<]*</AssemblyName>'), f'<AssemblyName>{safe_panel_name}</AssemblyName>'),

        # C# AssemblyInfo.cs attributes
        (re.compile(r'\[assembly:\s*AssemblyTitle\("[^"]*"\)\]'), f'[assembly: AssemblyTitle("{safe_panel_name}")]'),
        (re.compile(r'\[assembly:\s*AssemblyProduct\("[^"]*"\)\]'), f'[assembly: AssemblyProduct("{safe_panel_name}")]'),
        (re.compile(r'\[assembly:\s*AssemblyCompany\("[^"]*"\)\]'), f'[assembly: AssemblyCompany("{safe_dev_name}")]'),
        (re.compile(r'\[assembly:\s*AssemblyCopyright\("[^"]*"\)\]'), f'[assembly: AssemblyCopyright("Copyright © {safe_dev_name} 2026")]'),

        # C# WinForms Form1.Designer.cs
        (re.compile(r'this\.label2\.Text\s*=\s*"[^"]*";'), f'this.label2.Text = "{safe_panel_name}";'),
        (re.compile(r'this\.Text\s*=\s*"[^"]*";'), f'this.Text = "{safe_panel_name}";'),
        (re.compile(r'"HIDDEN\s+ARC\s+PREMIUM"', re.IGNORECASE), f'"{safe_panel_name}"'),

        # C# Loader Auto-Close & Crash Prevention Fixes
        (re.compile(r'Application\.Exit\(\);'), '// Application.Exit(); // Auto-close disabled'),
        (re.compile(r'await\s+Task\.Delay\(2000\);\s*Application\.Exit\(\);'), 'guna2GradientButton1.Text = "ACTIVE & INJECTED"; guna2GradientButton1.Enabled = true;'),
        (re.compile(r'System\.Text\.Encoding\.ASCII\.GetBytes\(tempDllPath\)'), 'System.Text.Encoding.ASCII.GetBytes(tempDllPath + "\\0")'),
        (re.compile(r'VirtualAllocEx\(hProcess,\s*IntPtr\.Zero,\s*\(IntPtr\)tempDllPath\.Length,'), 'VirtualAllocEx(hProcess, IntPtr.Zero, (IntPtr)(tempDllPath.Length + 1),'),
        (re.compile(r'WriteProcessMemory\(hProcess,\s*allocMemAddress,\s*System\.Text\.Encoding\.ASCII\.GetBytes\(tempDllPath\s*\+\s*"\\0"\),\s*\(uint\)tempDllPath\.Length,'),
         'WriteProcessMemory(hProcess, allocMemAddress, System.Text.Encoding.ASCII.GetBytes(tempDllPath + "\\0"), (uint)(tempDllPath.Length + 1),'),

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
            if p.suffix.lower() == ".ico" and has_ico and p != target_ico:
                try:
                    shutil.copy(target_ico, p)
                    log(f"Replaced project icon: {p.name}")
                except Exception:
                    pass

            # Inject full icon and Windows Version Info (Company/Product/Description) into resources.rc
            if p.name.lower() in ["resources.rc", "resource.rc"]:
                update_resources_rc(p, safe_panel_name, safe_dev_name, has_ico)
                if has_ico and target_ico.exists():
                    try:
                        shutil.copy(target_ico, p.parent / "app.ico")
                    except Exception as e:
                        log(f"Warning: could not copy icon to {p.parent}: {e}")

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
