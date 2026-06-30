/* ============================================================
   LittleDaisy — drawing front-end
   ============================================================ */

const canvas    = document.getElementById('canvas');
const ctx       = canvas.getContext('2d');
const statusEl  = document.getElementById('status');
const infoEl    = document.getElementById('info');
const lastSaved = document.getElementById('last-saved');

/* ---------- state ---------- */

let strokes        = [];      // [{stroke_id, points:[[x,y], ...]}], top-left origin
let currentStroke  = null;
let activePointer  = null;    // single-pointer drawing (no multi-touch chaos)
let tool           = 'pen';   // 'pen' | 'eraser-stroke' | 'eraser-pixel'

let previewSocket      = null;
let previewSendPending = false;
let previewReconnectId = null;

/* visual config */
const PEN_WIDTH_PX           = 3;
const PIXEL_ERASER_RADIUS_PX = 18;
const STROKE_ERASER_HIT_PX   = 12;   // tap-distance for stroke selection

/* Capture a dense path. Coalesced pointer samples preserve stylus/touch data
   that the browser may combine into a single pointermove event. Long gaps are
   interpolated so curves such as U do not become sharp V shapes. */
const POINT_SPACING_PX          = 0.75;
const MAX_POINTS_PER_STROKE     = 50000;
const PREVIEW_SEND_INTERVAL_MS  = 33;
let fallbackStrokeCounter        = 0;

function makeStrokeId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
    }
    fallbackStrokeCounter += 1;
    return `stroke-${Date.now()}-${fallbackStrokeCounter}`;
}


/* ---------- live Raspberry Pi preview ---------- */

