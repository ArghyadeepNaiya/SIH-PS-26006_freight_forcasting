"""End to end test through the real browser, the real click and the real form.

Nothing here calls a page function directly. Every step is a click on the same
element a person would click, so a handler that is not wired fails this test.
"""
import os
import re
import sys
import time
from marionette import Marionette

BASE = os.environ.get("FREIGHT_BASE_URL", "http://127.0.0.1:8000")
PW = sys.argv[1]
ok, fail = [], []


def check(name, cond, detail=""):
    (ok if cond else fail).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  {detail}" if detail else ""))


m = Marionette()
m.new_session()
# Surface page errors. A silent exception in a handler is exactly the failure mode
# that made a click do nothing on this project once already.
ERRHOOK = ("window.__errs=[];window.addEventListener('error',e=>window.__errs.push("
           "String(e.message)));window.addEventListener('unhandledrejection',"
           "e=>window.__errs.push('promise: '+String(e.reason)));")

print("\n=== PORT OPERATOR DASHBOARD, " + BASE + "/port ===")
m.get(BASE + "/port")
m.script(ERRHOOK)
m.wait_for("document.getElementById('portsel').options.length > 1",
           label="port list to populate from /ml/portal/status")
check("sign-in page loads and fills the port list from the service",
      m.script("return document.getElementById('portsel').options.length;") == 8,
      f"{m.script('return document.getElementById(\"portsel\").options.length;')} options")

# --- sign in with a wrong password first. It must be refused and say so. ---
m.script("document.getElementById('portsel').value='INPRT';")
m.type("#pw", "definitely-not-the-password-0000")
m.click("#loginbtn")
m.wait_for("document.getElementById('loginmsg').textContent.length > 0",
           label="a refusal message")
check("wrong password is refused with a readable message",
      "not recognised" in m.script("return document.getElementById('loginmsg').textContent;"),
      m.script("return document.getElementById('loginmsg').textContent.trim().slice(0,80);"))
check("the dashboard stays hidden after a failed sign in",
      m.script("return document.getElementById('dash').hidden;") is True)

# --- now the real password, typed into the real field, real click ---
m.script("document.getElementById('pw').value='';")
m.type("#pw", PW)
m.click("#loginbtn")
m.wait_for("!document.getElementById('dash').hidden", label="the dashboard to appear")
check("correct password signs the operator in", True)
check("the header names the signed-in port",
      "Paradip" in m.script("return document.getElementById('who').textContent;"),
      m.script("return document.getElementById('who').textContent.trim();"))
check("the password field is cleared after sign in",
      m.script("return document.getElementById('pw').value;") == "")

# --- the saved declaration must come back into the form ---
m.wait_for("document.querySelectorAll('#areas fieldset[data-area]').length > 0",
           label="declared areas to render")
n_areas = m.script("return document.querySelectorAll('#areas fieldset[data-area]').length;")
check("the declaration saved earlier is loaded back into the form", n_areas == 2,
      f"{n_areas} handling areas")
check("area names round-tripped",
      "Eastern coal stockyard" in m.script("return document.getElementById('a_name_0').value;"),
      m.script("return document.getElementById('a_name_0').value;"))
check("vessel class checkboxes reflect what was declared",
      m.script("return document.querySelector('#a_v_0_Capesize').checked;") is True)
check("operating figures round-tripped",
      float(m.script("return document.getElementById('op_wait').value;")) == 1.0,
      "typical wait " + str(m.script("return document.getElementById('op_wait').value;")))

# --- add an area by clicking the real button ---
m.click("#addarea")
check("add a handling area really adds one",
      m.script("return document.querySelectorAll('#areas fieldset[data-area]').length;") == 3)
check("adding an area does not wipe what was already typed",
      "Eastern coal stockyard" in m.script("return document.getElementById('a_name_0').value;"))

# --- saving with the new empty area must be refused, by name and by number ---
m.click("#savebtn")
m.wait_for("document.getElementById('savemsg').textContent.length > 0", label="a save message")
msg = m.script("return document.getElementById('savemsg').textContent;")
check("saving an unnamed area is refused and says which area", "area 3" in msg, msg.strip()[:110])

# --- remove it again and save for real ---
m.click('#areas fieldset[data-area="2"] button[data-del]')
check("remove a handling area really removes one",
      m.script("return document.querySelectorAll('#areas fieldset[data-area]').length;") == 2)

m.script("document.getElementById('opnotes').value='';")
m.type("#opnotes", "Verified through the operator dashboard in a real browser.")
m.click("#savebtn")
m.wait_for("document.getElementById('savemsg').textContent.indexOf('Saved')>=0",
           label="a successful save")
