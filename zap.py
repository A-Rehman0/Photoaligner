"""
Multi-reference overlay photo capture (mobile friendly).

Single file. Run:  streamlit run zap.py
(The overlay_cam/index.html helper file is created automatically.)
"""
import base64
import io
import re
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

# Tighter padding on phones
st.markdown(
    "<style>.block-container{padding-top:1rem;padding-left:.6rem;padding-right:.6rem;}</style>",
    unsafe_allow_html=True,
)

COMPONENT_HTML = r'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body { margin: 0; padding: 4px; font-family: -apple-system, Segoe UI, Roboto, sans-serif; color: #31333f; touch-action: manipulation; }
  #title { text-align: center; font-weight: 600; font-size: 16px; margin: 2px 0 6px; word-break: break-all; }
  #title small { font-weight: 400; color: #777; display: block; font-size: 13px; }

  #thumbs { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 6px; margin-bottom: 6px; }
  .th { position: relative; flex: 0 0 auto; width: 52px; height: 52px; border: 2px solid transparent; border-radius: 8px; overflow: hidden; background: #ddd; }
  .th img { width: 100%; height: 100%; object-fit: cover; }
  .th.cur { border-color: #ff4b4b; }
  .th.done::after { content: "\2713"; position: absolute; right: 2px; bottom: 2px; background: #1db954; color: #fff; font-size: 11px; width: 16px; height: 16px; line-height: 16px; text-align: center; border-radius: 50%; }

  #stage { display: flex; justify-content: center; }
  #wrap { position: relative; background: #000; overflow: hidden; border-radius: 12px; width: 100%; aspect-ratio: 3/4; }
  #video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  #overlay { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; pointer-events: none; opacity: .5; }
  #grid { position: absolute; inset: 0; pointer-events: none; display: none;
          background-image: linear-gradient(rgba(255,255,255,.35) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.35) 1px, transparent 1px);
          background-size: 33.333% 33.333%; }
  #flash { position: absolute; inset: 0; background: #fff; opacity: 0; pointer-events: none; transition: opacity .25s; }
  .chip { position: absolute; top: 8px; width: 42px; height: 42px; border-radius: 50%; border: 0; background: rgba(0,0,0,.45); color: #fff; font-size: 20px; padding: 0; }
  #flip { right: 8px; }
  #eye { left: 8px; }

  .bar { display: flex; justify-content: center; align-items: center; gap: 30px; margin: 12px 0 8px; }
  .round { width: 52px; height: 52px; border-radius: 50%; border: 0; background: #555; color: #fff; font-size: 20px; padding: 0; }
  .round:disabled { opacity: .35; }
  .shutter { width: 76px; height: 76px; border-radius: 50%; border: 4px solid #ff4b4b; background: #fff; box-shadow: inset 0 0 0 4px #fff, inset 0 0 0 40px #ff4b4b; padding: 0; }
  .shutter:active { transform: scale(.93); }

  .row { display: flex; align-items: center; gap: 10px; margin: 8px 4px; font-size: 14px; }
  .row input[type=range] { flex: 1; height: 28px; }
  .row .v { width: 44px; text-align: right; }
  details { margin: 6px 4px; font-size: 14px; }
  summary { cursor: pointer; padding: 6px 0; }
  details label { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
  #msg { color: #c00; font-size: 14px; margin: 6px 4px; }

  @media (prefers-color-scheme: dark) {
    body { color: #eee; }
    #title small { color: #aaa; }
  }
</style>
</head>
<body>
  <div id="title">-</div>
  <div id="thumbs"></div>

  <div id="stage">
    <div id="wrap">
      <video id="video" autoplay playsinline muted></video>
      <img id="overlay">
      <div id="grid"></div>
      <div id="flash"></div>
      <button class="chip" id="eye" title="Show / hide reference">&#128065;</button>
      <button class="chip" id="flip" title="Switch camera">&#128260;</button>
    </div>
  </div>
  <div id="msg"></div>

  <div class="bar">
    <button class="round" id="prev">&#9664;</button>
    <button class="shutter" id="snap" aria-label="Capture"></button>
    <button class="round" id="next">&#9654;</button>
  </div>

  <div class="row">
    <span>Opacity</span>
    <input type="range" id="opacity" min="0" max="100" value="50">
    <span class="v" id="opv">50%</span>
  </div>

  <details>
    <summary>More options</summary>
    <div class="row">
      <span>Scale</span>
      <input type="range" id="scale" min="50" max="200" value="100">
      <span class="v" id="scv">100%</span>
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
function setHeight() { send("streamlit:setFrameHeight", { height: document.documentElement.scrollHeight + 8 }); }

// ---------- State ----------
let refs = [], done = new Set(), idx = 0, quality = 0.92, refsKey = "";
let facing = "environment", stream = null;

const $ = id => document.getElementById(id);
const video = $("video"), overlay = $("overlay"), wrap = $("wrap");

// ---------- Sizing: portrait on phones, never taller than the screen ----------
function parentH() {
  try { return window.parent.innerHeight; } catch (e) { return window.screen.height; }
}
function fit() {
  const portrait = parentH() >= document.body.clientWidth;
  const vw = video.videoWidth || (portrait ? 3 : 4);
  const vh = video.videoHeight || (portrait ? 4 : 3);
  const W = document.body.clientWidth - 8;
  const maxH = Math.max(300, parentH() * 0.62);
  let w = W, h = W * vh / vw;
  if (h > maxH) { h = maxH; w = h * vw / vh; }
  wrap.style.width = w + "px";
  wrap.style.height = h + "px";
  wrap.style.aspectRatio = "auto";
  setHeight();
}
video.addEventListener("loadedmetadata", fit);
video.addEventListener("resize", fit);
window.addEventListener("resize", fit);
window.addEventListener("orientationchange", () => setTimeout(() => { startCamera(); fit(); }, 300));

// ---------- Rendering ----------
function renderThumbs() {
  const box = $("thumbs");
  box.innerHTML = "";
  refs.forEach((r, i) => {
    const d = document.createElement("div");
    d.className = "th" + (i === idx ? " cur" : "") + (done.has(r.stem) ? " done" : "");
    d.innerHTML = '<img src="' + r.src + '">';
    d.onclick = () => go(i);
    box.appendChild(d);
  });
  const cur = box.querySelector(".cur");
  if (cur) cur.scrollIntoView({ inline: "center", block: "nearest" });
}

function renderCurrent() {
  if (!refs.length) return;
  const r = refs[idx];
  overlay.src = r.src;
  $("title").innerHTML = r.name + "<small>" + (idx + 1) + " / " + refs.length +
    " &middot; " + done.size + " captured" + (done.has(r.stem) ? " &middot; &#10003; tap shutter to retake" : "") + "</small>";
  $("prev").disabled = idx === 0;
  $("next").disabled = idx === refs.length - 1;
  renderThumbs();
  setHeight();
}

function go(i) {
  idx = Math.max(0, Math.min(refs.length - 1, i));
  renderCurrent();
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

// ---------- Camera ----------
async function startCamera() {
  if (stream) stream.getTracks().forEach(t => t.stop());
  const portrait = parentH() >= document.body.clientWidth;
  const size = portrait ? { width: { ideal: 1536 }, height: { ideal: 2048 } }
                        : { width: { ideal: 2048 }, height: { ideal: 1536 } };
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

// ---------- Capture ----------
function capture() {
  if (!video.videoWidth || !refs.length) return;
  const c = document.createElement("canvas");
  c.width = video.videoWidth; c.height = video.videoHeight;
  const ctx = c.getContext("2d");
  ctx.drawImage(video, 0, 0, c.width, c.height);

  if ($("burn").checked && $("show").checked) {
    const s = $("scale").value / 100;
    const fitS = Math.min(c.width / overlay.naturalWidth, c.height / overlay.naturalHeight) * s;
    const w = overlay.naturalWidth * fitS, h = overlay.naturalHeight * fitS;
    ctx.globalAlpha = $("opacity").value / 100;
    ctx.drawImage(overlay, (c.width - w) / 2, (c.height - h) / 2, w, h);
    ctx.globalAlpha = 1;
  }

  const r = refs[idx];
  setValue({ id: Date.now() + "-" + Math.random(), stem: r.stem, name: r.name,
             data: c.toDataURL("image/jpeg", quality) });
  done.add(r.stem);

  if (navigator.vibrate) navigator.vibrate(30);
  $("flash").style.opacity = .8;
  setTimeout(() => $("flash").style.opacity = 0, 120);

  if ($("auto").checked && idx < refs.length - 1) go(idx + 1); else renderCurrent();
}

$("snap").onclick = capture;
$("prev").onclick = () => go(idx - 1);
$("next").onclick = () => go(idx + 1);
document.addEventListener("keydown", e => {
  if (e.key === "ArrowLeft") go(idx - 1);
  else if (e.key === "ArrowRight") go(idx + 1);
  else if (e.key === " " || e.key === "Enter") { e.preventDefault(); capture(); }
});

// ---------- Receive data from Python ----------
window.addEventListener("message", e => {
  if (!e.data || e.data.type !== "streamlit:render") return;
  const a = e.data.args || {};
  quality = a.quality || 0.92;
  done = new Set(a.done || []);
  const key = (a.refs || []).map(r => r.stem + ":" + r.src.length).join("|");
  if (key !== refsKey) {
    refsKey = key;
    refs = a.refs || [];
    idx = 0;
  }
  renderCurrent();
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

# Write the camera component next to this script (so you only need ONE file)
_comp_dir = Path(__file__).parent / "overlay_cam"
_comp_dir.mkdir(exist_ok=True)
(_comp_dir / "index.html").write_text(COMPONENT_HTML, encoding="utf-8")

_camera = components.declare_component(
    "overlay_cam", path=str(Path(__file__).parent / "overlay_cam")
)


# ----------------------------------------------------------------- helpers
def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def safe(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s).strip("_") or "item"


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


# ----------------------------------------------------------------- state
if "photos" not in st.session_state:
    st.session_state.photos = {}      # stem -> jpeg bytes
if "last_id" not in st.session_state:
    st.session_state.last_id = None
photos = st.session_state.photos

st.subheader("📷 Reference Overlay Camera")

# ----------------------------------------------------------------- settings
with st.expander("⚙️ Settings"):
    session_name = st.text_input("Session / job name", value=time.strftime("job_%Y%m%d"))
    save_disk = st.checkbox("Also save photos on the computer running this app", value=True)
    out_dir = st.text_input("Save folder", value="captures", disabled=not save_disk)
    quality = st.slider("JPEG quality", 60, 100, 92)
    if st.button("🗑️ Clear all captured photos"):
        st.session_state.photos = {}
        st.session_state.last_id = None
        st.rerun()

# ----------------------------------------------------------------- references
with st.expander("📁 Reference images", expanded=not st.session_state.get("had_files", False)):
    files = st.file_uploader(
        "Upload reference images (one per object / position)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )

if not files:
    st.session_state.had_files = False
    st.info("Upload one or more reference images to start the camera.")
    st.stop()
st.session_state.had_files = True

files = sorted(files, key=lambda f: natural_key(f.name))

refs, seen = [], {}
for f in files:
    stem = safe(Path(f.name).stem)
    seen[stem] = seen.get(stem, 0) + 1
    if seen[stem] > 1:
        stem = f"{stem}_{seen[stem]}"
    mime, b64 = prepare_ref(f.getvalue())
    refs.append({"name": f.name, "stem": stem, "src": f"data:{mime};base64,{b64}"})

stems = [r["stem"] for r in refs]

# ----------------------------------------------------------------- camera
result = _camera(
    refs=refs,
    done=[s for s in stems if s in photos],
    quality=quality / 100,
    key="cam",
    default=None,
)

# New capture coming from the browser?
if result and result.get("id") != st.session_state.last_id:
    st.session_state.last_id = result["id"]
    jpeg = base64.b64decode(result["data"].split(",", 1)[1])
    photos[result["stem"]] = jpeg
    if save_disk:
        folder = Path(out_dir) / safe(session_name)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{result['stem']}.jpg").write_bytes(jpeg)

# ----------------------------------------------------------------- progress
captured = [s for s in stems if s in photos]
missing = [s for s in stems if s not in photos]

st.progress(len(captured) / len(stems), text=f"{len(captured)} of {len(stems)} captured")
if missing:
    st.caption("Still missing: " + ", ".join(missing))
else:
    st.success("All references captured ✅")

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

    with st.expander("Captured photos vs reference", expanded=False):
        ref_by_stem = {r["stem"]: r for r in refs}
        cols = st.columns(2)
        for i, s in enumerate(captured):
            with cols[i % 2]:
                st.image(photos[s], caption=f"{s} (captured)")
                st.image(ref_by_stem[s]["src"], caption="reference")