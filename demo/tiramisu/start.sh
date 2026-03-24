#!/bin/bash

echo "Starting DeepAnalyze Tiramisu"
echo "========================================"

# Ensure logs directory exists
mkdir -p logs

# Function to check and free ports
check_port() {
    local port=$1
    local pids
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Port $port in use by PIDs: $pids. Terminating..."
        kill $pids 2>/dev/null || true
        sleep 1
        local pids2
        pids2=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
        if [ -n "$pids2" ]; then
            echo "Force terminating remaining PIDs on $port: $pids2"
            kill -9 $pids2 2>/dev/null || true
            sleep 1
        fi
    fi
}

# Ports
BACKEND_PORT=8200
TIRAMISU_PORT=${TIRAMISU_PORT:-3000}

# Clean up old processes
echo "Cleaning old processes..."
pkill -f "python.*backend.py" 2>/dev/null || true
pkill -f "npm.*dev" 2>/dev/null || true
pkill -f "next.*dev" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true

# Check and clean ports
check_port $BACKEND_PORT
check_port "$TIRAMISU_PORT"

echo "Cleanup completed."
echo ""

# Start backend API
echo "Starting backend API..."
nohup python3 backend.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
echo "API running on: http://localhost:$BACKEND_PORT"

# Wait for backend to initialize
sleep 3

# Start frontend
echo ""
echo "Starting Tiramisu frontend..."
nohup npm run dev -- -p "$TIRAMISU_PORT" > logs/tiramisu.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
echo "Frontend running on: http://localhost:$TIRAMISU_PORT"

# Save PIDs
echo $BACKEND_PID > logs/backend.pid
echo $FRONTEND_PID > logs/tiramisu.pid

echo ""
echo "All services started successfully."
echo ""
echo "Service URLs:"
echo "  Backend API: http://localhost:$BACKEND_PORT"
echo "  Frontend:    http://localhost:$TIRAMISU_PORT"
echo ""
echo "Log files:"
echo "  Backend:  logs/backend.log"
echo "  Frontend: logs/tiramisu.log"
echo ""
echo "Stop services: ./stop.sh"
