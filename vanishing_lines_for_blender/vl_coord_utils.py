import math
from typing import Tuple, Literal

def get_view3d_zoom_to_fac(camzoom: float) -> float:
    """Blender internal zoom conversion
    this is some magic formula apparently used by Blender to convert the 3D view zoom level
    """
    return ((math.sqrt(2.0) + camzoom / 50.0) ** 2) / 4.0

def project_output_to_region(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        output_coords: Tuple[float, float]) -> Tuple[float, float]:
    """Convert output frame coordinates to region space using cached viewport state"""
    x, y = output_coords
    assert isinstance(x, (int, float)), f"got: {x}"
    assert isinstance(y, (int, float)), f"got: {y}"

    resolution_x = output_size[0]
    resolution_y = output_size[1]
    
    # Convert image pixels to centered NDC (-1..1)
    x = (x / resolution_x - 0.5) * 2.0
    y = (y / resolution_y - 0.5) * 2.0
    
    # Apply zoom
    zoom_fac = get_view3d_zoom_to_fac(view_camera_zoom)
    x *= zoom_fac
    y *= zoom_fac
    
    # Correct aspect ratio mismatch between region and render
    region_aspect = region_size[0] / region_size[1]
    render_aspect = resolution_x / resolution_y

    if render_aspect < 1.0:
        scale = 1/render_aspect
        x /= scale
        y /= scale

    y *= region_aspect / render_aspect

    match fit_mode:
        case 'HORIZONTAL':
            if render_aspect < 1.0:   
                x /= render_aspect
                y /= render_aspect

        case 'VERTICAL':
            if render_aspect<1.0:
                x *= 1/region_aspect
                y *= 1/region_aspect
            else:
                x *= render_aspect/region_aspect
                y *= render_aspect/region_aspect
                
        case 'AUTO':
            if region_aspect < 1.0:
                scale = 1/region_aspect
                x *= scale
                y *= scale
    
    # Apply camera pan
    offset_x, offset_y = view_camera_offset
    x -= offset_x * 4.0 * zoom_fac
    y -= offset_y * 4.0 * zoom_fac
    
    # Convert NDC to region pixels
    x = (x / 2.0 + 0.5) * region_size[0]
    y = (y / 2.0 + 0.5) * region_size[1]
    
    return x, y

def unproject_output_from_region(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        region_coords: Tuple[float, float]) -> Tuple[float, float]:
    """Convert region coordinates to output frame space using cached viewport state"""
    x, y = region_coords
    assert isinstance(x, (int, float)), f"got: {x}"
    assert isinstance(y, (int, float)), f"got: {y}"

    resolution_x = output_size[0]
    resolution_y = output_size[1]
    
    # Convert region pixels to NDC (-1..1)
    x = (x / region_size[0] - 0.5) * 2.0
    y = (y / region_size[1] - 0.5) * 2.0
    
    # Unapply camera pan
    zoom_fac = get_view3d_zoom_to_fac(view_camera_zoom)
    offset_x, offset_y = view_camera_offset
    x += offset_x * 4.0 * zoom_fac
    y += offset_y * 4.0 * zoom_fac
    
    # Unapply aspect ratio correction and sensor fit
    region_aspect = region_size[0] / region_size[1]
    render_aspect = resolution_x / resolution_y
    
    match fit_mode:
        case 'HORIZONTAL':
            if render_aspect < 1.0:   
                x *= render_aspect
                y *= render_aspect

        case 'VERTICAL':
            if render_aspect<1.0:
                x *= region_aspect
                y *= region_aspect
            else:
                x /= render_aspect/region_aspect
                y /= render_aspect/region_aspect
                
        case 'AUTO':
            if region_aspect < 1.0:
                scale = 1/region_aspect
                x /= scale
                y /= scale
    
    y /= region_aspect / render_aspect

    if render_aspect < 1.0:
        scale = 1/render_aspect
        x *= scale
        y *= scale
    
    # Unapply zoom
    x /= zoom_fac
    y /= zoom_fac
    
    # Convert NDC to image pixels
    x = (x / 2.0 + 0.5) * resolution_x
    y = (y / 2.0 + 0.5) * resolution_y
    
    return x, y

def get_sensor_size(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'],
        sensor_size: Tuple[float, float]
    ) -> Tuple[float, float]:
    """Get sensor size based on sensor fit mode"""
    w, h = sensor_size
    match fit_mode:
        case 'AUTO':
            # on auto mode, in blender, the sensor becomes a square.
            # the square size, therefore the field of view is driven by the
            # sensor_width property
            return (w, w)
        case 'HORIZONTAL':
            return (w, h)
        case 'VERTICAL':
            return (w, h)

