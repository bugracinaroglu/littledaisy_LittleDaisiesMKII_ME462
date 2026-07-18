import cv2
import numpy as np

w, h = 240, 240
img = np.zeros((h, w, 3), dtype=np.uint8)

# Draw a face oval in white
cv2.ellipse(img, (w//2, h//2), (80, 100), 0, 0, 360, (255, 255, 255), 2)
# Draw eyes
cv2.circle(img, (w//2 - 30, h//2 - 20), 3, (255, 255, 255), -1)
cv2.circle(img, (w//2 + 30, h//2 - 20), 3, (255, 255, 255), -1)

# Now manually do a single cv2.warpAffine of the whole image to simulate stretching
src_pts = np.float32([[0,0], [w,0], [w,h]])
dst_pts = np.float32([[0,0], [w*1.5,0], [w*1.5, h*1.5]]) # Stretch 1.5x

warp_mat = cv2.getAffineTransform(src_pts, dst_pts)
warped = cv2.warpAffine(img.astype(np.float32), warp_mat, (int(w*1.5), int(h*1.5)), flags=cv2.INTER_LINEAR)
warped = warped.astype(np.uint8)

print("Max value in img:", np.max(img))
print("Max value in warped:", np.max(warped))
print("Nonzero pixels in img:", np.count_nonzero(img))
print("Nonzero pixels in warped:", np.count_nonzero(warped))
