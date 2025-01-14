#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Wen Tao Lin, Kris Mannino
"""
from shapely.geometry import Point, box
from shapely.geometry import mapping
from rasterio.mask import mask
from rasterio.crs import CRS
from rasterio.warp import calculate_default_transform, reproject, Resampling
import rasterio
import numpy as np
import geopandas as gpd

def generate_rectangle_area(longitude: float,
                            latitude: float,
                            width_km: float,
                            height_km: float) -> box:
    width_deg = width_km / 111.13
    height_deg = height_km / (111.13 * np.cos(np.radians(latitude)))
    
    # Calculate bounds
    min_lon = longitude - width_deg/2
    max_lon = longitude + width_deg/2
    min_lat = latitude - height_deg/2
    max_lat = latitude + height_deg/2
    
    return box(min_lon, min_lat, max_lon, max_lat)

# Radius functionality disabled
def generate_area(longitude: float, 
                  latitude: float, 
                  radius_in_km: float) -> Point:
    radius_in_degree = radius_in_km / 111.13
    return Point(longitude, latitude).buffer(radius_in_degree)

def crop_image_by_coordinates(path_to_image: str, 
                              output_name: str, 
                              center_longitude: float, 
                              center_latitude: float, 
                              # radius_in_km: float
                              width_km: float,
                              height_km: float
                              ) -> None:
    """
    Crops a raster image by finding the intersection of the original image and 
    the circle generated by the user inputted radius and center coordinates.

    Parameters
    ----------
    path_to_image : str
        Path to the image cropping from.
    output_name : str
        Name of the output file.
    center_longitude : float
        Center longitude of the fire.
    center_latitude : float
        Center latitude of the fire.
    radius_in_km : float
        Radius from the coordinate in kilometer to crop.

    Returns
    -------
    None
        Outputs a GeoTIFF file that is a cropped version of the input image 
        based intersection of the specificed circle.

    """
    # Generate the rectangular polygon
    aoi = generate_rectangle_area(center_longitude, center_latitude, width_km, height_km)

    # Radius functionality disabled
    # Generate the circular polygon
    # aoi = generate_area(center_longitude, center_latitude, radius_in_km)
    shapes = [mapping(aoi)]
    
    # Crop the raster using the polygon
    with rasterio.open(path_to_image) as src:
        out_image, out_transform = mask(dataset=src, shapes=shapes, crop=True, pad=True)
        out_meta = src.meta.copy()

    out_meta.update({"driver": "GTiff",
                     "nodata": np.nan,
                     "height": out_image.shape[1],
                     "width": out_image.shape[2],
                     "transform": out_transform})

    with rasterio.open(output_name, "w", **out_meta) as dest:
        dest.write(out_image)
    print(output_name + ' is outputted!')


def crop_image_by_geojson_shp(path_to_polygon_file: str, 
                              path_to_image: str, 
                              output_name: str) -> None:
    """
    Crops a raster image based on the shape of the first polygon in the 
    inputted GeoJSON or shapefile.

    Parameters
    ----------
    path_to_shp : str
        Path to the shapefile.
    path_to_image : str
        Path to the image cropping from.
    output_name : str
        Name of the output file.

    Returns
    -------
    None
        Outputs a GeoTIFF file that is a cropped version of the input image 
        corresponding to polygon in the input GeoJSON or shapefile.

    Notes
    -------
    There should only be one tuple in either GeoJSON or SHP, whether it is a 
    multi-polygon or polygon.
    
    """
    gdf = gpd.read_file(path_to_polygon_file)
    target_crs = CRS.from_epsg(4326)
    gdf_reprojected = gdf.to_crs(target_crs)
    
    # Extract the shapes from the shapefile
    polygon = gdf_reprojected['geometry'].iloc[0]
    shapes = [mapping(polygon)]

    with rasterio.open(path_to_image) as src:
        out_image, out_transform = mask(dataset=src, shapes=shapes, crop=True, pad=True)
        out_meta = src.meta.copy()

    out_meta.update({"driver": "GTiff",
                     "nodata": np.nan,
                     "height": out_image.shape[1],
                     "width": out_image.shape[2],
                     "transform": out_transform})

    with rasterio.open(output_name, "w", **out_meta) as dest:
        dest.write(out_image)
    print(output_name + ' is outputted.')


def reproject_geotiff(target_crs: CRS, 
                      input_raster_path: str, 
                      output_raster_path: str) -> None:
    """
    Reproject a raster image to another coordinate reference systems.

    Parameters
    ----------
    target_crs : CRS
        The coordinate reference systems projecting to.
    input_raster_path : str
        Path to the orginal raster image.
    output_raster_path : str
        Path for the reprojected raster image.

    Returns
    -------
    None
        Outputs the same GeoTIFF file but in the inputted crs.

    """
    # Open the source raster and get its transform and profile
    with rasterio.open(input_raster_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': target_crs,
            'transform': transform,
            'width': width,
            'height': height,
            'dtype': 'float32',
            'nodata': np.nan
        })

        # Create the output raster and reproject
        with rasterio.open(output_raster_path, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.nearest
                )

    print("Reprojected raster saved to:", output_raster_path)
