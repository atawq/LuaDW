import os
import shutil
import requests
import subprocess
import winreg
import zipfile
import io
import webview
import threading
import time
import ctypes
import sys
import json
import webbrowser
import re
from pathlib import Path

# ==============================
# bypass desteklenen oyunlar
# ==============================
BYPASS_GAMES_DB = {
    "12210": "Grand Theft Auto IV: The Complete Edition",
    "33230": "Assassin's Creed II",
    "39140": "FINAL FANTASY VII (2013)",
    "47790": "Medal of Honor(TM) Single Player",
    "48190": "Assassin's Creed Brotherhood",
    "50300": "Spec Ops: The Line",
    "110800": "L.A. Noire",
    "220240": "Far Cry® 3",
    "221910": "The Stanley Parable",
    "234080": "Castlevania: Lords of Shadow - Ultimate Edition",
    "239250": "Castlevania: Lords of Shadow 2",
    "242050": "Assassin's Creed IV Black Flag",
    "243470": "Watch_Dogs",
    "256290": "Child of Light",
    "289650": "Assassin's Creed Unity",
    "298110": "Far Cry 4",
    "311560": "Assassin's Creed Rogue",
    "315210": "Suicide Squad: Kill the Justice League",
    "368500": "Assassin's Creed Syndicate",
    "371660": "Far Cry Primal",
    "447040": "Watch_Dogs 2",
    "466130": "White Day: A Labyrinth Named School",
    "552520": "Far Cry 5",
    "582160": "Assassin's Creed Origins",
    "646910": "The Crew 2",
    "678950": "DRAGON BALL FighterZ",
    "916440": "Anno 1800",
    "939960": "Far Cry New Dawn",
    "1114150": "CarX Street",
    "1174180": "Red Dead Redemption 2",
    "1196590": "Resident Evil Village",
    "1222680": "Need for Speed™ Heat",
    "1222730": "STAR WARS™: Squadrons",
    "1237320": "Sonic Frontiers",
    "1238000": "Mass Effect™: Andromeda",
    "1313860": "EA SPORTS™ FIFA 21",
    "1328660": "Need for Speed™ Hot Pursuit Remastered",
    "1328670": "Mass Effect™ Legendary Edition",
    "1413480": "Shin Megami Tensei III Nocturne HD Remaster",
    "1506830": "FIFA 22",
    "1677280": "Company of Heroes 3",
    "1693980": "Dead Space",
    "2050650": "Resident Evil 4",
    "2055290": "Sonic Colors: Ultimate",
    "2172010": "Until Dawn™",
    "2208920": "Assassin's Creed Valhalla",
    "2215260": "Scott Pilgrim vs The World",
    "2239550": "Watch Dogs: Legion",
    "2369390": "Far Cry 6",
    "2668510": "Red Dead Redemption",
    "2807960": "Battlefield™ 6",
    "3017860": "DOOM: The Dark Ages",
    "3035570": "Assassin's Creed Mirage",
    "3764200": "Resident Evil Requiem",
    "3800340": "ScootX"
}

OPENSTEAMTOOL_DLL_URL = "https://github.com/atawq/LuaDW/raw/refs/heads/main/dll/OpenSteamTool.dll"
DWMAPI_URL = "https://github.com/atawq/LuaDW/raw/refs/heads/main/dll/dwmapi.dll"
XINPUT_DLL_URL = "https://github.com/atawq/LuaDW/raw/refs/heads/main/dll/xinput1_4.dll"
GITHUB_REPO_URL = "https://github.com/atawq/LuaDW"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

