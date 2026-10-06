import unittest
from test_server import SecurityAndOrders
from inventory import Stock,StockMovement
from sqlalchemy.orm import Session
from sqlalchemy import select
class InventoryTests(unittest.TestCase):
 setUp=SecurityAndOrders.setUp
 tearDown=SecurityAndOrders.tearDown
 login=SecurityAndOrders.login
 post=SecurityAndOrders.post
 open=SecurityAndOrders.open
 payload=SecurityAndOrders.payload
 def adjust(self,quantity,mode='count',pid=None,bar=None):
  return self.post(self.staff,f'/api/bars/{bar or self.bars[0]}/stock/{pid or self.product}',{'quantity':quantity,'mode':mode,'reason':'Contagem de teste'},self.staff_csrf)
 def inventory(self):return self.staff.get(f'/api/bars/{self.bars[0]}/stock').json
 def test_threshold_initial_and_entries(self):
  self.assertIsNone(self.inventory()['items'][0]['quantity']);self.assertEqual(self.inventory()['suggestions'],[])
  self.assertEqual(self.adjust(1,'entry').status_code,409)
  self.adjust(6);self.assertEqual(self.inventory()['suggestions'],[])
  self.adjust(5);self.assertEqual(self.inventory()['suggestions'][0]['buy_quantity'],1)
  self.adjust(0);self.assertEqual(self.inventory()['suggestions'][0]['buy_quantity'],6)
  self.adjust(8,'entry');self.assertEqual(self.inventory()['items'][0]['quantity'],8);self.assertEqual(self.inventory()['suggestions'],[])
 def test_sales_are_atomic_and_idempotent(self):
  self.adjust(7);self.open();payload=self.payload();path='/api/public/'+self.table['token']+'/orders'
  self.assertEqual(self.post(self.guest,path,payload,self.guest_csrf).status_code,201)
  self.assertEqual(self.inventory()['items'][0]['quantity'],5)
  self.assertEqual(self.post(self.guest,path,payload,self.guest_csrf).status_code,200);self.assertEqual(self.inventory()['items'][0]['quantity'],5)
  self.assertEqual(len([m for m in self.inventory()['movements'] if m['kind']=='Pedido']),1)
  payload=self.payload();payload['items'].append({'id':'invalid','quantity':1});self.assertEqual(self.post(self.guest,path,payload,self.guest_csrf).status_code,400);self.assertEqual(self.inventory()['items'][0]['quantity'],5)
 def test_unknown_and_negative_balance(self):
  self.open();path='/api/public/'+self.table['token']+'/orders';self.post(self.guest,path,self.payload(),self.guest_csrf)
  self.assertIsNone(self.inventory()['items'][0]['quantity'])
  self.adjust(1);payload=self.payload();payload['items']=[{'id':self.product,'quantity':1},{'id':self.product,'quantity':1}];self.post(self.guest,path,payload,self.guest_csrf)
  self.assertEqual(self.inventory()['items'][0]['quantity'],-1);self.assertEqual(self.inventory()['suggestions'][0]['buy_quantity'],7)
 def test_access_validation_and_private_stock(self):
  for quantity in [-1,1.5,True,1000001]:self.assertEqual(self.adjust(quantity).status_code,400)
  self.assertEqual(self.adjust(5,bar=self.bars[1]).status_code,404)
  self.assertEqual(self.guest.get(f'/api/bars/{self.bars[0]}/stock').status_code,401)
  self.adjust(5);menu=self.guest.get('/api/public/'+self.table['token']).json;self.assertNotIn('stock',str(menu));self.assertNotIn('buy_quantity',str(menu))
  with Session(self.app.extensions['engine']) as db:
   self.assertEqual(db.get(Stock,self.product).quantity,5);m=db.scalar(select(StockMovement));self.assertIsNotNone(m.actor)
