import unittest
from unittest.mock import patch
from datetime import timedelta
from sqlalchemy.orm import Session
from server import Bar,today
from test_server import SecurityAndOrders
class TrialTests(unittest.TestCase):
 setUp=SecurityAndOrders.setUp
 tearDown=SecurityAndOrders.tearDown
 login=SecurityAndOrders.login
 post=SecurityAndOrders.post
 def test_trial_login_expiration_and_upgrade(self):
  result=self.post(self.owner,'/api/bars',{'name':'Teste local','email':'triallocal','password':'LocalTest123!','plan':'trial'},self.owner_csrf)
  self.assertEqual(result.status_code,201);bar=result.json['bar'];self.assertTrue(bar['trial']);self.assertEqual(bar['block'],bar['due'])
  client=self.app.test_client();csrf=self.login(client,'triallocal','LocalTest123!');self.assertEqual(client.get('/api/bars/'+bar['id']+'/products').status_code,200)
  with patch('server.today',return_value=today()+timedelta(days=7)):
   self.assertEqual(client.get('/api/bars/'+bar['id']+'/products').status_code,402)
   self.assertEqual(self.owner.get('/api/bars/'+bar['id']+'/products').status_code,200)
  renewed=self.post(self.owner,'/api/bars/'+bar['id']+'/renew',{},self.owner_csrf).json['bar'];self.assertFalse(renewed['trial']);self.assertNotEqual(renewed['block'],renewed['due'])
 def test_paid_subscription_is_unchanged(self):
  bar=self.owner.get('/api/bars').json['bars'][0];self.assertFalse(bar['trial']);self.assertEqual(bar['notice'],'')
