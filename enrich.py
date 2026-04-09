"""
C4N Enricher — Streamlined
============================
Shows you the LinkedIn URL. You open it, click Job Openings tab, press Enter.
Script reads the page and saves directly to Supabase. No preview, no confirm.

USAGE:
  python enrich.py run 5      — enrich next 5 companies
  python enrich.py run 10     — enrich next 10
  python enrich.py status     — show progress
  python enrich.py retry      — reset errors back to Pending

SETUP (one time):
  pip install selenium requests
  Open Chrome with debug port:
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --profile-directory="Profile 1"
"""

import sys
import json
import requests
from datetime import datetime

SUPABASE_URL = "https://qwkynqdcrwukfnryguyn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3a3lucWRjcnd1a2ZucnlndXluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3MjA5NTIsImV4cCI6MjA5MTI5Njk1Mn0.SEG3nfXXMbCZgxUl2I2V-V2SItQy0WR4s7YbWDs9ZhA"
H = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

FIELDS = [
    "website","hq_city","hq_state","hq_location","about_full",
    "latest_post_snippet",
    "contact1_name","contact1_title","contact1_linkedin_url",
    "contact2_name","contact2_title","contact2_linkedin_url",
    "total_open_roles","eng_open_roles","eng_roles_pct_of_total",
    "eng_roles_change_3m","eng_roles_change_6m","eng_roles_change_1y",
]
REQUIRED = {"website","hq_location","about_full","total_open_roles","eng_open_roles"}

