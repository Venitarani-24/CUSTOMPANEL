param (
    [Parameter(Mandatory=$true)][string]$ProjectDir,
    [Parameter(Mandatory=$true)][string]$PanelName,
    [Parameter(Mandatory=$true)][string]$DevName,
    [Parameter(Mandatory=$true)][string]$KeyAuthName,
    [Parameter(Mandatory=$true)][string]$KeyAuthOwnerId,
    [Parameter(Mandatory=$true)][string]$KeyAuthSecret,
    [string]$KeyAuthVersion = "1.0",
    [string]$KeyAuthUrl = "https://keyauth.win/api/1.2/",
    [string]$IconUrl = "",
    [string]$ZipTemplate = ""
)

Write-Host "[AutoPanelMaker] Starting PowerShell Customization..." -ForegroundColor Cyan

# Extract zip template if present
if ($ZipTemplate -and (Test-Path $ZipTemplate)) {
    Write-Host "[AutoPanelMaker] Extracting zip template: $ZipTemplate"
    Expand-Archive -Path $ZipTemplate -DestinationPath $ProjectDir -Force
}

$projPath = Resolve-Path $ProjectDir

# Download Icon if provided
$targetIco = Join-Path $projPath "app.ico"
$hasIco = $false
if ($IconUrl -and $IconUrl.Trim() -ne "") {
    try {
        $tempImg = Join-Path $projPath "temp_logo.png"
        Write-Host "[AutoPanelMaker] Downloading logo from $IconUrl..."
        Invoke-WebRequest -Uri $IconUrl -OutFile $tempImg -UseBasicParsing -UserAgent "Mozilla/5.0"
        
        if ($IconUrl -like "*.ico") {
            Copy-Item $tempImg $targetIco -Force
            $hasIco = $true
        }
        Remove-Item $tempImg -ErrorAction SilentlyContinue
    } catch {
        Write-Host "[AutoPanelMaker] Warning: Failed to download icon: $_" -ForegroundColor Yellow
    }
}

if (-not $hasIco -and (Test-Path $targetIco)) {
    $hasIco = $true
}