def project_sensor_to_region(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        sensor_size: Tuple[float, float],
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        sensor_coords: Tuple[float, float]
    ) -> Tuple[float, float]:
        
        sensor_size = get_sensor_size(fit_mode, sensor_size)        
        output_aspect = output_size[0] / output_size[1]
        match fit_mode:
            case 'AUTO':
                output_coord = map_space(sensor_coords, 
                    source=fit_space_to_aspect((0,0,sensor_size[0], sensor_size[1]), output_aspect),
                    target=(0, 0, output_size[0], output_size[1]))
                
            case 'HORIZONTAL':
                scale = output_size[0] / sensor_size[0]
                offset_x = (output_size[0] - sensor_size[0] * scale) / 2.0
                offset_y = (output_size[1] - sensor_size[1] * scale) / 2.0
                output_coord = (
                    sensor_coords[0] * scale + offset_x,
                    sensor_coords[1] * scale + offset_y)
                
            case 'VERTICAL':
                scale = output_size[1] / sensor_size[1]
                offset_x = (output_size[0] - sensor_size[0] * scale) / 2.0
                offset_y = (output_size[1] - sensor_size[1] * scale) / 2.0
                output_coord = (
                    sensor_coords[0] * scale + offset_x,
                    sensor_coords[1] * scale + offset_y)
        
        region_coord = project_output_to_region(
            fit_mode=fit_mode,
            output_size=output_size,
            region_size=region_size,
            view_camera_zoom=view_camera_zoom,
            view_camera_offset=view_camera_offset,
            output_coords=output_coord)
        
        return region_coord

def unproject_sensor_from_region(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        sensor_size: Tuple[float, float],
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        region_coords: Tuple[float, float]) -> Tuple[float, float]:
    """Map from region space to sensor space (uses cached viewport state)"""
    # First unproject from region to output space
    output_coord = unproject_output_from_region(
        fit_mode=fit_mode,
        output_size=output_size,
        region_size=region_size,
        view_camera_zoom=view_camera_zoom,
        view_camera_offset=view_camera_offset,
        region_coords=region_coords)
    
    # Then convert from output space to sensor space
    sensor_size = get_sensor_size(fit_mode, sensor_size)
    output_aspect = output_size[0] / output_size[1]
    
    match fit_mode:
        case 'AUTO':
            sensor_coord = map_space(output_coord,
                source=(0, 0, output_size[0], output_size[1]),
                target=fit_space_to_aspect((0, 0, sensor_size[0], sensor_size[1]), output_aspect))
        
        case 'HORIZONTAL':
            scale = output_size[0] / sensor_size[0]
            offset_x = (output_size[0] - sensor_size[0] * scale) / 2.0
            offset_y = (output_size[1] - sensor_size[1] * scale) / 2.0
            sensor_coord = (
                (output_coord[0] - offset_x) / scale,
                (output_coord[1] - offset_y) / scale)
        
        case 'VERTICAL':
            scale = output_size[1] / sensor_size[1]
            offset_x = (output_size[0] - sensor_size[0] * scale) / 2.0
            offset_y = (output_size[1] - sensor_size[1] * scale) / 2.0
            sensor_coord = (
                (output_coord[0] - offset_x) / scale,
                (output_coord[1] - offset_y) / scale)
    
    return sensor_coord

def project_compute_to_region(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        compute_rect: Tuple[float, float, float, float],
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        compute_coords: Tuple[float, float]) -> Tuple[float, float]:
    """Map from compute space to region space
    fit_mode: how to fit the compute space to the output space
    """
    x, y, w, h = compute_rect
    compute_size = get_sensor_size(fit_mode, (w, h))        
    output_aspect = output_size[0] / output_size[1]
    match fit_mode:
        case 'AUTO':
            output_coords = map_space(compute_coords, 
                source=fit_space_to_aspect(compute_rect, output_aspect),
                target=(0, 0, output_size[0], output_size[1]))
            
        case 'HORIZONTAL':
            scale = output_size[0] / compute_size[0]
            offset_x = (output_size[0] - compute_size[0] * scale) / 2.0
            offset_y = (output_size[1] - compute_size[1] * scale) / 2.0
            output_coords = (
                (compute_coords[0] - x) * scale + offset_x,
                (compute_coords[1] - y) * scale + offset_y)
            
        case 'VERTICAL':
            scale = output_size[1] / compute_size[1]
            offset_x = (output_size[0] - compute_size[0] * scale) / 2.0
            offset_y = (output_size[1] - compute_size[1] * scale) / 2.0
            output_coords = (
                (compute_coords[0] - x) * scale + offset_x,
                (compute_coords[1] - y) * scale + offset_y)
    
    region_coord = project_output_to_region(
        fit_mode=fit_mode,
        output_size=output_size,
        region_size=region_size,
        view_camera_zoom=view_camera_zoom,
        view_camera_offset=view_camera_offset,
        output_coords=output_coords)
    
    return region_coord

