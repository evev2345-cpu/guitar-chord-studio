"""Compare the refined extraction with stored labels on the selected sample."""
import json
from pathlib import Path
import cv2
import numpy as np


def main():
    from two_stage_fret_pipeline import TwoStageFretPipeline, CORNER_NAMES
    pipeline = TwoStageFretPipeline('sample_images/images (1).jpg')
    pipeline.stage1_detect_corners()
    cv2.imwrite('sample_images/refined_candidate_crop.png',pipeline.corner_crop)
    pipeline.stage2_unwarp_and_enhance()
    cv2.imwrite('sample_images/refined_flat.png',pipeline.flat)
    data = json.loads(Path('dataset/labels/images (1).json').read_text(encoding='utf-8'))
    by_name = {p['name']: [p['x'],p['y']] for p in data['corners']}
    manual = np.array([by_name[n] for n in CORNER_NAMES], np.float32)
    old = np.array(json.loads(Path('sample_images/random_check_result.json').read_text(encoding='utf-8'))['corners'],np.float32)
    new = np.array(pipeline.corners,np.float32)
    def metrics(points):
        error = np.linalg.norm(points-manual,axis=1)
        intersection,_ = cv2.intersectConvexConvex(points,manual)
        union = abs(cv2.contourArea(points))+abs(cv2.contourArea(manual))-intersection
        return dict(corner_errors_px=error.tolist(), mean_error_px=float(error.mean()), polygon_iou=float(intersection/union))
    report = dict(corners=pipeline.corners, detection=pipeline.corner_detection,
                  old=metrics(old), refined=metrics(new))
    Path('sample_images/refined_corner_comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    vis=pipeline.raw.copy()
    for points,color in [(old,(0,0,255)),(manual,(0,255,0)),(new,(255,255,0))]:
        cv2.polylines(vis,[np.round(points).astype(np.int32)],True,color,1,cv2.LINE_AA)
    zoom=cv2.resize(vis[95:350,145:345],(600,765))
    cv2.rectangle(zoom,(0,0),(600,35),(20,20,20),-1)
    cv2.putText(zoom,'RED old | GREEN manual | CYAN refined',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1)
    cv2.imwrite('sample_images/refined_corner_comparison.png',zoom)
    print(json.dumps({'old':report['old'],'refined':report['refined']},indent=2))
    pipeline.stage3_detect_frets_two_points()
    pipeline.render_and_save('sample_images/refined_check')


if __name__ == '__main__':
    main()
