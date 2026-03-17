#!/usr/bin/env python3
"""
Enhanced Core System with Cross-Platform Serial Port Detection

This version automatically detects available serial ports on both macOS and Linux.
"""

import serial
import serial.tools.list_ports
import time
import random
import platform
from typing import Optional, List

# Copy all the constants and data from your original core.py directly
TROW = 7  # Number of rows in the display
TCOLUMN = 105  # Number of columns in the display
ROW_BREAK = 75  # Column index where the display wraps to the next row
BITMASK = [1, 2, 4, 8, 0x10, 0x20, 0x40]  # Bitmask for each row
DEFAULT_DELAY = 0.2  # Default animation delay

# Serial control commands
reset = b'\x81'
row1 = b'\x81'
row2 = b'\x82'

# Your existing character dictionary
dict = {
    ' ': b'\x00\x00\x00',
    '$': b'2I\x7fI&',
    '(': b'>A',
    ',': b'\x01\x06',
    '0': b'>AAA>',
    '4': b'\x1c$D\x7f\x04',
    '8': b'6III6',
    '<': b'\x08\x14"',
    '@': b'\x1f\x10\x17\x15\x1f',
    'D': b'\x7fAAA>',
    'H': b'\x7f\x08\x08\x08\x7f',
    'L': b'\x7f\x01\x01\x01',
    'P': b'\x7fHHH0',
    'T': b'@@\x7f@@',
    'X': b'A"\x1c"A',
    '\\': b'`\x1c\x03',
    '`': b'@ ',
    'd': b'\x0e\x11\x11\x7f',
    'h': b'\x7f\x10\x10\x10\x0f',
    'l': b'~\x01',
    'p': b'?$$\x18',
    't': b'\x10>\x11',
    'x': b'\x1b\x04\x04\x1b',
    '|': b'w',
    '#': b'\x14\x7f\x14\x7f\x14',
    "'": b'`',
    'space': b'\x00',
    '+': b'\x08\x08>\x08\x08',
    '/': b'\x03\x1c`',
    '3': b'"AII6',
    '7': b'`@GX`',
    ';': b'\x016',
    '?': b' OH0',
    'C': b'>AAA"',
    'G': b'>AAI/',
    'K': b'\x7f\x08\x14"A',
    'O': b'>AAA>',
    'S': b'2III&',
    'W': b'~\x01\x01~\x01\x01~',
    '[': b'\x7fA',
    '_': b'\x01\x01\x01',
    'c': b'\x0e\x11\x11\x11',
    'g': b'\x81\x15\x15\x15\x0e',
    'k': b'\x7f\x06\n\x11',
    'o': b'\x0e\x11\x11\x0e',
    's': b'\t\x15\x15\x12',
    'w': b'\x1e\x01\x01\x1e\x01\x01\x1e',
    '{': b'\x086A',
    '"': b'``',
    '&': b'7IE+\x07',
    '*': b'(\x10|\x10(',
    '.': b'\x01',
    '2': b'!CEI1',
    '6': b'\x1e)II\x06',
    ':': b'6',
    '>': b'"\x14\x08',
    'B': b'\x7fIII6',
    'F': b'\x7fHH@',
    'J': b'\x02\x01A~',
    'N': b'\x7f \x10\x08\x04\x7f',
    'R': b'\x7fHHH7',
    'V': b'x\x06\x01\x06x',
    'Z': b'CEIQa',
    '^': b' @ ',
    'b': b'\x7f\x11\x11\x0e',
    'f': b'\x10?P',
    'j': b'\x11^',
    'n': b'\x1f\x10\x10\x0f',
    'r': b'\x1f\x08\x10',
    'v': b'\x1e\x01\x01\x1e',
    'z': b'\x13\x14\x14\x19',
    '~': b'\x08\x10\x08\x04\x08',
    '!': b'}',
    '%': b'1JL>\x19)F',
    ')': b'A>',
    '-': b'\x08\x08\x08\x08\x08',
    '1': b' \x7f',
    '5': b'rQQQN',
    '9': b'0IIJ<',
    '=': b'\x14\x14\x14\x14',
    'A': b'?HHH?',
    'E': b'\x7fIIA',
    'I': b'\x7f',
    'M': b'\x7f \x10\x08\x10 \x7f',
    'Q': b'<BFB=',
    'U': b'~\x01\x01\x01~',
    'Y': b'`\x10\x0f\x10`',
    ']': b'A\x7f',
    'a': b'\x0e\x11\x11\x1f',
    'e': b'\x0e\x15\x15\r',
    'i': b'\x10_',
    'm': b'\x1f\x10\x10\x0f\x10\x10\x0f',
    'q': b'\x18$$?',
    'u': b'\x1e\x01\x01\x1f',
    'y': b'8\x05\x05>',
    '}': b'A6\x08'
}

