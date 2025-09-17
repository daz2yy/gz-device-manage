#!/bin/bash

# Device Management System - One-Click Startup Script
# Author: CodeBuddy Code
# Description: Starts both backend and frontend services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# PID files for process management
BACKEND_PID_FILE="$PROJECT_ROOT/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT/.frontend.pid"

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process by PID file
kill_by_pid_file() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log "Stopping $service_name (PID: $pid)..."
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                log_warning "Force killing $service_name..."
                kill -9 "$pid"
            fi
        fi
        rm -f "$pid_file"
    fi
}

# Function to stop services
stop_services() {
    log "Stopping Device Management System services..."
    
    kill_by_pid_file "$BACKEND_PID_FILE" "Backend"
    kill_by_pid_file "$FRONTEND_PID_FILE" "Frontend"
    
    # Also kill by port if PID files don't work
    if check_port 8001; then
        log_warning "Force stopping backend on port 8001..."
        lsof -ti:8001 | xargs kill -9 2>/dev/null || true
    fi
    
    if check_port 5173; then
        log_warning "Force stopping frontend on port 5173..."
        lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    fi
    
    log_success "All services stopped"
}

# Function to check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 is not installed"
        return 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js is not installed"
        return 1
    fi
    
    # Check npm
    if ! command -v npm &> /dev/null; then
        log_error "npm is not installed"
        return 1
    fi
    
    # Check ADB (optional)
    if ! command -v adb &> /dev/null; then
        log_warning "ADB is not installed - device detection may not work"
    else
        log_success "ADB is available"
    fi
    
    log_success "Dependencies check completed"
    return 0
}

# Function to install backend dependencies
install_backend_deps() {
    log "Installing backend dependencies..."
    cd "$BACKEND_DIR"
    
    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt not found in backend directory"
        return 1
    fi
    
    pip install -r requirements.txt
    log_success "Backend dependencies installed"
}

# Function to install frontend dependencies
install_frontend_deps() {
    log "Installing frontend dependencies..."
    cd "$FRONTEND_DIR"
    
    if [ ! -f "package.json" ]; then
        log_error "package.json not found in frontend directory"
        return 1
    fi
    
    npm install
    log_success "Frontend dependencies installed"
}

# Function to start backend
start_backend() {
    log "Starting backend service..."
    cd "$BACKEND_DIR"
    
    if check_port 8001; then
        log_error "Port 8001 is already in use"
        return 1
    fi
    
    # Start backend in background
    python start.py > "$PROJECT_ROOT/backend.log" 2>&1 &
    local backend_pid=$!
    echo $backend_pid > "$BACKEND_PID_FILE"
    
    # Wait for backend to start
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8001/docs > /dev/null 2>&1; then
            log_success "Backend started successfully (PID: $backend_pid)"
            return 0
        fi
        
        if ! kill -0 $backend_pid 2>/dev/null; then
            log_error "Backend process died unexpectedly"
            cat "$PROJECT_ROOT/backend.log"
            return 1
        fi
        
        sleep 1
        ((attempt++))
    done
    
    log_error "Backend failed to start within 30 seconds"
    return 1
}

# Function to start frontend
start_frontend() {
    log "Starting frontend service..."
    cd "$FRONTEND_DIR"
    
    if check_port 5173; then
        log_error "Port 5173 is already in use"
        return 1
    fi
    
    # Start frontend in background
    npm run dev > "$PROJECT_ROOT/frontend.log" 2>&1 &
    local frontend_pid=$!
    echo $frontend_pid > "$FRONTEND_PID_FILE"
    
    # Wait for frontend to start
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -I http://localhost:5173 > /dev/null 2>&1; then
            log_success "Frontend started successfully (PID: $frontend_pid)"
            return 0
        fi
        
        if ! kill -0 $frontend_pid 2>/dev/null; then
            log_error "Frontend process died unexpectedly"
            cat "$PROJECT_ROOT/frontend.log"
            return 1
        fi
        
        sleep 1
        ((attempt++))
    done
    
    log_error "Frontend failed to start within 30 seconds"
    return 1
}