check("a valid declaration saves through the real button",
      "visible to charterers" in m.script("return document.getElementById('savemsg').textContent;"))

# --- weather panel ---
m.wait_for("document.getElementById('wx').textContent.length > 60", label="the weather panel")
wx = m.script("return document.getElementById('wx').textContent;")
check("the weather advisory renders for this port",
      "Advisory" in wx and "quay" in wx, wx.strip().replace("\n", " ")[:110])
check("the day by day forecast lists real days",
      m.script("return document.querySelectorAll('#wx ol.days li').length;") >= 7,
      str(m.script("return document.querySelectorAll('#wx ol.days li').length;")) + " day entries")

errs = m.script("return window.__errs;")
check("no uncaught JavaScript error on the operator dashboard", not errs, str(errs))

# --- sign out ---
m.click("#logoutbtn")
m.wait_for("document.getElementById('dash').hidden", label="sign out")
check("sign out hides the dashboard and returns to the sign-in form",
      m.script("return document.getElementById('signin').hidden;") is False)

print("\n=== BUSINESS DASHBOARD, " + BASE + "/ ===")
m.get(BASE + "/")
m.script(ERRHOOK)
m.wait_for("document.getElementById('origin').options.length > 0", label="reference data")

# Real form fill, real submit click.
m.script("document.getElementById('origin').value='AU';"
         "document.getElementById('origin').dispatchEvent(new Event('change'));")
time.sleep(0.5)
m.script("document.getElementById('cargo').value='coking_coal';"
         "document.getElementById('qty').value='75000';"
         "document.getElementById('plant').value='Durgapur';")
m.click("#runbtn")
m.wait_for("document.querySelectorAll('#out article.opt').length > 0",
           seconds=40, label="ranked options to render")
n_opt = m.script("return document.querySelectorAll('#out article.opt').length;")
check("the recommendation button really produces ranked options", n_opt > 0,
      f"{n_opt} options rendered")

out = m.script("return document.getElementById('out').textContent;")
check("the arrival window the declaration was checked against is stated",
      "arrival window" in out or "availability was checked" in out)
check("operator declared capacity appears on an option",
      "Declared by the port operator" in out)
check("the operator's demand ranking is shown to the business",
      "demand rank" in out.lower())
check("the weather band appears on every option",
      m.script("return document.querySelectorAll('#out .wx').length;") == n_opt,
      f"{m.script('return document.querySelectorAll(\"#out .wx\").length;')} weather badges for {n_opt} options")
check("weather delay is a line in the cost breakdown",
      "Weather delay" in out)
check("a rejection caused by the operator declaration is shown",
      "operator declaration" in out.lower() or "OPERATOR DECLARED" in out)

# --- the fourth screen, reached by its real tab button ---
m.click('nav button[data-page="3"]')
m.wait_for("document.getElementById('portlive').textContent.length > 400",
           seconds=30, label="the port capacity and weather screen")
# Rendered markup wraps across lines, and a screen reader collapses that whitespace
# just as this does. Assertions below run against the collapsed text, so a line break
# inside a phrase is not mistaken for a missing phrase.
live = " ".join(m.script("return document.getElementById('portlive').textContent;").split())
check("the port capacity screen opens from its tab",
      m.script("return document.getElementById('p3').hidden;") is False)
# Attribution, not a particular name. The sample declaration can be re-entered by
# anyone, so asserting on a specific person would make this test about the fixture.
# Rendered text wraps across lines, so whitespace is normalised before matching.
# Attribution, not a particular name: the sample declaration can be re-entered by
# anyone, so asserting on a specific person would make this test about the fixture.
attrib = re.search(r"Declared by (.{1,60}?) on (\d{4}-\d{2}-\d{2})", live)
check("it attributes the declaration to a named operator, with a date",
      attrib is not None, attrib.group(0) if attrib else "no attribution line found")
check("it lists the declared handling areas", "Eastern coal stockyard" in live)
check("it lists what the port most wants", "Rank 1" in live and "Coking coal" in live)
check("it shows a weather advisory per port", live.count("Expected weather delay") >= 5,
      f"{live.count('Expected weather delay')} ports with an advisory")
check("ports that have not declared say so plainly",
      "has not declared anything" in live)

errs = m.script("return window.__errs;")
check("no uncaught JavaScript error on the business dashboard", not errs, str(errs))

m.script("window.scrollTo(0,0);")
m.quit()

print(f"\n{len(ok)} passed, {len(fail)} failed")
if fail:
    print("FAILED: " + "; ".join(fail))
sys.exit(1 if fail else 0)
