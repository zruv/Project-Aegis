import serial
import hashlib
import hmac
import time
import sys
import glob
import docker
import os

# --- CONFIGURATION ---
BAUD_RATE = 115200
# Must match firmware/src/secrets.h
SHARED_SECRET_KEY = "my_super_secret_key_12345".encode('utf-8')
# The master key to inject into the vault container
VAULT_MASTER_KEY = "production_master_key_XYZ987"
DOCKER_IMAGE = "aegis-vault"
CONTAINER_NAME = "aegis-vault-instance"
HEARTBEAT_INTERVAL = 2 # Seconds between checks
# ---------------------

def list_serial_ports():
    if sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    elif sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    else:
        return []
    
    result = []
    for port in ports:
        # Filter for likely USB devices on Linux to avoid ttyS0 etc
        if sys.platform.startswith('linux') and not ("USB" in port or "ACM" in port):
            continue
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def perform_handshake(ser):
    """Sends a challenge and verifies the signature."""
    try:
        ser.reset_input_buffer()
        challenge = f"AuthRequest:{os.urandom(8).hex()}"
        ser.write(f"{challenge}\n".encode('utf-8'))
        
        # Wait for response
        time.sleep(0.1)
        if ser.in_waiting == 0:
            time.sleep(0.5) # Give it a bit more time
            
        response = ser.readline().decode('utf-8').strip()
        
        if not response:
            return False

        expected_hmac = hmac.new(SHARED_SECRET_KEY, challenge.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if response.lower() == expected_hmac.lower():
            return True
        return False
    except Exception as e:
        print(f"Handshake error: {e}")
        return False

def start_vault(client):
    try:
        # Check if already running
        try:
            container = client.containers.get(CONTAINER_NAME)
            if container.status == 'running':
                return
            container.remove(force=True)
        except docker.errors.NotFound:
            pass

        print(">>> STARTING VAULT CONTAINER...")
        client.containers.run(
            DOCKER_IMAGE,
            name=CONTAINER_NAME,
            detach=True,
            ports={'5000/tcp': 5000},
            environment={'AEGIS_MASTER_KEY': VAULT_MASTER_KEY},
            volumes={os.path.abspath(os.getcwd()) + '/aegis_data': {'bind': '/data', 'mode': 'rw'}}
        )
        print(">>> VAULT OPEN at http://127.0.0.1:5000")
    except Exception as e:
        print(f"Failed to start docker: {e}")

def stop_vault(client):
    try:
        container = client.containers.get(CONTAINER_NAME)
        print(">>> LOCKING VAULT (Stopping Container)...")
        container.stop()
        container.remove()
        print(">>> VAULT LOCKED.")
    except docker.errors.NotFound:
        pass
    except Exception as e:
        print(f"Error stopping vault: {e}")

def main():
    print("--- Aegis Watcher Started ---")
    
    client = None
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        # Fallback: Check for Docker Desktop socket
        potential_paths = []
        
        # 1. Check current user's home
        potential_paths.append(os.path.expanduser("~/.docker/desktop/docker.sock"))
        
        # 2. Check SUDO_USER's home if running as root
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            potential_paths.append(f"/home/{sudo_user}/.docker/desktop/docker.sock")
            
        for socket_path in potential_paths:
            if os.path.exists(socket_path):
                print(f"Attempting to connect to Docker socket at: {socket_path}")
                try:
                    client = docker.DockerClient(base_url=f"unix://{socket_path}")
                    client.ping()
                    break # Success
                except Exception as e:
                    print(f"Failed to connect to {socket_path}: {e}")
                    client = None

    if not client:
        print("ERROR: Could not connect to Docker Daemon.")
        print("Ensure Docker is running. If using Docker Desktop, wait for it to initialize.")
        return

    # Ensure any leftover container is gone
    stop_vault(client)
    
    current_ser = None
    is_unlocked = False

    while True:
        if not is_unlocked:
            # SEARCH MODE
            ports = list_serial_ports()
            for port in ports:
                print(f"Probing {port}...")
                try:
                    ser = serial.Serial(port, BAUD_RATE, timeout=2)
                    time.sleep(2) # Wait for ESP32 reset
                    
                    if perform_handshake(ser):
                        print(f"SUCCESS: Key detected on {port}")
                        current_ser = ser
                        start_vault(client)
                        is_unlocked = True
                        break
                    else:
                        ser.close()
                except Exception as e:
                    print(f"Error probing {port}: {e}")
            
            if not is_unlocked:
                time.sleep(2)

        else:
            # MONITOR MODE
            try:
                # Send a heartbeat challenge
                if not perform_handshake(current_ser):
                    print("Heartbeat failed! Key removed?")
                    raise Exception("Handshake failed")
                
                # print("Heartbeat OK") # Optional logging
                time.sleep(HEARTBEAT_INTERVAL)
                
            except Exception as e:
                print(f"Connection lost: {e}")
                stop_vault(client)
                if current_ser:
                    current_ser.close()
                current_ser = None
                is_unlocked = False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopping Watcher...")
        # Clean up
        try:
            client = docker.from_env()
            stop_vault(client)
        except:
            pass
