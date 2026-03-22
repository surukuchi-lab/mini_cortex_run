import numpy as np
import serial
import time

def generate_boxes(size_of_box, gap=0, n=3):
    dx, dy, dz = size_of_box
    box_bounds = []

    for i in range(n):
        for j in range(n):
            for k in range(n):
                bound = [
                    [i*dx, i*dx + dx],
                    [j*dy, j*dy + dy],
                    [k*(dz+gap), k*(dz+gap) + dz]
                ]
                box_bounds.append(bound)

    return box_bounds

size_of_detector = np.array([5, 5, 2]) * 3
box_size = size_of_detector / 8
box_8x8x8 = generate_boxes(box_size, n=8)
box_info = [size_of_detector, box_size, box_8x8x8]

mapping = {
    #z = 1 layer
    0:  [2.5,  2.5,  1], 1:  [7.5,  2.5,  1], 2:  [12.5, 2.5,  1],
    3:  [2.5,  7.5,  1], 4:  [7.5,  7.5,  1], 5:  [12.5, 7.5,  1],
    6:  [2.5,  12.5, 1], 7:  [7.5,  12.5, 1], 8:  [12.5, 12.5, 1],

    #z = 3 layer
    9:  [2.5,  2.5,  3], 10: [7.5,  2.5,  3], 11: [12.5, 2.5,  3],
    12: [2.5,  7.5,  3], 13: [7.5,  7.5,  3], 14: [12.5, 7.5,  3],
    15: [2.5,  12.5, 3], 16: [7.5,  12.5, 3], 17: [12.5, 12.5, 3],

    #z = 5 layer
    18: [2.5,  2.5,  5], 19: [7.5,  2.5,  5], 20: [12.5, 2.5,  5],
    21: [2.5,  7.5,  5], 22: [7.5,  7.5,  5], 23: [12.5, 7.5,  5],
    24: [2.5,  12.5, 5], 25: [7.5,  12.5, 5], 26: [12.5, 12.5, 5],
}

bit_low = 0
bit_high = 27

# Functions and setup to setup LED cube functionality 
def fit_line_to_3d_points_svd(points):
    centroid = np.mean(points, axis=0)
    centered = points - centroid

    _, _, vh = np.linalg.svd(centered)
    direction = vh[0] 

    dx, dy, dz = direction
    norm = np.linalg.norm(direction)

    theta = np.arccos(dz / norm)  
    phi = np.arctan2(dy, dx)      

    if np.round(theta, 2) == 3.14:
        theta = 0

    return (*centroid, theta, phi)

def calculate_hit_boxes(fit_params, array_of_boxes):
    def check(a,b,c,x1,x2,y1,y2):
        f1 = a*x1+b*y1+c
        f2 = a*x2+b*y2+c
        if(f1*f2<=0): return True
        return False
    x0, y0, z0, theta, phi = fit_params

    size_of_box = [np.abs(array_of_boxes[0][0][0] - array_of_boxes[0][0][1]), np.abs(array_of_boxes[0][1][0] - array_of_boxes[0][1][1]), np.abs(array_of_boxes[0][2][0] - array_of_boxes[0][2][1])]
    hit_boxes = []
    
    #We find the parameters that characterize the three planes that make up the box (i.e a, b, c in the check function)
    xy = [np.sin(phi), - np.cos(phi), - (x0 * np.sin(phi) - y0 * np.cos(phi))]
    xz = [np.cos(theta), - np.sin(theta) * np.cos(phi), - (x0 * np.cos(theta) - z0 * np.sin(theta) * np.cos(phi))]
    yz = [np.cos(theta), -np.sin(theta) * np.sin(phi), - (y0 * np.cos(theta) - z0 * np.sin(theta) * np.sin(phi))]

    #We loop through each box, checking if the vertexes are seperated in all three planes defined above. If it does, it's a hit
    i = 0 
    while i < len(array_of_boxes):
        x1 = array_of_boxes[i][0][0]
        x2 = array_of_boxes[i][0][1]
        y1 = array_of_boxes[i][1][0]
        y2 = array_of_boxes[i][1][1]
        z1 = array_of_boxes[i][2][0]
        z2 = array_of_boxes[i][2][1]
        if all(
                (any((check(xy[0],xy[1],xy[2],x1,x2,y1,y2), check(xy[0],xy[1],xy[2],x1,x2,y2,y1))),
                any((check(xz[0],xz[1],xz[2],x1,x2,z1,z2), check(xz[0],xz[1],xz[2],x1,x2,z2,z1))),
                any((check(yz[0],yz[1],yz[2],y1,y2,z1,z2), check(yz[0],yz[1],yz[2],y1,y2,z2,z1))))
            ):
            hit_boxes.append(array_of_boxes[i])
        i += 1
    
    return hit_boxes