# Function to show status
show_status() {
    echo
    log "=== Device Management System Status ==="
    
    # Backend status
    if check_port 8001; then
        log_success "Backend: Running on http://localhost:8001"
        log "  - API Documentation: http://localhost:8001/docs"
        log "  - API Base URL: http://localhost:8001/api"
    else
        log_error "Backend: Not running"
    fi
    
    # Frontend status
    if check_port 5173; then
        log_success "Frontend: Running on http://localhost:5173"
        log "  - Web Interface: http://localhost:5173"
    else
        log_error "Frontend: Not running"
    fi
    
    echo
    log "Default Admin Credentials:"
    log "  Username: admin"
    log "  Password: admin123"
    echo
}

# Function to show logs
show_logs() {
    local service=$1
    
    case $service in
        "backend")
            if [ -f "$PROJECT_ROOT/backend.log" ]; then
                tail -f "$PROJECT_ROOT/backend.log"
            else
                log_error "Backend log file not found"
            fi
            ;;
        "frontend")
            if [ -f "$PROJECT_ROOT/frontend.log" ]; then
                tail -f "$PROJECT_ROOT/frontend.log"
            else
                log_error "Frontend log file not found"
            fi
            ;;
        *)
            log_error "Invalid service. Use 'backend' or 'frontend'"
            ;;
    esac
}

# Main function
main() {
    local command=${1:-"start"}
    
    case $command in
        "start")
            log "🚀 Starting Device Management System..."
            echo "=================================================="
            
            # Check dependencies
            if ! check_dependencies; then
                exit 1
            fi
            
            # Stop any existing services
            stop_services
            
            # Install dependencies if needed
            if [ ! -d "$BACKEND_DIR/env" ] && [ ! -f "$BACKEND_DIR/.deps_installed" ]; then
                install_backend_deps
                touch "$BACKEND_DIR/.deps_installed"
            fi
            
            if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
                install_frontend_deps
            fi
            
            # Start services
            if start_backend && start_frontend; then
                show_status
                log_success "🎉 Device Management System started successfully!"
                log "Press Ctrl+C to stop all services"
                
                # Wait for interrupt
                trap 'stop_services; exit 0' INT TERM
                
                # Keep script running and monitor services
                while true; do
                    sleep 10
                    
                    # Check if services are still running
                    if [ -f "$BACKEND_PID_FILE" ]; then
                        local backend_pid=$(cat "$BACKEND_PID_FILE")
                        if ! kill -0 $backend_pid 2>/dev/null; then
                            log_error "Backend service died unexpectedly"
                            break
                        fi
                    fi
                    
                    if [ -f "$FRONTEND_PID_FILE" ]; then
                        local frontend_pid=$(cat "$FRONTEND_PID_FILE")
                        if ! kill -0 $frontend_pid 2>/dev/null; then
                            log_error "Frontend service died unexpectedly"
                            break
                        fi
                    fi
                done
            else
                log_error "Failed to start services"
                stop_services
                exit 1
            fi
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            stop_services
            sleep 2
            $0 start
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs $2
            ;;
        "install")
            check_dependencies
            install_backend_deps
            install_frontend_deps
            log_success "All dependencies installed"
            ;;
        *)
            echo "Usage: $0 {start|stop|restart|status|logs|install}"
            echo ""
            echo "Commands:"
            echo "  start    - Start both backend and frontend services"
            echo "  stop     - Stop all services"
            echo "  restart  - Restart all services"
            echo "  status   - Show service status"
            echo "  logs     - Show logs (backend|frontend)"
            echo "  install  - Install all dependencies"
            echo ""
            echo "Examples:"
            echo "  $0 start"
            echo "  $0 logs backend"
            echo "  $0 logs frontend"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"