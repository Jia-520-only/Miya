#!/bin/bash

# MIYA - Launch Menu

echo "========================================"
echo "  MIYA - Launch Menu"
echo "========================================"
echo ""

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "[ERROR] Virtual environment not found"
    echo "Please run install.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check configuration file
if [ ! -f "config/.env" ]; then
    echo "[ERROR] Configuration file not found: config/.env"
    echo "Please create and configure config/.env file"
    exit 1
fi

# Display menu
while true; do
    clear
    echo "========================================"
    echo "  MIYA - Launch Menu"
    echo "========================================"
    echo ""
echo "1. Start Main Program (Full Mode)"
echo "2. Start QQ Bot"
echo "3. Start PC UI"
echo "4. Start Desktop UI (Electron)"
echo "5. Start Runtime API Server"
echo "6. Start Health Check"
echo "7. Check System Status"
echo "8. Exit"
echo ""
read -p "Select mode (1-8): " choice

case $choice in
        1)
            echo ""
            echo "[Starting] Main Program (Full Mode)..."
            echo ""
            echo "[Info] Testing imports first..."
            python test_imports.py
            if [ $? -ne 0 ]; then
                echo "[ERROR] Import test failed"
                read -p "Press Enter to continue..."
                continue
            fi
            echo ""
            echo "[Info] Launching main program..."
            python run/main.py
            break
            ;;
        2)
            echo ""
            echo "[Starting] QQ Bot..."
            echo ""
            python run/qq_main.py
            break
            ;;
        3)
            echo ""
            echo "[Starting] Web UI (Frontend + Backend)..."
            echo ""
            python run/web_main.py
            break
            ;;
        4)
            echo ""
            echo "[Starting] Desktop UI (Electron)..."
            echo ""
            python run/desktop_main.py
            break
            ;;
        5)
            echo ""
            echo "[Starting] Runtime API Server..."
            echo ""
            python run/runtime_api_start.py
            break
            ;;
        6)
            echo ""
            echo "[Starting] Health Check..."
            echo ""
            python run/health.py
            break
            ;;
        7)
            echo ""
            echo "[Status] System Status Check..."
            echo ""
            python -c "import sys; print('Python Version:', sys.version.split()[0]); import platform; print('OS:', platform.system(), platform.version()); print('Machine:', platform.machine()); print('Processor:', platform.processor())"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        8)
            echo ""
            echo "[Done] Exiting..."
            exit 0
            ;;
        *)
            echo ""
            echo "[ERROR] Invalid choice"
            sleep 1
            ;;
    esac
done
