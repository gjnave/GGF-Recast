"""Get Going Fast header and companion app artwork, embedded for local and phone use."""
import base64
from settings import APP


def embedded_image(filename, mime_type):
    encoded = base64.b64encode((APP / 'assets' / filename).read_bytes()).decode('ascii')
    return f'data:image/{mime_type};base64,{encoded}'


HEADER = f"""
<header class="recast-hero">
  <div class="recast-hero-copy">
    <div class="recast-kicker">GET GOING FAST · LOCAL AI</div>
    <h1>Viggle Recast</h1>
    <p>Change the characters in any video while keeping the original performance.</p>
    <nav class="recast-links" aria-label="Get Going Fast links">
      <a href="https://getgoingfast.pro" target="_blank" rel="noopener noreferrer">GetGoingFast.pro ↗</a>
      <a href="https://www.youtube.com/@theaihobbyguy" target="_blank" rel="noopener noreferrer">TheAIHobbyGuy ↗</a>
    </nav>
  </div>
  <div class="recast-hero-slogan">Your Time Is Limited.<br><strong>Get Going Fast.</strong></div>
  <img class="recast-hero-logo" src="{embedded_image('ggf-brain-logo.png','png')}"
       width="120" height="120" alt="Get Going Fast brain logo">
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
.recast-hero {display:grid;grid-template-columns:minmax(0,1fr) minmax(220px,.8fr) 120px;
  gap:20px;align-items:center;padding:25px 28px;margin-bottom:14px;min-width:0;
  border:1px solid #334a6b;border-radius:18px;background:linear-gradient(135deg,#0b1220,#172554);
  font-family:'Segoe UI',Arial,sans-serif;}
.recast-hero-copy {min-width:0;}
.recast-hero .recast-kicker {color:#f5b942;font-weight:800;letter-spacing:.14em;font-size:.78rem;}
.recast-hero h1 {color:#f5b942!important;font-size:clamp(1.8rem,3vw,2.6rem);margin:7px 0;}
.recast-hero p {color:#dbeafe!important;margin:0 0 8px;}
.recast-hero .recast-links {display:flex;flex-wrap:wrap;gap:10px 18px;}
.recast-hero .recast-links a {color:#9dcbff!important;font-weight:700;text-decoration:underline;}
.recast-hero-slogan {color:#f4f7fc;font-family:'Segoe UI Variable Display','Segoe UI',Arial,sans-serif;
  font-size:clamp(1.3rem,2.2vw,1.9rem);font-weight:750;letter-spacing:-.035em;
  line-height:1.18;text-align:center;}
.recast-hero-slogan strong {color:#f5b942;font-weight:800;}
.recast-hero-logo {display:block;width:120px;height:120px;object-fit:cover;}
.recast-floyd {width:100%;max-width:640px;margin:20px auto 4px;}
.recast-floyd p {margin:0 0 8px;font-size:1.05rem;font-weight:700;}
.recast-floyd a,.recast-floyd img {display:block;width:100%;border-radius:12px;}
.recast-floyd img {height:auto;}
.recast-hero a:focus-visible,.recast-floyd a:focus-visible {outline:3px solid #f5b942;outline-offset:3px;}
@media (max-width:900px) {
  .recast-hero {grid-template-columns:minmax(0,1fr) 96px;gap:14px;}
  .recast-hero-slogan {grid-column:1 / -1;grid-row:2;}
  .recast-hero-logo {width:96px;height:96px;}
}
@media (max-width:680px) {
  .recast-hero {padding:18px;gap:12px;grid-template-columns:minmax(0,1fr) 72px;}
  .recast-hero-copy {grid-column:1 / -1;grid-row:1;}
  .recast-hero h1 {font-size:clamp(1.7rem,8vw,2.2rem);}
  .recast-hero-slogan {grid-column:1;grid-row:2;font-size:1.25rem;}
  .recast-hero-logo {grid-column:2;grid-row:2;width:72px;height:72px;}
}
"""
