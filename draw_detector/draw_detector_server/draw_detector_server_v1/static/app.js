/* ============================================================
   LittleDaisy — drawing front-end
   ============================================================ */

const canvas    = document.getElementById('canvas');
const ctx       = canvas.getContext('2d');
const statusEl  = document.getElementById('status');
const infoEl    = document.getElementById('info');
const lastSaved = document.getElementById('last-saved');

/* ---------- state ---------- */

let strokes        = [];      // [{points: [[x,y], ...]}]  x, y in 0..1
let currentStroke  = null;
let activePointer  = null;    // single-pointer drawing (no multi-touch chaos)
let tool           = 'pen';   // 'pen' | 'eraser-stroke' | 'eraser-pixel'

/* visual config */
const PEN_WIDTH_PX           = 3;
const PIXEL_ERASER_RADIUS_PX = 18;
const STROKE_ERASER_HIT_PX   = 12;   // tap-distance for stroke selection

/* ---------- canvas sizing ---------- */

function resizeCanvas() {
    /* 1:1 square, sized to the shorter side of the wrap container */
    const wrap = document.querySelector('.canvas-wrap');
    const side = Math.floor(Math.min(wrap.clientWidth, wrap.clientHeight)) - 4;

    /* Use devicePixelRatio for crisp lines on Retina/HiDPI */
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = side * dpr;
    canvas.height = side * dpr;
    canvas.style.width  = side + 'px';
    canvas.style.height = side + 'px';
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    redraw();
}

window.addEventListener('resize',           resizeCanvas);
window.addEventListener('orientationchange', resizeCanvas);

/* ---------- coordinate helpers ---------- */

function pointerToNorm(ev) {
    /* Convert a PointerEvent to normalized 0..1 canvas coords. */
    const rect = canvas.getBoundingClientRect();
    const x = (ev.clientX - rect.left) / rect.width;
    const y = (ev.clientY - rect.top)  / rect.height;
    return [
        Math.max(0, Math.min(1, x)),
        Math.max(0, Math.min(1, y)),
    ];
}

function normToCss(p) {
    /* Normalized → CSS pixel coords (for drawing on the canvas). */
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    return [p[0] * w, p[1] * h];
}

/* ---------- drawing primitives ---------- */

function clearCanvas() {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
}

function drawStroke(stroke) {
    if (!stroke.points || stroke.points.length < 1) return;

    ctx.beginPath();
    ctx.lineCap   = 'round';
    ctx.lineJoin  = 'round';
    ctx.lineWidth = PEN_WIDTH_PX;
    ctx.strokeStyle = 'black';

    if (stroke.erased) return;   // (only used during stroke-erase preview)

    const pts = stroke.points;
    if (pts.length === 1) {
        const [x, y] = normToCss(pts[0]);
        ctx.fillStyle = 'black';
        ctx.beginPath();
        ctx.arc(x, y, PEN_WIDTH_PX / 2, 0, Math.PI * 2);
        ctx.fill();
        return;
    }

    const [x0, y0] = normToCss(pts[0]);
    ctx.moveTo(x0, y0);
    for (let i = 1; i < pts.length; i++) {
        const [x, y] = normToCss(pts[i]);
        ctx.lineTo(x, y);
    }
    ctx.stroke();
}

function redraw() {
    clearCanvas();
    for (const s of strokes) drawStroke(s);
    if (currentStroke) drawStroke(currentStroke);
    updateInfo();
}

function updateInfo() {
    const totalPoints = strokes.reduce((s, st) => s + st.points.length, 0);
    infoEl.textContent = `strokes: ${strokes.length}  ·  points: ${totalPoints}`;
}

/* ---------- stroke eraser ---------- */

function distPointToSegment(p, a, b) {
    const [px, py] = p, [ax, ay] = a, [bx, by] = b;
    const dx = bx - ax, dy = by - ay;
    if (dx === 0 && dy === 0) return Math.hypot(px - ax, py - ay);
    let t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy);
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function eraseStrokeAt(normPt) {
    /* Convert hit radius to normalized units. Canvas is square. */
    const hitNorm = STROKE_ERASER_HIT_PX / canvas.clientWidth;

    for (let i = strokes.length - 1; i >= 0; i--) {
        const pts = strokes[i].points;

        if (pts.length === 1) {
            if (Math.hypot(pts[0][0] - normPt[0], pts[0][1] - normPt[1]) < hitNorm) {
                strokes.splice(i, 1);
                return true;
            }
            continue;
        }

        for (let j = 1; j < pts.length; j++) {
            if (distPointToSegment(normPt, pts[j - 1], pts[j]) < hitNorm) {
                strokes.splice(i, 1);
                return true;
            }
        }
    }
    return false;
}

