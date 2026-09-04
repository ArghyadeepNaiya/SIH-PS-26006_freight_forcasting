"""Structural accessibility audit in the real browser, after the JavaScript has run.

Checks the things that decide whether a page is usable with JAWS. Auditing the raw
HTML file would miss every control the page builds at runtime, which on the operator
dashboard is most of them.
"""
import os, sys, time
from marionette import Marionette

BASE = os.environ.get("FREIGHT_BASE_URL", "http://127.0.0.1:8000")
PW = sys.argv[1]
m = Marionette(); m.new_session()
problems = []

AUDIT = """
var out = {};
// 1. Every form control must have an accessible name.
out.unlabelled = Array.from(document.querySelectorAll('input,select,textarea'))
  .filter(function(e){
    if (e.type === 'hidden') return false;
    if (e.id && document.querySelector('label[for="' + CSS.escape(e.id) + '"]')) return false;
    if (e.closest('label')) return false;
    return !(e.getAttribute('aria-label') || e.getAttribute('aria-labelledby'));
  }).map(function(e){ return e.tagName + '#' + (e.id || '(no id)'); });

// 2. Heading levels must not skip, so heading navigation works.
var hs = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6'))
  .filter(function(h){ return h.offsetParent !== null || h.closest('[hidden]') === null; });
out.headings = hs.map(function(h){ return h.tagName + ' ' + h.textContent.trim().slice(0,44); });
out.skips = [];
var prev = 0;
hs.forEach(function(h){
  var lvl = Number(h.tagName[1]);
  if (prev && lvl > prev + 1) out.skips.push(h.tagName + ' after H' + prev + ': ' + h.textContent.trim().slice(0,40));
  prev = lvl;
});

// 3. No layout or data tables. They do not read linearly.
out.tables = document.querySelectorAll('table').length;

// 4. Every fieldset must carry a legend.
out.fieldsets = document.querySelectorAll('fieldset').length;
out.legendless = Array.from(document.querySelectorAll('fieldset'))
  .filter(function(f){ return !f.querySelector(':scope > legend'); }).length;

// 5. Landmarks and a skip link.
out.landmarks = ['header','nav','main','footer'].filter(function(t){ return document.querySelector(t); });
out.skiplink = !!document.querySelector('a.skip');
out.mainFocusable = !!document.querySelector('main[tabindex]');

// 6. Live regions, so status changes are announced.
out.live = document.querySelectorAll('[aria-live],[role=status],[role=alert]').length;

// 7. Images must have alt text; SVG used decoratively must carry a text equivalent.
out.imgNoAlt = Array.from(document.querySelectorAll('img')).filter(function(i){ return !i.hasAttribute('alt'); }).length;
out.svgNoLabel = Array.from(document.querySelectorAll('svg')).filter(function(s){
  return !(s.getAttribute('aria-label') || s.getAttribute('role') === 'presentation' || s.getAttribute('aria-hidden'));
}).length;

// 8. Buttons must have text, not only an icon or colour.
out.emptyButtons = Array.from(document.querySelectorAll('button'))
  .filter(function(b){ return !b.textContent.trim() && !b.getAttribute('aria-label'); }).length;
return out;
"""

def audit(name):
    r = m.script(AUDIT)
    print("\n--- " + name + " ---")
    print("  form controls with no label:", r["unlabelled"] or "none")
    print("  heading level skips:", r["skips"] or "none")
    print("  headings:", len(r["headings"]))
    print("  tables (must be 0):", r["tables"])
    print("  fieldsets:", r["fieldsets"], "without a legend:", r["legendless"])
    print("  landmarks:", r["landmarks"])
    print("  skip link:", r["skiplink"], "| main focusable:", r["mainFocusable"])
    print("  live regions:", r["live"])
    print("  images with no alt:", r["imgNoAlt"], "| svg with no label:", r["svgNoLabel"])
    print("  buttons with no text:", r["emptyButtons"])
    for k, msg in [("unlabelled","form control with no label"),("skips","heading level skip")]:
        for x in r[k]: problems.append(f"{name}: {msg}: {x}")
    if r["tables"]: problems.append(f"{name}: {r['tables']} table(s) present")
    if r["legendless"]: problems.append(f"{name}: {r['legendless']} fieldset(s) with no legend")
    if r["emptyButtons"]: problems.append(f"{name}: {r['emptyButtons']} button(s) with no text")
    if r["imgNoAlt"]: problems.append(f"{name}: {r['imgNoAlt']} image(s) with no alt")
    if r["svgNoLabel"]: problems.append(f"{name}: {r['svgNoLabel']} svg with no text equivalent")
    if not r["skiplink"]: problems.append(f"{name}: no skip link")
    return r

m.get(BASE + "/port")
m.wait_for("document.getElementById('portsel').options.length > 1")
audit("operator dashboard, signed out")

m.script("document.getElementById('portsel').value='INPRT';")
m.type("#pw", PW)
m.click("#loginbtn")
m.wait_for("!document.getElementById('dash').hidden")
m.wait_for("document.querySelectorAll('#areas fieldset[data-area]').length > 0")
m.wait_for("document.getElementById('wx').textContent.length > 60")
audit("operator dashboard, signed in with the form built")

m.get(BASE + "/")
m.wait_for("document.getElementById('origin').options.length > 0")
m.click("#runbtn")
m.wait_for("document.querySelectorAll('#out article.opt').length > 0", seconds=45)
m.click('nav button[data-page="p3"]')
m.wait_for("document.getElementById('portlive').textContent.length > 400", seconds=30)
audit("business dashboard, results and port screen rendered")

print()
if problems:
    print("PROBLEMS FOUND:")
    for p in problems: print("  -", p)
else:
    print("No structural accessibility problems found on either page.")
sys.exit(1 if problems else 0)
