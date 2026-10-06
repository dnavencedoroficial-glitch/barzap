import unittest
from test_server import SecurityAndOrders
from server import Product,ProductPreset,seed_catalog,create_app
from sqlalchemy.orm import Session
from sqlalchemy import select
import starter_catalog
class StarterCatalog(unittest.TestCase):
 setUp=SecurityAndOrders.setUp
 tearDown=SecurityAndOrders.tearDown
 login=SecurityAndOrders.login
 post=SecurityAndOrders.post
 open=SecurityAndOrders.open
 payload=SecurityAndOrders.payload
 def test_catalog_idempotence_and_preservation(self):
  bar=self.bars[0]
  with Session(self.app.extensions['engine']) as db:
   db.add(Product(id='old-amstel',bar_id=bar,name='amsrel',category='cerveja 600ml',price_cents=1100,enabled=True));db.commit()
   seed_catalog(db,bar);db.commit();seed_catalog(db,bar);db.commit()
   products=list(db.scalars(select(Product).where(Product.bar_id==bar)))
   self.assertEqual(len(products),62);self.assertEqual(db.get(Product,'old-amstel').price_cents,1100)
   self.assertEqual(len(list(db.scalars(select(ProductPreset).where(ProductPreset.bar_id==bar)))),61)
   draft=next(p for p in products if p.price_cents==0);draft_id=draft.id;draft.enabled=False;db.commit();seed_catalog(db,bar);db.commit();self.assertFalse(db.get(Product,draft_id).enabled)
 def test_pending_price_isolation_and_activation(self):
  with Session(self.app.extensions['engine']) as db:
   seed_catalog(db,self.bars[0]);db.commit();draft=db.scalar(select(Product).where(Product.price_cents==0));pid=draft.id
  path=f'/api/bars/{self.bars[0]}/products/{pid}/price'
  self.assertNotIn(pid,[p['id'] for p in self.guest.get('/api/public/'+self.table['token']).json['products']])
  self.open();payload=self.payload();payload['items']=[{'id':pid,'quantity':1}]
  self.assertEqual(self.post(self.guest,'/api/public/'+self.table['token']+'/orders',payload,self.guest_csrf).status_code,400)
  self.assertEqual(self.post(self.staff,path,{'price':'0'},self.staff_csrf).status_code,400)
  self.assertEqual(self.post(self.staff,path.replace(self.bars[0],self.bars[1]),{'price':'8'},self.staff_csrf).status_code,404)
  self.assertEqual(self.post(self.staff,path,{'price':'8.50'},self.staff_csrf).status_code,200)
  menu=self.guest.get('/api/public/'+self.table['token']).json['products'];self.assertEqual(next(p for p in menu if p['id']==pid)['price_cents'],850)
  self.assertEqual(self.post(self.guest,'/api/public/'+self.table['token']+'/orders',payload,self.guest_csrf).json['total_cents'],850)
 def test_startup_and_new_bars(self):
  app=create_app({'TESTING':True,'STARTER_CATALOG':True,'SECRET_KEY':'test-only-key-not-for-production','DATABASE_URL':self.url})
  with Session(app.extensions['engine']) as db:self.assertEqual(len(list(db.scalars(select(ProductPreset)))),122)
  client=app.test_client();csrf=self.login(client,'admin@example.test','AdminTest123!')
  result=self.post(client,'/api/bars',{'name':'Novo','email':'new@example.test','password':'NewTest123!'},csrf)
  products=client.get('/api/bars/'+result.json['bar']['id']+'/products').json['products'];self.assertEqual(len(products),61);self.assertTrue(all(p['price_pending'] and p['image'] for p in products))
  app.extensions['engine'].dispose()
 def test_packaged_images(self):
  self.assertEqual(len(starter_catalog.CATALOG),61)
  for filename in starter_catalog.STATIC_FILES:
   response=self.guest.get('/static/'+filename);self.assertEqual(response.status_code,200);self.assertEqual(response.mimetype,'image/jpeg');response.close()
  self.assertEqual(self.guest.get('/static/starter_catalog.json').status_code,404)
