"""Curated menu photographs; no customer/bar data is sent to external image sites."""
import re
import unicodedata

CATALOG = {
    'amstel-600': ('Amstel 600 ml', 'Amstel Brasil', 'https://www.amstelbrasil.com/produtos/amstel-600ml/', None),
    'brahma-600': ('Brahma 600 ml', 'Rizatti / Brahma', 'https://www.rizatti.com.br/nossas-marcas/cervejas/brahma/brahma-chopp', None),
    'brahma-litro': ('Brahma 1 litro', 'Rizatti / Brahma', 'https://www.rizatti.com.br/nossas-marcas/cervejas/brahma/brahma-chopp', None),
    'original-litro': ('Original 1 litro', 'Supermercado Bresciani / Original', 'https://www.superbresciani.com.br/loja-1/produto/m/cervoriginal-1l-garrafa-12746', None),
    'batata-frita': ('Batata frita', 'City Foodsters', 'https://commons.wikimedia.org/wiki/File:Complimentary_plate_of_fries_(9379689031).jpg', 'https://creativecommons.org/licenses/by/2.0/'),
    'batata-bacon-cheddar': ('Batata frita com bacon e cheddar', 'Ser Amantio di Nicolao', 'https://commons.wikimedia.org/wiki/File:Cheddar_Bacon_Fries_from_Roy_Rogers,_overhead_view.jpg', 'https://creativecommons.org/licenses/by-sa/3.0/'),
}
FILES = {'menu-'+key+'.jpg' for key in CATALOG}

def normalize(value):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', value.lower()).encode('ascii', 'ignore').decode()).split())

def image_for(product):
    name=normalize(product.name)
    category=normalize(product.category)
    key=None
    if name in ('batata frita', 'batatas fritas'):
        key='batata-frita'
    elif name in ('batata frita com bacon e cheddar', 'batata frita com bacon e chaddar', 'batata frita bacon cheddar', 'batata frita com cheddar e bacon'):
        key='batata-bacon-cheddar'
    elif 'cerveja' in category or name.startswith('cerveja '):
        beer=name.removeprefix('cerveja ')
        # Match only reviewed brands/volumes, never e.g. Brahma Duplo Malte.
        volume=normalize(beer+' '+category)
        size='600' if re.search(r'\b600\s*ml\b',volume) else 'litro' if re.search(r'\b(?:litro|litrao|1\s*l|1\s*litro)\b',volume) else None
        brand=beer
        for suffix in (' 600ml',' 600 ml',' 1 litro',' 1l',' 1 l'):
            if brand.endswith(suffix):brand=brand[:-len(suffix)]
        if brand in ('amstel','amsrel') and size=='600':key='amstel-600'
        elif brand in ('brahma','brahma chopp') and size in ('600','litro'):key='brahma-'+size
        elif brand in ('original','antarctica original') and size=='litro':key='original-litro'
    if key is None:return None
    title,credit,source,license_url=CATALOG[key]
    return {'url':'/static/menu-'+key+'.jpg','alt':title,'credit':credit,'source':source,'license':license_url,'kind':'food' if key.startswith('batata') else 'bottle'}

def product_data(product):
    return {'id':product.id,'category':product.category,'name':product.name,'price_cents':product.price_cents,'image':image_for(product)}
