#!/bin/bash

echo "Stopping DeepAnalyze Tiramisu"
echo "========================================"

# Stop service by PID file
stop_service() {
    local service_name=$1
    local pid_file=$2

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                echo "   Force stopping $service_name..."
                kill -9 "$pid" 2>/dev/null || true
            fi
            echo "   $service_name stopped."
        else
            echo "   $service_name process not found."
        fi
        rm -f "$pid_file"
    else
        echo "   PID file for $service_name not found."
    fi
}

# Stop services
stop_service "Backend API" "logs/backend.pid"
stop_service "Tiramisu Frontend" "logs/tiramisu.pid"

echo ""
echo "Cleaning up remaining processes..."

pkill -f "python.*backend.py" 2>/dev/null && echo "   Cleaned up backend.py process." || true
pkill -f "npm.*dev" 2>/dev/null && echo "   Cleaned up npm dev process." || true
pkill -f "next.*dev" 2>/dev/null && echo "   Cleaned up next dev process." || true
pkill -f "next-server" 2>/dev/null && echo "   Cleaned up next-server process." || true

echo ""
echo "Releasing ports..."

BACKEND_PORT=8200
TIRAMISU_PORT=${TIRAMISU_PORT:-3000}
for port in $BACKEND_PORT "$TIRAMISU_PORT"; do
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "   Releasing port $port (PIDs: $pids)..."
        kill $pids 2>/dev/null || true
        sleep 1
        pids2=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
        if [ -n "$pids2" ]; then
            echo "   Force releasing port $port (PIDs: $pids2)..."
            kill -9 $pids2 2>/dev/null || true
        fi
    fi
done

echo ""
echo "System stopped successfully."
echo ""
echo "Log files are kept in the logs/ directory."
echo "To restart: ./start.sh"
