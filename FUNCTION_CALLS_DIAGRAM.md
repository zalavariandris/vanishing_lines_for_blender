# Vanishing Lines for Blender - Function Call Diagram

## Main Entry Points and Call Flow

```mermaid
graph TD
    A["Blender Event<br/>Modal Operator Invoked"] -->|invoke()| B["VIEW3D_OT_vl_solve_orientation"]
    
    B -->|modal()| C["Handle User Input<br/>Mouse/Keyboard Events"]
    C -->|mouse drag| D["Draw Vanishing Lines<br/>on View3D"]
    C -->|settings change| E["update_solve()"]
    
    E -->|calls| F["solver.core.solve()"]
    F -->|mode matching| G{"Solve Mode"}
    
    G -->|OneVP| H["compute_vanishing_point()"]
    G -->|TwoVP| H
    G -->|ThreeVP| H
    
    H -->|intersect lines| I["utils.least_squares_intersection()"]
    
    G -->|OneVP| J["orientation_from_one_vanishing_point()"]
    G -->|TwoVP| K["orientation_from_two_vanishing_points()"]
    G -->|ThreeVP| L["orientation_from_three_vanishing_points()"]
    
    J -->|returns| M["projection, view matrices"]
    K -->|returns| M
    L -->|returns| M
    
    M -->|validate| N["utils.validate_orthogonality()"]
    N -->|invalid| O["utils.apply_gram_schmidt_orthogonalization()"]
    
    M -->|adjust position| P["adjust_position_to_origin()"]
    P -->|returns| Q["updated view matrix"]
    
    Q -->|if reference axis| R["adjust_scale_to_reference_distance()"]
    R -->|returns| S["scaled view matrix"]
    
    S -->|assign axes| T["adjust_axis_assignment()"]
    T -->|returns| U["axis-assigned view matrix"]
    
    U -->|translate| V["glm.translate()"]
    V -->|returns final| W["Final: projection, view matrices"]
    
    W -->|apply to camera| X["vl_utils.apply_solver_results_to_blender_camera()"]
    X -->|set camera transform| Y["Blender Camera Object Updated"]
    
    W -->|apply to view3d| Z["vl_utils.apply_solver_results_to_view3d()"]
    Z -->|set view3d transform| AA["View3D Viewport Updated"]
    
    E -->|draw UI| AB["View3dGUI class"]
    AB -->|render| AC["View3dPainter.draw_*()"]
    AC -->|viewport draw| AD["Display Vanishing Lines & Controls"]
```

---

## Solver Core Components

```mermaid
graph LR
    subgraph Main["solve() - Main Solver Function"]
        A1["Input:<br/>- vanishing_lines<br/>- focal_length<br/>- principal_point<br/>- reference_axis<br/>- mode"]
        A2["Compute Vanishing Points"]
        A3["Solve Orientation"]
        A4["Validate & Orthogonalize"]
        A5["Adjust Position"]
        A6["Adjust Scale"]
        A7["Adjust Axis Assignment"]
        A8["Output:<br/>projection_matrix<br/>view_matrix"]
        
        A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7 --> A8
    end
    
    subgraph Helpers["Helper Functions"]
        H1["compute_vanishing_point()"]
        H2["orientation_from_one_vp()"]
        H3["orientation_from_two_vp()"]
        H4["orientation_from_three_vp()"]
        H5["adjust_position_to_origin()"]
        H6["adjust_scale_to_reference_distance()"]
        H7["adjust_axis_assignment()"]
    end
    
    subgraph Utils["Utils Functions"]
        U1["least_squares_intersection()"]
        U2["validate_orthogonality()"]
        U3["apply_gram_schmidt_orthogonalization()"]
        U4["cast_ray()"]
        U5["intersect_ray_with_plane()"]
    end
    
    A2 --> H1
    A3 --> H2
    A3 --> H3
    A3 --> H4
    A5 --> H5
    A6 --> H6
    A7 --> H7
    
    H1 --> U1
    H5 --> U4
    H5 --> U5
    A4 --> U2
    A4 --> U3
```

---

## Operator Flow

```mermaid
graph TD
    OP["VIEW3D_OT_vl_solve_orientation<br/>Operator"]
    
    OP -->|invoke| INV["Initialize Context<br/>- Get camera object<br/>- Save camera state<br/>- Create View3dGUI"]
    
    INV -->|register| DRAW["Register draw_handler<br/>for viewport updates"]
    
    DRAW -->|subscribe| MSG["Subscribe to camera<br/>lens changes via msgbus"]
    
    MSG -->|modal_handler_add| MODAL["Enter Modal Mode"]
    
    MODAL -->|loop| EVENT["Wait for Events"]
    
    EVENT -->|mouse move| MM["update_solve()"]
    EVENT -->|mouse click| MC["Handle Line Drawing<br/>Edit vanishing lines"]
    EVENT -->|key press| KP{"Which Key?"}
    
    KP -->|ESC| CANCEL["cancel()<br/>- Restore camera state<br/>- Cleanup resources"]
    KP -->|ENTER| FINISH["Finalize<br/>- Keep camera changes"]
    
    MM --> UPDATE["Apply solver results<br/>to camera/viewport"]
    UPDATE --> REDRAW["tag_redraw()"]
    REDRAW --> EVENT
    
    MC --> UPDATE
    
    CANCEL -->|return| DONE1["CANCELLED"]
    FINISH -->|return| DONE2["FINISHED"]
```

---

## View3D UI/Drawing Flow

