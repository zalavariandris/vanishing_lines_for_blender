
def draw_background_images_panel(layout, camera):
    #####################
    # BACKGROUND IMAGES #
    #####################
    header, background_images_panel = layout.panel("Background_Images", default_closed=True)

    header.prop(camera.data, "show_background_images", text="Background Images")
    
    if background_images_panel:
        background_images_panel.operator("camera.add_bg_image", text="Add Background Image", icon='ADD')

        for i, bg_image in enumerate(camera.data.background_images):
            box = background_images_panel.box()
            header, bg_panel = box.panel(f"No{i}_vl_bg_image", default_closed=True)
            
            header.label(text=f"{bpy.path.basename(bg_image.image.filepath)}" if bg_image.image else "Not Set")
            icon = 'RESTRICT_VIEW_OFF' if bg_image.show_background_image else 'RESTRICT_VIEW_ON'
            header.prop(bg_image, "show_background_image", text="", icon=icon, emboss=False)
            
            # ASSIGN THE INDEX HERE
            op = header.operator("camera.remove_bg_image", text="", icon="X", emboss=False)
            op.index = i
            
            if bg_panel:
                col = bg_panel.column()
                col.use_property_split = True
                col.use_property_decorate = False
                col.row().prop(bg_image, "source", expand=True, text="Background Source")
                
                match bg_image.source:
                    case 'IMAGE':
                        col.template_ID(bg_image, "image", open="image.open")

                        has_data = True if bg_image.image else False
                        if has_data:
                            # 3. Main Settings (Opacity, Depth, Frame Method)
                            col.template_image(bg_image, "image", bg_image.image_user, compact=True)

                    case 'MOVIE_CLIP':
                        has_data = True if bg_image.clip else False
                        
                        col.prop(bg_image, "use_camera_clip", text="Active Clip")
                        col.template_movieclip(bg_image, "clip")
                        clip_user_col = col.column()
                        clip_user_col.enabled = has_data
                        clip_user_col.prop(bg_image.clip_user, "use_render_undistorted", text="Render Undistorted")
                        clip_user_col.prop(bg_image.clip_user, "proxy_render_size", text="Proxy Render Size")
                    
                if has_data:
                    ## BG SETTINGS
                    col.prop(bg_image.image, "use_view_as_render", text="View as Render")
                    col.prop(bg_image, "alpha", text="Opacity", slider=True)
                    # row = panel.row(align=True)
                    row = col.row(align=True)
                    row.prop(bg_image, "display_depth", text="Depth", expand=True)
                    row = col.row(align=True)
                    row.prop(bg_image, "frame_method", text="Frame Method", expand=True)

                    # row = col.row(align=True)
                    col.prop(bg_image, "offset", text="Offset")
                    col.prop(bg_image, "rotation", text="Rotation")
                    col.prop(bg_image, "scale", text="Scale")

                    flip_column = col.column(align=True, heading="Flip")
                    flip_column.prop(bg_image, "use_flip_x", text="X", toggle=False)
                    flip_column.prop(bg_image, "use_flip_y", text="Y", toggle=False)

                    # # 4. Background vs Foreground Toggle
                    # panel.prop(bg_image, "show_on_foreground", text="Front")

                    # # 5. Transformation Layout
                    # # Blender uses a column with a label and then a grid-like layout
                    # col = panel.column(align=True)
                    
                    # # Offset (X and Y)
                    # row = col.row(align=True)
                    # row.prop(bg_image, "offset", text="Offset")
                    
                    # # Rotation and Scale
                    # row = col.row(align=True)
                    # row.prop(bg_image, "rotation", text="Rotation")
                    # row.prop(bg_image, "scale", text="Scale")

                    # # 6. Flip Options (Horizontal / Vertical)
                    # row = panel.row(align=True)
                    # row.prop(bg_image, "show_expanded", text="Flip", icon='TRIA_DOWN' if bg_image.show_expanded else 'TRIA_RIGHT', emboss=False)
                    
                    # if bg_image.show_expanded:
                    #     sub = panel.column(align=True)
                    #     row = sub.row(align=True)
                    #     row.prop(bg_image, "use_flip_x", text="Flip Horizontal", toggle=True)
                    #     row.prop(bg_image, "use_flip_y", text="Flip Vertical", toggle=True)

                background_images_panel.separator()
                
def draw_solver_panel(layout, camera):
    ##########
    # SOLVER #
    ##########
    header, solver_panel = layout.panel("solver", default_closed=False)
    header_row = header.row()
    header_row.alert = camera.data.vl_settings.error_message != ""
    header_row.label(text="Solver")
    
    if solver_panel:


        # panel.prop(camera.data.vl_settings, "compute_space", text="Compute Space")
        # panel.separator()
        solver_panel.prop(camera.data.vl_settings, "mode", text="Mode")

        mode = camera.data.vl_settings.mode

        # match mode:
        #     case 'ONE_POINT':
        focal_length_row = solver_panel.row()
        focal_length_row.enabled = mode == 'ONE_POINT'
        focal_length_row.prop(camera.data, "lens", text="Focal Length")

        manual_principal_row = solver_panel.row()
        manual_principal_row.enabled = mode in {'ONE_POINT', 'TWO_POINT'}
        manual_principal_row.prop(camera.data.vl_settings, "enable_manual_principal", text="Manual Principal Point")

        # row = solver_panel.row()
        # row.enabled = mode in {'TWO_POINT', 'THREE_POINT'}

        solver_panel.separator()

        if error_msg:=camera.data.vl_settings.error_message:
            error_row = solver_panel.column()
            error_row.alert = True
            lines = str(error_msg).splitlines()
            for i, line in enumerate(lines):
                line_row = error_row.row()
                if i == 0:
                    line_row.label(text=line, icon='ERROR')
                else:
                    line_row.label(text=line)

