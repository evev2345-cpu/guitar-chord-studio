import os
from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=180, right=180):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_callout(doc, text, title="알아두기", border_color="0D9488", bg_color="F0FDFA"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Inches(6.2)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

    # Left border only
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="none"/>\n'
        f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>\n'
        f'  <w:bottom w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    run_t = p.add_run(f"📌 {title}: ")
    run_t.bold = True
    run_t.font.name = "맑은 고딕"
    run_t.font.size = Pt(10)
    run_t.font.color.rgb = RGBColor(13, 148, 136) if border_color == "0D9488" else RGBColor(37, 99, 235)

    run_body = p.add_run(text)
    run_body.font.name = "맑은 고딕"
    run_body.font.size = Pt(9.5)
    run_body.font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def build_manual():
    doc = Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    # Normal Style Font
    style_normal = doc.styles['Normal']
    style_normal.font.name = '맑은 고딕'
    style_normal.font.size = Pt(10.5)
    style_normal.font.color.rgb = RGBColor(30, 41, 59)
    style_normal.paragraph_format.line_spacing = 1.3
    style_normal.paragraph_format.space_after = Pt(6)

    # Image Paths (converted to standard PNG)
    img_dir = Path(r'E:\GUITAR\manual_images')
    img_home = img_dir / 'media_1794004610143_15a39a10.png'
    img_studio = img_dir / 'media_1794009155691_44c22d7b.png'
    img_calib = img_dir / 'media_1794007959249_462bc725.png'
    img_history = img_dir / 'media_1794019067922_11189a4c.png'

    # Title Banner
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(12)
    title_p.paragraph_format.space_after = Pt(2)
    title_run = title_p.add_run("Guitar Chord Studio v2.0")
    title_run.bold = True
    title_run.font.size = Pt(24)
    title_run.font.color.rgb = RGBColor(15, 23, 42)

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(16)
    sub_run = sub_p.add_run("사용자 매뉴얼 (User Guide) — AI 기반 코드 악보 에디터 & 비전 지판 분석")
    sub_run.font.size = Pt(12)
    sub_run.font.color.rgb = RGBColor(100, 116, 139)

    add_callout(
        doc,
        "본 프로그램은 AI 딥러닝 기술을 사용하여 연주 영상과 음악에서 기타 코드를 자동 추출하지만, 완벽하지 않습니다!!\n"
        "원곡의 믹싱 상태, 악기 간섭, 특수 이펙터, 변칙 튜닝 및 촬영 조명/각도 등에 따라 일부 코드가 다르게 인식될 수 있습니다. "
        "따라서 AI가 제안한 코드를 기초로 삼으시고, 프로그램에 내장된 '클릭 한 번으로 코드 직접 수정' 및 '추천 후보 교체' 기능을 적극 활용하여 연주자 본인만의 완벽한 악보를 완성해 주시기 바랍니다.",
        title="필독: 본 프로그램은 완벽하지 않습니다!!",
        border_color="DC2626",
        bg_color="FEF2F2"
    )

    doc.add_paragraph("—" * 45).paragraph_format.space_after = Pt(12)

    # Section 1: Overview
    h1 = doc.add_heading("1. 프로그램 소개 및 특징", level=1)
    h1.paragraph_format.space_before = Pt(14)
    h1.paragraph_format.space_after = Pt(6)
    for r in h1.runs:
        r.font.name = '맑은 고딕'
        r.font.color.rgb = RGBColor(13, 148, 136)

    p1 = doc.add_paragraph(
        "Guitar Chord Studio는 음악(MP3, WAV) 또는 연주 영상(MP4, AVI, MOV)을 업로드하면, "
        "딥러닝 음향 AI와 컴퓨터 비전 기술을 결합하여 실시간으로 16박자 기타 코드 악보를 추출하고, "
        "화면 위 연주자의 손가락과 기타 지판을 3차원으로 추적해 주는 전문 기타 연습 및 채보 데스크톱 솔루션입니다."
    )

    doc.add_paragraph(
        "• 100% 완전 무설치 독립 실행 (Standalone): 파이썬이나 별도 개발 도구 설치 없이 더블 클릭만으로 즉시 구동됩니다.\n"
        "• AI 기타 트랙 분리 (Demucs 6s): 드럼, 베이스, 보컬 등에서 기타 소리만 분리하여 높은 코드 정확도를 제공합니다.\n"
        "• 마우스 클릭 즉각 편집: 오인식된 코드는 클릭 한 번으로 손쉽게 수정 및 저장할 수 있습니다.\n"
        "• 지판 4점 비전 추적: 영상 속 기타 너트와 브릿지 4점만 지정하면, 전체 영상의 프렛 격자와 손가락 골격을 자동 추적합니다.\n"
        "• 영구 자동 보관: 프로그램을 종료하고 컴퓨터를 재부팅해도 이전 분석 곡과 편집 내역이 100% 보존됩니다."
    )

    add_callout(
        doc,
        "배포 시 제공되는 'GuitarChordStudio_v2.0_Windows.zip' 압축을 푼 뒤, "
        "폴더 안의 'GuitarChordStudio.exe'를 더블 클릭하시면 바로 실행됩니다.",
        title="빠른 시작",
        border_color="0D9488",
        bg_color="F0FDFA"
    )

    # Section 2: Home Screen
    h2 = doc.add_heading("2. 메인 화면 및 파일 업로드", level=1)
    h2.paragraph_format.space_before = Pt(16)
    h2.paragraph_format.space_after = Pt(6)
    for r in h2.runs:
        r.font.name = '맑은 고딕'
        r.font.color.rgb = RGBColor(13, 148, 136)

    doc.add_paragraph(
        "프로그램을 실행하면 첫 홈 화면이 나타납니다. "
        "중앙의 점선 업로드 상자에 음원(WAV, MP3) 또는 연주 영상(MP4) 파일을 끌어다 놓거나(Drag & Drop), "
        "클릭하여 파일을 선택하면 자동으로 AI 분석이 시작됩니다."
    )

    if img_home.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(4)
        p_img.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(img_home), width=Inches(3.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(10)
        r_cap = p_cap.add_run("▲ [그림 1] 메인 홈 화면 — 파일 드래그 앤 드롭 및 최근 분석 보관함")
        r_cap.font.size = Pt(8.5)
        r_cap.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph(
        "• 분석 진행 중에는 화면 하단에 진행률(%)과 상태 메시지가 실시간으로 표시됩니다.\n"
        "• 5분 길이의 곡 기준, 약 10~20초 내외로 음향 분리 및 16박자 코드 추출이 완료되고 작업 공간(스튜디오)으로 자동 전환됩니다."
    )

    # Section 3: Studio Workspace
    h3 = doc.add_heading("3. 스튜디오 작업 공간 (악보, 파형, 코드 에디터)", level=1)
    h3.paragraph_format.space_before = Pt(16)
    h3.paragraph_format.space_after = Pt(6)
    for r in h3.runs:
        r.font.name = '맑은 고딕'
        r.font.color.rgb = RGBColor(13, 148, 136)

    doc.add_paragraph(
        "분석이 완료되면 직관적인 전문 작업 공간이 열립니다. "
        "음악을 재생하면서 실시간으로 코드의 흐름을 확인하고, 템포와 오프셋을 미세 조절하며, 잘못된 코드를 즉각 교정할 수 있습니다."
    )

    if img_studio.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(4)
        p_img.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(img_studio), width=Inches(5.8))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(10)
        r_cap = p_cap.add_run("▲ [그림 2] Chord Studio 스튜디오 작업 공간 (영상, 가상 지판, 16박자 악보, 파형 스크롤러)")
        r_cap.font.size = Pt(8.5)
        r_cap.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph(
        "주요 조작 컨트롤 안내:\n"
        "1. 표기 기준 & 카포(Capo): 상단에서 '운지(카포)' 또는 '실음(콘서트)' 표기를 선택하고 카포 위치(0~12)를 변경할 수 있습니다.\n"
        "2. BPM & 첫박 오프셋: 자동 계산된 16박자 격자 오차가 있을 경우, -1칸 / +1칸 버튼이나 수치 조절로 박자를 완벽히 일치시킬 수 있습니다.\n"
        "3. 코드 클릭 수정: 악보 상의 특정 코드 블록을 클릭하면 루트(C, D, E...) 및 퀄리티(Major, minor, 7, m7 등)를 즉시 변경할 수 있으며, 수정 즉시 영구 저장됩니다.\n"
        "4. 키보드 단축키: 스페이스바(Space)로 재생/일시정지, 좌우 방향키(← / →)로 5초 이동, 쉼표/마침표(, / .)로 이전/다음 마디 이동이 가능합니다."
    )

    # Section 4: 4-Point Vision Calibration
    h4 = doc.add_heading("4. 지판 직접 지정(4점) 및 비전 추적", level=1)
    h4.paragraph_format.space_before = Pt(16)
    h4.paragraph_format.space_after = Pt(6)
    for r in h4.runs:
        r.font.name = '맑은 고딕'
        r.font.color.rgb = RGBColor(13, 148, 136)

    doc.add_paragraph(
        "동영상(MP4)을 업로드한 경우, 상단 우측의 [지판 직접 지정 (4점)] 버튼 또는 지판 비전 인디케이터를 클릭하여 "
        "화면 위 기타 지판의 4개 꼭짓점을 직접 지정할 수 있습니다."
    )

    add_callout(
        doc,
        "지판 4점을 찍은 뒤 실행하는 비전 분석은 영상의 모든 프레임마다 AI가 손가락 관절과 프렛 좌표를 정밀 추적하므로 "
        "처리 시간이 많이 오래 걸립니다! (동영상 길이와 PC 사양에 따라 수 분에서 수십 분 이상 소요될 수 있습니다.)\n"
        "💡 안심하세요: 비전 분석이 백그라운드에서 진행되는 동안에도 음악 재생, 코드 확인, 악보 편집 등 다른 모든 작업은 멈춤 없이 정상 작동하므로 "
        "비전 분석을 켜두고 먼저 다른 작업을 진행하셔도 좋습니다.",
        title="분석 시간 주의: 비전 분석은 많이 오래 걸립니다!!",
        border_color="F59E0B",
        bg_color="FFFBEB"
    )

    if img_calib.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(4)
        p_img.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(img_calib), width=Inches(3.4))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(10)
        r_cap = p_cap.add_run("▲ [그림 3] 4점 지판 캘리브레이션 모달 — 1번 줄/6번 줄 너트 및 브릿지 순서 클릭")
        r_cap.font.size = Pt(8.5)
        r_cap.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph(
        "4점 지정 순서 (화면 안내 문구에 따라 클릭):\n"
        "  ① 1번 줄(가장 얇은 줄) 너트 (헤드 쪽 끝)\n"
        "  ② 6번 줄(가장 굵은 줄) 너트 (헤드 쪽 끝)\n"
        "  ③ 6번 줄 브릿지 방향 끝 (또는 마지막 22프렛 바디 쪽)\n"
        "  ④ 1번 줄 브릿지 방향 끝\n\n"
        "좌표 지정 후 [저장 및 비전 분석 시작]을 누르면 백그라운드에서 AI가 전체 영상 프레임의 손가락 스켈레톤과 가상 지판 격자를 자동 생성합니다. "
        "상단 인디케이터가 '⏳ 지판 비전 분석 중 (0%~100%)'으로 바뀌며, 분석 중에도 악보 재생과 코드 편집을 계속 진행하실 수 있습니다."
    )

    add_callout(
        doc,
        "비전 분석이 완료되면 상단 인디케이터가 민트색 '✓ 지판 비전 활성'으로 바뀌고, "
        "동영상 위 실시간 지판 그리드와 손가락 추적선이 나타나 실제 누른 프렛을 시각적으로 확인할 수 있습니다.",
        title="비전 추적 효과",
        border_color="0D9488",
        bg_color="F0FDFA"
    )

    # Section 5: History Archive
    h5 = doc.add_heading("5. 분석 보관함 및 영구 저장 관리", level=1)
    h5.paragraph_format.space_before = Pt(16)
    h5.paragraph_format.space_after = Pt(6)
    for r in h5.runs:
        r.font.name = '맑은 고딕'
        r.font.color.rgb = RGBColor(13, 148, 136)

    doc.add_paragraph(
        "홈 화면 하단에는 지금까지 분석했던 모든 곡들이 안전하게 보관되는 '분석 보관함'이 있습니다. "
        "사용자가 수정한 코드, 지판 4점 좌표, 분리 음원 등 모든 작업 결과가 영구 저장됩니다."
    )

    if img_history.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(4)
        p_img.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(img_history), width=Inches(5.8))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(10)
        r_cap = p_cap.add_run("▲ [그림 4] 분석 보관함 — 음성 완료 / 비전 완료 분리 상태 배지 표시")
        r_cap.font.size = Pt(8.5)
        r_cap.font.color.rgb = RGBColor(100, 116, 139)

    # Table of Badges
    table = doc.add_table(rows=5, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    headers = ["상태 배지", "표시 조건", "상세 설명"]
    col_widths = [Inches(1.5), Inches(1.8), Inches(2.9)]

    # Header Row
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        hdr_cells[i].width = col_widths[i]
        set_cell_background(hdr_cells[i], "0F172A")
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.bold = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(255, 255, 255)

    badge_data = [
        ("✓ 음성 완료", "오디오 코드 분석 완료 시", "기타 코드, 16박자 격자, BPM, 첫박 오프셋이 즉시 복원 가능"),
        ("✓ 비전 완료", "4점 지판 캘리브레이션 완료 시", "전체 영상 프레임 손가락 스켈레톤 및 지판 추적이 적용됨"),
        ("⌖ 비전 대기", "영상 업로드 후 지판 미지정 시", "음성은 완료되었으나 지판 4점을 아직 찍지 않은 상태"),
        ("오디오 전용", "WAV, MP3 파일 업로드 시", "영상 화면이 없는 순수 오디오 파일 (비전 미지원)")
    ]

    for row_idx, data in enumerate(badge_data, start=1):
        row_cells = table.rows[row_idx].cells
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for c_idx, text in enumerate(data):
            row_cells[c_idx].text = text
            row_cells[c_idx].width = col_widths[c_idx]
            set_cell_background(row_cells[c_idx], bg)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=120, right=120)
            p = row_cells[c_idx].paragraphs[0]
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].font.bold = True
                p.runs[0].font.size = Pt(9.5)
                p.runs[0].font.color.rgb = RGBColor(13, 148, 136) if "완료" in text else RGBColor(100, 116, 139)
            else:
                p.runs[0].font.size = Pt(9)
                p.runs[0].font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Section 6: FAQ & Distribution
    h6 = doc.add_heading("6. 자주 묻는 질문 (FAQ) 및 배포 팁", level=1)
    h6.paragraph_format.space_before = Pt(16)
    h6.paragraph_format.space_after = Pt(6)
    for r in h6.runs:
        r.font.name = '맑은 고딕'
        r.font.color.rgb = RGBColor(13, 148, 136)

    doc.add_paragraph(
        "Q1. 분석 시간은 얼마나 걸리나요?\n"
        "  → 기본 음원 분리 및 16박자 코드 추출: 일반 4~5분 가요 기준 약 15~30초 내외로 빠르고 쾌적하게 완료됩니다.\n"
        "  → 지판 4점 비전 분석: 많이 오래 걸립니다!! 영상의 모든 프레임에서 손가락 관절 골격과 지판 프렛을 하나하나 정밀 추적하므로 수 분에서 수십 분 이상 걸릴 수 있습니다. 비전 분석을 실행해 두고 백그라운드로 돌리면서 악보 재생 및 코드 수정 작업을 먼저 진행하시는 것을 추천합니다.\n\n"
        "Q2. 상대방 컴퓨터에 파이썬을 설치해야 하나요?\n"
        "  → 전혀 필요 없습니다. 패키지 내부에 파이썬 런타임, AI 딥러닝 모델, FFMpeg 영상 변환기가 모두 들어있어 다른 프로그램 설치 없이 바로 실행됩니다.\n\n"
        "Q3. 배포할 때 'GuitarChordStudio.exe' 파일만 복사해서 주면 되나요?\n"
        "  → 안 됩니다! 'GuitarChordStudio.exe'는 같은 폴더에 있는 '_internal' 폴더와 한 세트입니다. "
        "반드시 'GuitarChordStudio_v2.0_Windows.zip' 압축 파일 전체를 전달하셔야 정상 작동합니다.\n\n"
        "Q4. 실행 시 'Windows의 PC 보호' 파란 창이 뜨면 어떻게 하나요?\n"
        "  → 자체 개발 무설치 프로그램의 일반적인 Windows 스마트스크린 안내입니다. "
        "[추가 정보]를 누른 뒤 [실행] 버튼을 클릭하시면 정상적으로 시작됩니다.\n\n"
        "Q5. 분석했던 음악 데이터를 다른 PC로 옮기거나 백업할 수 있나요?\n"
        "  → 가능합니다. 프로그램 폴더 내 '_internal/chord_studio_v2/runs' 폴더를 복사하여 백업하거나 다른 PC의 동일 위치에 붙여넣으면 분석 기록이 그대로 이어집니다."
    )

    out_path = Path(r"E:\GUITAR\ChordStudio_v2.0_사용자_매뉴얼.docx")
    doc.save(str(out_path))
    print(f"Manual successfully created: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")

    dist_out = Path(r"E:\GUITAR\dist\GuitarChordStudio\ChordStudio_v2.0_사용자_매뉴얼.docx")
    if dist_out.parent.exists():
        doc.save(str(dist_out))
        print(f"Dist manual copied: {dist_out} ({dist_out.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    build_manual()