# Sanitize strings
function Sanitize([string]$val) {
    $v = $val.Replace("`r", "").Replace("`n", "").Trim()
    return $v.Replace('\', '\\').Replace('"', '\"')
}

$safePanel = Sanitize $PanelName
$safeDev = Sanitize $DevName
$safeAuthName = Sanitize $KeyAuthName
$safeAuthOwner = Sanitize $KeyAuthOwnerId
$safeAuthSecret = Sanitize $KeyAuthSecret
$safeAuthVersion = Sanitize $KeyAuthVersion
$safeAuthUrl = Sanitize $KeyAuthUrl

# Dual-tone title splitting
$words = $safePanel -split '\s+'
if ($words.Count -gt 1) {
    $safeTitle1 = ($words[0..($words.Count - 2)] -join " ") + " "
    $safeTitle2 = $words[-1]
} else {
    $safeTitle1 = $safePanel + " "
    $safeTitle2 = ""
}

Write-Host "[AutoPanelMaker] Panel: '$safePanel' (Title1: '$safeTitle1', Title2: '$safeTitle2') | Dev: '$safeDev'" -ForegroundColor Cyan

$replacements = @{
    "__PLACEHOLDER_PANEL_NAME__"    = $safePanel
    "__PLACEHOLDER_DEV_NAME__"      = $safeDev
    "__PLACEHOLDER_KEYAUTH_NAME__"  = $safeAuthName
    "__PLACEHOLDER_KEYAUTH_OWNERID__"= $safeAuthOwner
    "__PLACEHOLDER_KEYAUTH_SECRET__"= $safeAuthSecret
    "__PLACEHOLDER_KEYAUTH_VERSION__"= $safeAuthVersion
    "__PLACEHOLDER_KEYAUTH_URL__"   = $safeAuthUrl

    # Header Titles
    'const char* title1 = "RED X ";'     = "const char* title1 = `"$safeTitle1`";"
    'const char* title2 = "CHEATS";'     = "const char* title2 = `"$safeTitle2`";"
    'const char* title1 = OBF("RED X ");'= "const char* title1 = OBF(`"$safeTitle1`");"
    'const char* title2 = OBF("CHEATS");'= "const char* title2 = OBF(`"$safeTitle2`");"
    'OBF("RED X ")'                      = "OBF(`"$safeTitle1`")"
    'OBF("CHEATS")'                      = "OBF(`"$safeTitle2`")"

    # Developer Name
    '"DEVELOPED BY Red Corporation"'     = "`"DEVELOPED BY $safeDev`""
    '"Developer: (Red Corporation)"'     = "`"Developer: ($safeDev)`""
    'OBF("Dev</>Red Corporation")'       = "OBF(`"Dev</>$safeDev`")"
    '"Dev</>Red Corporation"'            = "`"Dev</>$safeDev`""
    '"Red Corporation"'                  = "`"$safeDev`""
    'OBF("Red Corporation")'             = "OBF(`"$safeDev`")"

    # Panel Name & Overlays
    'const char* watermarkLabel = "RED X CHEATS";' = "const char* watermarkLabel = `"$safePanel`";"
    'const char* titleText = "RED X CHEATS";'      = "const char* titleText = `"$safePanel`";"
    'OBF("RED X CHEATS")'                = "OBF(`"$safePanel`")"
    '"RED X CHEATS"'                     = "`"$safePanel`""
    '"REDX CHEATS"'                      = "`"$safePanel`""
    'OBF("REDX CHEATS")'                 = "OBF(`"$safePanel`")"
    '"WELCOME TO RED X CHEATS"'          = "`"WELCOME TO $safePanel`""
    '"Welcome To RED X CHEATS'           = "`"Welcome To $safePanel"
    '<ProjectName>RED X CHEATS</ProjectName>' = "<ProjectName>$safePanel</ProjectName>"

    # Discord RPC
    '"RED X CHEATS • Connecting"'        = "`"$safePanel • Connecting`""
    '"RED X CHEATS • Lobby • "'          = "`"$safePanel • Lobby • `""
    '"RED X CHEATS • "'                  = "`"$safePanel • `""

    # Window Creation
    'CreateWindowExW(NULL, wc.lpszClassName, L"PP",' = "CreateWindowExW(NULL, wc.lpszClassName, L`"$safePanel`","
    'wc.lpszMenuName = L"PP";'           = "wc.lpszMenuName = L`"$safePanel`";"
    'wc.lpszClassName = L"PP";'          = "wc.lpszClassName = L`"$safePanel`";"

    # KeyAuth patterns
    'g_name = "EXTERNAL"'                = "g_name = `"$safeAuthName`""
    'g_ownerid = "6862743278"'           = "g_ownerid = `"$safeAuthOwner`""
    'g_secret = "bda5ce36ddc610adc203a9f904103ae13eaf4b20f3aacff9b8cd505fe916d301"' = "g_secret = `"$safeAuthSecret`""
    'g_version = "1.0"'                  = "g_version = `"$safeAuthVersion`""
    'OBF("EXTERNAL")'                    = "OBF(`"$safeAuthName`")"
    'OBF("6862743278")'                  = "OBF(`"$safeAuthOwner`")"
    'OBF("bda5ce36ddc610adc203a9f904103ae13eaf4b20f3aacff9b8cd505fe916d301")' = "OBF(`"$safeAuthSecret`")"
    'OBF("https://www.keyauth-manager.online/api/1.2/")' = "OBF(`"$safeAuthUrl`")"
    'OBF("https://keyauth.win/api/1.2/")'= "OBF(`"$safeAuthUrl`")"
    "https://www.keyauth-manager.online/api/1.2/" = $safeAuthUrl
    "https://keyauth.win/api/1.2/"       = $safeAuthUrl
}

# Replace tokens across all source files
$files = Get-ChildItem -Path $projPath -Recurse -Include *.h, *.hpp, *.c, *.cpp, *.rc, *.vcxproj
foreach ($file in $files) {
    $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
    $modified = $false
    foreach ($k in $replacements.Keys) {
        if ($content.Contains($k)) {
            $content = $content.Replace($k, $replacements[$k])
            $modified = $true
        }
    }
    
    # Regex backups
    $content = $content -replace 'const\s+char\*\s+title1\s*=\s*"[^"]*";', "const char* title1 = `"$safeTitle1`";"
    $content = $content -replace 'const\s+char\*\s+title2\s*=\s*"[^"]*";', "const char* title2 = `"$safeTitle2`";"
    $content = $content -replace 'const\s+char\*\s+title1\s*=\s*OBF\("[^"]*"\);', "const char* title1 = OBF(`"$safeTitle1`");"
    $content = $content -replace 'const\s+char\*\s+title2\s*=\s*OBF\("[^"]*"\);', "const char* title2 = OBF(`"$safeTitle2`");"
    $content = $content -replace '"DEVELOPED\s+BY\s+[^"]*"', "`"DEVELOPED BY $safeDev`""
    $content = $content -replace '"Developer:\s*\([^)]*\)"', "`"Developer: ($safeDev)`""
    $content = $content -replace 'OBF\("Dev</>[^"]*"\)', "OBF(`"Dev</>$safeDev`")"
    $content = $content -replace '"Dev</>[^"]*"', "`"Dev</>$safeDev`""
    $content = $content -replace 'const\s+char\*\s+watermarkLabel\s*=\s*(?:OBF\()?"[^"]*"\)?;', "const char* watermarkLabel = `"$safePanel`";"
    $content = $content -replace 'const\s+char\*\s+titleText\s*=\s*(?:OBF\()?"[^"]*"\)?;', "const char* titleText = `"$safePanel`";"

    if ($modified -or ($content -ne [System.IO.File]::ReadAllText($file.FullName))) {
        [System.IO.File]::WriteAllText($file.FullName, $content, [System.Text.Encoding]::UTF8)
        Write-Host "[AutoPanelMaker] Injected tokens in: $($file.Name)" -ForegroundColor Green
    }

    # Handle resources.rc
    if ($file.Name -like "*resource*.rc") {
        $iconLine = if ($hasIco) { "1 ICON `"app.ico`"`r`n`r`n" } else { "" }
        $rcContent = @"
// Auto Custom Panel Maker - Generated Resource File
${iconLine}1 VERSIONINFO
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
            VALUE "CompanyName", "$safeDev"
            VALUE "FileDescription", "$safePanel"
            VALUE "FileVersion", "1.0.0.0"
            VALUE "InternalName", "$safePanel"
            VALUE "LegalCopyright", "Copyright (C) 2026 $safeDev"
            VALUE "OriginalFilename", "$safePanel.exe"
            VALUE "ProductName", "$safePanel"
            VALUE "ProductVersion", "1.0.0.0"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x0409, 1200
    END
END
"@
        [System.IO.File]::WriteAllText($file.FullName, $rcContent, [System.Text.Encoding]::UTF8)
        Write-Host "[AutoPanelMaker] Injected Windows Version Info & Branding into: $($file.Name)" -ForegroundColor Green
        $destIco = Join-Path $file.DirectoryName "app.ico"
        if ($hasIco -and (Test-Path $targetIco) -and ($targetIco -ne $destIco)) {
            Copy-Item $targetIco $destIco -Force
        }
    }
}

Write-Host "[AutoPanelMaker] Customization complete!" -ForegroundColor Green