/* ---------- pixel eraser ----------
   Splits strokes by removing points inside the eraser circle. A stroke
   passing through the eraser is broken into two strokes.
*/

function pixelEraseAt(normPt) {
    const rNorm = PIXEL_ERASER_RADIUS_PX / canvas.clientWidth;
    const newStrokes = [];
    let changed = false;

    for (const stroke of strokes) {
        const segs   = [];   // segments of points that survive
        let current  = [];

        for (const p of stroke.points) {
            const inside = Math.hypot(p[0] - normPt[0], p[1] - normPt[1]) < rNorm;
            if (inside) {
                if (current.length) { segs.push(current); current = []; }
                changed = true;
            } else {
                current.push(p);
            }
        }
        if (current.length) segs.push(current);

        if (segs.length === 1 && segs[0].length === stroke.points.length) {
            newStrokes.push(stroke);   // untouched
        } else {
            for (const seg of segs) {
                if (seg.length >= 2) newStrokes.push({ points: seg });
            }
        }
    }

    if (changed) strokes = newStrokes;
    return changed;
}

/* ---------- pointer events ---------- */

canvas.addEventListener('pointerdown', (ev) => {
    if (activePointer !== null) return;   // ignore extra fingers
    activePointer = ev.pointerId;
    canvas.setPointerCapture(ev.pointerId);
    ev.preventDefault();

    const p = pointerToNorm(ev);

    if (tool === 'pen') {
        currentStroke = { points: [p] };
        redraw();
    } else if (tool === 'eraser-stroke') {
        if (eraseStrokeAt(p)) redraw();
    } else if (tool === 'eraser-pixel') {
        if (pixelEraseAt(p)) redraw();
    }
});

canvas.addEventListener('pointermove', (ev) => {
    if (ev.pointerId !== activePointer) return;
    ev.preventDefault();

    const p = pointerToNorm(ev);

    if (tool === 'pen' && currentStroke) {
        /* dedupe identical consecutive points (jitter) */
        const last = currentStroke.points[currentStroke.points.length - 1];
        if (last[0] !== p[0] || last[1] !== p[1]) {
            currentStroke.points.push(p);
            redraw();
        }
    } else if (tool === 'eraser-stroke') {
        if (eraseStrokeAt(p)) redraw();
    } else if (tool === 'eraser-pixel') {
        if (pixelEraseAt(p)) redraw();
    }
});

function endPointer(ev) {
    if (ev.pointerId !== activePointer) return;
    activePointer = null;

    if (tool === 'pen' && currentStroke) {
        if (currentStroke.points.length >= 1) strokes.push(currentStroke);
        currentStroke = null;
        redraw();
    }
}
canvas.addEventListener('pointerup',     endPointer);
canvas.addEventListener('pointercancel', endPointer);
canvas.addEventListener('pointerleave',  endPointer);

/* ---------- toolbar ---------- */

function setTool(t) {
    tool = t;
    for (const b of document.querySelectorAll('.tool[data-tool]')) {
        b.classList.toggle('active', b.dataset.tool === t);
    }
    canvas.style.cursor =
        t === 'pen' ? 'crosshair'
      : t === 'eraser-pixel' ? 'cell'
      : 'not-allowed';
}

document.getElementById('tool-pen').addEventListener('click',
    () => setTool('pen'));
document.getElementById('tool-eraser-stroke').addEventListener('click',
    () => setTool('eraser-stroke'));
document.getElementById('tool-eraser-pixel').addEventListener('click',
    () => setTool('eraser-pixel'));

document.getElementById('btn-clear').addEventListener('click', () => {
    if (strokes.length === 0) return;
    strokes = [];
    currentStroke = null;
    redraw();
    setStatus('Cleared', 'ok');
});

/* ---------- detect / save ---------- */

function setStatus(msg, cls = '') {
    statusEl.textContent = msg;
    statusEl.className   = 'status ' + cls;
}

document.getElementById('btn-detect').addEventListener('click', async () => {
    if (strokes.length === 0) {
        setStatus('Nothing to send', 'err');
        return;
    }

    setStatus('Sending…', 'working');

    /* size in CSS pixels — server records it but does not need it for math */
    const canvasSizePx = canvas.clientWidth;

    try {
        const res = await fetch('/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                canvas_size_px: canvasSizePx,
                strokes:        strokes,
            }),
        });

        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();

        setStatus(
            `Saved · ${data.raw_count} → ${data.processed_count}`,
            'ok'
        );
        lastSaved.textContent = data.saved_to;
    } catch (e) {
        console.error(e);
        setStatus('Error: ' + e.message, 'err');
    }
});

/* ---------- init ---------- */

setTool('pen');
resizeCanvas();
