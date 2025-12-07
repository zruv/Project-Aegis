import serial
import hashlib
import hmac
import time
import sys
import glob

# --- CONFIGURATION ---
# The default port. We will try to auto-detect if this fails or is not set.
DEFAULT_SERIAL_PORT = '/dev/ttyUSB0' 
BAUD_RATE = 115200

# MUST match the key in firmware/src/secrets.h
SHARED_SECRET_KEY = "my_super_secret_key_12345".encode('utf-8') 
# --- END CONFIGURATION ---

def list_serial_ports():
    """ Lists serial port names on Linux """
    if sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    elif sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def run_test():
    # 1. Determine Port
    port = DEFAULT_SERIAL_PORT
    
    # Simple auto-detection attempt for Linux USB Serial devices
    available_ports = list_serial_ports()
    usb_ports = [p for p in available_ports if "USB" in p or "ACM" in p]
    
    if usb_ports:
        print(f"Auto-detected USB Serial ports: {usb_ports}")
        port = usb_ports[0] # Pick the first one
    else:
        print(f"No obvious USB serial ports found. Defaulting to {port}")
        print(f"Available ports: {available_ports}")

    print(f"Attempting to open serial port: {port}...")

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=5)
        print(f"Successfully opened {port}.")
        print("Waiting 2 seconds for ESP32 to reset...")
        time.sleep(2) # Give ESP32 time to reset and initialize

        challenge = "UserRequestingAccess:Nonce-123456"
        print(f"\n[PC] Sending challenge: '{challenge}'")
        
        # Send the challenge + newline to the ESP32
        ser.write(f"{challenge}\n".encode('utf-8'))
        
        print("[PC] Waiting for response from ESP32...")
        response = ser.readline().decode('utf-8').strip()
        print(f"[ESP32] Received response: '{response}'")

        if not response:
            print("\n[ERROR] No response received. Check connection and baud rate.")
            return

        # --- VERIFICATION ON PC SIDE ---
        # Calculate the expected HMAC-SHA256 signature on the PC
        expected_hmac = hmac.new(SHARED_SECRET_KEY, challenge.encode('utf-8'), hashlib.sha256).hexdigest()
        print(f"[PC] Calculated expected signature: '{expected_hmac}'")

        if response.lower() == expected_hmac.lower():
            print("\n>>> SUCCESS: ESP32 signature matches! Handshake Verified. <<<")
        else:
            print("\n>>> FAILURE: Signatures DO NOT match. <<<")
            print("Check: 1. Secret Key in firmware/src/secrets.h")
            print("       2. Secret Key in this script")
            print("       3. Baud rate mismatch?")

    except serial.SerialException as e:
        print(f"\n[ERROR] Could not open serial port {port}.")
        print(f"Details: {e}")
        print("Suggestion: Check if the device is plugged in and you have permissions (try sudo).")
        print("You can manually edit the 'DEFAULT_SERIAL_PORT' at the top of this script.")

    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial port closed.")

if __name__ == "__main__":
    run_test()
