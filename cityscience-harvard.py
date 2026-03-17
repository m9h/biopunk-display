#!/usr/bin/env python3
"""
Enhanced Biopunk Playlist with Multi-Size Text

Updated mainplaylist-biopunk.py that uses the working double-height text system
for dramatic visual impact and varied text sizing.
"""

from __future__ import absolute_import
from video import video
from games.scavengerhunt import scavengerhunt
import time

# Import the working double-height system
from simple_working_double_height import (
    single_text, double_text, wide_text,
    double_flash, wide_dramatic, scroll_double_text,
    impact_text, smart_text
)

__author__ = 'boselowitz'

# ============================================================================
# ENHANCED BIOPUNK PLAYLIST with Multi-Size Text
# ============================================================================

ENHANCED_BIOPUNK_PLAYLIST = [
    # Dramatic opening sequence
    {"function": lambda: wide_dramatic("Hi!"), "parameter": None, "description": "Maximum impact opening"},
    {"function": lambda: time.sleep(0.5), "parameter": None, "description": "Brief pause"},
    {"function": lambda: wide_dramatic("Malls"), "parameter": None, "description": "Second impact word"},
    
    # Video transition  
    {"function": video.display_video, "parameter": "barber-pole-10s.mov", "description": "Visual break"},
    
    # Information sequence with varied sizing
    {"function": lambda: double_flash("Frontier"), "parameter": None, "description": "Alert-style emphasis"},
    {"function": lambda: single_text("cityscience workshop"), "parameter": None, "description": "Detailed info"},
    {"function": lambda: time.sleep(2), "parameter": None, "description": "Read time"},
    
    # Build excitement
    {"function": lambda: impact_text("Artists"), "parameter": None, "description": "Auto-sized impact"},
    {"function": lambda: scroll_double_text("Artificial Intelligence"), "parameter": None, "description": "Scrolling emphasis"},
    
    # Video break
 #   {"function": video.display_video, "parameter": "block-game", "description": "Game visual"},
    
    # Climax sequence
    {"function": lambda: double_text("FUTURE"), "parameter": None, "description": "Big concept"},
    {"function": lambda: time.sleep(1), "parameter": None, "description": "Pause for impact"},
    {"function": lambda: wide_text("DNA"), "parameter": None, "description": "Core concept - wide"},
    {"function": lambda: time.sleep(2), "parameter": None, "description": "Hold for impact"},
    
    # Technical details
    {"function": lambda: single_text("Save the city"), "parameter": None, "description": "Technical readout"},
    {"function": lambda: double_flash("TODAY"), "parameter": None, "description": "Status alert"},
    
    # Grand finale
    {"function": lambda: wide_dramatic("GO"), "parameter": None, "description": "Action call"},
    {"function": lambda: scroll_double_text("EVOLUTION INITIATED"), "parameter": None, "description": "Final message"},
]

# ============================================================================
# ALTERNATIVE PLAYLISTS for Different Moods
# ============================================================================

# High-impact version - maximum visual drama
HIGH_IMPACT_BIOPUNK = [
    {"function": lambda: wide_dramatic("BIO"), "parameter": None},
    {"function": lambda: wide_dramatic("PUNK"), "parameter": None},
    {"function": lambda: wide_text("HACK"), "parameter": None},
    {"function": lambda: wide_flash("DNA"), "parameter": None},
    {"function": video.display_video, "parameter": "barber-pole-10s.mov"},
    {"function": lambda: wide_dramatic("GO"), "parameter": None},
    {"function": lambda: wide_text("NOW"), "parameter": None},
]

# Information-heavy version - more content, varied sizing
INFO_HEAVY_BIOPUNK = [
    {"function": lambda: double_text("CITY SCIENCE"), "parameter": None},
    {"function": lambda: single_text("biotechnology research facility online"), "parameter": None},
    {"function": lambda: double_flash("ALERT"), "parameter": None},
    {"function": lambda: single_text("genetic sequencing in progress"), "parameter": None},
    {"function": lambda: scroll_double_text("DNA ANALYSIS COMPLETE"), "parameter": None},
    {"function": video.display_video, "parameter": "block-game"},
    {"function": lambda: single_text("neural enhancement protocols loaded"), "parameter": None},
    {"function": lambda: impact_text("READY"), "parameter": None},
    {"function": lambda: single_text("awaiting user command"), "parameter": None},
]

