"""Rails + Cloudflare Recon Collector for Hancock — Enhanced v0.4.13"""

import requests
from typing import Dict, Any

def run_rails_cloudflare_recon(target: str) -> Dict[str, Any]:
    result = {
        "target": target,
        "status_code": None,
        "server": None,
        "cloudflare": False,
        "rails_detected": False,
        "security_headers": {},
        "cf_ray": None,
        "robots_txt": None,
        "security_txt": None,
        "response_time_ms": None
    }
    
    try:
        import time
        start = time.time()
        resp = requests.head(f"https://{target}", timeout=12, allow_redirects=True)
        result["response_time_ms"] = round((time.time() - start) * 1000, 2)
        
        result["status_code"] = resp.status_code
        result["server"] = resp.headers.get("server", "unknown")
        result["cf_ray"] = resp.headers.get("cf-ray")
        result["cloudflare"] = "cloudflare" in result["server"].lower() or bool(result["cf_ray"])
        
        # Rails detection
        if any(x in str(resp.headers).lower() for x in ["x-request-id", "rails"]):
            result["rails_detected"] = True
            
        # Security headers
        security_headers = ["strict-transport-security", "x-frame-options", 
                           "x-content-type-options", "referrer-policy", "permissions-policy"]
        result["security_headers"] = {h: resp.headers.get(h) for h in security_headers if resp.headers.get(h)}
        
        # Check robots.txt
        try:
            r = requests.get(f"https://{target}/robots.txt", timeout=8)
            if r.status_code == 200:
                result["robots_txt"] = r.text[:500]
        except:
            pass
            
        # Check security.txt
        try:
            r = requests.get(f"https://{target}/.well-known/security.txt", timeout=8)
            if r.status_code == 200:
                result["security_txt"] = r.text[:500]
        except:
            pass
            
    except Exception as e:
        result["error"] = str(e)
    
    return result