def find_serial_ports() -> List[str]:
    """Find available serial ports that might be the flipdot display."""
    ports = []
    
    # Get all available serial ports
    available_ports = serial.tools.list_ports.comports()
    
    system = platform.system().lower()
    
    for port in available_ports:
        port_name = port.device
        description = port.description.lower() if port.description else ""
        
        # macOS patterns
        if system == "darwin":
            if "usbserial" in port_name or "tty.usb" in port_name:
                ports.append(port_name)
        
        # Linux patterns
        elif system == "linux":
            if any(pattern in port_name for pattern in ["/dev/ttyUSB", "/dev/ttyACM", "/dev/serial"]):
                ports.append(port_name)
            # Also check by description for FTDI, Arduino, etc.
            elif any(keyword in description for keyword in ["ftdi", "arduino", "usb", "serial"]):
                ports.append(port_name)
        
        # Windows patterns (just in case)
        elif system == "windows":
            if port_name.startswith("COM"):
                ports.append(port_name)
    
    return ports

def test_flipdot_connection(port: str, baud: int = 38400) -> bool:
    """Test if a port responds like a flipdot display."""
    try:
        with serial.Serial(port, baud, timeout=2) as ser:
            # Send a simple command and see if it doesn't error
            ser.write(reset)
            ser.write(b'\x00' * 10)  # Send some null bytes
            time.sleep(0.1)
            return True
    except Exception:
        return False

def find_flipdot_port(baud: int = 38400) -> Optional[str]:
    """Automatically find the flipdot display port."""
    print("Searching for flipdot display...")
    
    candidate_ports = find_serial_ports()
    
    if not candidate_ports:
        print("No USB serial ports found")
        return None
    
    print(f"Found {len(candidate_ports)} potential serial ports:")
    for port in candidate_ports:
        print(f"  - {port}")
    
    # Test each port
    for port in candidate_ports:
        print(f"Testing {port}...")
        if test_flipdot_connection(port, baud):
            print(f"✅ Flipdot display found on {port}")
            return port
        else:
            print(f"❌ No response from {port}")
    
    print("No flipdot display found on any port")
    return None

class FallbackSerial:
    """Simulates the flipdot display when hardware is not available."""
    
    def __init__(self):
        self.last_message_was_control = False
        self.cursor_position = 0
        self.screen_matrix = []
        
    def write(self, message: bytes) -> None:
        """
        Simulates writing to the flipdot display.
        
        Args:
            message: Bytes to send to the display
        """
        for char_byte in message:
            character = char_byte  
            
            if character > 128:
                if self.last_message_was_control:
                    self.cursor_position += (character - 129) * ROW_BREAK
                    self.last_message_was_control = False
                else:
                    self.cursor_position = character - 129
                    self.last_message_was_control = True
            else:
                if not self.screen_matrix:
                    self.screen_matrix = [["." for _ in range(30)] for _ in range(14)]
                
                character_value = character
                for row in range(7):  
                    row_inverse = 6 - row
                    if self.cursor_position < 30:
                        if character_value & BITMASK[row_inverse]:
                            character_value -= BITMASK[row_inverse]
                            self.screen_matrix[row][self.cursor_position] = "O"
                        else:
                            self.screen_matrix[row][self.cursor_position] = "."
                    elif self.cursor_position >= 75 and self.cursor_position < 105:
                        display_col = self.cursor_position - 75
                        if display_col < 30:
                            if character_value & BITMASK[row_inverse]:
                                character_value -= BITMASK[row_inverse]
                                self.screen_matrix[row + 7][display_col] = "O"
                            else:
                                self.screen_matrix[row + 7][display_col] = "."
                
                if self.cursor_position % 10 == 0:
                    self._print_screen()
                
                self.cursor_position += 1
                self.last_message_was_control = False
    
    def _print_screen(self):
        """Print the current screen state to terminal."""
        print("\n" + "="*32)
        print("  FLIPDOT DISPLAY SIMULATION")
        print("="*32)
        for row in self.screen_matrix:
            print("| " + " ".join(row) + " |")
        print("="*32 + "\n")

