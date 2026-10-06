import unittest
from test_finance import FinanceTests
class ChangeTests(unittest.TestCase):
 setUp=FinanceTests.setUp
 tearDown=FinanceTests.tearDown
 login=FinanceTests.login
 post=FinanceTests.post
 payload=FinanceTests.payload
 open=FinanceTests.open
 endpoint=FinanceTests.endpoint
 staffpost=FinanceTests.staffpost
 order=FinanceTests.order
 settle=FinanceTests.settle
 def test_cash_change_and_cash_report(self):
  self.order();r=self.settle(payments=[{'method':'Dinheiro','amount_cents':2000}]);self.assertEqual(r.status_code,201);receipt=r.json['receipt'];self.assertEqual(receipt['change_cents'],800);self.assertEqual(receipt['payments'][0]['amount_cents'],1200)
  cash=self.staff.get(self.endpoint('cash')).json['cash'];self.assertEqual(cash['methods']['Dinheiro'],1200);self.assertEqual(cash['expected_cash_cents'],11200)
 def test_split_payment_with_change(self):
  self.order();r=self.settle(payments=[{'method':'Pix','amount_cents':700},{'method':'Dinheiro','amount_cents':1000}]);self.assertEqual(r.status_code,201);self.assertEqual(r.json['receipt']['change_cents'],500)
  cash=self.staff.get(self.endpoint('cash')).json['cash'];self.assertEqual(cash['methods']['Pix'],700);self.assertEqual(cash['methods']['Dinheiro'],500)
 def test_overpayment_only_in_cash(self):
  self.order();self.assertEqual(self.settle(payments=[{'method':'Pix','amount_cents':2000}]).status_code,400);self.assertEqual(self.settle(payments=[{'method':'Crédito','amount_cents':1300},{'method':'Dinheiro','amount_cents':100}]).status_code,400)
 def test_change_allocated_across_cash_lines(self):
  self.order();r=self.settle(payments=[{'method':'Dinheiro','amount_cents':1500},{'method':'Dinheiro','amount_cents':500}]);self.assertEqual(r.status_code,201);self.assertEqual(sum(p['change_cents'] for p in r.json['receipt']['payments']),800);self.assertEqual(sum(p['amount_cents'] for p in r.json['receipt']['payments']),1200)
