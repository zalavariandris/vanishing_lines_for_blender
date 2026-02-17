![capture](docs/assets/rome_lake_vanishing_lines.gif)

# Vanishing Lines _for Blender_
A Blender add-on for aligning cameras to images using vanishing lines.


__v0.8-beta__

_work in progress_

## Quick Start Guide (v0.8-beta)

1. **Set up your scene**  
   Add a background image to your camera view  
   *(Camera Properties → Background Images)*

2. **Start the tool**  
   In the 3D Viewport, open the **View** menu and select **Vanishing Lines**.

3. **Align the vanishing lines**  
   Drag the vanishing line endpoints to align with parallel lines in your background image.  
   The camera updates automatically as you adjust them.

4. **Choose a perspective mode**  
   Select the mode that best fits your scene:
   - **1-Point** - One vanishing point (e.g., hallways or roads).  
     *Note: Field of view cannot be calculated automatically in 1-point mode, so set it manually in the Camera Data panel.*
   - **2-Point** - Two vanishing points (e.g., building corners).
   - **3-Point** - Adds control over the third axis (principal point / tilt-shift), useful for off-center cameras.

5. **Fine-tune**
   - Adjust the **Reference Distance** to define scene scale
   - Right-click to open the context menu for additional **options**
   - Use the keyboard shortcuts shown in the status bar at the bottom of the viewport

6. **Finish**
   - Press `Enter` to confirm
   - Press `Esc` to cancel

---

## Mouse Gestures

- `Left Click` + `Drag` – Move vanishing line endpoints
- `Mouse Wheel` – Zoom camera view
- `Ctrl` + `Mouse Wheel` – Adjust reference distance (scene scale)
- `Ctrl` + `Middle Mouse Drag` – Move camera origin
- `Ctrl` + `Alt` + `Middle Mouse Drag` – Adjust focal length *(1-point mode only)*
- `Right Click` – Open context menu

## Keyboard Shortcuts

- `1` `2` `3` - Switch to 1-point, 2-point, or 3-point perspective mode
- `Q` - Toggle quad mode *(2-point and 3-point modes)*
- `R` - Cycle through scale modes (Origin, Reference Distance, etc.)
- `Enter` - Finish and apply changes
- `Esc` - Exit tool

*Note: All shortcuts are displayed in the status bar at the bottom of the viewport while the tool is active.*
