# PyGame Vector Racer 2026

A high-speed, lo-fi pseudo-3D racer built with PyGame.

This Python script implements a fast racing game using pygame that utilizes a custom 3D projection engine to render a wireframe/polygonal/vector world.

The game features a "big curve" tile system for smooth track transitions, a barrel roll mechanic via camera roll manipulation, and various decorative 3D structures like geodesic domes, skyscrapers, and brutalist tunnels. It includes high-score persistence via a text file, dynamic motion blur based on ship velocity. Support of keyboard and xbox compatible controller.
It is a bit fun to chase a highscore but do not expect too much.

# Physics & Controls
- Space to boost
- Arrows or WASD to steer
- Stop boosting right before curves!
- **Drift System:** The ship physics allow for lateral sliding, enabling players to "drift" through corners to maintain momentum.
- **Verticality:** Players can utilize ramps (`r`) to jump between track segments or over voids.
- **Joystick Support:** Fully optimized for Xbox/X-Input controllers.
  - **Left Stick / D-Pad:** Steering
  - **Button X:** Boost
  - **Button A:** Barrel Roll while jumping
  - **Start Button:** Exit Race

## Intro
This project was **"vibe coded"** over the course of a few evenings. 
The goal was to capture the high-velocity feel of early 32-bit era racers.

## Music
The accompanying soundtracks were composed in FL Studio providing the rhythmic foundation and atmospheric energy that defines the gameplay experience.

## Technical Details

### Resolution & Aspect Ratio
The game runs at an internal resolution of **512x288**. 
- This is a true **16:9 widescreen** aspect ratio.
- By using a low internal resolution scaled to fill the screen, we achieve a retro "pixelated" look while maintaining a modern field of view (FOV).

### Filtering & Aesthetic
The demo utilizes hardware-accelerated scaling via SDL2 hints.
- **Anisotropic Filtering (Level 2):** Unlike standard bilinear filtering which can blur textures at sharp angles, anisotropic filtering keeps the track textures sharp as they recede toward the horizon.

### Map System
Tracks are loaded from simple `.txt` files located in the `levels/` directory. 
- `-` / `|`: Standard Road
- `c`: Checkpoints
- `r`: Ramps for jumping
- `_`: Boost Pads
- `1234` Small curves
- `5678` Big curves, use blocks of 4, see usage in demo levels
- `B`: Tunnel south / north
- `#`: Building (deco)
- `0`: Pyramid (deco)
- `%`: 3d mesh building (deco)

See example levels.

## Requirements
- Python 3.x
- Pygame 2.x

## How to Run
1. Ensure your music is in the `music/` folder and sounds are in `sounds/`.
2. Place your level files in the `levels/` folder as .txt files, see examples.
3. Run: `python xyz.py`, Python 3.12+ recommended or use `run.sh`

## License
This demo, including the maps and music and sounds, is open-source (MIT license).
Feel free to fork, modify, and build your own retro racers!

