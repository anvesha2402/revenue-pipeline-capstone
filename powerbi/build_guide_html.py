import base64, re, markdown
md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"], extension_configs={"toc": {"toc_depth": "2-3"}})
body = md.convert(open("POWER_BI_BUILD_GUIDE.md").read())

def img(m):
    p = m.group(1)
    b = base64.b64encode(open(p, "rb").read()).decode()
    return f'src="data:image/png;base64,{b}" loading="lazy"'
body = re.sub(r'src="(design/[^"]+\.png)"', img, body)
body = body.replace("<h1", '<h1 class="doc-title"', 1)
body = re.sub(r"<table>", '<div class="tw"><table>', body)
body = body.replace("</table>", "</table></div>")
# step checkboxes
def step(m):
    sid = re.sub(r"[^0-9a-z.]+", "", m.group(2).lower())
    return f'<p class="step"><label class="chk"><input type="checkbox" data-step="{sid}"><span class="box" aria-hidden="true"></span><span class="sr">Done</span></label><strong>{m.group(1)}{m.group(2)}'
body = re.sub(r"<p><strong>(Step )(\d+\.\d+(?:\.\d+)?)", step, body)
body = re.sub(r"<p><strong>(CHECKPOINT[^<]*)</strong>", r'<p class="checkpoint"><strong>\1</strong>', body)
# sidebar from h2
heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
toc = "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in heads)