def hitboxes_to_bit_array(hit_boxes, box_dims=(8, 8, 8), box_size=None):
    '''
    From the hitboxes array (Formatted: [[xmin,xmax], [ymin, ymax], [zmin, zmax]]) returns a NxNxN array filled 
    with 1s for lit LEDs and 0s for unlit LEDS 
    '''
    if box_size is None:
        raise ValueError("box_size must be provided")

    grid = np.zeros(box_dims, dtype=np.uint8) 

    for box in hit_boxes:
        (xmin, xmax), (ymin, ymax), (zmin, zmax) = box

        xi_min = box_dims[2] - int(np.ceil(xmax / box_size[0]))
        xi_max = box_dims[2] - int(np.floor(xmin / box_size[0]))

        yi_min = box_dims[0] - int(np.ceil(ymax / box_size[1]))
        yi_max = box_dims[0] - int(np.floor(ymin / box_size[1]))

        zi_min = box_dims[1] - int(np.ceil(zmax / box_size[2]))
        zi_max = box_dims[1] - int(np.floor(zmin / box_size[2]))

        xi_min, xi_max = max(0, xi_min), min(box_dims[2], xi_max)
        yi_min, yi_max = max(0, yi_min), min(box_dims[0], yi_max)
        zi_min, zi_max = max(0, zi_min), min(box_dims[1], zi_max)

        #Did some rotations here to make it correct
        grid[yi_min:yi_max, zi_min:zi_max, xi_min:xi_max] = 1

    return grid


def array_to_hex(array, n=8):
    '''
    Takes a NxNxN dimension array filled with 1s and 0s and converts
    to hex array to send to LED cube.
    '''
    header = [0xf2]
    hex_data = []

    array = array.astype(np.uint8)

    for y in range(n):       
        for z in range(n):   
            bits = array[:, y, z]
            byte = 0
            for i, bit in enumerate(bits):
                byte |= (bit & 1) << i
            hex_data.append(byte)

    return bytearray(header + hex_data)

def send_LED_cube(bitstring, box_info=box_info, mapping=mapping, bit_low=bit_low, bit_high=bit_high):
    ser = serial.Serial('/dev/ttyS0', baudrate=9600)

    size_of_detector, box_size, box_8x8x8 = box_info
    hit_box_to_point_mapping_xside = mapping

    bitstring = bitstring[::-1]

    points = []
    bitstring_filtered = bitstring[bit_low:bit_high]
    for index, bit in enumerate(bitstring_filtered):
        if bit == "1":
            point = hit_box_to_point_mapping_xside[index]
            points.append(point)
    
    if len(points) < 2:
        ser.close()
        return
    else:
        params = fit_line_to_3d_points_svd(points)

        hit_boxes_8x8x8 = calculate_hit_boxes(params, box_8x8x8)
        bit_array_8x8x8 = hitboxes_to_bit_array(hit_boxes_8x8x8,box_dims=(8, 8, 8), box_size=box_size)

        hex_array = array_to_hex(bit_array_8x8x8)

        ser.write(hex_array)

        ser.close()

def send_LED_cube_animate(bitstring, box_info=box_info, mapping=mapping, bit_low=bit_low, bit_high=bit_high):
    ser = serial.Serial('/dev/ttyS0', baudrate=9600)

    size_of_detector, box_size, box_8x8x8 = box_info
    hit_box_to_point_mapping_xside = mapping

    bitstring = bitstring[::-1]

    points = []
    bitstring_filtered = bitstring[bit_low:bit_high]
    for index, bit in enumerate(bitstring_filtered):
        if bit == "1":
            point = hit_box_to_point_mapping_xside[index]
            points.append(point)

    if len(points) < 2:
        ser.close()
        return
    else:
        params = fit_line_to_3d_points_svd(points)

        hit_boxes_8x8x8 = calculate_hit_boxes(params, box_8x8x8)
        bit_array_8x8x8 = hitboxes_to_bit_array(
            hit_boxes_8x8x8,
            box_dims=(8, 8, 8),
            box_size=box_size
        )

        temp = np.zeros_like(bit_array_8x8x8)

        for z in range(8):
            temp[:, z, :] = bit_array_8x8x8[:, 7 - z, :]
            hex_array = array_to_hex(temp)
            ser.write(hex_array)
            time.sleep(0.05)

        ser.close()