"""
Overlay photo capture for MANY reference images (mobile friendly).

Single file. Run:  streamlit run zap.py

Reference images are loaded from the folder set in REFERENCE_DIR (see CONFIG below).
"""
import base64
import io
import re
import tempfile
import time
import zipfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps

st.set_page_config(
    page_title="Overlay Photo Capture",
    page_icon="📷",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    "<style>.block-container{padding-top:1rem;padding-left:.6rem;padding-right:.6rem;}</style>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- CONFIG
# >>> PUT THE PATH OF YOUR IMAGES FOLDER HERE (png / jpg / jpeg / webp) <<<
REFERENCE_DIR = Path(r"job_20261019/")
EXTS = {".png", ".jpg", ".jpeg", ".webp"}

COMPONENT_HTML = r'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body { margin: 0; padding: 4px; font-family: -apple-system, Segoe UI, Roboto, sans-serif; color: #31333f; touch-action: manipulation; }

  #stage { display: flex; justify-content: center; }
  #wrap { position: relative; background: #000; overflow: hidden; border-radius: 18px; width: 100%; aspect-ratio: 9/16; }
  #video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  #overlay { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; pointer-events: none; opacity: .5; }
  #grid { position: absolute; inset: 0; pointer-events: none; display: none;
          background-image: linear-gradient(rgba(255,255,255,.35) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.35) 1px, transparent 1px);
          background-size: 33.333% 33.333%; }
  #flash { position: absolute; inset: 0; background: #fff; opacity: 0; pointer-events: none; transition: opacity .25s; }

  .chip { position: absolute; width: 42px; height: 42px; border-radius: 50%; border: 0; background: rgba(0,0,0,.45); color: #fff; font-size: 20px; padding: 0; }
  #eye  { top: 10px; left: 10px; }
  #flip { top: 10px; right: 10px; }
  #fs   { top: 60px; right: 10px; }
  #info { position: absolute; top: 14px; left: 62px; right: 62px; text-align: center; color: #fff; font-size: 13px; line-height: 1.25;
          background: rgba(0,0,0,.45); border-radius: 14px; padding: 5px 8px; pointer-events: none; word-break: break-all; }

  .hud { position: absolute; left: 0; right: 0; bottom: 0; padding: 26px 12px 16px; color: #fff;
         background: linear-gradient(transparent, rgba(0,0,0,.6)); }
  .row { display: flex; align-items: center; gap: 10px; font-size: 13px; margin-bottom: 10px; }
  .row input[type=range] { flex: 1; height: 26px; }
  .row .v { width: 40px; text-align: right; }
  .bar { display: flex; justify-content: center; align-items: center; gap: 34px; }
  .round { width: 50px; height: 50px; border-radius: 50%; border: 0; background: rgba(255,255,255,.25); color: #fff; font-size: 20px; padding: 0; }
  .round:disabled { opacity: .3; }
  .shutter { width: 72px; height: 72px; border-radius: 50%; border: 4px solid #fff; background: #ff4b4b; box-shadow: inset 0 0 0 4px rgba(0,0,0,.35); padding: 0; }
  .shutter:active { transform: scale(.92); }

  details { margin: 8px 4px; font-size: 14px; }
  summary { cursor: pointer; padding: 6px 0; }
  details label, details .line { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
  details select { font-size: 14px; padding: 4px; }
  details input[type=range] { flex: 1; }
  #msg { color: #c00; font-size: 14px; margin: 6px 4px; }

  /* Fullscreen "camera app" mode */
  body.fs { padding: 0; background: #000; overflow: hidden; }
  body.fs #wrap { border-radius: 0; }
  body.fs details { display: none; }
  body.fs #msg { position: fixed; top: 60px; left: 10px; right: 70px; color: #fff; background: rgba(160,0,0,.8); border-radius: 8px; padding: 6px; z-index: 5; }

  @media (prefers-color-scheme: dark) { body { color: #eee; } }
</style>
</head>
<body>
  <div id="stage">
    <div id="wrap">
      <video id="video" autoplay playsinline muted></video>
      <img id="overlay">
      <div id="grid"></div>
      <div id="flash"></div>

      <button class="chip" id="eye" title="Show / hide reference">&#128065;</button>
      <div id="info">-</div>
      <button class="chip" id="flip" title="Switch camera">&#128260;</button>
      <button class="chip" id="fs" title="Fullscreen camera">&#9974;</button>

      <div class="hud">
        <div class="row">
          <span>Opacity</span>
          <input type="range" id="opacity" min="0" max="100" value="50">
          <span class="v" id="opv">50%</span>
        </div>
        <div class="bar">
          <button class="round" id="prev">&#9664;</button>
          <button class="shutter" id="snap" aria-label="Capture"></button>
          <button class="round" id="next">&#9654;</button>
        </div>
      </div>
    </div>
  </div>
  <div id="msg"></div>

  <details>
    <summary>More options</summary>
    <div class="line">
      <span>Shape</span>
      <select id="aspect">
        <option value="0.5625" selected>Phone screen 9:16</option>
        <option value="0.75">Portrait 3:4</option>
        <option value="1">Square 1:1</option>
        <option value="1.3333">Landscape 4:3</option>
      </select>
    </div>
    <div class="line">
      <span>Scale</span>
      <input type="range" id="scale" min="50" max="200" value="100">
      <span id="scv">100%</span>
    </div>
    <label><input type="checkbox" id="show" checked> Show reference overlay</label>
    <label><input type="checkbox" id="gridcb"> Grid lines</label>
    <label><input type="checkbox" id="auto" checked> Go to next reference after capture</label>
    <label><input type="checkbox" id="burn"> Burn overlay into saved photo</label>
  </details>

<script>
// ---------- Streamlit component protocol (no build step needed) ----------
function send(type, data) {
  window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, data || {}), "*");
}
function setValue(v) { send("streamlit:setComponentValue", { value: v, dataType: "json" }); }
function setHeight() {
  if (fs) return;
  send("streamlit:setFrameHeight", { height: document.documentElement.scrollHeight + 8 });
}
function uid() { return Date.now() + "-" + Math.random().toString(36).slice(2); }

// ---------- State ----------
let cur = null, meta = {}, curKey = "", quality = 0.92;
let facing = "environment", stream = null;
let aspect = 9 / 16;                 // box shape when not fullscreen
let fs = false, pseudo = false;
let pending = {};                    // captures not yet confirmed saved by Python

const $ = id => document.getElementById(id);
const video = $("video"), overlay = $("overlay"), wrap = $("wrap");

function emit(nav) {                 // one message carries nav request + all unconfirmed captures
  setValue({ id: uid(), nav: nav || null, captures: Object.values(pending) });
}

// ---------- Sizing ----------
function parentH() {
  try { return window.parent.innerHeight; } catch (e) { return window.screen.availHeight; }
}
function curAspect() { return fs ? window.innerWidth / window.innerHeight : aspect; }
function fit() {
  if (fs) {
    wrap.style.width = window.innerWidth + "px";
    wrap.style.height = window.innerHeight + "px";
    wrap.style.aspectRatio = "auto";
    return;
  }
  const W = document.body.clientWidth - 8;
  const maxH = Math.max(360, parentH() * 0.82);
  let w = W, h = W / aspect;
  if (h > maxH) { h = maxH; w = h * aspect; }
  wrap.style.width = Math.round(w) + "px";
  wrap.style.height = Math.round(h) + "px";
  wrap.style.aspectRatio = "auto";
  setHeight();
}
window.addEventListener("resize", fit);
window.addEventListener("orientationchange", () => setTimeout(fit, 300));

// ---------- Fullscreen camera mode ----------
function pseudoFS(on) {
  const fe = window.frameElement;
  if (!fe) return false;
  if (on) {
    if (fe.dataset.oldStyle === undefined) fe.dataset.oldStyle = fe.getAttribute("style") || "";
    fe.style.cssText = "position:fixed;top:0;left:0;width:100vw;height:" + parentH() + "px;z-index:999999;border:0;background:#000;";
    return true;
  }
  if (fe.dataset.oldStyle !== undefined) {
    fe.setAttribute("style", fe.dataset.oldStyle);
    delete fe.dataset.oldStyle;
  }
  return false;
}
async function enterFS() {
  fs = true;
  document.body.classList.add("fs");
  $("fs").innerHTML = "&#10005;";
  try {
    if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
  } catch (e) { /* fall back below */ }
  if (!document.fullscreenElement) pseudo = pseudoFS(true);   // iPhone / blocked: fill the page instead
  setTimeout(fit, 150);
  setTimeout(fit, 500);
}
function exitFS() {
  fs = false;
  document.body.classList.remove("fs");
  $("fs").innerHTML = "&#9974;";
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  if (pseudo) { pseudoFS(false); pseudo = false; }
  setTimeout(() => { fit(); setHeight(); }, 150);
}
$("fs").onclick = () => (fs ? exitFS() : enterFS());
document.addEventListener("fullscreenchange", () => {
  if (fs && !pseudo && !document.fullscreenElement) exitFS();
});

// ---------- Rendering ----------
function renderInfo() {
  if (!cur) return;
  $("info").innerHTML = cur.name + "<br>" + (meta.index + 1) + " / " + meta.total + " &middot; " +
    meta.doneCount + " captured" + (meta.isDone ? " &#10003;" : "");
  $("prev").disabled = !meta.prev;
  $("next").disabled = !meta.next;
}

function applyOverlay() {
  overlay.style.opacity = $("opacity").value / 100;
  overlay.style.transform = "scale(" + $("scale").value / 100 + ")";
  overlay.style.display = $("show").checked ? "block" : "none";
  $("grid").style.display = $("gridcb").checked ? "block" : "none";
  $("opv").textContent = $("opacity").value + "%";
  $("scv").textContent = $("scale").value + "%";
}
["opacity", "scale", "show", "gridcb"].forEach(id => $(id).addEventListener("input", applyOverlay));
applyOverlay();

$("eye").onclick = () => { $("show").checked = !$("show").checked; applyOverlay(); };
$("aspect").onchange = () => { aspect = parseFloat($("aspect").value); fit(); startCamera(); };

// ---------- Camera ----------
async function startCamera() {
  if (stream) stream.getTracks().forEach(t => t.stop());
  const a = curAspect();
  let size;
  if (a < 1) size = { width: { ideal: Math.round(1920 * a) }, height: { ideal: 1920 } };
  else       size = { width: { ideal: 1920 }, height: { ideal: Math.round(1920 / a) } };
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: Object.assign({ facingMode: facing }, size), audio: false
    });
    video.srcObject = stream;
    $("msg").textContent = "";
  } catch (e) {
    $("msg").textContent = "Camera error: " + e.message + " (allow camera access; the page must be opened over HTTPS or localhost)";
  }
}
$("flip").onclick = () => { facing = facing === "environment" ? "user" : "environment"; startCamera(); };

// ---------- Capture: crop to exactly what the box shows ----------
function capture() {
  const vw = video.videoWidth, vh = video.videoHeight;
  if (!vw || !cur) return;
  const a = curAspect();

  let sw = vw, sh = vh;
  if (vw / vh > a) sw = vh * a; else sh = vw / a;
  const sx = (vw - sw) / 2, sy = (vh - sh) / 2;

  const c = document.createElement("canvas");
  c.width = Math.round(sw); c.height = Math.round(sh);
  const ctx = c.getContext("2d");
  ctx.drawImage(video, sx, sy, sw, sh, 0, 0, c.width, c.height);

  if ($("burn").checked && $("show").checked && overlay.naturalWidth) {
    const s = $("scale").value / 100;
    const f = Math.min(c.width / overlay.naturalWidth, c.height / overlay.naturalHeight) * s;
    const w = overlay.naturalWidth * f, h = overlay.naturalHeight * f;
    ctx.globalAlpha = $("opacity").value / 100;
    ctx.drawImage(overlay, (c.width - w) / 2, (c.height - h) / 2, w, h);
    ctx.globalAlpha = 1;
  }

  const capId = uid();
  pending[capId] = { capId: capId, stem: cur.stem, name: cur.name, data: c.toDataURL("image/jpeg", quality) };

  if (navigator.vibrate) navigator.vibrate(30);
  $("flash").style.opacity = .8;
  setTimeout(() => $("flash").style.opacity = 0, 120);

  const goNext = $("auto").checked && meta.next;
  emit(goNext ? meta.next : null);
}

$("snap").onclick = capture;
$("prev").onclick = () => { if (meta.prev) emit(meta.prev); };
$("next").onclick = () => { if (meta.next) emit(meta.next); };
document.addEventListener("keydown", e => {
  if (e.target && e.target.tagName === "SELECT") return;
  if (e.key === "ArrowLeft" && meta.prev) emit(meta.prev);
  else if (e.key === "ArrowRight" && meta.next) emit(meta.next);
  else if (e.key === " " || e.key === "Enter") { e.preventDefault(); capture(); }
});

// ---------- Receive data from Python ----------
window.addEventListener("message", e => {
  if (!e.data || e.data.type !== "streamlit:render") return;
  const a = e.data.args || {};
  quality = a.quality || 0.92;
  (a.acked || []).forEach(id => { delete pending[id]; });

  if (a.current) {
    const key = a.current.stem + ":" + a.current.src.length;
    if (key !== curKey) { curKey = key; overlay.src = a.current.src; }
    cur = a.current;
  }
  meta = { index: a.index || 0, total: a.total || 0, doneCount: a.done_count || 0,
           isDone: !!a.is_done, prev: a.prev_stem || null, next: a.next_stem || null };
  renderInfo();
  fit();
});

send("streamlit:componentReady", { apiVersion: 1 });
fit();
startCamera();
new ResizeObserver(setHeight).observe(document.body);
</script>
</body>
</html>
'''

# The camera component file is written to the system temp folder (nothing is created next to this script)
_comp_dir = Path(tempfile.gettempdir()) / "overlay_cam_component"
_comp_dir.mkdir(exist_ok=True)
(_comp_dir / "index.html").write_text(COMPONENT_HTML, encoding="utf-8")

_camera = components.declare_component(
    "overlay_cam", path=str(_comp_dir)
)


# ----------------------------------------------------------------- helpers
def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def safe(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s).strip("_") or "item"


def get_bytes(src) -> bytes:
    return src.read_bytes() if isinstance(src, Path) else src.getvalue()


@st.cache_data(show_spinner=False)
def prepare_ref(data: bytes, max_side: int = 1280):
    """Resize the reference so the page stays light; keep transparency if any."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P"):
        img.convert("RGBA").save(buf, "PNG")
        mime = "image/png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=85)
        mime = "image/jpeg"
    return mime, base64.b64encode(buf.getvalue()).decode()


def jump_to_missing():
    """Button callback: select the next reference that has no photo yet."""
    ss = st.session_state
    stems = ss.get("stems", [])
    if not stems:
        return
    cur = stems.index(ss["sel"]) if ss.get("sel") in stems else 0
    for s in stems[cur + 1:] + stems[:cur + 1]:
        if s not in ss.photos:
            ss["sel"] = s
            return


# ----------------------------------------------------------------- state
ss = st.session_state
ss.setdefault("photos", {})        # stem -> jpeg bytes
ss.setdefault("last_id", None)     # last camera event handled (for navigation)
ss.setdefault("saved_ids", [])     # capture ids already saved (prevents duplicates)
photos = ss.photos

# A navigation request from the camera must be applied BEFORE the selectbox is drawn
if "pending_sel" in ss:
    ss["sel"] = ss.pop("pending_sel")

st.subheader("📷 Reference Overlay Camera")

# ----------------------------------------------------------------- settings
with st.expander("⚙️ Settings"):
    session_name = st.text_input("Session / job name", value=time.strftime("job_%Y%m%d"))
    save_disk = st.checkbox("Also save photos on the computer running this app", value=True)
    out_dir = st.text_input("Save folder", value="captures", disabled=not save_disk)
    quality = st.slider("JPEG quality", 60, 100, 92)
    if st.button("🗑️ Clear all captured photos"):
        ss.photos = {}
        ss.saved_ids = []
        ss.last_id = None
        st.rerun()

# ----------------------------------------------------------------- references
if REFERENCE_DIR.is_dir():
    sources = [(p.name, p) for p in REFERENCE_DIR.iterdir() if p.suffix.lower() in EXTS]
else:
    sources = []
    st.error(f"Images folder not found: `{REFERENCE_DIR}` - set REFERENCE_DIR near the top of the code.")

with st.expander("➕ Add extra reference images for this session (optional)"):
    uploads = st.file_uploader(
        "Upload images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )
sources += [(u.name, u) for u in (uploads or [])]

if not sources:
    st.info("No reference images found. Check REFERENCE_DIR near the top of the code.")
    st.stop()

sources.sort(key=lambda x: natural_key(x[0]))
by_stem, seen = {}, {}
for name, src in sources:
    stem = safe(Path(name).stem)
    seen[stem] = seen.get(stem, 0) + 1
    if seen[stem] > 1:
        stem = f"{stem}_{seen[stem]}"
    by_stem[stem] = {"name": name, "src": src}
stems = list(by_stem)
ss["stems"] = stems

if ss.get("sel") not in stems:
    ss.pop("sel", None)

# ----------------------------------------------------------------- choose reference
c1, c2 = st.columns([5, 1])
with c1:
    st.selectbox(
        "Reference photo (tap and type to search)",
        stems,
        key="sel",
        format_func=lambda s: ("✅ " if s in photos else "⬜ ") + by_stem[s]["name"],
    )
with c2:
    st.write("")
    st.write("")
    st.button("⏭", on_click=jump_to_missing, help="Jump to the next photo not captured yet")

sel = ss["sel"]
i = stems.index(sel)
mime, b64 = prepare_ref(get_bytes(by_stem[sel]["src"]))   # only the selected image is processed

# ----------------------------------------------------------------- camera
result = _camera(
    current={"name": by_stem[sel]["name"], "stem": sel, "src": f"data:{mime};base64,{b64}"},
    index=i,
    total=len(stems),
    done_count=sum(1 for s in stems if s in photos),
    is_done=sel in photos,
    prev_stem=stems[i - 1] if i > 0 else None,
    next_stem=stems[i + 1] if i < len(stems) - 1 else None,
    quality=quality / 100,
    acked=ss.saved_ids[-100:],
    key="cam",
    default=None,
)

# Events coming from the camera: photos to save and/or "go to another reference"
if result:
    changed = False
    for cap in result.get("captures") or []:
        if cap["capId"] in ss.saved_ids or cap["stem"] not in by_stem:
            continue
        jpeg = base64.b64decode(cap["data"].split(",", 1)[1])
        photos[cap["stem"]] = jpeg
        ss.saved_ids.append(cap["capId"])
        ss.saved_ids = ss.saved_ids[-300:]
        if save_disk:
            folder = Path(out_dir) / safe(session_name)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{cap['stem']}.jpg").write_bytes(jpeg)
        changed = True

    if result.get("nav") and result["id"] != ss.last_id:
        ss.last_id = result["id"]
        if result["nav"] in by_stem:
            ss["pending_sel"] = result["nav"]
            changed = True

    if changed:
        st.rerun()

# ----------------------------------------------------------------- progress
captured = [s for s in stems if s in photos]
st.progress(len(captured) / len(stems), text=f"{len(captured)} of {len(stems)} captured")

# ----------------------------------------------------------------- results
if captured:
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        for s in captured:
            z.writestr(f"{s}.jpg", photos[s])
    st.download_button(
        "⬇️ Download all photos (ZIP)",
        zbuf.getvalue(),
        file_name=f"{safe(session_name)}.zip",
        mime="application/zip",
        use_container_width=True,
    )
    if save_disk:
        st.caption(f"Also saved in: `{(Path(out_dir) / safe(session_name)).resolve()}`")

    with st.expander(f"Captured photos ({len(captured)})"):
        cols = st.columns(3)
        for n, s in enumerate(captured):
            with cols[n % 3]:
                st.image(photos[s], caption=by_stem[s]["name"])
