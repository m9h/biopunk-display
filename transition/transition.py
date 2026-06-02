#!/usr/bin/env python3
"""
Working Transitions Module

Updated transitions that use the working core system with perfect positioning.
"""

import time
import random as _random  # aliased: a transition function below is named `random` and would shadow the module
from core.core import working_core, getbytes, scrollleft, fillfrombottomup, fillfromtopdown, erasefromtopdown, erasefrombottomup, fillrandomorder, eraserandomorder, clear

def upnext(message: str):
    """Up next announcement with flashing."""
    for j in range(3):
        for i in range(5):
            working_core.display_text("UP NEXT", justify='center')
            time.sleep(0.25)
            clear()
            time.sleep(0.2)
            working_core.display_text("UP NEXT", justify='center')
            time.sleep(0.1)
            clear()
            time.sleep(0.2)
        
        # Show the message
        if j == 2:
            scrollleft(getbytes(message), t=0.15, d=3)
        else:
            msg_bytes = getbytes(message)
            scrollleft(msg_bytes, t=0.15, d=3)

def righttoleft(message: str):
    """Simple right to left scroll."""
    msg_bytes = getbytes(message)
    scrollleft(msg_bytes, t=0.2)

def pop(message: str):
    """Flashing pop effect."""
    clear()
    for i in range(7):
        working_core.display_text(message, justify='center')
        time.sleep(0.25)
        clear()
        time.sleep(0.25)
    clear()
    time.sleep(1)

def amdissolve(message: str):
    """AMD dissolve effect."""
    msg_bytes = getbytes(message)
    working_core.display_text_from_bytes(msg_bytes)
    time.sleep(2)
    eraserandomorder(msg_bytes)

def dissolve(message: str):
    """Dissolve effect."""
    msg_bytes = getbytes(message)
    working_core.display_text_from_bytes(msg_bytes)
    time.sleep(2)
    eraserandomorder(msg_bytes)

def magichat(message: str):
    """Magic hat effect with multi-screen support."""
    # Split long messages into screens
    long_string = message
    screens = []
    more = True
    
    while more:
        if len(long_string) <= 21:
            screens.append(long_string)
            more = False
            break
        
        # Find good break point
        for i in range(21, 0, -1):
            if long_string[i] == " ":
                test_bytes = getbytes(long_string[:i])
                if len(test_bytes) < 60:  # Fits reasonably on display
                    screens.append(long_string[:i])
                    long_string = long_string[i+1:]
                    break
    
    for screen in screens:
        msg_bytes = getbytes(screen)
        fillfrombottomup(msg_bytes, t=0.3)
        time.sleep(1)
        if screen != screens[-1]:  # Not last screen
            erasefromtopdown(msg_bytes, t=0.2)

def adventurelook(message: str):
    """Adventure game style display."""
    # Split message similar to magichat
    long_string = message
    screens = []
    more = True
    
    while more:
        if len(long_string) <= 21:
            screens.append(long_string)
            more = False
            break
        
        for i in range(21, 0, -1):
            if long_string[i] == " ":
                test_bytes = getbytes(long_string[:i])
                if len(test_bytes) < 60:
                    screens.append(long_string[:i])
                    long_string = long_string[i+1:]
                    break
    
    for i, screen in enumerate(screens):
        msg_bytes = getbytes(screen)
        fillfrombottomup(msg_bytes, t=0.2)
        
        if i == len(screens) - 1:
            time.sleep(5)  # Longer pause for last screen
        else:
            time.sleep(1)
            erasefrombottomup(msg_bytes, t=0.2)

def plain(message: str):
    """Plain scrolling."""
    msg_bytes = getbytes(message)
    scrollleft(msg_bytes, t=0.2)

def typewriter(message: str):
    """Typewriter effect."""
    for i in range(1, len(message) + 1):
        partial = message[:i]
        working_core.display_text(partial, justify='left')
        time.sleep(0.1)
    time.sleep(2)

def matrix_effect(message: str):
    """Matrix digital rain effect."""
    # Matrix effect with random characters
    for _ in range(15):
        random_text = ''.join(_random.choice('01') for _ in range(10))
        working_core.display_text(random_text, justify='left')
        time.sleep(0.1)
    
    clear()
    time.sleep(0.5)
    righttoleft(message)

def bounce(message: str):
    """Bouncing text effect."""
    msg_bytes = getbytes(message)
    
    for _ in range(6):
        working_core.display_text_from_bytes(msg_bytes)
        time.sleep(0.2)
        clear()
        time.sleep(0.1)
        working_core.display_text_from_bytes(msg_bytes)
        time.sleep(0.2)

def slide_in_left(message: str):
    """Slide in from left using scroll effect."""
    # Use partial scroll to simulate sliding
    msg_bytes = getbytes(' ' * 10 + message)  # Pad with spaces
    scrollleft(msg_bytes, t=0.05, d=2)

# Transition lists
TRANSITION_LIST = [plain, upnext, magichat, adventurelook, typewriter, matrix_effect, bounce]
GENERAL_TRANSITION_LIST = [plain, magichat, adventurelook, typewriter]
ANNOUNCEMENT_TRANSITION_LIST = [upnext, pop, bounce]
SPECIAL_TRANSITION_LIST = [dissolve, matrix_effect, slide_in_left]

def random_pick(pick_list):
    """Randomly pick from transition list."""
    return _random.choice(pick_list)

def random(message: str):
    """Random transition."""
    random_pick(TRANSITION_LIST)(message)

def randomgeneral(message: str):
    """Random general transition."""
    random_pick(GENERAL_TRANSITION_LIST)(message)

def randomannouncement(message: str):
    """Random announcement transition."""
    random_pick(ANNOUNCEMENT_TRANSITION_LIST)(message)

def randomspecial(message: str):
    """Random special transition."""
    random_pick(SPECIAL_TRANSITION_LIST)(message)

# Test function
def test_transitions():
    """Test all transitions."""
    transitions = [
        ("Plain", plain),
        ("Right to Left", righttoleft), 
        ("Pop", pop),
        ("Magic Hat", magichat),
        ("Adventure Look", adventurelook),
        ("Typewriter", typewriter),
        ("Matrix Effect", matrix_effect),
        ("Bounce", bounce),
        ("Up Next", upnext)
    ]
    
    test_message = "HELLO WORLD"
    
    for name, transition_func in transitions:
        print(f"\nTesting: {name}")
        try:
            transition_func(test_message)
            time.sleep(1)
            clear()
            time.sleep(0.5)
            print(f"✅ {name} completed")
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            clear()

if __name__ == "__main__":
    print("Working Transitions Test")
    print("="*30)
    test_transitions()
