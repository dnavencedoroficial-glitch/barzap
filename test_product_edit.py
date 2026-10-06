import unittest
from test_server import SecurityAndOrders
from server import Product,Order
from inventory import Stock
from sqlalchemy.orm import Session
from sqlalchemy import select
class EditProductTests(unittest.TestCase):
 setUp=SecurityAndOrders.setUp
 tearDown=SecurityAndOrders.tearDown
 login=SecurityAndOrders.login
 post=SecurityAndOrders.post
 open=SecurityAndOrders.open
 payload=SecurityAndOrders.payload
 def edit(self,data,bar=None):return self.staff.patch(f'/api/bars/{bar or self.bars[0]}/products/{self.product}',json=data,headers={'X-CSRF-Token':self.staff_csrf})
 def test_edit_preserves_orders_and_stock(self):
  self.open();self.post(self.guest,'/api/public/'+self.table['token']+'/orders',self.payload(),self.guest_csrf)
  with Session(self.app.extensions['engine']) as db:db.add(Stock(product_id=self.product,quantity=9));db.commit()
  response=self.edit({'name':'Suco de laranja','category':'Sucos','price':'8.50'});self.assertEqual(response.status_code,200)
  with Session(self.app.extensions['engine']) as db:
   self.assertEqual(db.get(Stock,self.product).quantity,9);order=db.scalar(select(Order));self.assertEqual(order.items[0]['name'],'Suco');self.assertEqual(order.total_cents,1200)
  menu=self.guest.get('/api/public/'+self.table['token']).json['products'][0];self.assertEqual(menu['name'],'Suco de laranja');self.assertEqual(menu['price_cents'],850)
 def test_tenant_and_invalid_edit(self):
  valid={'name':'Outro','category':'Bebidas','price':'8'};self.assertEqual(self.edit(valid,bar=self.bars[1]).status_code,404)
  for invalid in [{**valid,'name':''},{**valid,'price':'0'},{**valid,'price':''}]:self.assertEqual(self.edit(invalid).status_code,400)
  self.assertEqual(self.staff.get(f'/api/bars/{self.bars[0]}/products').json['products'][0]['name'],'Suco')
 def test_pending_product_can_keep_blank_price(self):
  with Session(self.app.extensions['engine']) as db:db.get(Product,self.product).price_cents=0;db.commit()
  self.assertEqual(self.edit({'name':'Novo nome','category':'Nova categoria','price':''}).status_code,200)
  self.assertEqual(self.guest.get('/api/public/'+self.table['token']).json['products'],[])
