import unittest
from pathlib import Path
from types import SimpleNamespace
from menu_images import image_for,FILES
from test_server import SecurityAndOrders

class MenuImageTests(unittest.TestCase):
    setUp=SecurityAndOrders.setUp
    tearDown=SecurityAndOrders.tearDown
    login=SecurityAndOrders.login
    post=SecurityAndOrders.post

    def test_six_registered_products_and_no_false_variants(self):
        samples=[('amsrel','cerveja 600ml','amstel-600'),('brahma','cerveja 600ml','brahma-600'),('brahma','cerveja litro','brahma-litro'),('original','cerveja litro','original-litro'),('batata frita','petisco','batata-frita'),('batata frita com bacon e chaddar','petisco','batata-bacon-cheddar')]
        for name,category,key in samples:
            photo=image_for(SimpleNamespace(name=name,category=category))
            self.assertEqual(photo['url'],'/static/menu-'+key+'.jpg')
        for name,category in [('Brahma Duplo Malte','cerveja litro'),('Amstel','cerveja 550ml'),('Batata frita com frango','petisco')]:
            self.assertIsNone(image_for(SimpleNamespace(name=name,category=category)))

    def test_menu_images_preserve_price_and_bar_isolation(self):
        own=self.bars[0]
        self.post(self.staff,f'/api/bars/{own}/products',{'name':'Amstel','category':'cerveja 600ml','price':'11'},self.staff_csrf)
        self.post(self.owner,f'/api/bars/{self.bars[1]}/products',{'name':'Original','category':'cerveja litro','price':'18'},self.owner_csrf)
        menu=self.guest.get('/api/public/'+self.table['token']).json['products']
        self.assertEqual(len(menu),2)
        amstel=next(p for p in menu if p['name']=='Amstel')
        self.assertEqual(amstel['price_cents'],1100)
        self.assertEqual(amstel['image']['alt'],'Amstel 600 ml')
        self.assertFalse(any(p['name']=='Original' for p in menu))

    def test_images_are_local_and_private_files_remain_hidden(self):
        for name in FILES:
            response=self.guest.get('/static/'+name)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.mimetype,'image/jpeg')
            self.assertGreater(len(response.data),1000);response.close()
        self.assertEqual(self.guest.get('/static/server.py').status_code,404)

if __name__=='__main__':unittest.main()
