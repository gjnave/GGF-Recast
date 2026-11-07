"""Get Going Fast header and companion app artwork, embedded for local and phone use."""
import base64
from settings import APP


def embedded_image(filename, mime_type):
    encoded = base64.b64encode((APP / 'assets' / filename).read_bytes()).decode('ascii')
    return f'data:image/{mime_type};base64,{encoded}'


HEADER = f"""
<header class="recast-hero">
  <div>
    <div class="recast-kicker">GET GOING FAST · LOCAL AI</div>
    <h1>GGF Recast</h1>
    <p>Replace characters in video while keeping the original performance.</p>
    <nav aria-label="Get Going Fast links">
      <a href="https://getgoingfast.pro" target="_blank" rel="noopener noreferrer">GetGoingFast.pro ↗</a>
      <a href="https://getgoingfast.pro/tools/" target="_blank" rel="noopener noreferrer">GGF Tools ↗</a>
      <a href="https://www.youtube.com/@theaihobbyguy" target="_blank" rel="noopener noreferrer">TheAIHobbyGuy on YouTube ↗</a>
    </nav>
  </div>
  <img src="{embedded_image('ggf-brain-logo.png','png')}" alt="Get Going Fast logo">
</header>"""

FLOYD_PROMO = f"""
<aside class="recast-floyd" aria-label="Floyd Headliner">
  <p>This app works best with Floyd Headliner.</p>
  <a href="https://floydheadliner.com" target="_blank" rel="noopener noreferrer">
    <img src="{embedded_image('floyd-headliner.webp','webp')}" width="1280" height="720"
         alt="Visit Floyd Headliner for likeness transfer">
  </a>
</aside>"""

CSS = """
.recast-hero {display:grid;grid-template-columns:minmax(0,1fr) auto;gap:clamp(8px,2vw,22px);
  align-items:center;padding:clamp(14px,3vw,28px);border:1px solid #334a6b;border-radius:18px;
  background:linear-gradient(135deg,#0b1220,#172554);font-family:'Segoe UI',Arial,sans-serif;}
.recast-hero .recast-kicker {color:#f5b942;font-weight:800;letter-spacing:.14em;font-size:.78rem;}
.recast-hero h1 {color:#f5b942!important;font-size:clamp(1.8rem,3vw,2.6rem);margin:6px 0;}
.recast-hero p {color:#dbeafe!important;margin:0 0 10px;}
.recast-hero nav {display:flex;flex-wrap:wrap;gap:8px 18px;}
.recast-hero nav a {color:#9dcbff!important;font-weight:700;text-decoration:underline;}
.recast-hero img {display:block;width:clamp(54px,10vw,120px);height:auto;}
.recast-floyd {width:100%;max-width:640px;margin:20px auto 4px;}
.recast-floyd p {margin:0 0 8px;font-size:1.05rem;font-weight:700;}
.recast-floyd a,.recast-floyd img {display:block;width:100%;border-radius:12px;}
.recast-floyd img {height:auto;}
.recast-hero a:focus-visible,.recast-floyd a:focus-visible {outline:3px solid #f5b942;outline-offset:3px;}
"""