# Initialize serial connection with fallback
ser_main = None

class WorkingFlipdotCore:
    """Complete flipdot core that properly handles both rows."""
    
    def __init__(self, port: Optional[str] = None, baud: int = 38400):
        """Initialize display with auto-detection."""
        global ser_main
        
        if port is None:
            port = find_flipdot_port(baud)
        
        if port:
            try:
                ser_main = serial.Serial(port, baud, timeout=1)
                print(f"✅ Connected to flipdot display on {port}")
            except (serial.SerialException, OSError) as e:
                print(f"❌ Failed to connect to {port}: {e}")
                print("🔄 Using terminal simulation mode")
                ser_main = FallbackSerial()
        else:
            print("🔄 No flipdot display found, using terminal simulation mode")
            ser_main = FallbackSerial()
    
    def clear(self) -> None:
        """Clear display."""
        if ser_main:
            ser_main.write(reset + row1)
            ser_main.write(b'\x00' * TCOLUMN)
    
    def getbytes(self, message: str, delim: bytes = dict['space'], dmult: int = 1) -> bytes:
        """Get bytes for message."""
        buf = b''
        for x in message:
            if x not in dict:
                buf += dict.get('?', b'\x00')
            else:
                buf += dict[x]
            buf += delim * dmult
        
        return buf[:-len(delim * dmult)] if dmult > 0 and delim else buf
    
    def fill(self, message: bytes, fillmask: int = 127) -> bytes:
        """Fill display."""
        if not ser_main:
            return message
            
        ser_main.write(reset + row1)

        for i in range(150):
            if i == ROW_BREAK:
                ser_main.write(reset + row2)

            if (i // 30) % 2 == 0:
                if i < len(message):
                    ser_main.write(bytes([message[i] & fillmask]))
                else:
                    ser_main.write(b"\x00")
            else:
                index = ((i % 30) + (25 - (10 * ((i % 30) // 5)))) + (30 * (i // 30))
                if index < len(message):
                    ser_main.write(bytes([message[index] & fillmask]))
                else:
                    ser_main.write(b"\x00")

        return message
    
    def negative(self, message: bytes) -> bytes:
        """Get negative of message."""
        return bytes([x ^ 127 for x in message])
    
    def display_text(self, message: str, justify: str = 'left') -> None:
        """Display text with perfect positioning."""
        text_bytes = self.getbytes(message.upper())
        padded_message = TCOLUMN * dict['space'] + text_bytes + TCOLUMN * dict['space']
        
        if len(text_bytes) <= 30:
            position = 103
            if justify == 'center':
                position = 103 - (30 - len(text_bytes)) // 4
            elif justify == 'right':
                position = 103 - (30 - len(text_bytes)) // 2
        else:
            position = 90
        
        chunk = padded_message[position:position + TCOLUMN]
        self.fill(chunk)
    
    def scrollleft(self, message: bytes, t: float = 0.2, d: int = 1, 
                  pausedelay: Optional[float] = None, o: bool = False) -> bytes:
        """Scroll left."""
        if not o:
            padded_message = TCOLUMN * dict['space'] + message + TCOLUMN * dict['space']
        else:
            padded_message = TCOLUMN * dict['space'] + message
            
        message_len = len(padded_message) - TCOLUMN
        
        for k in range((message_len // d) + 1):
            self.fill(padded_message[k*d:(k*d) + TCOLUMN])
            
            if pausedelay and k == ((message_len // d) + 1) // 2:
                time.sleep(pausedelay - t)
                
            time.sleep(t)
            
        return padded_message
    
    def rotateleft(self, message: bytes, t: float = 0.2, d: int = 1) -> bytes:
        """Rotate left."""
        for k in range(TCOLUMN // d):
            self.fill(message)
            message = message[d:] + message[:d]
            time.sleep(t)
        return message
    
    def rotateright(self, message: bytes, t: float = 0.2, d: int = 1) -> bytes:
        """Rotate right."""
        for k in range(TCOLUMN // d):
            self.fill(message)
            message = message[-d:] + message[:-d]
            time.sleep(t)
        return message
    
    def scrollup(self, message: bytes, t: float = 0.2) -> bytes:
        """Scroll up."""
        for _ in range(TROW):
            message = bytes([(x << 1) & 127 for x in message])
            self.fill(message)
            time.sleep(t)
        return message
    
    def scrolldown(self, message: bytes, t: float = 0.2) -> bytes:
        """Scroll down."""
        for _ in range(TROW):
            message = bytes([x >> 1 for x in message])
            self.fill(message)
            time.sleep(t)
        return message
    
    def fillfrombottomup(self, message: bytes, t: float = 0.2) -> bytes:
        """Fill from bottom up."""
        btm = 0
        for k in range(len(BITMASK)):
            btm += BITMASK[k]
            self.fill(message, btm)
            time.sleep(t)
        return message
    
    def fillfromtopdown(self, message: bytes, t: float = 0.2) -> bytes:
        """Fill from top down."""
        btm = 0
        for k in range(len(BITMASK) - 1, -1, -1):
            btm += BITMASK[k]
            self.fill(message, btm)
            time.sleep(t)
        return message
    
    def erasefromtopdown(self, message: bytes, t: float = 0.2) -> bytes:
        """Erase from top down."""
        btm = 127
        for k in range(len(BITMASK) - 1, -1, -1):
            btm -= BITMASK[k]
            self.fill(message, btm)
            time.sleep(t)
        return message
    
    def erasefrombottomup(self, message: bytes, t: float = 0.2) -> bytes:
        """Erase from bottom up."""
        btm = 127
        for k in range(len(BITMASK)):
            btm -= BITMASK[k]
            self.fill(message, btm)
            time.sleep(t)
        return message
    
    def fillrandomorder(self, message: bytes, t: float = 0.2) -> bytes:
        """Fill in random order."""
        btm = 0
        for k in range(8):
            if k < 6:
                btm = min(random.getrandbits(TROW), 127)
            else:
                btm = min(btm + random.getrandbits(TROW), 127)
            self.fill(message, btm)
            time.sleep(t)
            
        if btm < 127:
            self.fill(message)
            
        return message
    
    def eraserandomorder(self, message: bytes, t: float = 0.2) -> bytes:
        """Erase in random order."""
        btm = 127
        for k in range(8):
            if k < 6:
                btm = max(127 - random.getrandbits(TROW), 0)
            else:
                btm = max(btm - random.getrandbits(TROW), 0)
            self.fill(message, btm)
            time.sleep(t)
            
        if btm > 0:
            self.clear()
            
        return message
    
    def filltypewriter(self, message: bytes) -> None:
        """Fill typewriter style."""
        message_str = self.bytes_to_approx_string(message)
        
        for i in range(1, len(message_str) + 1):
            partial = message_str[:i]
            self.display_text(partial, justify='left')
            time.sleep(0.1)
    
    def fillmakerbot(self, message: bytes) -> None:
        """Fill makerbot style."""
        self.filltypewriter(message)
    
    def display_text_from_bytes(self, message: bytes) -> None:
        """Display text from bytes using perfect positioning."""
        padded_message = TCOLUMN * dict['space'] + message + TCOLUMN * dict['space']
        
        if len(message) <= 30:
            position = 103
        else:
            position = 90
        
        chunk = padded_message[position:position + TCOLUMN] 
        self.fill(chunk)
    
    def bytes_to_approx_string(self, message: bytes) -> str:
        """Approximate conversion from bytes back to string."""
        result = ""
        i = 0
        while i < len(message):
            found = False
            for char, char_bytes in dict.items():
                if char != 'space' and message[i:i+len(char_bytes)] == char_bytes:
                    result += char if char != 'space' else ' '
                    i += len(char_bytes)
                    found = True
                    break
            if not found:
                if message[i] == 0:
                    result += ' '
                else:
                    result += '?'
                i += 1
        return result
    
    def flip(self, message: str, d: int = 1) -> None:
        """Display text (improved version of original flip)."""
        self.display_text(message, justify='left')
    
    def pad(self, message: bytes, padsym: str = '', justify: int = 3) -> bytes:
        """Pad message."""
        return message

# Create global instance for backward compatibility (safe initialization)
working_core = None

def init_display(port: Optional[str] = None):
    """Initialize the display safely with auto-detection."""
    global working_core
    if working_core is None:
        try:
            working_core = WorkingFlipdotCore(port)
        except Exception as e:
            print(f"Could not initialize display: {e}")
            working_core = WorkingFlipdotCore.__new__(WorkingFlipdotCore)
            working_core.serial = None
    return working_core

def _ensure_initialized():
    """Lazily initialize the display on first use of a convenience function."""
    global working_core
    if working_core is None:
        init_display()

# Export functions for compatibility with existing code
def clear():
    _ensure_initialized()
    return working_core.clear()

def getbytes(message: str, delim: bytes = dict['space'], dmult: int = 1) -> bytes:
    _ensure_initialized()
    return working_core.getbytes(message, delim, dmult)

def fill(message: bytes, fillmask: int = 127) -> bytes:
    _ensure_initialized()
    return working_core.fill(message, fillmask)

def negative(message: bytes) -> bytes:
    _ensure_initialized()
    return working_core.negative(message)

def scrollleft(message: bytes, t: float = 0.2, d: int = 1, pausedelay: Optional[float] = None, o: bool = False) -> bytes:
    _ensure_initialized()
    return working_core.scrollleft(message, t, d, pausedelay, o)

def rotateleft(message: bytes, t: float = 0.2, d: int = 1) -> bytes:
    _ensure_initialized()
    return working_core.rotateleft(message, t, d)

def rotateright(message: bytes, t: float = 0.2, d: int = 1) -> bytes:
    _ensure_initialized()
    return working_core.rotateright(message, t, d)

def scrollup(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.scrollup(message, t)

def scrolldown(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.scrolldown(message, t)

def fillfrombottomup(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.fillfrombottomup(message, t)

def fillfromtopdown(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.fillfromtopdown(message, t)

def erasefromtopdown(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.erasefromtopdown(message, t)

def erasefrombottomup(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.erasefrombottomup(message, t)

def fillrandomorder(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.fillrandomorder(message, t)

def eraserandomorder(message: bytes, t: float = 0.2) -> bytes:
    _ensure_initialized()
    return working_core.eraserandomorder(message, t)

def filltypewriter(message: bytes) -> None:
    _ensure_initialized()
    return working_core.filltypewriter(message)

def fillmakerbot(message: bytes) -> None:
    _ensure_initialized()
    return working_core.fillmakerbot(message)

def flip(message: str, d: int = 1) -> None:
    _ensure_initialized()
    return working_core.flip(message, d)

def pad(message: bytes, padsym: str = '', justify: int = 3) -> bytes:
    _ensure_initialized()
    return working_core.pad(message, padsym, justify)

if __name__ == "__main__":
    init_display()
    print("Enhanced Cross-Platform Core System")
    print("="*40)
    
    try:
        print("Testing working core...")
        
        clear()
        time.sleep(1)
        
        print("1. Static text...")
        working_core.display_text("HELLO WORLD")
        time.sleep(3)
        
        print("2. Scroll text...")
        msg_bytes = getbytes("SCROLLING MESSAGE")
        scrollleft(msg_bytes, t=0.2)
        
        clear()
        print("✅ Enhanced core test complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