# Cinematic version - like a movie trailer
CINEMATIC_BIOPUNK = [
    {"function": lambda: single_text("in a world where"), "parameter": None},
    {"function": lambda: time.sleep(2), "parameter": None},
    {"function": lambda: double_text("BIOLOGY"), "parameter": None},
    {"function": lambda: time.sleep(1.5), "parameter": None},
    {"function": lambda: single_text("meets"), "parameter": None},
    {"function": lambda: time.sleep(1), "parameter": None},
    {"function": lambda: double_text("TECHNOLOGY"), "parameter": None},
    {"function": lambda: time.sleep(2), "parameter": None},
    {"function": video.display_video, "parameter": "barber-pole-10s.mov"},
    {"function": lambda: single_text("one hacker"), "parameter": None},
    {"function": lambda: time.sleep(1.5), "parameter": None},
    {"function": lambda: double_flash("WILL"), "parameter": None},
    {"function": lambda: single_text("change everything"), "parameter": None},
    {"function": lambda: time.sleep(2), "parameter": None},
    {"function": lambda: wide_dramatic("BIOPUNK"), "parameter": None},
]

# Fast-paced action version
ACTION_BIOPUNK = [
    {"function": lambda: impact_text("HACK"), "parameter": None},
    {"function": lambda: impact_text("SPLICE"), "parameter": None},
    {"function": lambda: impact_text("CODE"), "parameter": None},
    {"function": lambda: double_flash("BREACH"), "parameter": None},
    {"function": lambda: scroll_double_text("SYSTEM COMPROMISED"), "parameter": None},
    {"function": video.display_video, "parameter": "block-game"},
    {"function": lambda: wide_text("RUN"), "parameter": None},
    {"function": lambda: double_flash("NOW"), "parameter": None},
]

# ============================================================================
# PLAYLIST SELECTION and EXECUTION
# ============================================================================

def select_biopunk_playlist():
    """Interactive playlist selection."""
    playlists = {
        "1": ("Enhanced Biopunk (Recommended)", ENHANCED_BIOPUNK_PLAYLIST),
        "2": ("High Impact", HIGH_IMPACT_BIOPUNK),
        "3": ("Information Heavy", INFO_HEAVY_BIOPUNK),
        "4": ("Cinematic Trailer", CINEMATIC_BIOPUNK),
        "5": ("Fast Action", ACTION_BIOPUNK),
    }
    
    print("\n🧬 Biopunk Playlist Options:")
    print("=" * 50)
    for key, (name, playlist) in playlists.items():
        print(f"{key}. {name} ({len(playlist)} items)")
    
    choice = input("\nSelect playlist (1-5): ").strip()
    
    if choice in playlists:
        name, playlist = playlists[choice]
        print(f"\n🎬 Loading: {name}")
        return playlist, name
    else:
        print("Invalid choice, using Enhanced Biopunk")
        return ENHANCED_BIOPUNK_PLAYLIST, "Enhanced Biopunk"

def execute_playlist_item(item, item_num, total_items):
    """Execute a single playlist item with error handling."""
    try:
        description = item.get("description", "")
        print(f"[{item_num}/{total_items}] {description}")
        
        if item.get("parameter") is not None:
            item["function"](item["parameter"])
        else:
            item["function"]()
            
        # Brief pause between items for smooth flow
        time.sleep(0.3)
        
    except Exception as e:
        print(f"Error executing item {item_num}: {e}")
        # Clear display on error and continue
        try:
            from simple_working_double_height import clear
            clear()
        except:
            pass
        time.sleep(1)