css = r"""
:root{
  /* Layout: fixed contents rail on the left, one reading column on the right. Instruction page: calm, high-contrast, steps are checkable. */
  --bg:#f6f7f9; --surface:#ffffff; --fg:#14202e; --fg2:#4a5868; --muted:#6c7886; --line:#dde2e8;
  --accent:#0d5bb5; --accent-soft:#e6eefa; --navy:#0d366b; --ok:#0a7a3d; --ok-soft:#e5f4ea; --warn:#8a5a00; --warn-soft:#fdf3dc;
  --code-bg:#eef1f5; --code-fg:#14202e;
  --f-body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif; --f-mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f1620; --surface:#161f2b; --fg:#e8edf3; --fg2:#b5c0cc; --muted:#8c99a8; --line:#2a3645;
  --accent:#6aa8ee; --accent-soft:#16283f; --navy:#9ec5f4; --ok:#5cc88a; --ok-soft:#12291d; --warn:#e2b45a; --warn-soft:#2a2210;
  --code-bg:#1d2836; --code-fg:#e8edf3; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f1620; --surface:#161f2b; --fg:#e8edf3; --fg2:#b5c0cc; --muted:#8c99a8; --line:#2a3645;
  --accent:#6aa8ee; --accent-soft:#16283f; --navy:#9ec5f4; --ok:#5cc88a; --ok-soft:#12291d; --warn:#e2b45a; --warn-soft:#2a2210;
  --code-bg:#1d2836; --code-fg:#e8edf3; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:16px/1.6 var(--f-body);padding-inline:16px;padding-block:0}
.shell{display:grid;grid-template-columns:240px minmax(0,1fr);gap:40px;max-width:1160px;margin:0 auto;padding-block:28px 80px}
nav.rail{position:sticky;top:env(safe-area-inset-top,0px);align-self:start;padding-top:8px;max-height:100vh;overflow:auto}
nav.rail h2{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;font-weight:600}
nav.rail ol{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:2px}
nav.rail a{display:block;padding:5px 8px;border-radius:5px;color:var(--fg2);text-decoration:none;font-size:14px;line-height:1.35}
nav.rail a:hover,nav.rail a.on{background:var(--accent-soft);color:var(--accent)}
.prog{margin:0 0 14px;font-size:13px;color:var(--fg2)}
.bar{height:6px;background:var(--line);border-radius:3px;margin-top:6px;overflow:hidden}
.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .2s}
.reset{margin-top:10px;font:inherit;font-size:12px;background:none;border:1px solid var(--line);color:var(--fg2);border-radius:5px;padding:3px 8px;cursor:pointer}
main{min-width:0;max-width:820px}
h1.doc-title{font-size:clamp(28px,4vw,38px);line-height:1.15;margin:0 0 16px;font-weight:600;letter-spacing:-.01em;text-wrap:balance;color:var(--navy)}
h2{font-size:26px;line-height:1.25;margin:56px 0 14px;padding-top:20px;border-top:1px solid var(--line);font-weight:600;text-wrap:balance;scroll-margin-top:16px}
h3{font-size:18px;margin:32px 0 8px;font-weight:600;scroll-margin-top:16px}
p,li{max-width:70ch}
a{color:var(--accent)}
strong{font-weight:600}
code{font:13.5px var(--f-mono);background:var(--code-bg);color:var(--code-fg);padding:1px 5px;border-radius:4px;overflow-wrap:anywhere}
pre{background:var(--code-bg);padding:12px 14px;border-radius:8px;overflow-x:auto;position:relative}
pre code{background:none;padding:0}
.tw{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:8px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-weight:600;background:var(--code-bg);white-space:nowrap}
tr:last-child td{border-bottom:0}
td code{white-space:normal}
img{display:block;margin:14px 0;border:1px solid var(--line);border-radius:8px;max-width:100%;height:auto}
em{color:var(--fg2)}
hr{display:none}
p.step{position:relative;padding-left:32px;margin:22px 0 6px;max-width:70ch}
.chk{position:absolute;left:0;top:4px;cursor:pointer}
.chk input{position:absolute;opacity:0;inset:0;width:100%;height:100%;margin:0;cursor:pointer}
.chk .box{display:block;width:18px;height:18px;border:2px solid var(--muted);border-radius:4px;background:var(--surface)}
.chk input:checked+.box{background:var(--ok);border-color:var(--ok)}
.chk input:checked+.box::after{content:"";display:block;width:5px;height:9px;margin:1px 0 0 5px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg)}
.chk input:focus-visible+.box{outline:2px solid var(--accent);outline-offset:2px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
p.step.done>strong{color:var(--muted)}
p.checkpoint{background:var(--ok-soft);border-left:4px solid var(--ok);padding:10px 14px;border-radius:0 8px 8px 0;margin:16px 0}
p.checkpoint strong:first-child{color:var(--ok)}
.copy{position:absolute;top:6px;right:6px;font:12px var(--f-body);border:1px solid var(--line);background:var(--surface);color:var(--fg2);border-radius:5px;padding:2px 8px;cursor:pointer}
.themebtn{position:fixed;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));font:13px var(--f-body);border:1px solid var(--line);background:var(--surface);color:var(--fg2);border-radius:999px;padding:6px 12px;cursor:pointer;z-index:5}
@media (max-width:860px){
  .shell{grid-template-columns:minmax(0,1fr);gap:12px}
  nav.rail{position:static;max-height:none}
  nav.rail details{border:1px solid var(--line);border-radius:8px;background:var(--surface);padding:8px 12px}
  nav.rail summary{cursor:pointer;font-weight:600;font-size:14px}
}
@media (min-width:861px){nav.rail summary{display:none}nav.rail details>*{display:block}}
@media (prefers-reduced-motion:reduce){.bar i{transition:none}}
"""
js = r"""
(function(){
  var boxes=[].slice.call(document.querySelectorAll('input[data-step]'));
  var KEY='rpc-pbi-guide-steps';
  var saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
  function paint(){
    var n=0;boxes.forEach(function(b){if(b.checked)n++;b.closest('p.step').classList.toggle('done',b.checked)});
    document.getElementById('pc').textContent=n+' of '+boxes.length+' steps done';
    document.getElementById('pb').style.width=(boxes.length?100*n/boxes.length:0)+'%';
  }
  boxes.forEach(function(b){
    var id=b.getAttribute('data-step');b.checked=!!saved[id];
    b.addEventListener('change',function(){saved[id]=b.checked;try{localStorage.setItem(KEY,JSON.stringify(saved))}catch(e){}paint()});
  });
  document.getElementById('rs').addEventListener('click',function(){boxes.forEach(function(b){b.checked=false});saved={};try{localStorage.removeItem(KEY)}catch(e){}paint()});
  paint();
  if(innerWidth<=860){var d=document.querySelector('nav.rail details');if(d)d.removeAttribute('open')}
  [].slice.call(document.querySelectorAll('pre')).forEach(function(p){
    var b=document.createElement('button');b.className='copy';b.type='button';b.textContent='Copy';
    b.addEventListener('click',function(){var t=p.innerText.replace(/^Copy\n?/,'');
      function sel(){var r=document.createRange();r.selectNodeContents(p.querySelector('code')||p);var s=getSelection();s.removeAllRanges();s.addRange(r);b.textContent='Selected'}
      if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(function(){b.textContent='Copied'},sel)}else sel();
      setTimeout(function(){b.textContent='Copy'},1500)});
    p.appendChild(b);
  });
  var links=[].slice.call(document.querySelectorAll('nav.rail a'));
  var heads=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1))});
  function spy(){var y=innerHeight*0.3,cur=0;heads.forEach(function(h,i){if(h&&h.getBoundingClientRect().top<y)cur=i});links.forEach(function(a,i){a.classList.toggle('on',i===cur)})}
  addEventListener('scroll',spy,{passive:true});spy();
  var tb=document.getElementById('tb');
  tb.addEventListener('click',function(){var r=document.documentElement;var dark=r.getAttribute('data-theme')?r.getAttribute('data-theme')==='dark':matchMedia('(prefers-color-scheme: dark)').matches;r.setAttribute('data-theme',dark?'light':'dark')});
})();
"""
html = f"""<title>Power BI Build Guide</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{css}</style>
<div class="shell">
<nav class="rail" aria-label="Contents"><details open><summary>Contents</summary>
<div class="prog"><span id="pc"></span><div class="bar"><i id="pb"></i></div><button class="reset" id="rs" type="button">Clear ticks</button></div>
<h2>Parts</h2><ol>{toc}</ol></details></nav>
<main>{body}</main>
</div>
<button class="themebtn" id="tb" type="button">Light / dark</button>
<script>{js}</script>
"""
open("guide_page.html", "w").write(html)
print(len(html)/1e6, "MB; steps:", len(re.findall("data-step", html)))
