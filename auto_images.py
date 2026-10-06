"""Bounded Openverse lookup and normalized JPEGs stored in the database."""
import base64,io,json,re,uuid
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen,HTTPRedirectHandler,build_opener
from PIL import Image,ImageOps,UnidentifiedImageError
from menu_images import normalize

Image.MAX_IMAGE_PIXELS=20_000_000
MAX_BYTES=2_000_000
ALIASES={
 'hamburguer':'hamburger','hamburguer artesanal':'hamburger','hamburger':'hamburger',
 'pizza':'pizza','pizza de queijo':'cheese pizza','pizza de mussarela':'cheese pizza',
 'suco de laranja':'orange juice','suco natural de laranja':'orange juice',
 'suco de limao':'lemon juice','cafe':'coffee','cafe expresso':'espresso',
 'cachorro quente':'hot dog','hot dog':'hot dog','espetinho':'espetinho',
 'coxinha':'coxinha','pastel':'pastel brasileiro','agua mineral':'mineral water',
}

class ApiRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parts=urlsplit(newurl)
        if parts.scheme!='https' or parts.hostname!='api.openverse.org':raise ValueError('Destino de imagem inválido')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def read_api(url,limit):
    with build_opener(ApiRedirects()).open(Request(url,headers={'User-Agent':'BarZap/1.0 (menu photographs)'}),timeout=4) as response:
        content=response.read(limit+1)
        if len(content)>limit:raise ValueError('Arquivo grande demais')
        return content

def jpeg(content):
    if len(content)>MAX_BYTES:raise ValueError('Foto deve ter até 2 MB')
    with Image.open(io.BytesIO(content)) as picture:
        if picture.format not in ('JPEG','PNG','WEBP'):raise ValueError('Use foto JPG, PNG ou WebP')
        picture=ImageOps.exif_transpose(picture).convert('RGBA')
        picture.thumbnail((1000,1000))
        background=Image.new('RGB',picture.size,'white')
        background.paste(picture,mask=picture.getchannel('A'))
        output=io.BytesIO();background.save(output,'JPEG',quality=85,optimize=True)
        return output.getvalue()

def uploaded_photo(value):
    if not isinstance(value,str) or not value.startswith('data:image/jpeg;base64,'):raise ValueError('Foto inválida')
    try:return jpeg(base64.b64decode(value.split(',',1)[1],validate=True))
    except (ValueError,UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:raise ValueError('Use uma foto válida com até 2 MB') from exc

def https(value):
    return isinstance(value,str) and len(value)<2000 and urlsplit(value).scheme=='https' and bool(urlsplit(value).hostname)

def find_photo(name,category):
    query=ALIASES.get(normalize(name),name.strip())
    if not query:return None
    try:
        payload=json.loads(read_api('https://api.openverse.org/v1/images/?'+urlencode({'q':query,'license_type':'commercial,modification','mature':'false','page_size':20}),250000))
        candidates=[]
        wanted=set(normalize(query).split())
        for item in payload.get('results',[]):
            title=normalize(str(item.get('title','')))
            # Search ranking can return unrelated cities, cakes or signs. Only
            # exact photo titles are accepted automatically; ambiguous results
            # stay without a photo and can be replaced by the bar's own picture.
            if title not in (normalize(query),normalize(query)+'s'):continue
            if item.get('license') not in ('by','by-sa','cc0','pdm') or item.get('mature'):continue
            if not https(item.get('foreign_landing_url')) or not https(item.get('license_url')):continue
            image_id=str(uuid.UUID(item['id']))
            candidates.append((item,image_id))
        if not candidates:return None
        item,image_id=candidates[0]
        content=jpeg(read_api('https://api.openverse.org/v1/images/'+image_id+'/thumb/',MAX_BYTES))
        return content,{'alt':name,'credit':str(item.get('creator') or 'Autor informado no Openverse')[:200],
            'source':item['foreign_landing_url'],'license':item['license_url'],'kind':'food','origin':'Openverse'}
    except Exception:
        # Provider outages/rate limits must never prevent a product being saved.
        return None
