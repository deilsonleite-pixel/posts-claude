"""PUT de um arquivo no uploadUrl do mLabs (prepare_media_upload). Uso: mlabs_put.py <resposta.json> <arquivo>"""
import json, sys, urllib.request
r = json.load(open(sys.argv[1])); data = open(sys.argv[2], 'rb').read()
req = urllib.request.Request(r['uploadUrl'], data=data, method=r.get('method', 'PUT'))
for k, v in r['headers'].items(): req.add_header(k, v)
req.add_header('Content-Length', str(len(data)))
with urllib.request.urlopen(req, timeout=120) as resp: print(resp.status)
