import json
from pathlib import Path
import cv2
from baze_client import request_json,to_messages
from fretboard_prompts import CANDIDATE_PROMPT
from two_stage_fret_pipeline import encode_cv2_image,resize_for_analysis
image=cv2.imread('sample_images/1051_5603_0000.jpg')
contents=[{'role':'user','parts':[{'text':CANDIDATE_PROMPT},{'inline_data':{'mime_type':'image/jpeg','data':encode_cv2_image(resize_for_analysis(image))}}]}]
data=request_json('POST','/chat/completions/',dict(model='claude-sonnet-5-5',messages=to_messages(contents),stream=False,max_tokens=16000),120)
Path('dataset/baze_comparison/claude_response_diagnostic.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps(data,ensure_ascii=False))
