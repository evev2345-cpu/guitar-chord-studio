import base64

with open('sample_images/user_fret_b64.txt', 'r') as f:
    b64 = f.read().strip()

html_template = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>🎸 지판 프렛 & 칸 정밀 라벨러 (Zoom & Pan 지원)</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #18181f;
    color: #e0e0e0;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }
  header {
    background: #23232e;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #383848;
    z-index: 10;
  }
  h1 { font-size: 1.05rem; color: #4af; font-weight: 600; display: flex; align-items: center; gap: 8px; }
  .toolbar {
    background: #1c1c24;
    padding: 8px 20px;
    font-size: 0.85rem;
    border-bottom: 1px solid #2d2d3a;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
  }
  .zoom-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .zoom-btn {
    background: #2b2b38;
    color: #eee;
    border: 1px solid #444;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .zoom-btn.active, .zoom-btn:hover {
    background: #0070f3;
    border-color: #0070f3;
  }
  .viewport {
    flex: 1;
    overflow: auto;
    position: relative;
    background: #101014;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px;
  }
  .canvas-container {
    position: relative;
    box-shadow: 0 10px 40px rgba(0,0,0,0.8);
    border: 2px solid #0070f3;
    background: #000;
  }
  canvas { display: block; cursor: crosshair; }
  button {
    background: #333344;
    color: #fff;
    border: 1px solid #555;
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  button:hover { background: #444458; border-color: #4af; }
  button.primary { background: #0070f3; border-color: #0070f3; }
  button.primary:hover { background: #0051b3; }
  button.danger { background: #d32f2f; border-color: #d32f2f; }
  button.danger:hover { background: #9a0007; }
  button.success { background: #2e7d32; border-color: #2e7d32; }
  button.success:hover { background: #1b5e20; }
  .footer-bar {
    background: #1c1c24;
    padding: 8px 20px;
    border-top: 1px solid #2d2d3a;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    color: #88c0d0;
  }
  .fret-summary {
    font-family: monospace;
    color: #a3be8c;
  }
</style>
</head>
<body>

<header>
  <h1>🎸 기타 지판 프렛 & 칸 라벨러</h1>
  <div style="display: flex; gap: 8px;">
    <button id="btn-undo">↩ 취소 (Ctrl+Z)</button>
    <button id="btn-clear" class="danger">🗑 초기화</button>
    <button id="btn-download" class="success">📥 JSON 다운로드</button>
    <button id="btn-copy">📋 클립보드 복사</button>
    <button id="btn-save" class="primary">💾 서버 저장</button>
  </div>
</header>

<div class="toolbar">
  <div class="zoom-controls">
    <span>🔍 <b>화면 배율:</b></span>
    <button class="zoom-btn" onclick="setZoom(1.0)">100%</button>
    <button class="zoom-btn" onclick="setZoom(1.5)">150%</button>
    <button class="zoom-btn active" id="btn-zoom-2" onclick="setZoom(2.0)">200%</button>
    <button class="zoom-btn" onclick="setZoom(2.5)">250%</button>
    <button class="zoom-btn" onclick="setZoom(3.0)">300%</button>
    <button class="zoom-btn" onclick="setZoom(4.0)">400%</button>
    <span style="color:#888; margin-left: 10px;">(마우스 휠 스크롤로도 부드럽게 확대/축소 가능)</span>
  </div>
  <div>
    💡 <b>조작법:</b> 와이어 <b>상단(6번줄 쪽) 클릭 ➔ 하단(1번줄 쪽) 클릭</b>하면 선과 칸이 완성됩니다.
  </div>
</div>

<div class="viewport" id="viewport">
  <div class="canvas-container" id="container">
    <canvas id="labelCanvas"></canvas>
  </div>
</div>

<div class="footer-bar">
  <div id="status-text">와이어의 상단 점을 클릭하세요.</div>
  <div class="fret-summary" id="fret-summary">와이어: 0개 / 0칸</div>
</div>

<script>
const B64_DATA = 'data:image/png;base64,__B64_PLACEHOLDER__';
const canvas = document.getElementById('labelCanvas');
const ctx = canvas.getContext('2d');
const container = document.getElementById('container');
const viewport = document.getElementById('viewport');
const statusText = document.getElementById('status-text');
const fretSummary = document.getElementById('fret-summary');

let zoom = 2.0;
let img = new Image();
img.src = B64_DATA;

let rawW = 800;
let rawH = 150;

let wires = [];
let pendingTop = null;
let mousePos = { x: 0, y: 0 };

img.onload = () => {
  rawW = img.width;
  rawH = img.height;
  updateCanvasSize();
  render();
};

function setZoom(val) {
  zoom = Math.max(0.5, Math.min(6.0, val));
  document.querySelectorAll('.zoom-btn').forEach(b => {
    b.classList.toggle('active', b.innerText === `${Math.round(zoom * 100)}%`);
  });
  updateCanvasSize();
  render();
}

function updateCanvasSize() {
  canvas.width = Math.round(rawW * zoom);
  canvas.height = Math.round(rawH * zoom);
}

// 휠 줌 기능
viewport.addEventListener('wheel', (e) => {
  e.preventDefault();
  const delta = e.deltaY > 0 ? -0.2 : 0.2;
  setZoom(zoom + delta);
}, { passive: false });

const COLORS = [
  'rgba(255, 90, 90, 0.35)',
  'rgba(90, 255, 90, 0.35)',
  'rgba(90, 150, 255, 0.35)',
  'rgba(255, 200, 70, 0.35)',
  'rgba(200, 90, 255, 0.35)',
  'rgba(70, 255, 255, 0.35)'
];

function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

  // 1. 칸(Cell/Box) 색칠
  for (let i = 0; i < wires.length - 1; i++) {
    const w1 = wires[i];
    const w2 = wires[i + 1];

    ctx.fillStyle = COLORS[i % COLORS.length];
    ctx.beginPath();
    ctx.moveTo(w1.xt * zoom, 0);
    ctx.lineTo(w2.xt * zoom, 0);
    ctx.lineTo(w2.xb * zoom, canvas.height);
    ctx.lineTo(w1.xb * zoom, canvas.height);
    ctx.closePath();
    ctx.fill();

    // 칸 번호
    const midX = (w1.xt + w2.xt + w1.xb + w2.xb) / 4.0 * zoom;
    ctx.fillStyle = '#ffffff';
    ctx.font = `bold ${Math.round(11 * Math.min(zoom, 2.5))}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = '#000000';
    ctx.shadowBlur = 4;
    ctx.fillText(`${i + 1}칸`, midX, canvas.height / 2);
    ctx.shadowBlur = 0;
  }

  // 2. 와이어 선 긋기
  wires.forEach((w, idx) => {
    ctx.strokeStyle = idx === 0 ? '#ffff00' : '#00ff88';
    ctx.lineWidth = Math.max(1.5, zoom * 1.1);
    ctx.beginPath();
    ctx.moveTo(w.xt * zoom, 0);
    ctx.lineTo(w.xb * zoom, canvas.height);
    ctx.stroke();

    // 점
    ctx.fillStyle = '#ff0055';
    ctx.beginPath(); ctx.arc(w.xt * zoom, 4 * zoom, 3 * Math.min(zoom, 2.0), 0, Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.arc(w.xb * zoom, canvas.height - 4 * zoom, 3 * Math.min(zoom, 2.0), 0, Math.PI*2); ctx.fill();

    // 번호
    ctx.fillStyle = '#ffff55';
    ctx.font = `bold ${Math.round(10 * Math.min(zoom, 2.5))}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(idx === 0 ? 'Nut' : `${idx}`, w.xt * zoom, 14 * zoom);
  });

  // 3. 대기 중인 상단 점 및 가이드선
  if (pendingTop) {
    ctx.fillStyle = '#ff0055';
    ctx.beginPath();
    ctx.arc(pendingTop.x * zoom, 4 * zoom, 5 * zoom, 0, Math.PI*2);
    ctx.fill();

    ctx.strokeStyle = 'rgba(255, 255, 0, 0.9)';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pendingTop.x * zoom, 0);
    ctx.lineTo(mousePos.x, mousePos.y);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  fretSummary.innerText = `와이어: ${wires.length}개 / 칸(Box): ${Math.max(0, wires.length - 1)}칸`;
}

canvas.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  mousePos.x = e.clientX - rect.left;
  mousePos.y = e.clientY - rect.top;
  if (pendingTop) {
    render();
  }
});

canvas.addEventListener('click', (e) => {
  const rect = canvas.getBoundingClientRect();
  const rawX = (e.clientX - rect.left) / zoom;
  const rawY = (e.clientY - rect.top) / zoom;

  if (!pendingTop) {
    pendingTop = { x: rawX, y: rawY };
    statusText.innerText = `와이어 ${wires.length}번: 하단 점(1번줄 쪽)을 클릭해 선을 완성하세요.`;
  } else {
    const topX = pendingTop.x;
    const botX = rawX;

    wires.push({
      wire_idx: wires.length,
      xt: parseFloat(topX.toFixed(1)),
      xb: parseFloat(botX.toFixed(1)),
      m: parseFloat(((botX - topX) / rawH).toFixed(4)),
      b: parseFloat(topX.toFixed(1))
    });

    wires.sort((a, b) => a.xt - b.xt);
    wires.forEach((w, i) => w.wire_idx = i);

    pendingTop = null;
    statusText.innerText = `와이어 추가 완료! (총 ${wires.length}개 와이어, ${Math.max(0, wires.length - 1)}칸)`;
    render();
  }
});

// 취소
document.getElementById('btn-undo').addEventListener('click', () => {
  if (pendingTop) {
    pendingTop = null;
    statusText.innerText = '취소되었습니다. 다시 상단 점을 클릭하세요.';
  } else if (wires.length > 0) {
    wires.pop();
    statusText.innerText = `마지막 와이어 삭제됨. (남은 와이어: ${wires.length}개)`;
  }
  render();
});

// 초기화
document.getElementById('btn-clear').addEventListener('click', () => {
  if (confirm('모든 라벨을 초기화하시겠습니까?')) {
    wires = [];
    pendingTop = null;
    render();
  }
});

// 다운로드
document.getElementById('btn-download').addEventListener('click', () => {
  const data = { image: 'user_fret_example.png', width: rawW, height: rawH, wires: wires };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'user_fret_example.json';
  a.click();
});

// 클립보드 복사
document.getElementById('btn-copy').addEventListener('click', () => {
  const jsonStr = JSON.stringify({ image: 'user_fret_example.png', width: rawW, height: rawH, wires: wires }, null, 2);
  navigator.clipboard.writeText(jsonStr).then(() => {
    alert('📋 클립보드에 JSON 라벨이 복사되었습니다!');
  });
});

// 서버 저장
document.getElementById('btn-save').addEventListener('click', () => {
  fetch('/api/save_frets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: 'user_fret_example.png', width: rawW, height: rawH, wires: wires })
  }).then(r => r.json()).then(() => {
    alert('✅ 서버에 성공적으로 저장되었습니다!');
  }).catch(() => {
    alert('⚠️ 서버 미연결 상태입니다. 상단의 [JSON 다운로드] 또는 [클립보드 복사]를 이용해주세요!');
  });
});

window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
    document.getElementById('btn-undo').click();
  }
});
</script>
</body>
</html>
""".replace('__B64_PLACEHOLDER__', b64)

with open('fret_labeler.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print("Generated fret_labeler.html successfully!")
