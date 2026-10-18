# Auto Custom Panel Maker & Compiler 🚀

Automated Discord Bot + GitHub Actions system that customizes and builds **C and C++** Windows Executables (`.exe`) with customer's:
- **Panel Name**
- **Custom Logo / Icon**
- **Developer Name**
- **KeyAuth Credentials** (App Name, Owner ID, Secret, Version)

---

## 📁 Repository Structure

```
├── .github/
│   └── workflows/
│       └── build-panel.yml         # GitHub Actions Windows runner compiler workflow
├── scripts/
│   └── patch_and_build.py          # Script that injects logo, config, and KeyAuth into C/C++ source
│   └── patch_and_build.ps1         # PowerShell alternative patch script
├── project_template/               # Clean C/C++ Project Template ready for compilation
│   ├── config.h                    # Configuration placeholder file
│   ├── main.cpp                    # Sample C/C++ panel source code
│   ├── KeyAuth.hpp                 # KeyAuth C++ API client
│   ├── resource.h                  # Windows resource header
│   ├── resource.rc                 # Windows resource definition (icon, version info)
│   ├── app.ico                     # Default application icon
│   ├── Panel.vcxproj               # MSBuild C++ project file (Release /MT x64)
│   └── Panel.sln                   # Visual Studio Solution
├── bot/                            # Discord Bot (Python discord.py)
│   ├── bot.py                      # Main Discord Bot with Slash Commands & Modals
│   ├── config.py                   # Bot configuration loader
│   ├── github_client.py            # GitHub Actions REST API client
│   ├── requirements.txt            # Python dependencies
│   └── .env.example                # Bot environment variables template
├── bot_nodejs/                     # Alternative Discord Bot (Node.js discord.js)
│   ├── index.js                    # Node.js Discord bot
│   ├── package.json                # Node.js dependencies
│   └── .env.example                # Node.js environment variables
├── SETUP_GUIDE.md                  # Complete step-by-step setup walkthrough
└── README.md                       # Main documentation
```
