"""Reviewed packaged drinks. Prices belong to each bar."""
import json,re,unicodedata
from pathlib import Path
CATALOG=json.loads(Path(__file__).with_name('starter_catalog.json').read_text(encoding='utf-8'))
BY_KEY={p['key']:p for p in CATALOG}
STATIC_FILES={p['file'] for p in CATALOG}
def normalize(value):
 return ' '.join(re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',value.lower()).encode('ascii','ignore').decode()).split())
def matches(product,preset):
 name=normalize(product.name).removeprefix('cerveja ')
 if name==normalize(preset['name']):return True
 aliases=[normalize(a) for a in preset['aliases']]
 aliases+= {'coca-350':['coca cola lata','coca cola original lata'],'coca-zero-350':['coca cola lata zero','coca cola lata zera','coca cola zero lata'],'guarana-ant-350':['guarana antartica lata','guarana antarctica lata']}.get(preset['key'],[])
 if name not in aliases:return False
 value=normalize(product.name+' '+product.category)
 size='600' if re.search(r'\b600\s*ml\b',value) else '350' if 'lata' in value or re.search(r'\b350\s*ml\b',value) else '1000' if re.search(r'\b(?:litro|litrao|1\s*l)\b',value) else None
 return size==preset['key'].rsplit('-',1)[-1]
def metadata(preset):
 return {'url':'/static/'+preset['file'],'alt':preset['name'],'credit':preset['credit'],'source':preset['source'],'license':None,'kind':'bottle'}
def image_for(product):
 preset=next((p for p in CATALOG if matches(product,p)),None)
 return metadata(preset) if preset else None