def draw_reference_distance_panel(layout, camera):
    ######################
    # REFERENCE DISTANCE #
    ######################
    header, reference_distance_panel = layout.panel("reference_distance", default_closed=False)
    header.label(text="Reference Distance")
    if reference_distance_panel:
        reference_distance_panel.prop(camera.data.vl_settings, "scene_scale_mode", text="Scale Mode")
        reference_distance_panel.prop(camera.data.vl_settings, "scene_scale", text="Scene Scale")

        row = reference_distance_panel.row()
        row.enabled = camera.data.vl_settings.scene_scale_mode != 'ORIGIN'
        # row.prop(camera.data.vl_settings, "reference_distance", text="Reference Distance")
        row.prop(camera.data.vl_settings, "reference_distance_segment", text="Reference Distance Segment")
        reference_distance_panel.separator()

def draw_axis_assignment_panel(layout, camera):
    ###################
    # AXIS ASSIGNMENT #
    ###################
    header, axis_assignment_panel = layout.panel("axis_assignment", default_closed=True)
    header.label(text="Axis Assignment")

    if axis_assignment_panel:
        # panel.prop(camera.data.vl_settings, "floor", text="Floor", expand=False)
        row = axis_assignment_panel.row()
        row.prop(camera.data.vl_settings, "first_axis", text="First Axis", expand=False)
        row = axis_assignment_panel.row()
        incompatible_second_axis = camera.data.vl_settings.first_axis[0] == camera.data.vl_settings.second_axis[0]
        row.alert = incompatible_second_axis
        row.prop(camera.data.vl_settings, "second_axis", text="Second Axis", expand=False)
        axis_assignment_panel.separator()

        box = axis_assignment_panel.row()
        box.label(text="First Axis")
        col = box.column(align=True)
        
        row = col.row(align=True)
        row.prop_enum(camera.data.vl_settings, "first_axis", "X-")
        row.prop_enum(camera.data.vl_settings, "first_axis", "X+")

        row = col.row(align=True)
        row.prop_enum(camera.data.vl_settings, "first_axis", "Y-")
        row.prop_enum(camera.data.vl_settings, "first_axis", "Y+")

        row = col.row(align=True)
        row.prop_enum(camera.data.vl_settings, "first_axis", "Z-")
        row.prop_enum(camera.data.vl_settings, "first_axis", "Z+")

        box = axis_assignment_panel.row()
        box.label(text="Second Axis")
        col = box.column(align=True)
        
        row = col.row(align=True)
        row.enabled = not camera.data.vl_settings.first_axis.startswith("X")
        row.prop_enum(camera.data.vl_settings, "second_axis", "X-")
        row.prop_enum(camera.data.vl_settings, "second_axis", "X+")

        row = col.row(align=True)
        row.enabled = not camera.data.vl_settings.first_axis.startswith("Y")
        row.prop_enum(camera.data.vl_settings, "second_axis", "Y-")
        row.prop_enum(camera.data.vl_settings, "second_axis", "Y+")


        row = col.row(align=True)
        row.enabled = not camera.data.vl_settings.first_axis.startswith("Z")
        row.prop_enum(camera.data.vl_settings, "second_axis", "Z-")
        row.prop_enum(camera.data.vl_settings, "second_axis", "Z+")

        # col.prop_enum(camera.data.vl_settings, "second_axis", text="Second Axis", expand=False)
        # col.prop_enum(camera.data.vl_settings, "third_axis", text="Third Axis", expand=False)
        # row = panel.row(align=False)
        # row.prop(camera.data.vl_settings, "first_axis_assignment", text="1st Axis", expand=True)
        # row.prop(camera.data.vl_settings, "first_axis_sign", text="1st Sign", expand=True)
        # row = panel.row(align=True)
        # row.prop(camera.data.vl_settings, "second_axis_assignment", text="2nd Axis", expand=True)
        # panel.separator()

def draw_coordinates_panel(layout, camera):
    ##################
    # CONTROL POINTS #
    ##################
    header, coordinates_panel = layout.panel("control_points", default_closed=True)
    header.label(text="Coordinates")

    def prop_point(layout, data, prop, text):
        col = layout.column(align=True, heading=text)
        col.prop(data, prop, index=0, text=f"{text} X")
        col.prop(data, prop, index=1, text="Y")

    if coordinates_panel:
        col = coordinates_panel.column()
        col.use_property_split = True
        col.use_property_decorate = False

        # origin
        prop_point(col, camera.data.vl_settings, 'origin', "Origin")
        prop_point(col, camera.data.vl_settings, 'principal', "Principal")

        for axis_idx, (axis_label, lines) in enumerate([
            ("1st Axis", camera.data.vl_settings.first_vanishing_lines), 
            ("2nd Axis", camera.data.vl_settings.second_vanishing_lines),
            ("3rd Axis", camera.data.vl_settings.third_vanishing_lines),
        ]):
            col.separator()
            # row = panel.row(align=True)
            # panel.label(text=label)
            for line_idx, line in enumerate(lines):
                row = col.row()
                row.prop(line, 'start', text=f"{ f'{axis_label} ' if line_idx == 0 else ' '}" + f"#{line_idx}")
                row.prop(line, "end",   text="")

        coordinates_panel.separator()