class LuaDWBridge:
    def __init__(self):
        self._window = None
        self.session = requests.Session()

    def set_window(self, window):
        self._window = window
        window.events.loaded += self._on_dom_ready

    def _on_dom_ready(self):
        # DOM hazır olduğunda çalışır — evaluate_js güvenli
        self.load_bypass_games()
        threading.Thread(target=self._run_auto_repair, daemon=True).start()

    def load_bypass_games(self):
        if self._window:
            js_code = f"populateBypassMenu({json.dumps(BYPASS_GAMES_DB)});"
            self._window.evaluate_js(js_code)

    def _ui_log(self, loading, message, status_type="info"):
        if self._window:
            msg_json = json.dumps(message.upper())
            self._window.evaluate_js(f"updateUI({str(loading).lower()}, {msg_json}, '{status_type}')")

    def open_github(self):
        webbrowser.open(GITHUB_REPO_URL)

    def get_steam_path(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            value, _ = winreg.QueryValueEx(key, "SteamPath")
            return Path(value)
        except Exception:
            return None

    def get_all_steam_libraries(self):
        main_path = self.get_steam_path()
        if not main_path:
            return []
        
        libraries = [main_path / "steamapps"]
        vdf_path = main_path / "steamapps" / "libraryfolders.vdf"
        
        if vdf_path.exists():
            try:
                with open(vdf_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    matches = re.findall(r'"path"\s+"([^"]+)"', content, re.IGNORECASE)
                    for match in matches:
                        clean_path = match.replace("\\\\", "\\")
                        lib_path = Path(clean_path) / "steamapps"
                        if lib_path.exists() and lib_path not in libraries:
                            libraries.append(lib_path)
            except Exception:
                pass
        return libraries

    def _run_auto_repair(self):
        # Spinner'ın her durumda kapanmasını garantile
        self._ui_log(True, "ALTYAPI DOSYALARI STEAM DİZİNİNE İNDİRİLİYOR...", "info")
        path = self.get_steam_path()
        if not path:
            self._ui_log(False, "STEAM YOLU BULUNAMADI!", "error")
            return

        try:
            subprocess.run(["taskkill", "/f", "/im", "steam.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            dll_files = [
                (OPENSTEAMTOOL_DLL_URL, "OpenSteamTool.dll"),
                (DWMAPI_URL, "dwmapi.dll"),
                (XINPUT_DLL_URL, "xinput1_4.dll")
            ]

            for url, name in dll_files:
                r = self.session.get(url, timeout=10)
                if r.status_code == 200:
                    with open(path / name, "wb") as f:
                        f.write(r.content)
                else:
                    raise Exception(f"{name} İNDİRİLEMEDİ!")

            self._ui_log(False, "SİSTEM HAZIR ALTYAPILAR İNDİRİLDİ", "success")
        except Exception as e:
            self._ui_log(False, f"DLL HATASI: {str(e)}", "error")

    def restart_steam(self):
        def worker():
            self._ui_log(True, "STEAM YENİDEN BAŞLATILIYOR...", "info")
            subprocess.run(["taskkill", "/f", "/im", "steam.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            path = self.get_steam_path()
            if path:
                shutil.rmtree(path / "appcache", ignore_errors=True)
                steam_exe = path / "steam.exe"
                try:
                    os.startfile(str(steam_exe))
                    self._ui_log(False, "STEAM YENİDEN BAŞLATILDI.", "success")
                except Exception as e:
                    self._ui_log(False, f"STEAM AÇILAMADI: {str(e)}", "warning")
        threading.Thread(target=worker, daemon=True).start()

    def fetch_and_fix_lua(self, app_id):
        def worker(target_id):
            clean_id = str(target_id).strip()
            if not clean_id.isdigit():
                return self._ui_log(False, "LÜTFEN SADECE GEÇERLİ BİR APPID GİRİN!", "error")

            self._ui_log(True, f"EKLENİYOR (APPID: {clean_id})...", "info")
            path = self.get_steam_path()
            if not path:
                return self._ui_log(False, "STEAM YOLU BULUNAMADI!", "error")

            target_dir = path / "config" / "stplug-in"
            target_dir.mkdir(parents=True, exist_ok=True)

            try:
                url = f"https://codeload.github.com/SSMGAlt/ManifestHub2/zip/refs/heads/{clean_id}"
                r = self.session.get(url, timeout=15)
                if r.status_code != 200:
                    return self._ui_log(False, f"MANIFEST BULUNAMADI ({clean_id})!", "error")

                z = zipfile.ZipFile(io.BytesIO(r.content))
                count = 0
                for fpath in z.namelist():
                    if fpath.lower().endswith(".lua"):
                        fname = os.path.basename(fpath)
                        if fname:
                            with z.open(fpath) as src, open(target_dir / fname, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                            count += 1
                
                self._ui_log(False, f"BAŞARILI: {count} LUA DOSYASI EKLENDİ", "success")
            except Exception as e:
                self._ui_log(False, f"LUA EKLENİRKEN HATA: {str(e)}", "error")

        threading.Thread(target=worker, args=(app_id,), daemon=True).start()

    def apply_game_bypass(self, app_id):
        def worker(target_id):
            self._ui_log(True, f"KLASÖR ARANIYOR (APPID: {target_id})...", "info")
            
            game_path = None
            for lib in self.get_all_steam_libraries():
                manifest_file = lib / f"appmanifest_{target_id}.acf"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            match = re.search(r'"InstallDir"\s+"([^"]+)"', f.read())
                            if match:
                                folder = match.group(1)
                                possible_path = lib / "common" / folder
                                if possible_path.exists():
                                    game_path = possible_path
                                    break
                    except Exception:
                        pass

            if not game_path:
                self._ui_log(True, "KLASÖR BULUNAMADI! LÜTFEN OYUN KLASÖRÜNÜ SEÇİN.", "warning")
                result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
                if result and len(result) > 0:
                    game_path = Path(result[0])
                else:
                    return self._ui_log(False, "İŞLEM İPTAL EDİLDİ (KLASÖR SEÇİLMEDİ).", "error")

            self._ui_log(True, f"BYPASS İNDİRİLİYOR... ({target_id})", "info")
            try:
                url = f"https://files.luatools.work/GameBypasses/{target_id}.zip"
                r = self.session.get(url, headers={'User-Agent': 'LuaDWClient'}, timeout=30)
                
                if r.status_code != 200:
                    return self._ui_log(False, f"SUNUCUDA BYPASS BULUNAMADI ({target_id})!", "error")
                
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    z.extractall(game_path)
                
                self._ui_log(False, f"BYPASS UYGULANDI! ({game_path.name})", "success")

            except Exception as e:
                self._ui_log(False, f"HATA: {str(e)}", "error")

        threading.Thread(target=worker, args=(str(app_id),), daemon=True).start()

# ==============================
# ui
# ==============================
html_content = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap');
        
        :root { 
            --bg-color: #050508;
            --surface: rgba(18, 20, 28, 0.75);
            --border: rgba(60, 65, 85, 0.4);
            --accent: #5e35b1;
            --accent-glow: #9c27b0;
            --bypass-accent: #00acc1;
            --bypass-glow: #1e88e5;
            --success: #00e676;
            --text-main: #ffffff;
            --text-muted: #8b949e;
        }
        
        body { 
            background: radial-gradient(circle at 50% 0%, #1a1025 0%, var(--bg-color) 70%);
            color: var(--text-main); 
            font-family: 'Montserrat', sans-serif;
            margin: 0; padding: 25px; height: 100vh; box-sizing: border-box;
            overflow: hidden; user-select: none;
        }

        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .logo-text { 
            font-size: 24px; font-weight: 900; margin: 0;
            background: linear-gradient(45deg, #fff, #b39ddb);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .status-badge { 
            background: rgba(0, 230, 118, 0.15); border: 1px solid var(--success);
            padding: 6px 14px; border-radius: 20px; font-size: 10px; font-weight: 800;
            color: var(--success); cursor: pointer;
        }

        .nav-container { display: flex; gap: 10px; margin-bottom: 20px; background: rgba(0,0,0,0.3); padding: 5px; border-radius: 12px; }
        .nav-btn { 
            flex: 1; text-align: center; padding: 12px; border-radius: 8px;
            font-size: 12px; font-weight: 800; cursor: pointer; color: var(--text-muted); transition: 0.3s;
        }
        .nav-btn:hover { color: #fff; background: rgba(255,255,255,0.05); }
        .nav-btn.active { background: linear-gradient(135deg, var(--accent), var(--accent-glow)); color: #fff; }

        .glass-panel { 
            background: var(--surface); backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 16px;
            padding: 20px; margin-bottom: 15px; position: relative;
        }

        input, select {
            width: 100%; padding: 14px 16px; background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border); border-radius: 10px;
            color: #fff; font-size: 13px; font-family: inherit; font-weight: 600;
            box-sizing: border-box; outline: none; transition: 0.3s;
            margin-bottom: 15px; appearance: none;
        }
        input:focus, select:focus { border-color: var(--accent-glow); background: rgba(0, 0, 0, 0.6); }
        select option { background: var(--bg-color); color: #fff; font-weight: 600; }

        button {
            width: 100%; padding: 14px; border-radius: 10px; border: none;
            font-size: 13px; font-weight: 800; text-transform: uppercase; cursor: pointer; transition: 0.2s;
        }
        .btn-glow { 
            background: linear-gradient(45deg, var(--accent), var(--accent-glow)); color: #fff; 
            box-shadow: 0 5px 20px rgba(156, 39, 176, 0.4);
        }
        .btn-glow:hover { filter: brightness(1.1); }

        .btn-bypass {
            background: linear-gradient(45deg, var(--bypass-glow), var(--bypass-accent)); color: #fff; 
            box-shadow: 0 5px 20px rgba(0, 172, 193, 0.4);
        }
        .btn-bypass:hover { filter: brightness(1.1); }
        
        .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-muted); }
        .btn-outline:hover { background: rgba(255,255,255,0.05); color: #fff; }

        .footer { 
            position: absolute; bottom: 0; left: 0; right: 0; padding: 15px 25px;
            background: rgba(5, 5, 8, 0.9); border-top: 1px solid var(--border);
            display: flex; align-items: center; justify-content: space-between;
        }
        .log-text { font-size: 11px; font-weight: 600; color: var(--text-muted); }
        .spinner { width: 14px; height: 14px; border: 2px solid var(--accent-glow); border-top-color: transparent; border-radius: 50%; display: none; animation: spin 0.8s linear infinite; margin-right: 10px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        #t-main, #t-about { height: 490px; overflow-y: auto; padding-right: 5px; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="logo-text">LuaDW</h1>
        <div class="status-badge" onclick="exec('open_github')">GITHUB REPO</div>
    </div>

    <div class="nav-container">
        <div class="nav-btn active" onclick="tab('main')">PANEL</div>
        <div class="nav-btn" onclick="tab('about')">HAKKINDA</div>
    </div>

    <div id="t-main">
        <div class="glass-panel">
            <span style="display:block; font-size:11px; font-weight:800; color:var(--text-muted); margin-bottom:12px;">APPID İLE KÜTÜPHANEYE LUA EKLE</span>
            <input type="text" id="appid_input" placeholder="Örn: 730" autocomplete="off">
            <button class="btn-glow" onclick="runFix()">KÜTÜPHANEYE EKLE</button>
        </div>

        <div class="glass-panel">
            <span style="display:block; font-size:11px; font-weight:800; color:var(--text-muted); margin-bottom:12px;">GENERIC BYPASS</span>
            <select id="bypass_appid">
                <option value="" disabled selected>Oyun Listesi Yükleniyor...</option>
            </select>
            <button class="btn-bypass" onclick="runBypass()">OYUNA BYPASS UYGULA</button>
        </div>

        <button class="btn-outline" onclick="exec('restart_steam')" style="margin-bottom: 20px;">STEAM'İ YENİDEN BAŞLAT</button>
    </div>

    <div id="t-about" style="display:none;">
        <div class="glass-panel">
            <h3 style="margin-top:0; font-size:14px; color:#fff;">Tamamen Açık Kaynak</h3>
            <p style="font-size:11px; color:var(--text-muted); line-height:1.6;">
                LuaDW, Steam platformunda LUA dosyalarını indirdiğiniz uygulamaları kütüphanenizde görünür hale getiren açık kaynak bir yazılımdır.
            </p>
            <button class="btn-glow" onclick="exec('open_github')">GITHUB REPOSITORY</button>
        </div>
    </div>

    <div class="footer">
        <div style="display:flex; align-items:center;">
            <div id="spin" class="spinner"></div>
            <span class="log-text" id="stText">SİSTEM BAŞLATILIYOR...</span>
        </div>
        <div style="width: 8px; height: 8px; border-radius: 50%; background: var(--success);"></div>
    </div>

    <script>
        function tab(t) {
            ['main','about'].forEach(x => document.getElementById('t-'+x).style.display = 'none');
            document.getElementById('t-'+t).style.display = 'block';
            document.querySelectorAll('.nav-btn').forEach(n => n.classList.remove('active'));
            event.target.classList.add('active');
        }

        function updateUI(load, msg, type) {
            document.getElementById('spin').style.display = load ? 'block' : 'none';
            const s = document.getElementById('stText');
            s.innerText = msg;
            s.style.color = type == 'error' ? '#ff5252' : (type == 'success' ? '#00e676' : '#8b949e');
            document.querySelectorAll('button').forEach(b => b.disabled = load);
        }

        function populateBypassMenu(gamesDict) {
            const select = document.getElementById('bypass_appid');
            select.innerHTML = '<option value="" disabled selected>Desteklenen Bir Oyun Seçin</option>';
            const sortedGames = Object.entries(gamesDict).sort((a, b) => a[1].localeCompare(b[1]));
            
            for (const [appid, name] of sortedGames) {
                const opt = document.createElement('option');
                opt.value = appid;
                opt.textContent = `${name} (${appid})`;
                select.appendChild(opt);
            }
        }

        function exec(fn) { window.pywebview.api[fn](); }

        function runFix() { 
            const appId = document.getElementById('appid_input').value.trim();
            if(!appId) return updateUI(false, "LÜTFEN BIR APPID GİRİN!", "error");
            window.pywebview.api.fetch_and_fix_lua(appId); 
        }

        function runBypass() {
            const val = document.getElementById('bypass_appid').value;
            if(!val) return updateUI(false, "LÜTFEN BİR OYUN SEÇİN!", "error");
            window.pywebview.api.apply_game_bypass(val);
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    bridge = LuaDWBridge()
    window = webview.create_window(
        'LuaDW', 
        html=html_content, 
        width=450, 
        height=680, 
        resizable=False, 
        js_api=bridge,
        background_color='#050508'
    )
    bridge.set_window(window)
    webview.start()