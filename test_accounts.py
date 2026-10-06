import unittest
from test_server import SecurityAndOrders
class AccountTests(unittest.TestCase):
 setUp=SecurityAndOrders.setUp
 tearDown=SecurityAndOrders.tearDown
 login=SecurityAndOrders.login
 post=SecurityAndOrders.post
 def test_self_change_and_session_revocation(self):
  other=self.app.test_client();self.login(other,'bar1@example.test','BarTest123!')
  path='/api/account/password';new='ChangedLocal123!'
  self.assertEqual(self.post(self.staff,path,{'current_password':'incorrect','new_password':new,'confirm_password':new},self.staff_csrf).status_code,400)
  self.assertEqual(self.post(self.staff,path,{'current_password':'BarTest123!','new_password':new,'confirm_password':new},self.staff_csrf).status_code,200)
  self.assertEqual(other.get('/api/bars').status_code,401);self.assertEqual(self.staff.get('/api/bars').status_code,200)
  self.login(self.app.test_client(),'bar1@example.test',new)
 def test_owner_reset_and_access(self):
  path='/api/bars/'+self.bars[0]+'/accounts';self.assertEqual(self.staff.get(path).status_code,403)
  accounts=self.owner.get(path).json['accounts'];uid=accounts[0]['id'];self.assertNotIn('password',str(accounts));endpoint=path+'/'+uid+'/password';new='TemporaryLocal123!'
  self.assertEqual(self.post(self.staff,endpoint,{'new_password':new,'confirm_password':new},self.staff_csrf).status_code,403)
  self.assertEqual(self.post(self.owner,endpoint.replace(self.bars[0],self.bars[1]),{'new_password':new,'confirm_password':new},self.owner_csrf).status_code,404)
  self.assertEqual(self.post(self.owner,endpoint,{'new_password':new,'confirm_password':new},self.owner_csrf).status_code,200)
  self.assertEqual(self.staff.get('/api/bars').status_code,401);self.login(self.app.test_client(),'bar1@example.test',new)
