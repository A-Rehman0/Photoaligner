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
# ===== REPLACE 1: settings =====
REFERENCE_DIR = Path(r"job_20261019/")   # your images folder
EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SIDE = 720 

COMPONENT_HTML = r'''<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;padding:4px;font-family:sans-serif;color:#31333f}
#cv{width:100%;max-height:60vh;object-fit:contain;background:#000;border-radius:14px;display:block}
.r{display:flex;gap:8px;margin-top:8px}
button{flex:1;font-size:16px;padding:12px;border:0;border-radius:10px;background:#eee}
#pip{background:#ff4b4b;color:#fff;flex:3}
video{position:absolute;width:1px;height:1px;opacity:0}
@media(prefers-color-scheme:dark){body{color:#eee}}
</style></head><body>
<canvas id="cv" width="720" height="1280"></canvas><video id="v" muted playsinline></video>
<div class="r"><button id="p">◀</button><button id="pip">🎈 Float over apps</button><button id="n">▶</button></div>
<div id="m" style="font-size:13px;margin-top:6px"></div>
<script>
const $=i=>document.getElementById(i),cv=$("cv"),x=cv.getContext("2d"),v=$("v"),im=new Image();
let L=[],i=0,sig="",timer=null;
const post=(t,d)=>parent.postMessage({isStreamlitMessage:true,type:t,...d},"*");
const H=()=>post("streamlit:setFrameHeight",{height:document.documentElement.scrollHeight+8});
function draw(){
  x.fillStyle="#000";x.fillRect(0,0,720,1280);
  if(im.naturalWidth){const f=Math.min(720/im.naturalWidth,1280/im.naturalHeight),w=im.naturalWidth*f,h=im.naturalHeight*f;x.drawImage(im,(720-w)/2,(1280-h)/2,w,h);}
  if(L.length){x.fillStyle="rgba(0,0,0,.6)";x.fillRect(0,0,720,64);x.fillStyle="#fff";x.font="30px sans-serif";x.fillText((i+1)+"/"+L.length+"  "+L[i].n.slice(0,34),14,43);}
}
function show(n){if(!L.length)return;i=(n+L.length)%L.length;im.onload=draw;im.src=L[i].s;draw();}
$("p").onclick=()=>show(i-1);$("n").onclick=()=>show(i+1);
$("pip").onclick=async()=>{
  try{
    if(document.pictureInPictureElement){await document.exitPictureInPicture();return;}
    if(!v.srcObject)v.srcObject=cv.captureStream(10);
    await v.play();draw();await v.requestPictureInPicture();
    clearInterval(timer);timer=setInterval(draw,200);
    if("mediaSession" in navigator){const a=(k,f)=>{try{navigator.mediaSession.setActionHandler(k,f)}catch(e){}};
      a("previoustrack",()=>show(i-1));a("nexttrack",()=>show(i+1));a("play",()=>v.play());a("pause",()=>v.play());}
    $("m").textContent="";
  }catch(e){$("m").textContent="PiP not available: "+e.message;}
};
v.addEventListener("leavepictureinpicture",()=>clearInterval(timer));
addEventListener("message",e=>{
  if(!e.data||e.data.type!=="streamlit:render")return;
  const a=e.data.args||{};if(a.sig===sig)return;sig=a.sig;L=a.imgs||[];show(Math.min(i,L.length-1));H();
});
post("streamlit:componentReady",{apiVersion:1});H();
</script></body></html>
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
    try:
        with Image.open(io.BytesIO(data)) as source:
            img = ImageOps.exif_transpose(source)
            img.load()
            img.thumbnail((max_side, max_side))

            buf = io.BytesIO()
            if "A" in img.getbands() or img.mode == "P":
                img.convert("RGBA").save(buf, format="PNG")
                mime = "image/png"
            else:
                img.convert("RGB").save(buf, format="JPEG", quality=85)
                mime = "image/jpeg"

            return mime, base64.b64encode(buf.getvalue()).decode("utf-8")

    except Exception as e:
        st.error(f"Cannot open reference image. Check that it is a valid image file. Details: {e}")
        st.stop()


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