def sb_get(params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/companies", headers=H, params=params)
    r.raise_for_status()
    return r.json()

def sb_patch(cid, data):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/companies?id=eq.{cid}", headers=H, json=data)
    r.raise_for_status()

def get_pending(limit):
    return sb_get({
        "select": "id,name,linkedin_url",
        "enrichment_status": "eq.Pending",
        "linkedin_url": "not.is.null",
        "order": "created_at.asc",
        "limit": limit
    })

JS = r"""(function(){
  const body = document.body.innerText || '';
  const lines = body.split('\n').map(l=>l.trim()).filter(l=>l.length>0);
  const r = {};
  const um = window.location.href.match(/\/sales\/company\/(\d+)/);
  r.linkedin_url = um ? 'https://www.linkedin.com/sales/company/'+um[1] : window.location.href;
  r.name = document.title.replace(' | Sales Navigator','').replace(' | LinkedIn','').trim();
  for(const a of document.querySelectorAll('a[href]')){
    const h=a.href||'';
    if(h.startsWith('http')&&!h.includes('linkedin.com')&&!h.includes('chrome-extension')&&h.length>10){
      r.website=h.split('?')[0]; break;
    }
  }
  for(const pat of [
    /([A-Za-z\s\-\.]+,\s*[A-Za-z\s]+,\s*United States)/,
    /([A-Za-z\s\-\.]+,\s*[A-Za-z\s]+,\s*Canada)/,
    /([A-Za-z\s\-\.]+,\s*[A-Za-z\s]+,\s*United Kingdom)/
  ]){
    const m=body.match(pat);
    if(m&&m[1].length<70){
      const loc=m[1].trim(), parts=loc.split(',').map(p=>p.trim());
      r.hq_location=loc; r.hq_city=parts[0]||null; r.hq_state=parts[1]||null; break;
    }
  }
  for(const line of lines){
    if(line.length>80&&!line.includes('employees')&&!line.includes('Hiring on')&&
       !line.includes('Sales Navigator')&&!line.includes('connection')&&
       !line.includes('Save')&&line.split(' ').length>10){
      r.about_full=line.substring(0,800); break;
    }
  }
  for(let i=0;i<lines.length-1;i++){
    if(lines[i].toLowerCase().includes('posted')&&lines[i].length<60){
      const nx=lines[i+1];
      if(nx&&nx.length>40&&!nx.toLowerCase().includes('view')){
        r.latest_post_snippet=nx.substring(0,300); break;
      }
    }
  }
  const DM=['cto','chief technology','co-founder','vp of engineering','vp engineering',
            'head of engineering','chief technical officer','director of engineering'];
  const INF=['engineering manager','vp of product','head of product','vp product',
             'director of product','principal engineer'];
  const cands=[], seen=new Set();
  for(let i=1;i<lines.length;i++){
    const lw=lines[i].toLowerCase();
    if([...DM,...INF].some(t=>lw.includes(t))){
      const nm=lines[i-1];
      if(nm&&nm.split(' ').length>=2&&nm.split(' ').length<=6&&nm.length<60&&
         !nm.includes('·')&&!nm.includes('Save')&&!nm.includes('Add ')&&!seen.has(nm)){
        seen.add(nm);
        let url=null;
        for(const pl of document.querySelectorAll('a[href*="/sales/lead/"]')){
          const pt=(pl.innerText||'').trim().toLowerCase();
          if(pt&&pt.includes(nm.split(' ')[0].toLowerCase())){url=pl.href.split('?')[0];break;}
        }
        cands.push({name:nm,title:lines[i],url,tier:DM.some(t=>lw.includes(t))?1:2});
      }
    }
  }
  const c1=cands.find(c=>c.tier===1)||cands[0]||null;
  const c2=(cands.find(c=>c.tier===2&&c!==c1))||cands[1]||null;
  if(c1){r.contact1_name=c1.name;r.contact1_title=c1.title;r.contact1_linkedin_url=c1.url;}
  if(c2){r.contact2_name=c2.name;r.contact2_title=c2.title;r.contact2_linkedin_url=c2.url;}
  for(const el of document.querySelectorAll('[aria-label]')){
    const a=(el.getAttribute('aria-label')||'').toLowerCase();
    const em=a.match(/engineering has (\d+) openings?,?\s*([\d.]+)%/);
    if(em){r.eng_open_roles=parseInt(em[1]);r.eng_roles_pct_of_total=parseFloat(em[2]);}
  }
  const tm=body.match(/(\d+)\s*\n\s*Q[1-4]\s*\d{4}/);
  if(tm) r.total_open_roles=parseInt(tm[1]);
  const ei=lines.findIndex(l=>l.toLowerCase()==='engineering');
  if(ei>=0){
    const ch=[];
    for(let i=ei+1;i<Math.min(ei+15,lines.length);i++){
      const pm=lines[i].match(/^([\d.]+)%$/);
      if(pm){
        const d=(lines[i+1]||'').toLowerCase();
        ch.push((d.includes('increase')?'+':'-')+pm[1]+'%');
        if(ch.length>=3) break;
      }
    }
    if(ch[0]) r.eng_roles_change_3m=ch[0];
    if(ch[1]) r.eng_roles_change_6m=ch[1];
    if(ch[2]) r.eng_roles_change_1y=ch[2];
  }
  return JSON.stringify(r);
})();"""

def get_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts = Options()
        opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        return webdriver.Chrome(options=opts)
    except Exception as e:
        print(f"\n❌ Chrome not reachable: {e}")
        print('\nClose all Chrome windows first, then run:')
        print('"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"'
              ' --remote-debugging-port=9222 --profile-directory="Profile 1"\n')
        return None

def enrich(driver, company, idx, total):
    cid  = company["id"]
    name = company["name"]
    url  = company["linkedin_url"]

    print(f"\n[{idx}/{total}] {name}")
    print(f"    {url}")
    input("\n    Open URL -> Job Openings tab -> ENTER when ready: ")

    try:
        raw  = driver.execute_script(JS)
        data = json.loads(raw)
    except Exception as e:
        print(f"    ❌ Could not read page: {e}")
        sb_patch(cid, {"enrichment_status": "Error"})
        return False

    found = sum(1 for f in REQUIRED if data.get(f) not in (None, "", 0))
    if found < 4:
        missing = [f for f in REQUIRED if data.get(f) in (None, "", 0)]
        print(f"    ⚠️  Only {found}/5 key fields. Missing: {', '.join(missing)}")
        again = input("    [Enter=retry / s=skip]: ").strip().lower()
        if again == "s":
            print("    Skipped.")
            return False
        try:
            raw  = driver.execute_script(JS)
            data = json.loads(raw)
        except:
            pass

    payload = {"enrichment_status": "Done", "enriched_at": datetime.utcnow().isoformat()}
    for f in FIELDS:
        v = data.get(f)
        if v is not None and v != "":
            payload[f] = v

    try:
        sb_patch(cid, payload)
        filled = len([f for f in FIELDS if payload.get(f) not in (None, "")])
        print(f"    ✅ Saved — {filled} fields")
        return True
    except Exception as e:
        print(f"    ❌ Save failed: {e}")
        sb_patch(cid, {"enrichment_status": "Error"})
        return False

def run(count):
    print(f"\nFetching {count} pending companies...")
    companies = get_pending(count)
    if not companies:
        print("✅ Nothing pending — all done!")
        return
    print(f"Got {len(companies)}. Connecting to Chrome...")
    driver = get_driver()
    if not driver:
        return
    print(f"Connected ✅\n{'─'*50}")

    ok = fail = 0
    for i, co in enumerate(companies, 1):
        if enrich(driver, co, i, len(companies)):
            ok += 1
        else:
            fail += 1
        if i < len(companies):
            if input("\n    Next? [Enter=yes / q=quit]: ").strip().lower() in ("q","quit","n","no"):
                break

    try:
        s = sb_get({"select":"id","limit":2000})
        d = sb_get({"select":"id","enrichment_status":"eq.Done","limit":2000})
        t = len(s); dn = len(d); pct = int(dn/t*100) if t else 0
        bar = "█"*(pct//5)+"░"*(20-pct//5)
        print(f"\n{'═'*50}\n  Session: ✅ {ok}  ❌ {fail}")
        print(f"  Overall: {dn}/{t} [{bar}] {pct}%\n{'═'*50}\n")
    except:
        print(f"\nDone — {ok} saved, {fail} failed\n")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "status":
        try:
            s=sb_get({"select":"id","limit":2000})
            d=sb_get({"select":"id","enrichment_status":"eq.Done","limit":2000})
            e=sb_get({"select":"id","enrichment_status":"eq.Error","limit":2000})
            t=len(s); dn=len(d); er=len(e); pct=int(dn/t*100) if t else 0
            bar="█"*(pct//5)+"░"*(20-pct//5)
            print(f"\n  Total: {t}  Done: {dn}  Pending: {t-dn-er}  Errors: {er}")
            print(f"  [{bar}] {pct}%\n")
        except Exception as ex:
            print(f"Error: {ex}")
    elif args[0] == "retry":
        try:
            requests.patch(f"{SUPABASE_URL}/rest/v1/companies?enrichment_status=eq.Error",
                           headers=H, json={"enrichment_status":"Pending"}).raise_for_status()
            print("✅ Errors reset to Pending")
        except Exception as ex:
            print(f"Error: {ex}")
    elif args[0] == "run":
        run(int(args[1]) if len(args)>1 else 5)
    else:
        print(__doc__)