```mermaid
graph TD
    DRAW_HANDLER["draw_handler callback<br/>Runs every viewport draw"]
    
    DRAW_HANDLER -->|create| GUI["View3dGUI instance"]
    
    GUI -->|draw| POINTS["_ControlPointGizmo<br/>Vanishing line endpoints"]
    
    POINTS -->|render| PAINTER["View3dPainter"]
    
    PAINTER -->|draw| LINES["draw_lines()"]
    PAINTER -->|draw| CIRCLES["draw_circles()"]
    PAINTER -->|draw| TEXT["draw_text()"]
    PAINTER -->|draw| RECTS["draw_rectangles()"]
    
    LINES --> VP["Vanishing lines<br/>on screen"]
    CIRCLES --> CTRL["Control point circles"]
    TEXT --> LABEL["Point labels"]
    RECTS --> REF["Reference scale rect"]
    
    VP --> OUTPUT["Viewport Rendering"]
    CTRL --> OUTPUT
    LABEL --> OUTPUT
    REF --> OUTPUT
    
    GUI -->|handle input| MANIP["manipulate()<br/>Gizmo control"]
    
    MANIP -->|calc delta| DELTA["Mouse movement<br/>calculation"]
    
    DELTA -->|setter callback| PROPS["Update VL Properties<br/>vanishing_lines array"]
    
    PROPS --> TRIGGER["Trigger update_solve()"]
```

---

## Vanishing Point Computation

```mermaid
graph TD
    INPUT["List of 2D Lines<br/>[(x1,y1)-(x2,y2), ...]"]
    
    INPUT -->|convert| LINES["Convert to glm.vec2 pairs"]
    
    LINES -->|intersect| LSQ["least_squares_intersection()<br/>Find optimal intersection<br/>of all lines"]
    
    LSQ -->|compute| MIN["Minimize sum of<br/>perpendicular distances"]
    
    MIN -->|solve| VP["Vanishing Point (x, y)"]
    
    VP -->|validate| DIST["Check distance from<br/>principal point"]
    
    DIST -->|valid| OUT["Return vanishing point"]
    
    DIST -->|invalid| ERR["Raise VanishingLinesError"]
```

---

## Solver Mode Decision Tree

```mermaid
graph TD
    SOLVE["solve() receives mode parameter"]
    
    SOLVE -->|mode| MODE{"Which mode?"}
    
    MODE -->|OneVP| ONE["One Vanishing Point Mode"]
    MODE -->|TwoVP| TWO["Two Vanishing Point Mode"]
    MODE -->|ThreeVP| THREE["Three Vanishing Point Mode"]
    
    ONE -->|input| O_INPUT["first_vanishing_lines<br/>second_vanishing_lines<br/>focal_length f<br/>principal_point P"]
    
    TWO -->|input| T_INPUT["first_vanishing_lines<br/>second_vanishing_lines<br/>principal_point P<br/>viewport"]
    
    THREE -->|input| TH_INPUT["first_vanishing_lines<br/>second_vanishing_lines<br/>third_vanishing_lines<br/>viewport"]
    
    O_INPUT -->|compute vp1| COMP1["vp1 = compute_vanishing_point(first)"]
    T_INPUT -->|compute vps| COMP2["vp1, vp2 = compute_vanishing_points()"]
    TH_INPUT -->|compute vps| COMP3["vp1, vp2, vp3 = compute_vanishing_points()"]
    
    COMP1 -->|solve orientation| ORIENT1["orientation_from_one_vanishing_point()"]
    COMP2 -->|solve orientation| ORIENT2["orientation_from_two_vanishing_points()"]
    COMP3 -->|solve orientation| ORIENT3["orientation_from_three_vanishing_points()"]
    
    ORIENT1 -->|returns| MAT["projection, view"]
    ORIENT2 -->|returns| MAT
    ORIENT3 -->|returns| MAT
    
    MAT -->|post-process| POST["validate, adjust position,<br/>adjust scale, assign axes"]
```

---

## Key Data Structures

```mermaid
graph TD
    SUBGRAPH1["Input Data Structures"]
    
    VL["Line2<br/>= Tuple[Point2, Point2]<br/>= Tuple[Tuple[float,float],<br/>Tuple[float,float]]"]
    
    RECT["Rect<br/>x: float<br/>y: float<br/>width: float<br/>height: float"]
    
    AXIS["Axis enum<br/>PositiveX, NegativeX<br/>PositiveY, NegativeY<br/>PositiveZ, NegativeZ"]
    
    MODE["SolverMode enum<br/>OneVP, TwoVP, ThreeVP"]
    
    REFAX["ReferenceAxis enum<br/>X_Axis, Y_Axis, Z_Axis<br/>Screen"]
    
    SUBGRAPH2["Output Data Structures"]
    
    PROJ["projection: glm.mat4<br/>4x4 projection matrix"]
    
    VIEW["view: glm.mat4<br/>4x4 view/camera matrix"]
    
    PROPS["VL Properties<br/>mode: str<br/>fovx: float<br/>first_axis: Axis<br/>second_axis: Axis<br/>reference_scale_mode<br/>reference_screen_segment"]
```

---

## Exception Handling

```mermaid
graph TD
    ERRORS["Exception Classes"]
    
    BASE["SolverError<br/>base class"]
    
    VLE["VanishingLinesError<br/>- Parallel lines<br/>- Divergent lines<br/>- Invalid VP location"]
    
    AXE["AxisAssignmentError<br/>- Invalid axis pair"]
    
    BASE -->|inherits| VLE
    BASE -->|inherits| AXE
    
    CALLS["Functions that raise"]
    
    CALLS -->|compute_vanishing_point| VLE
    CALLS -->|orientation functions| VLE
    CALLS -->|adjust functions| AXE
    
    HANDLE["Operator handles<br/>with try/catch"]
    
    HANDLE -->|shows error| ERROR_MSG["Display error message<br/>in status text"]
```