function connectPreviewSocket() {
    if (previewSocket &&
        (previewSocket.readyState === WebSocket.OPEN ||
         previewSocket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    previewSocket = new WebSocket(
        `${protocol}//${window.location.host}/ws/preview`
    );

    previewSocket.addEventListener('open', () => {
        if (previewReconnectId !== null) {
            clearTimeout(previewReconnectId);
            previewReconnectId = null;
        }
        queuePreviewUpdate();
    });

    previewSocket.addEventListener('close', () => {
        previewSocket = null;
        if (previewReconnectId === null) {
            previewReconnectId = setTimeout(() => {
                previewReconnectId = null;
                connectPreviewSocket();
            }, 1500);
        }
    });

    previewSocket.addEventListener('error', () => {
        /* The close event handles reconnection. */
    });
}

function getPreviewStrokes() {
    const snapshot = strokes.map(stroke => ({
        stroke_id: stroke.stroke_id,
        ...(stroke.parent_stroke_id
            ? { parent_stroke_id: stroke.parent_stroke_id }
            : {}),
        points: stroke.points.map(point => [point[0], point[1]])
    }));

    if (currentStroke && currentStroke.points.length > 0) {
        snapshot.push({
            stroke_id: currentStroke.stroke_id,
            points: currentStroke.points.map(point => [point[0], point[1]])
        });
    }

    return snapshot;
}

function queuePreviewUpdate() {
    /* Full drawing snapshots at about 30 messages/second. */
    if (previewSendPending) return;
    previewSendPending = true;

    setTimeout(() => {
        previewSendPending = false;

        if (!previewSocket || previewSocket.readyState !== WebSocket.OPEN) {
            return;
        }

        previewSocket.send(JSON.stringify({
            type: 'raw_preview',
            canvas_size_px: canvas.clientWidth,
            strokes: getPreviewStrokes(),
        }));
    }, PREVIEW_SEND_INTERVAL_MS);
}

/* ---------- canvas sizing ---------- */

/* Aspect ratio is fetched from the server (/config) at startup so that
 * config.py is the single source of truth. Defaults to 1:1 until loaded. */
let ASPECT_W = 1;
let ASPECT_H = 1;

async function loadConfig() {
    try {
        const res = await fetch('/config');
        const cfg = await res.json();
        ASPECT_W = cfg.canvas_aspect_w;
        ASPECT_H = cfg.canvas_aspect_h;
    } catch (e) {
        console.warn('Could not load /config, using 1:1 default.', e);
    }
    resizeCanvas();
}

function resizeCanvas() {
    /* Fit the canvas inside the wrap container while preserving ASPECT_W:ASPECT_H.
     * getBoundingClientRect gives the post-layout size, which is accurate even
     * on the first paint and after orientation changes. */
    const wrap = document.querySelector('.canvas-wrap');
    const rect  = wrap.getBoundingClientRect();
    const availW = Math.floor(rect.width);
    const availH = Math.floor(rect.height);

    let w, h;
    if (ASPECT_W === 0 || ASPECT_H === 0) {
        /* 0:0 means "fill the wrap completely" — no letterboxing */
        w = availW;
        h = availH;
    } else if (availW / availH < ASPECT_W / ASPECT_H) {
        /* container is taller than the ratio → width is the limiting side */
        w = availW;
        h = Math.floor(w * ASPECT_H / ASPECT_W);
    } else {
        /* container is wider than the ratio → height is the limiting side */
        h = availH;
        w = Math.floor(h * ASPECT_W / ASPECT_H);
    }

    /* Use devicePixelRatio for crisp lines on Retina/HiDPI */
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width  = w + 'px';
    canvas.style.height = h + 'px';
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

function appendDensePoint(stroke, point) {
    if (!stroke || stroke.points.length >= MAX_POINTS_PER_STROKE) return;

    const last = stroke.points[stroke.points.length - 1];
    if (!last) {
        stroke.points.push(point);
        return;
    }

    const dxPx = (point[0] - last[0]) * canvas.clientWidth;
    const dyPx = (point[1] - last[1]) * canvas.clientHeight;
    const distancePx = Math.hypot(dxPx, dyPx);

    if (distancePx === 0) return;

    const steps = Math.max(1, Math.ceil(distancePx / POINT_SPACING_PX));
    const remaining = MAX_POINTS_PER_STROKE - stroke.points.length;
    const count = Math.min(steps, remaining);

    for (let index = 1; index <= count; index++) {
        const ratio = index / steps;
        stroke.points.push([
            last[0] + (point[0] - last[0]) * ratio,
            last[1] + (point[1] - last[1]) * ratio,
        ]);
    }
}

function appendPointerSamples(stroke, event) {
    const samples = typeof event.getCoalescedEvents === 'function'
        ? event.getCoalescedEvents()
        : [event];

    /* Some browsers return an empty array when there are no extra samples. */
    const usableSamples = samples.length > 0 ? samples : [event];
    for (const sample of usableSamples) {
        appendDensePoint(stroke, pointerToNorm(sample));
    }
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
    queuePreviewUpdate();
}

function updateInfo() {
    const storedPoints = strokes.reduce((sum, stroke) => sum + stroke.points.length, 0);
    const activePoints = currentStroke ? currentStroke.points.length : 0;
    const totalStrokes = strokes.length + (currentStroke ? 1 : 0);
    infoEl.textContent = `strokes: ${totalStrokes}  ·  points: ${storedPoints + activePoints}`;
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
                if (seg.length >= 2) {
                    newStrokes.push({
                        stroke_id: makeStrokeId(),
                        parent_stroke_id: stroke.stroke_id,
                        points: seg,
                    });
                }
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
        currentStroke = { stroke_id: makeStrokeId(), points: [p] };
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
        appendPointerSamples(currentStroke, ev);
        redraw();
    } else if (tool === 'eraser-stroke') {
        if (eraseStrokeAt(p)) redraw();
    } else if (tool === 'eraser-pixel') {
        if (pixelEraseAt(p)) redraw();
    }
});

function endPointer(ev) {
    if (ev.pointerId !== activePointer) return;

    if (tool === 'pen' && currentStroke) {
        appendPointerSamples(currentStroke, ev);
        if (currentStroke.points.length >= 1) strokes.push(currentStroke);
        currentStroke = null;
        redraw();
    }

    activePointer = null;
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
    strokes = [];
    currentStroke = null;
    redraw();

    if (previewSocket && previewSocket.readyState === WebSocket.OPEN) {
        previewSocket.send(JSON.stringify({ type: 'clear' }));
    }
    setStatus('Cleared', 'ok');
});

/* ---------- detect / save ---------- */

function setStatus(msg, cls = '') {
    statusEl.textContent = msg;
    statusEl.className   = 'status ' + cls;
}

document.getElementById('btn-detect').addEventListener('click', async () => {
    // An empty Detect snapshot is valid: it means the target drawing is empty
    // and a later difference job may need to erase committed robot strokes.
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
            `Saved · ${data.point_count} points · bottom-left origin`,
            'ok'
        );
        lastSaved.textContent = data.saved_to;
    } catch (e) {
        console.error(e);
        setStatus('Error: ' + e.message, 'err');
    }
});

/* ---------- init ---------- */

connectPreviewSocket();
setTool('pen');
loadConfig();   /* fetches aspect ratio from /config, then calls resizeCanvas() */