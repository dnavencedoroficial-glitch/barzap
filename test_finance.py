import unittest
import test_server

class FinanceTests(unittest.TestCase):
    setUp=test_server.SecurityAndOrders.setUp
    tearDown=test_server.SecurityAndOrders.tearDown
    login=test_server.SecurityAndOrders.login
    post=test_server.SecurityAndOrders.post
    payload=test_server.SecurityAndOrders.payload
    open=test_server.SecurityAndOrders.open
    def endpoint(self,path):return f'/api/bars/{self.bars[0]}/'+path
    def staffpost(self,path,data):return self.post(self.staff,self.endpoint(path),data,self.staff_csrf)
    def order(self):
        self.open()
        self.assertEqual(self.post(self.guest,'/api/public/'+self.table['token']+'/orders',self.payload(),self.guest_csrf).status_code,201)
    def settle(self,service=False,payments=None):
        tab=self.staff.get(self.endpoint('tabs')).json['tabs'][0]
        return self.staffpost('tables/'+self.table['id']+'/settle',{'session':tab['session'],'service':service,'payments':payments or [{'method':'Pix','amount_cents':1200}]})
    def test_opening_tables_and_duplicate_cash(self):
        self.open();self.assertTrue(self.staff.get(self.endpoint('tabs')).json['tabs'][0]['open'])
        self.assertEqual(self.staffpost('cash/open',{'opening_cents':1000}).status_code,409)
    def test_split_payments_and_waiter_fee(self):
        self.order();w=self.staffpost('waiters',{'name':'Ana'}).json['id']
        self.assertEqual(self.staffpost('tables/'+self.table['id']+'/waiter',{'waiter_id':w}).status_code,200)
        result=self.settle(True,[{'method':'Pix','amount_cents':600},{'method':'Dinheiro','amount_cents':720}])
        self.assertEqual(result.status_code,201);self.assertEqual(result.json['receipt']['service_cents'],120)
        cash=self.staff.get(self.endpoint('cash')).json['cash']
        self.assertEqual(cash['methods']['Pix'],600);self.assertEqual(cash['expected_cash_cents'],10720)
        self.assertEqual(cash['waiters']['Ana'],120)
        self.assertEqual(self.staff.get(self.endpoint('orders')).json['orders'],[])
        self.assertEqual(self.staff.get(self.endpoint('tabs')).json['tabs'],[])
        self.assertEqual(len(self.staff.get(self.endpoint('reports')).json['receipts']),1)
    def test_underpayment_and_repeated_close(self):
        self.order();self.assertEqual(self.settle(False,[{'method':'Crédito','amount_cents':1199}]).status_code,400)
        self.assertEqual(self.settle().status_code,201)
        self.assertEqual(self.staffpost('tables/'+self.table['id']+'/settle',{'session':1,'service':False,'payments':[]}).status_code,409)
    def test_pending_close_requires_password_and_reason(self):
        self.order();self.assertEqual(self.staffpost('cash/close',{'counted_cash_cents':10000}).status_code,403)
        self.assertEqual(self.staffpost('cash/close',{'counted_cash_cents':10000,'owner_password':'errada','reason':'Teste'}).status_code,403)
        result=self.staffpost('cash/close',{'counted_cash_cents':10000,'owner_password':'BarTest123!','reason':'Mesa pendente autorizada'})
        self.assertEqual(result.status_code,200);self.assertEqual(len(result.json['cash']['closing']['pending']),1)
        self.assertEqual(result.json['cash']['received_cents'],0)
        self.assertEqual(self.post(self.guest,'/api/public/'+self.table['token']+'/orders',self.payload(),self.guest_csrf).status_code,409)
        self.open();self.assertEqual(len(self.staff.get(self.endpoint('orders')).json['orders']),1)
    def test_cash_difference_and_receipt_snapshot(self):
        self.order();self.assertEqual(self.settle().status_code,201)
        result=self.staffpost('cash/close',{'counted_cash_cents':9900})
        self.assertEqual(result.status_code,200);self.assertEqual(result.json['cash']['closing']['difference_cents'],-100)
        self.staff.delete(self.endpoint('products/'+self.product),headers={'X-CSRF-Token':self.staff_csrf})
        receipt=self.staff.get(self.endpoint('reports')).json['receipts'][0]
        self.assertEqual(receipt['orders'][0]['items'][0]['name'],'Suco')
    def test_foreign_finance_access(self):
        self.assertEqual(self.staff.get(f'/api/bars/{self.bars[1]}/reports').status_code,404)
        self.assertEqual(self.post(self.staff,f'/api/bars/{self.bars[1]}/cash/open',{'opening_cents':0},self.staff_csrf).status_code,404)
    def test_old_session_cannot_settle_reopened_table(self):
        self.order();self.assertEqual(self.settle().status_code,201)
        self.staffpost('tables/'+self.table['id']+'/open',{})
        self.assertEqual(self.staffpost('tables/'+self.table['id']+'/settle',{'session':1,'service':False,'payments':[]}).status_code,409)
    def test_service_requires_waiter_and_defaults_optional(self):
        self.order();self.assertEqual(self.settle(True,[{'method':'Pix','amount_cents':1320}]).status_code,400)
        result=self.settle(False);self.assertEqual(result.json['receipt']['service_cents'],0)
    def test_qr_batch_preserves_existing_tables(self):
        self.assertEqual(self.staffpost('tables/batch',{}).status_code,200)
        self.assertEqual(self.staffpost('tables/batch',{}).status_code,200)
        tables=self.staff.get(self.endpoint('tables')).json['tables']
        self.assertEqual(len(tables),50)
        self.assertEqual(next(t for t in tables if t['name']=='1')['token'],self.table['token'])
    def test_selected_qr_pdf_and_privacy(self):
        from io import BytesIO
        from pypdf import PdfReader
        result=self.staff.get(self.endpoint('qr.pdf')+'?table='+self.table['id'])
        self.assertEqual(result.status_code,200)
        self.assertEqual(len(PdfReader(BytesIO(result.data)).pages),1)
        self.assertEqual(self.guest.get(self.endpoint('qr.pdf')+'?table='+self.table['id']).status_code,401)

if __name__=='__main__':unittest.main()

