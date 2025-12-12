# Vanishing Lines _for Blender_

A Blender add-on for aligning your camera’s perspective using vanishing lines.
__work in progress__

![capture](docs/rome_lake_vanishing_lines.gif)

## Usage
- when the addon is installed, open the VL sidepanel and click on Start Vanishing Lines Button.
- add a background to the camera
- select 1,2 or 3 mode vanishing points
- move the vanishing line endpoints to match the camera to the background


## TODO, ChangeLog
### **0.7.*
- [ ] REFACTOR coordinate space conversion
- [ ] FIX Portrait aspect
- [ ] ADD axis assignment

### **0.7.*
- [ ] ADD draw antialiased lines, and circle shader

### **0.7.*
- [ ] ADD align tracked camera
- [ ] ADD animation
- [ ] show errors in the UI, and phrase them to be helpful.
- [ ] FIX when a line is zero length, there is an unhandled error

### **0.7.*
- [ ] FIX🛠️ while dragging controlpoints, move them with mouse instead of setting the coords to the mousepos
- [ ] ADD slow point drag with SHIFT
- [ ] ADD Loupe

### **0.7.4
- [ ] Add arbitrary axis to measure distance.
- [X] ADD set scale by camera to origin distance.
- [X] FIX reference distance mouse handling.

### **0.7.3
- [x] ADD reference distance controls to the viewport
- [x] FIX draw extended vanishing lines with new ControlPoints
- [x] REFACTOR: vl_params now use FloatVectors to represent points, and also Operator now mostly uses tuples instead of a glm.vec2
- [x] ADD hover color for new controlopoints
- [x] FIX🔥 quad mode for new Control Points
- [x] 🔧 refactor ControlPoints

### **0.7.2 - 2025-11-28**
- [x] FIX use _centered_, _square_ (fit to output rectangle) normalized coordinates.
- [x] FIX quad mode
- [x] refactor draw code to DrawLayer class
- [x] FIX Active and HOVER control point color
- [x] ADD draw vanishing lines extended to vanishing points
- [x] ADD draw horizon

### **0.7.2 - 2025-11-24**
- [x] ADD support three-point perspective mode
- [x] ADD manual principal point
- [x] FIX quad mode

### **0.7.1 - 2025-11-24**
**Added**
- [x] ADD quad mode for two-point perspective mode.
- [x] ADD manual principal point to TWO and THREE-Point mode
- [x] FIX use principal point for til_shift, and apply to blender camera
- [x] ADD solve three vanishing point mode
- [x] FIX mouse hittest: use the screen coords for mouse hittest
- [x] FIX start running VL modal operator
- [x] ADD solve two vanishing point
- [x] ADD solve single vanishing point