def unproject_compute_from_region(
        fit_mode: Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
        compute_rect: Tuple[float, float, float, float],
        output_size: Tuple[float, float],
        region_size: Tuple[float, float],
        view_camera_zoom: float,
        view_camera_offset: Tuple[float, float],
        region_coords: Tuple[float, float]) -> Tuple[float, float]:
    """Map from region space to compute space
    fit_mode: how to fit the compute space to the output space
    """
    # First unproject from region to output space
    output_coord = unproject_output_from_region(
        fit_mode=fit_mode,
        output_size=output_size,
        region_size=region_size,
        view_camera_zoom=view_camera_zoom,
        view_camera_offset=view_camera_offset,
        region_coords=region_coords)
    
    # Then convert from output space to compute space
    x, y, w, h = compute_rect
    compute_size = get_sensor_size(fit_mode, (w, h))
    output_aspect = output_size[0] / output_size[1]
    
    match fit_mode:
        case 'AUTO':
            compute_coord = map_space(output_coord,
                source=(0, 0, output_size[0], output_size[1]),
                target=fit_space_to_aspect(compute_rect, output_aspect))
        
        case 'HORIZONTAL':
            scale = output_size[0] / compute_size[0]
            offset_x = (output_size[0] - compute_size[0] * scale) / 2.0
            offset_y = (output_size[1] - compute_size[1] * scale) / 2.0
            compute_coord = (
                (output_coord[0] - offset_x) / scale + x,
                (output_coord[1] - offset_y) / scale + y)
        
        case 'VERTICAL':
            scale = output_size[1] / compute_size[1]
            offset_x = (output_size[0] - compute_size[0] * scale) / 2.0
            offset_y = (output_size[1] - compute_size[1] * scale) / 2.0
            compute_coord = (
                (output_coord[0] - offset_x) / scale + x,
                (output_coord[1] - offset_y) / scale + y)
    
    return compute_coord

def map_space(
        coord:  tuple[float, float],
        source: Tuple[float, float, float, float],
        target: Tuple[float, float, float, float]
    ) -> tuple[float, float]:
        """
        Map coord from source space to target space.

        Params:
            coord: (x, y) coordinate in source space
            source: (x, y, width, height) defining the source rectangle
            target: (x, y, width, height) defining the target rectangle
        """
        sx, sy, sw, sh = source
        tx, ty, tw, th = target
        x, y = coord

        # Normalize coord within source [0–1]
        nx = (x - sx) / sw
        ny = (y - sy) / sh

        # Scale to target
        mapped_x = tx + nx * tw
        mapped_y = ty + ny * th

        return mapped_x, mapped_y

def fit_space_to_aspect(
    space: tuple[float, float, float, float],
    target_aspect: float
) -> tuple[float, float, float, float]:
    """
    Returns a rectangle that fits within the aspect ratio.
    """
    sx, sy, sw, sh = space
    source_ar = sw / sh

    if source_ar > target_aspect:
        # Source too wide → match height, reduce width
        new_h = sh
        new_w = new_h * target_aspect
        new_x = sx + (sw - new_w) / 2
        new_y = sy
    else:
        # Source too tall → match width, reduce height
        new_w = sw
        new_h = new_w / target_aspect
        new_x = sx
        new_y = sy + (sh - new_h) / 2

    return new_x, new_y, new_w, new_h

def crop_space_to_aspect(
    source: tuple[float, float, float, float],
    target_aspect: float
) -> tuple[float, float, float, float]:
    """
    Returns a rectangle that fills the aspect ratio by cropping the excess.
    (Crop)
    """
    sx, sy, sw, sh = source
    source_ar = sw / sh

    if source_ar > target_aspect:
        # Source too wide → match width, expand height
        new_w = sw
        new_h = new_w / target_aspect
        new_x = sx
        new_y = sy - (new_h - sh) / 2
    else:
        # Source too tall → match height, expand width
        new_h = sh
        new_w = new_h * target_aspect
        new_x = sx - (new_w - sw) / 2
        new_y = sy

    return new_x, new_y, new_w, new_h
