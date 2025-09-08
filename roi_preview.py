import cv2
import numpy as np
from mss import mss

monitor = {'left': 469, 'top': 123, 'width': 511, 'height': 889}

with mss() as sct:
    win = "Preview da area capturada (Q sai | M reposiciona)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    img0 = np.array(sct.grab(monitor))              # BGRA
    frame0 = cv2.cvtColor(img0, cv2.COLOR_BGRA2BGR) # -> BGR

    preview_max_w = 700
    scale = min(1.0, preview_max_w / frame0.shape[1])
    w = int(frame0.shape[1] * scale)
    h = int(frame0.shape[0] * scale)
    cv2.resizeWindow(win, w, h)  

    
    virtual = sct.monitors[0]
    margin = 20

    def place_safely():
        x = monitor["left"] + monitor["width"] + margin
        y = monitor["top"]
        if x + w > virtual["left"] + virtual["width"]:
            x = monitor["left"] - w - margin
        if x < virtual["left"]:
            x, y = virtual["left"] + margin, virtual["top"] + margin
        cv2.moveWindow(win, x, y)

    place_safely()

    while True:
        img = np.array(sct.grab(monitor))                # BGRA
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)    # -> BGR
        cv2.imshow(win, frame)

        k = cv2.waitKey(1) & 0xFF
        if k == ord('q'):
            break
        elif k == ord('m'):
            # Reposiciona fora da ROI se quiser (atalho)
            place_safely()

cv2.destroyAllWindows()