import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def draw_rounded_rect(draw, bbox, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)

def draw_badge(draw, x, y, text, font, fill, outline, text_color, pad_x=12, pad_y=4, radius=5):
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    box = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    draw_rounded_rect(draw, box, radius=radius, fill=fill, outline=outline, width=1)
    draw.text((x + pad_x, y + pad_y - 1), text, fill=text_color, font=font)
    return box

def draw_arrow(draw, start, end, color="#64748b", width=2, arrow_size=8):
    x0, y0 = start
    x1, y1 = end
    draw.line([x0, y0, x1, y1], fill=color, width=width)
    if x0 == x1: # Vertical arrow
        if y1 > y0:
            draw.polygon([(x1, y1), (x1 - arrow_size, y1 - arrow_size * 1.5), (x1 + arrow_size, y1 - arrow_size * 1.5)], fill=color)
        else:
            draw.polygon([(x1, y1), (x1 - arrow_size, y1 + arrow_size * 1.5), (x1 + arrow_size, y1 + arrow_size * 1.5)], fill=color)
    elif y0 == y1: # Horizontal arrow
        if x1 > x0:
            draw.polygon([(x1, y1), (x1 - arrow_size * 1.5, y1 - arrow_size), (x1 - arrow_size * 1.5, y1 + arrow_size)], fill=color)
        else:
            draw.polygon([(x1, y1), (x1 + arrow_size * 1.5, y1 - arrow_size), (x1 + arrow_size * 1.5, y1 + arrow_size)], fill=color)

