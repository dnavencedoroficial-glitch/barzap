import sys,tempfile,unittest,uuid
from pathlib import Path
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from server import create_app,User,Bar,Order,today

class SecurityAndOrders(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.url='sqlite:///'+str(Path(self.temp.name)/'test.sqlite3').replace('\\','/')
        self.app=create_app({'TESTING':True,'SECRET_KEY':'test-only-key-not-for-production','DATABASE_URL':self.url})
        with Session(self.app.extensions['engine']) as db:
            db.add(User(id='admin',email='admin@example.test',password_hash=generate_password_hash('AdminTest123!'),role='owner'));db.commit()
        self.owner=self.app.test_client();self.owner_csrf=self.login(self.owner,'admin@example.test','AdminTest123!')
        self.bars=[]
        for number in (1,2):
            result=self.post(self.owner,'/api/bars',{'name':'Bar '+str(number),'email':f'bar{number}@example.test','password':'BarTest123!'},self.owner_csrf)
            self.assertEqual(result.status_code,201);self.bars.append(result.json['bar']['id'])
        self.staff=self.app.test_client();self.staff_csrf=self.login(self.staff,'bar1@example.test','BarTest123!')
        self.guest=self.app.test_client();self.guest_csrf=self.guest.get('/api/session').json['csrf']
        self.product=self.post(self.staff,f'/api/bars/{self.bars[0]}/products',{'category':'Bebidas','name':'Suco','price':'6.00'},self.staff_csrf).json['id']
        self.post(self.staff,f'/api/bars/{self.bars[0]}/tables',{'name':'1'},self.staff_csrf)
        self.table=self.staff.get(f'/api/bars/{self.bars[0]}/tables').json['tables'][0]
    def tearDown(self):self.app.extensions['engine'].dispose();self.temp.cleanup()
    def login(self,client,email,password):
        csrf=client.get('/api/session').json['csrf'];result=self.post(client,'/api/login',{'email':email,'password':password},csrf);self.assertEqual(result.status_code,200);return result.json['csrf']
    def post(self,client,path,data,csrf):return client.post(path,json=data,headers={'X-CSRF-Token':csrf})
    def payload(self):return {'name':'Cliente','phone':'11999999999','request_id':str(uuid.uuid4()),'total_cents':0,'items':[{'id':self.product,'quantity':2}]}
    def open(self):self.post(self.staff,f'/api/bars/{self.bars[0]}/cash/open',{'opening_cents':10000},self.staff_csrf)
    def test_login_and_hash(self):
        with Session(self.app.extensions['engine']) as db:
            u=db.scalar(select(User).where(User.email=='bar1@example.test'));self.assertNotIn('BarTest123!',u.password_hash)
        client=self.app.test_client();csrf=client.get('/api/session').json['csrf'];self.assertEqual(self.post(client,'/api/login',{'email':'bar1@example.test','password':'errada'},csrf).status_code,401)
    def test_csrf_and_unauthenticated(self):
        self.assertEqual(self.staff.post(f'/api/bars/{self.bars[0]}/tables/open',json={}).status_code,403)
        self.assertEqual(self.guest.get('/api/bars').status_code,401)
    def test_bar_isolation(self):
        self.assertEqual(self.staff.get(f'/api/bars/{self.bars[1]}/products').status_code,404)
        self.assertEqual(self.post(self.staff,'/api/bars',{'name':'Inválido'},self.staff_csrf).status_code,403)
        self.assertEqual(len(self.staff.get('/api/bars').json['bars']),1)
    def test_public_menu_privacy(self):
        data=self.guest.get('/api/public/'+self.table['token']).json;self.assertNotIn('password',str(data));self.assertNotIn('phone',data);self.assertEqual(data['products'][0]['price_cents'],600)
    def test_closed_table(self):self.assertEqual(self.post(self.guest,'/api/public/'+self.table['token']+'/orders',self.payload(),self.guest_csrf).status_code,409)
    def test_real_shared_order_and_server_price(self):
        self.open();payload=self.payload();result=self.post(self.guest,'/api/public/'+self.table['token']+'/orders',payload,self.guest_csrf);self.assertEqual(result.status_code,201);self.assertEqual(result.json['total_cents'],1200)
        orders=self.staff.get(f'/api/bars/{self.bars[0]}/orders').json['orders'];self.assertEqual(len(orders),1);self.assertEqual(orders[0]['name'],'Cliente')
        duplicate=self.post(self.guest,'/api/public/'+self.table['token']+'/orders',payload,self.guest_csrf);self.assertEqual(duplicate.status_code,200)
        self.assertEqual(len(self.staff.get(f'/api/bars/{self.bars[0]}/orders').json['orders']),1)
    def test_cross_bar_product_rejected(self):
        p=self.post(self.owner,f'/api/bars/{self.bars[1]}/products',{'category':'Outra','name':'Outro','price':'10'},self.owner_csrf).json['id'];self.open();payload=self.payload();payload['items'][0]['id']=p
        self.assertEqual(self.post(self.guest,'/api/public/'+self.table['token']+'/orders',payload,self.guest_csrf).status_code,400)
    def test_five_day_grace_and_block(self):
        with Session(self.app.extensions['engine']) as db:bar=db.get(Bar,self.bars[0]);bar.due=today()-timedelta(days=4);db.commit()
        self.assertEqual(self.staff.get(f'/api/bars/{self.bars[0]}/products').status_code,200)
        with Session(self.app.extensions['engine']) as db:bar=db.get(Bar,self.bars[0]);bar.due=today()-timedelta(days=5);db.commit()
        self.assertEqual(self.staff.get(f'/api/bars/{self.bars[0]}/products').status_code,402)
        self.assertEqual(self.guest.get('/api/public/'+self.table['token']).status_code,402)
        self.assertEqual(self.owner.get(f'/api/bars/{self.bars[0]}/products').status_code,200)
    def test_subscription_renewal(self):
        self.assertEqual(self.post(self.staff,f'/api/bars/{self.bars[0]}/renew',{},self.staff_csrf).status_code,403)
        self.assertEqual(self.post(self.owner,f'/api/bars/{self.bars[0]}/renew',{},self.owner_csrf).status_code,200)
    def test_persistence(self):
        app=create_app({'TESTING':True,'SECRET_KEY':'test-only-key-not-for-production','DATABASE_URL':self.url});client=app.test_client();self.login(client,'bar1@example.test','BarTest123!');self.assertEqual(len(client.get(f'/api/bars/{self.bars[0]}/products').json['products']),1);app.extensions['engine'].dispose()

if __name__=='__main__':unittest.main()

