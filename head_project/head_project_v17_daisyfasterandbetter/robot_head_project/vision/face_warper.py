import cv2
import numpy as np
import mediapipe as mp

def warp_face_to_circle(image, face_landmarks):
    """
    Warps a face image so that the Face Oval boundary stretches perfectly into a circle.
    Uses Piecewise Affine Warping via Delaunay Triangulation.
    """
    h, w = image.shape[:2]
    
    # Convert normalized landmarks to pixel coordinates
    src_points = []
    for lm in face_landmarks.landmark:
        src_points.append([lm.x * w, lm.y * h])
    src_points = np.array(src_points, dtype=np.float32)
    
    # Get Face Oval indices
    oval_connections = list(mp.solutions.face_mesh.FACEMESH_FACE_OVAL)
    oval_indices = list(set([i for pair in oval_connections for i in pair]))
    
    # Center is nose tip (index 1)
    cx, cy = src_points[1]
    
    # Calculate angles and distances for oval points
    oval_data = []
    for idx in oval_indices:
        px, py = src_points[idx]
        angle = np.arctan2(py - cy, px - cx)
        dist = np.hypot(px - cx, py - cy)
        oval_data.append((angle, dist))
    
    # Sort oval data by angle
    oval_data.sort(key=lambda x: x[0])
    angles = np.array([x[0] for x in oval_data])
    dists = np.array([x[1] for x in oval_data])
    
    # Wrap around for interpolation
    angles = np.concatenate([angles[-1:] - 2*np.pi, angles, angles[:1] + 2*np.pi])
    dists = np.concatenate([dists[-1:], dists, dists[:1]])
    
    dst_points = np.zeros_like(src_points)
    R = min(w, h) / 2.0 - 5.0 # target radius
    
    # Center of target image
    dst_cx, dst_cy = w/2.0, h/2.0
    
    # Map all 478 points
    for i in range(len(src_points)):
        px, py = src_points[i]
        angle = np.arctan2(py - cy, px - cx)
        d = np.hypot(px - cx, py - cy)
        
        # Interpolate boundary distance for this angle
        D_bound = np.interp(angle, angles, dists)
        
        # Scale factor (stretch internal points proportionally)
        if D_bound > 0:
            scale = R / D_bound
        else:
            scale = 1.0
            
        dst_points[i][0] = dst_cx + d * scale * np.cos(angle)
        dst_points[i][1] = dst_cy + d * scale * np.sin(angle)
        
    # We also need corner points so the background doesn't get ripped out
    corners_src = np.array([[0,0], [w-1,0], [w-1,h-1], [0,h-1]], dtype=np.float32)
    corners_dst = np.array([[0,0], [w-1,0], [w-1,h-1], [0,h-1]], dtype=np.float32)
    
    all_src = np.vstack([src_points, corners_src])
    all_dst = np.vstack([dst_points, corners_dst])
    
    # ----------------------------------------------------
    # Delaunay Triangulation on dst_points
    # ----------------------------------------------------
    from scipy.spatial import Delaunay
    
    # tri.simplices returns an array of shape (N, 3) containing indices into all_dst
    try:
        tri = Delaunay(all_dst)
        triangle_indices = tri.simplices
    except Exception as e:
        print("Delaunay failed:", e)
        return image
        
    warped_img = np.zeros_like(image, dtype=np.float32)
    img_float = image.astype(np.float32)
    
    # ----------------------------------------------------
    # Piecewise Affine Warping
    # ----------------------------------------------------
    for idx_tuple in triangle_indices:
        idx1, idx2, idx3 = idx_tuple
        
        t_src = [all_src[idx1], all_src[idx2], all_src[idx3]]
        t_dst = [all_dst[idx1], all_dst[idx2], all_dst[idx3]]
            
        r1 = cv2.boundingRect(np.float32([t_src]))
        r2 = cv2.boundingRect(np.float32([t_dst]))
        
        # bounds check
        if r2[0] < 0 or r2[1] < 0 or r2[0]+r2[2] > w or r2[1]+r2[3] > h: continue
        if r1[0] < 0 or r1[1] < 0 or r1[0]+r1[2] > w or r1[1]+r1[3] > h: continue
        
        t1_rect = []
        t2_rect = []
        for i in range(3):
            t1_rect.append(((t_src[i][0] - r1[0]), (t_src[i][1] - r1[1])))
            t2_rect.append(((t_dst[i][0] - r2[0]), (t_dst[i][1] - r2[1])))
            
        mask = np.zeros((r2[3], r2[2], 3), dtype=np.float32)
        cv2.fillConvexPoly(mask, np.int32(t2_rect), (1.0, 1.0, 1.0), 16, 0)
        
        img1_rect = img_float[r1[1]:r1[1]+r1[3], r1[0]:r1[0]+r1[2]]
        
        warp_mat = cv2.getAffineTransform(np.float32(t1_rect), np.float32(t2_rect))
        img2_rect = cv2.warpAffine(img1_rect, warp_mat, (r2[2], r2[3]), None, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        
        img2_slice = warped_img[r2[1]:r2[1]+r2[3], r2[0]:r2[0]+r2[2]]
        img2_slice = img2_slice * (1.0 - mask) + (img2_rect * mask)
        warped_img[r2[1]:r2[1]+r2[3], r2[0]:r2[0]+r2[2]] = img2_slice
        
    return warped_img.astype(np.uint8)