def generate_white_diagram():
    W, H = 1520, 960
    # Clean Pure White Canvas
    img = Image.new('RGB', (W, H), color='#FFFFFF')
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 28)
    font_sub = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)
    font_badge = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 12)
    font_card_t = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 17)
    font_card_sub = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 13)
    font_body_b = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 13)
    font_body = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 12)
    font_mini = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 11)

    # Top Header Banner (White with subtle border)
    draw_rounded_rect(draw, (40, 30, 1480, 115), 14, fill='#F8FAFC', outline='#CBD5E1', width=1)
    
    # Mint tag
    draw_badge(draw, 60, 48, "Chord Studio v2.0", font_badge, fill='#E6FFFA', outline='#0D9488', text_color='#0D9488', pad_x=12, pad_y=4)

    draw.text((225, 46), "전체 시스템 작동 파이프라인 (System Architecture Pipeline)", fill='#0F172A', font=font_title)
    draw.text((225, 82), "음향 AI(Demucs 6s + Basic Pitch) · 컴퓨터 비전(MediaPipe C++) · 16박자 악보 에디터 · 무설치 단독 실행", fill='#64748B', font=font_sub)

    # --- 1. INPUT STAGE (Left Column: x=40..270) ---
    draw_rounded_rect(draw, (40, 140, 270, 770), 14, fill='#F8FAFC', outline='#CBD5E1', width=1)
    # Stage Badge
    draw_badge(draw, 60, 155, "STEP 1. 입력", font_badge, fill='#EFF6FF', outline='#3B82F6', text_color='#1D4ED8', pad_x=12, pad_y=4)
    draw.text((60, 195), "사용자 미디어 업로드", fill='#0F172A', font=font_card_t)
    draw.text((60, 222), "드래그 앤 드롭 파일 선택", fill='#64748B', font=font_body)

    # Video Card
    draw_rounded_rect(draw, (55, 270, 255, 480), 10, fill='#FFFFFF', outline='#93C5FD', width=1)
    draw.text((70, 285), "🎬 동영상 파일 (MP4)", fill='#1D4ED8', font=font_card_sub)
    draw.text((70, 315), "• 포맷: MP4, AVI, MOV", fill='#334155', font=font_body)
    draw.text((70, 340), "• 해상도: 720p ~ 1080p", fill='#334155', font=font_body)
    draw.text((70, 365), "• 프레임레이트: 30 / 60 fps", fill='#334155', font=font_body)
    draw.text((70, 400), "→ 오디오 트랙 자동 추출", fill='#0284C7', font=font_body_b)
    draw.text((70, 425), "→ 영상 프레임 캡처 대기", fill='#0284C7', font=font_body_b)
    draw.text((70, 450), "(음향 + 비전 동시 분석)", fill='#0369A1', font=font_body)

    # Audio Card
    draw_rounded_rect(draw, (55, 510, 255, 720), 10, fill='#FFFFFF', outline='#7DD3FC', width=1)
    draw.text((70, 525), "♬ 순수 음원 (WAV/MP3)", fill='#0369A1', font=font_card_sub)
    draw.text((70, 555), "• 포맷: WAV, MP3, FLAC", fill='#334155', font=font_body)
    draw.text((70, 580), "• 샘플레이트: 44.1 / 48 kHz", fill='#334155', font=font_body)
    draw.text((70, 615), "→ 오디오 단독 분석 경로", fill='#0284C7', font=font_body_b)
    draw.text((70, 640), "→ 비전 파이프라인 자동 생략", fill='#64748B', font=font_body)
    draw.text((70, 675), "('오디오 전용' 모드 가동)", fill='#475569', font=font_body)

    # --- 2. DUAL AI ENGINE (Middle Columns: x=340..980) ---
    # Lane A: Audio AI Engine (Upper Box: y=140..490)
    draw_rounded_rect(draw, (340, 140, 980, 490), 14, fill='#F0FDFA', outline='#0D9488', width=1)
    draw_badge(draw, 360, 155, "STEP 2-A. 음향 AI 엔진", font_badge, fill='#CCFBF1', outline='#0D9488', text_color='#0F766E', pad_x=12, pad_y=4)
    draw.text((540, 156), "Full-Song 기타 분리 & 16박자 화성 전사 파이프라인", fill='#475569', font=font_card_sub)

    # Box A1: Demucs
    draw_rounded_rect(draw, (360, 205, 535, 460), 10, fill='#FFFFFF', outline='#5EEAD4', width=1)
    draw.text((375, 220), "① AI 음원 분리", fill='#0F766E', font=font_card_sub)
    draw.text((375, 245), "Demucs v4 6-Stem", fill='#115E59', font=font_body_b)
    draw.text((375, 280), "• 보컬·드럼·베이스 제거", fill='#334155', font=font_body)
    draw.text((375, 305), "• 기타 단독 트랙 추출", fill='#334155', font=font_body)
    draw.text((375, 330), "  (`guitar.wav`)", fill='#0D9488', font=font_body_b)
    draw.text((375, 365), "• 코드 오인식 노이즈 차단", fill='#334155', font=font_body)
    draw.text((375, 415), "✓ 기타 솔로 트랙 완성", fill='#059669', font=font_body_b)

    # Arrow A1 -> A2
    draw_arrow(draw, (535, 330), (575, 330), color='#0D9488', width=2)

    # Box A2: Basic Pitch
    draw_rounded_rect(draw, (575, 205, 750, 460), 10, fill='#FFFFFF', outline='#5EEAD4', width=1)
    draw.text((590, 220), "② AI 피치 전사", fill='#0F766E', font=font_card_sub)
    draw.text((590, 245), "Spotify Basic Pitch", fill='#115E59', font=font_body_b)
    draw.text((590, 280), "• ONNX 경량 런타임", fill='#334155', font=font_body)
    draw.text((590, 305), "• 프레임별 피치 활성도", fill='#334155', font=font_body)
    draw.text((590, 330), "  (Pitch Salience Map)", fill='#0D9488', font=font_body_b)
    draw.text((590, 365), "• 음 시작점 감지 (Onset)", fill='#334155', font=font_body)
    draw.text((590, 415), "✓ 88건반 활성 맵 추출", fill='#059669', font=font_body_b)

    # Arrow A2 -> A3
    draw_arrow(draw, (750, 330), (790, 330), color='#0D9488', width=2)

    # Box A3: Harmony & Look-Ahead
    draw_rounded_rect(draw, (790, 205, 960, 460), 10, fill='#FFFFFF', outline='#5EEAD4', width=1)
    draw.text((805, 220), "③ 화성 & 비트 정렬", fill='#0F766E', font=font_card_sub)
    draw.text((805, 245), "Look-Ahead v2", fill='#115E59', font=font_body_b)
    draw.text((805, 280), "• 16박자 비트 격자(BPM)", fill='#334155', font=font_body)
    draw.text((805, 305), "• 0.25s 선확인 필터링", fill='#334155', font=font_body)
    draw.text((805, 330), "  (코드 깜빡임 -36.7%)", fill='#059669', font=font_body_b)
    draw.text((805, 365), "• 분수코드 복원 (D/F#)", fill='#334155', font=font_body)
    draw.text((805, 390), "• 카포 운지/실음 변환", fill='#334155', font=font_body)
    draw.text((805, 420), "✓ 16박자 코드 악보", fill='#059669', font=font_body_b)

    # Lane B: Vision AI Engine (Lower Box: y=520..870)
    draw_rounded_rect(draw, (340, 520, 980, 870), 14, fill='#FAF5FF', outline='#7C3AED', width=1)
    draw_badge(draw, 360, 535, "STEP 2-B. 컴퓨터 비전 엔진", font_badge, fill='#EDE9FE', outline='#7C3AED', text_color='#6D28D9', pad_x=12, pad_y=4)
    draw.text((565, 536), "동영상 4점 지판 원근 투영 및 MediaPipe C++ 손가락 골격 추적", fill='#475569', font=font_card_sub)

    # Box B1: Calibration
    draw_rounded_rect(draw, (360, 585, 535, 840), 10, fill='#FFFFFF', outline='#DDD6FE', width=1)
    draw.text((375, 600), "① 4점 모서리 지정", fill='#6D28D9', font=font_card_sub)
    draw.text((375, 625), "사용자 클릭 캘리브", fill='#5B21B6', font=font_body_b)
    draw.text((375, 660), "• 1·6번 줄 너트 2점", fill='#334155', font=font_body)
    draw.text((375, 685), "• 1·6번 줄 브릿지 2점", fill='#334155', font=font_body)
    draw.text((375, 720), "• 원근 투영 변환 행렬", fill='#334155', font=font_body)
    draw.text((375, 745), "  (Perspective Matrix)", fill='#7C3AED', font=font_body_b)
    draw.text((375, 780), "• 6현 x 22프렛 분할", fill='#334155', font=font_body)
    draw.text((375, 810), "✓ 지판 기하 기준 확립", fill='#059669', font=font_body_b)

    # Arrow B1 -> B2
    draw_arrow(draw, (535, 710), (575, 710), color='#7C3AED', width=2)

    # Box B2: MediaPipe C++
    draw_rounded_rect(draw, (575, 585, 750, 840), 10, fill='#FFFFFF', outline='#DDD6FE', width=1)
    draw.text((590, 600), "② 백그라운드 추적", fill='#6D28D9', font=font_card_sub)
    draw.text((590, 625), "MediaPipe C++ DLL", fill='#5B21B6', font=font_body_b)
    draw.text((590, 660), "• libmediapipe.dll (68MB)", fill='#334155', font=font_body)
    draw.text((590, 685), "• 왼손 21개 관절 추적", fill='#334155', font=font_body)
    draw.text((590, 720), "• 영상 전체 프레임 처리", fill='#334155', font=font_body)
    draw.text((590, 745), "  ([0%] ~ [100%] 실시간)", fill='#7C3AED', font=font_body_b)
    draw.text((590, 780), "• 해부학적 유효성 검증", fill='#334155', font=font_body)
    draw.text((590, 810), "✓ 손가락 골격 데이터", fill='#059669', font=font_body_b)

    # Arrow B2 -> B3
    draw_arrow(draw, (750, 710), (790, 710), color='#7C3AED', width=2)

    # Box B3: Visual Tuning & Tiebreak
    draw_rounded_rect(draw, (790, 585, 960, 840), 10, fill='#FFFFFF', outline='#DDD6FE', width=1)
    draw.text((805, 600), "③ 비전-음향 융합", fill='#6D28D9', font=font_card_sub)
    draw.text((805, 625), "동점 보정 & 지판 정합", fill='#5B21B6', font=font_body_b)
    draw.text((805, 660), "• 가상 지판 격자 생성", fill='#334155', font=font_body)
    draw.text((805, 685), "• 손가락 프렛 접촉 매핑", fill='#334155', font=font_body)
    draw.text((805, 720), "• 저음현(6·5현) 근음 가점", fill='#334155', font=font_body)
    draw.text((805, 745), "  (B6 vs G#m7 동점 해결)", fill='#7C3AED', font=font_body_b)
    draw.text((805, 780), "• 화면 위 실시간 시각화", fill='#334155', font=font_body)
    draw.text((805, 810), "✓ 비전 오버레이 확정", fill='#059669', font=font_body_b)

    # Connector Arrows from Input to Middle Engines
    # Video -> Audio Lane
    draw.line([(255, 330), (300, 330), (300, 240), (340, 240)], fill='#2563EB', width=2)
    draw_arrow(draw, (330, 240), (340, 240), color='#2563EB', width=2)
    # Video -> Vision Lane
    draw.line([(255, 350), (300, 350), (300, 680), (340, 680)], fill='#7C3AED', width=2)
    draw_arrow(draw, (330, 680), (340, 680), color='#7C3AED', width=2)
    # Audio -> Audio Lane
    draw.line([(255, 615), (320, 615), (320, 440), (340, 440)], fill='#0284C7', width=2)
    draw_arrow(draw, (330, 440), (340, 440), color='#0284C7', width=2)

    # --- 3. STUDIO WORKSPACE & OUTPUT (Right Column: x=1050..1480) ---
    draw_rounded_rect(draw, (1050, 140, 1480, 560), 14, fill='#F0FDF4', outline='#10B981', width=1)
    
    # STEP 3 Badge (Dynamic width with exact padding - NO OVERFLOW)
    draw_badge(draw, 1070, 155, "STEP 3. 스튜디오 워크스페이스", font_badge, fill='#D1FAE5', outline='#10B981', text_color='#065F46', pad_x=14, pad_y=4)
    draw.text((1070, 195), "Chord Studio 인터랙티브 DAW 뷰", fill='#0F172A', font=font_card_t)

    # Features list in workspace
    draw_rounded_rect(draw, (1070, 230, 1460, 535), 10, fill='#FFFFFF', outline='#A7F3D0', width=1)
    draw.text((1090, 245), "🖥️ 통합 데스크톱 UI (Edge WebView2)", fill='#047857', font=font_card_sub)
    draw.text((1090, 280), "1. 16박자 스마트 악보 (리드 시트 뷰)", fill='#0F172A', font=font_body_b)
    draw.text((1110, 305), "• 마디/박자별 코드 표시 및 카포(운지/실음) 즉시 변환", fill='#334155', font=font_body)
    
    draw.text((1090, 340), "2. 실시간 2D 가상 지판 & 손가락 스켈레톤", fill='#0F172A', font=font_body_b)
    draw.text((1110, 365), "• 동영상 위 프렛 그리드 + 21개 관절 실시간 오버레이", fill='#334155', font=font_body)

    draw.text((1090, 400), "3. 파형 스크롤러 & BPM / 오프셋 미세 조절", fill='#0F172A', font=font_body_b)
    draw.text((1110, 425), "• 실시간 재생 헤드 동기화, 첫박 오프셋 ±1칸 원클릭", fill='#334155', font=font_body)

    draw.text((1090, 460), "4. 마우스 클릭 즉각 코드 교정 (에디터 기능)", fill='#0F172A', font=font_body_b)
    draw.text((1110, 485), "• 오인식된 코드를 클릭하여 루트/퀄리티 즉시 수정", fill='#334155', font=font_body)

    # --- 4. PERSISTENCE STORAGE (Bottom Right: x=1050..1480, y=590..870) ---
    draw_rounded_rect(draw, (1050, 590, 1480, 870), 14, fill='#FFFBEB', outline='#F59E0B', width=1)
    
    # STEP 4 Badge (Dynamic width with exact padding)
    draw_badge(draw, 1070, 605, "STEP 4. 영구 보관함", font_badge, fill='#FEF3C7', outline='#F59E0B', text_color='#92400E', pad_x=14, pad_y=4)
    draw.text((1070, 645), "디스크 자동 보존 & 즉시 복원", fill='#0F172A', font=font_card_t)

    draw_rounded_rect(draw, (1070, 680, 1460, 845), 10, fill='#FFFFFF', outline='#FDE68A', width=1)
    draw.text((1090, 695), "💾 저장 위치: _internal/chord_studio_v2/runs/", fill='#B45309', font=font_card_sub)
    draw.text((1090, 725), "• job.json / result.json / vision_overlay.json 영구 보관", fill='#334155', font=font_body)
    draw.text((1090, 750), "• 앱 재시작 / PC 재부팅 시 재분석 없이 0.1초 즉시 복원", fill='#334155', font=font_body)
    draw.text((1090, 785), "• 보관함 배지 2종 분리 표시:", fill='#0F172A', font=font_body_b)
    
    # Pill Badges in Step 4 with clean colored boxes
    draw_badge(draw, 1090, 807, "✓ 음성 완료 (오디오 코드)", font_mini, fill='#ECFDF5', outline='#10B981', text_color='#047857', pad_x=8, pad_y=3, radius=4)
    draw_badge(draw, 1265, 807, "✓ 비전 완료 (지판·손 추적)", font_mini, fill='#F0F9FF', outline='#0284C7', text_color='#0369A1', pad_x=8, pad_y=3, radius=4)

    # Connector from Middle Engines to Studio
    # Audio Lane -> Studio
    draw.line([(980, 310), (1015, 310), (1015, 330), (1050, 330)], fill='#0D9488', width=2)
    draw_arrow(draw, (1040, 330), (1050, 330), color='#0D9488', width=2)
    # Vision Lane -> Studio
    draw.line([(980, 710), (1015, 710), (1015, 420), (1050, 420)], fill='#7C3AED', width=2)
    draw_arrow(draw, (1040, 420), (1050, 420), color='#7C3AED', width=2)

    # Studio -> Persistence
    draw.line([(1265, 560), (1265, 590)], fill='#D97706', width=2)
    draw_arrow(draw, (1265, 580), (1265, 590), color='#D97706', width=2)

    # Bottom Footer
    draw.text((40, 925), "Guitar Chord Studio v2.0 Architecture Pipeline | Powered by Demucs 6s · Spotify Basic Pitch · MediaPipe C++ · PyWebView", fill='#94A3B8', font=font_body)
    draw.text((1300, 925), "공식 배포본 v2.0 기준", fill='#94A3B8', font=font_body)

    # Save to both paths
    out_white = Path(r"E:\GUITAR\chord_studio_pipeline_white.png")
    out_default = Path(r"E:\GUITAR\chord_studio_pipeline.png")
    out_brain = Path(r"C:\Users\evev2\.gemini\antigravity\brain\4d6a6d70-1263-4f56-a0a9-6c2b7fea1875\chord_studio_pipeline_white.png")

    img.save(str(out_white), 'PNG', optimize=True)
    img.save(str(out_default), 'PNG', optimize=True)
    img.save(str(out_brain), 'PNG', optimize=True)
    print(f"White background pipeline diagram regenerated with fixed badge bounds:\n1. {out_white}\n2. {out_default}\n3. {out_brain}")

if __name__ == '__main__':
    generate_white_diagram()
