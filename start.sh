#!/bin/bash

# ============================================================
#  MIYA v4.1.11 - Launch Center
#
#  start.sh           Show menu
#  start.sh 1|2|3     Direct launch
#  start.sh a         Launch all
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_menu() {
    clear
    echo -e "${BLUE}================================================================================"
    echo "                         MIYA v4.1.11  Launch Center"
    echo -e "================================================================================${NC}"
    echo
    echo "  [1] Terminal    DSH TUI + DeepSeek V4"
    echo "  [2] Daemon      Backend (core + platforms + API :9800)"
    echo "  [3] Desktop     Electron desktop app"
    echo "  [4] Web UI      DSH Web (browser)"
    echo
    echo "  [A] All         Start everything"
    echo "  [0] Exit"
    echo
    echo -e "================================================================================"
    read -p "Enter choice: " choice
}

ensure_host() {
    if ! command -v node >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Node.js not found${NC}"
        return 1
    fi
    if [ ! -f "deepseek-harness/apps/cli/lib/bin.js" ]; then
        echo -e "${RED}[ERROR] DeepSeek Harness not found. Run: build.sh dsh${NC}"
        return 1
    fi
    # 检查 3199 端口是否已被 DSH host 占用，没有则启动
    if ! (command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 3199 >/dev/null 2>&1); then
        echo -e "${YELLOW}[INFO] Starting DSH host (127.0.0.1:3199)...${NC}"
        (export DSH_HOME="$SCRIPT_DIR/data/dsh" && node deepseek-harness/apps/cli/lib/bin.js web --host 127.0.0.1 --port 3199 &)
        sleep 3
    else
        echo -e "${YELLOW}[INFO] DSH host already running on 3199${NC}"
    fi
}

start_terminal() {
    if [ -f "deepseek-harness/apps/cli/lib/bin.js" ] && [ -f "tools/dsh-tui/node_modules/dsh-tui/bin/tui.js" ]; then
        ensure_host
        echo -e "${YELLOW}Starting MIYA Terminal (dsh-tui)...${NC}"
        export DSH_HOME="$SCRIPT_DIR/data/dsh"
        export DSH_URL="http://127.0.0.1:3199"
        node tools/dsh-tui/node_modules/dsh-tui/bin/tui.js
    else
        echo -e "${RED}[ERROR] DeepSeek Harness / dsh-tui not found. Run: build.sh dsh && (cd tools/dsh-tui && npm install)${NC}"
    fi
}

start_web() {
    if [ -f "deepseek-harness/apps/cli/lib/bin.js" ]; then
        ensure_host
        echo -e "${YELLOW}Opening DSH Web UI (http://127.0.0.1:3199)...${NC}"
        (xdg-open http://127.0.0.1:3199 >/dev/null 2>&1 || open http://127.0.0.1:3199 >/dev/null 2>&1 || true)
    else
        echo -e "${RED}[ERROR] DeepSeek Harness not found. Run: build.sh dsh${NC}"
    fi
}

start_daemon() {
    if command -v python >/dev/null 2>&1; then
        echo -e "${YELLOW}Starting MIYA Daemon (API on port 9800)...${NC}"
        echo "Press Ctrl+C to stop."
        echo
        python run/daemon.py --api-port 9800
        echo
        echo -e "${GREEN}[OK] Daemon stopped${NC}"
    else
        echo -e "${RED}[ERROR] Python not found${NC}"
    fi
}

start_desktop() {
    if [ -f "miya_frontend/package.json" ]; then
        # pnpm can quarantine npm-installed packages in node_modules/.ignored.
        # Checking for the actual runtime packages prevents a confusing
        # MODULE_NOT_FOUND from Vite and repairs the install before launching.
        if [ ! -f "miya_frontend/node_modules/vite/bin/vite.js" ] \
            || [ ! -f "miya_frontend/node_modules/@vitejs/plugin-vue/package.json" ] \
            || [ ! -f "miya_frontend/node_modules/vue/package.json" ] \
            || [ ! -f "miya_frontend/node_modules/unocss/package.json" ] \
            || [ ! -f "miya_frontend/node_modules/vite-plugin-electron/package.json" ] \
            || [ ! -f "miya_frontend/node_modules/electron/package.json" ] \
            || [ ! -f "miya_frontend/node_modules/esbuild/package.json" ]; then
            echo -e "${YELLOW}[WARN] Dependencies not installed, running npm install...${NC}"
            (cd miya_frontend && npm install --loglevel=info --foreground-scripts --legacy-peer-deps)
            if [ $? -ne 0 ]; then
                echo -e "${RED}[ERROR] Frontend dependency install failed${NC}"
                return 1
            fi
        fi
        echo -e "${YELLOW}Starting Electron desktop app...${NC}"
        echo "  Start backend separately (start.sh 2)"
        # Invoke the local toolchain directly; a broken global npm shim should
        # not prevent the desktop app from starting.
        (cd miya_frontend && MIYA_NO_BACKEND=1 node scripts/generate-audio-manifest.mjs \
            && node scripts/esbuild-electron.mjs \
            && MIYA_NO_BACKEND=1 ESBUILD_ELECTRON=1 node node_modules/vite/bin/vite.js)
    else
        echo -e "${RED}[ERROR] miya_frontend not found${NC}"
    fi
}

start_all() {
    echo -e "${GREEN}Starting MIYA All-in-One...${NC}"

    echo "[1/3] Starting Daemon (background)..."
    python run/daemon.py --api-port 9800 &
    sleep 3
    echo -e "${GREEN}[OK] Daemon started${NC}"

    if [ -f "miya_frontend/package.json" ]; then
        echo "[2/3] Starting Desktop app..."
        (cd miya_frontend && MIYA_NO_BACKEND=1 node scripts/generate-audio-manifest.mjs \
            && node scripts/esbuild-electron.mjs \
            && MIYA_NO_BACKEND=1 ESBUILD_ELECTRON=1 node node_modules/vite/bin/vite.js) &
        sleep 2
        echo -e "${GREEN}[OK] Desktop launched${NC}"
    else
        echo "[2/3] Desktop app not found, skipped"
    fi

    echo "[3/3] Starting Terminal (foreground)..."
    echo
    ensure_host
    export DSH_HOME="$SCRIPT_DIR/data/dsh"
    export DSH_URL="http://127.0.0.1:3199"
    node tools/dsh-tui/node_modules/dsh-tui/bin/tui.js

    echo
    echo -e "${GREEN}[OK] All-in-One session ended${NC}"
    echo "(Close Daemon/Desktop windows with Ctrl+C)"
}

# CLI direct launch
case "${1:-}" in
    1|t) start_terminal; exit 0 ;;
    2|d) start_daemon; exit 0 ;;
    3) start_desktop; exit 0 ;;
    4|w) start_web; exit 0 ;;
    a) start_all; exit 0 ;;
esac

while true; do
    show_menu

    case $choice in
        0)
            echo "Goodbye!"
            exit 0
            ;;
        1|t)
            start_terminal
            ;;
        2|d)
            start_daemon
            ;;
        3)
            start_desktop
            ;;
        4|w)
            start_web
            ;;
        a|A)
            start_all
            ;;
        *)
            echo -e "${RED}[ERROR] Invalid choice${NC}"
            ;;
    esac

    echo
    read -p "Press Enter to continue..."
done
