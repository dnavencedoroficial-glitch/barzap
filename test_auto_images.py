import base64,io,unittest
from unittest.mock import patch
from PIL import Image
from auto_images import find_photo
from test_server import SecurityAndOrders
from sqlalchemy.orm import Session
from server import ProductPhoto,create_app

class AutoImageTests(unittest.TestCase):
    setUp=SecurityAndOrders.setUp
    tearDown=SecurityAndOrders.tearDown
    login=SecurityAndOrders.login
    post=SecurityAndOrders.post
    def picture(self):
        output=io.BytesIO();Image.new('RGB',(80,60),'orange').save(output,'JPEG');return output.getvalue()
    def upload(self):return 'data:image/jpeg;base64,'+base64.b64encode(self.picture()).decode()
    def test_auto_image_is_persisted_and_local(self):
        self.app.config['IMAGE_LOOKUP']=lambda name,category:(self.picture(),{'alt':name,'credit':'Test author','source':'https://example.test/photo','license':'https://creativecommons.org/licenses/by/4.0/','kind':'food'})
        result=self.post(self.staff,f'/api/bars/{self.bars[0]}/products',{'name':'Hambúrguer','category':'Lanches','price':'15'},self.staff_csrf)
        self.assertEqual(result.status_code,201);self.assertEqual(result.json['image_state'],'found')
        product_id=result.json['id']
        menu=self.guest.get('/api/public/'+self.table['token']).json['products']
        product=next(p for p in menu if p['id']==product_id)
        self.assertEqual(product['price_cents'],1500)
        url=product['image']['url'];response=self.guest.get(url)
        self.assertEqual(response.status_code,200);self.assertEqual(response.mimetype,'image/jpeg');response.close()
        recreated=create_app({'TESTING':True,'SECRET_KEY':'test-only-key-not-for-production','DATABASE_URL':self.url})
        with Session(recreated.extensions['engine']) as db:self.assertGreater(len(db.get(ProductPhoto,product_id).content),100)
        recreated.extensions['engine'].dispose()
    def test_own_photo_replacement_requires_same_bar(self):
        path=f'/api/bars/{self.bars[0]}/products/{self.product}/image'
        result=self.post(self.staff,path,{'photo':self.upload()},self.staff_csrf)
        self.assertEqual(result.status_code,200);old=result.json['product']['image']['url']
        result=self.post(self.staff,path,{'photo':self.upload()},self.staff_csrf)
        self.assertNotEqual(old,result.json['product']['image']['url'])
        self.assertEqual(self.guest.get(old).status_code,404)
        self.assertEqual(self.post(self.staff,f'/api/bars/{self.bars[1]}/products/{self.product}/image',{'photo':self.upload()},self.staff_csrf).status_code,404)
        self.assertEqual(self.post(self.guest,path,{'photo':self.upload()},self.guest_csrf).status_code,401)
    def test_missing_photo_does_not_block_product_or_accept_bad_upload(self):
        self.app.config['IMAGE_LOOKUP']=lambda name,category:None
        path=f'/api/bars/{self.bars[0]}/products'
        result=self.post(self.staff,path,{'name':'Produto sem resultado','category':'Lanches','price':'10'},self.staff_csrf)
        self.assertEqual(result.status_code,201);self.assertEqual(result.json['image_state'],'missing')
        bad=self.post(self.staff,path,{'name':'Arquivo inválido','category':'Lanches','price':'10','photo':'data:image/jpeg;base64,AAAA'},self.staff_csrf)
        self.assertEqual(bad.status_code,400)
        self.assertFalse(any(p['name']=='Arquivo inválido' for p in self.staff.get(path).json['products']))
    def test_lookup_ignores_unrelated_and_noncommercial_results(self):
        import json
        item={'id':'487f6204-89f6-4e8e-8ef2-b2ebbc69c1d6','title':'Hamburger Cake','license':'by','foreign_landing_url':'https://example.test/photo','license_url':'https://creativecommons.org/licenses/by/4.0/'}
        with patch('auto_images.read_api',return_value=json.dumps({'results':[item]}).encode()):self.assertIsNone(find_photo('Hambúrguer','Lanches'))
        item['title']='Hamburger';item['license']='by-nc'
        with patch('auto_images.read_api',return_value=json.dumps({'results':[item]}).encode()):self.assertIsNone(find_photo('Hambúrguer','Lanches'))

if __name__=='__main__':unittest.main()