def run_biopunk_playlist(playlist, playlist_name, loop=True):
    """Run the selected biopunk playlist."""
    print(f"\n🎮 Running: {playlist_name}")
    print("=" * 60)
    print("Press Ctrl+C to stop")
    
    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            if loop:
                print(f"\n🔄 Cycle {cycle_count}")
            
            for i, item in enumerate(playlist, 1):
                execute_playlist_item(item, i, len(playlist))
            
            if not loop:
                break
            
            # Brief pause between cycles
            print("🔄 Cycle complete, restarting...")
            time.sleep(2)
            
    except KeyboardInterrupt:
        print(f"\n\n🛑 {playlist_name} stopped by user")
        try:
            from simple_working_double_height import clear
            clear()
        except:
            pass

def demo_text_sizes():
    """Demonstrate all text sizes with biopunk theme."""
    print("\n🎨 Biopunk Text Size Demo")
    print("=" * 40)
    
    demos = [
        ("Single Height", lambda: single_text("biotechnology")),
        ("Double Height", lambda: double_text("DIGITAL")),
        ("Wide Text", lambda: wide_text("DNA")),
        ("Double Flash", lambda: double_flash("HACK")),
        ("Wide Dramatic", lambda: wide_dramatic("BIO")),
        ("Scroll Double", lambda: scroll_double_text("EVOLUTION")),
        ("Impact Auto-Size", lambda: impact_text("PUNK")),
        ("Smart Size", lambda: smart_text("GENETIC CODE")),
    ]
    
    for name, demo_func in demos:
        print(f"\n▶️  {name}")
        demo_func()
        time.sleep(1.5)
        try:
            from simple_working_double_height import clear
            clear()
        except:
            pass
        time.sleep(0.5)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("🧬 Enhanced Biopunk Playlist System")
    print("=" * 60)
    print("Now with dramatic multi-size text effects!")
    
    mode = input("\nChoose mode:\n1. Run playlist\n2. Demo text sizes\n3. Interactive selection\nChoice (1-3): ").strip()
    
    if mode == "1":
        # Quick start - run enhanced playlist
        print("\n🚀 Quick Start: Running Enhanced Biopunk Playlist")
        run_biopunk_playlist(ENHANCED_BIOPUNK_PLAYLIST, "Enhanced Biopunk", loop=True)
        
    elif mode == "2":
        # Demo all text sizes
        demo_text_sizes()
        print("\n✅ Demo complete!")
        
    elif mode == "3":
        # Interactive selection
        playlist, name = select_biopunk_playlist()
        
        loop_choice = input("\nLoop playlist continuously? (y/n): ").strip().lower()
        loop = loop_choice == 'y'
        
        run_biopunk_playlist(playlist, name, loop=loop)
        
    else:
        print("Invalid choice, running Enhanced Biopunk Playlist...")
        run_biopunk_playlist(ENHANCED_BIOPUNK_PLAYLIST, "Enhanced Biopunk", loop=True)

# ============================================================================
# INTEGRATION NOTES
# ============================================================================
"""
🔧 To integrate this with your existing system:

1. REPLACE your mainplaylist-biopunk.py with this file

2. OR add these imports to your existing playlist:
   from simple_working_double_height import (
       single_text, double_text, wide_text, double_flash, 
       wide_dramatic, scroll_double_text, impact_text
   )

3. UPDATE your playlist items:
   OLD: {"function": transition.righttoleft, "parameter": "bioPunk"}
   NEW: {"function": lambda: double_text("BIOPUNK"), "parameter": None}

4. MIX different text sizes for visual variety:
   - wide_text() for maximum impact (1-3 chars)
   - double_text() for emphasis (4-6 chars)  
   - single_text() for information (7+ chars)
   - impact_text() for automatic sizing
   - scroll_double_text() for scrolling emphasis
   - double_flash() for alerts/attention

5. COMBINE with your existing video content:
   {"function": video.display_video, "parameter": "your-video.mov"}

6. RUN with: python enhanced_biopunk_playlist.py

The system now provides cinematic-quality text effects that match
the dramatic aesthetic of your biopunk theme!
"""
