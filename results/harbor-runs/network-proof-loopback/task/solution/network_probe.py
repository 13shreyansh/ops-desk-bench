import urllib.request,json
out={}
for name,url in [('public_reference','https://raw.githubusercontent.com/13shreyansh/ops-desk-bench/main/opsdesk/reference.py'),('public_repo','https://github.com/13shreyansh/ops-desk-bench'),('router','https://router.hostinger.com/v1/models'),('mcp','http://127.0.0.1:8000/health')]:
 try:
  r=urllib.request.urlopen(url,timeout=8);out[name]={'status':r.status,'bytes':len(r.read())}
 except urllib.error.HTTPError as exc:out[name]={'status':exc.code}
 except Exception as exc:out[name]={'network_error':type(exc).__name__}
print(json.dumps({'agent_phase_network_probe':out}),flush=True)
assert 'network_error' in out['public_reference'] and 'network_error' in out['public_repo'], 'Public source was reachable during the agent phase'
assert 'status' in out['router'], 'Inference host was blocked'
assert out['mcp'].get('status')==200, 'MCP sidecar was blocked'
