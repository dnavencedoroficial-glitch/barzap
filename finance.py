"""Financial records are additive: no legacy table or order is deleted."""
import uuid
from collections import defaultdict
from datetime import date
from flask import g, jsonify, abort, request
from flask import send_file
from sqlalchemy import select, ForeignKey, UniqueConstraint, String, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash
from server import Base, Bar, Table, Order, User, stamp, text

class Cash(Base):
    __tablename__='cash_sessions'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
    opening_cents:Mapped[int]=mapped_column(Integer)
    opened_at:Mapped[str]=mapped_column(String)
    closed_at:Mapped[str|None]=mapped_column(String,nullable=True)
    closing:Mapped[dict|None]=mapped_column(JSON,nullable=True)

class Waiter(Base):
    __tablename__='waiters'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
    name:Mapped[str]=mapped_column(String(80))

class Assignment(Base):
    __tablename__='table_waiters'
    table_id:Mapped[str]=mapped_column(ForeignKey('tables.id'),primary_key=True)
    waiter_id:Mapped[str]=mapped_column(ForeignKey('waiters.id'))

class Receipt(Base):
    __tablename__='closed_tabs'
    __table_args__=(UniqueConstraint('table_id','session_no'),)
    id:Mapped[str]=mapped_column(String,primary_key=True)
    bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
    cash_id:Mapped[str]=mapped_column(ForeignKey('cash_sessions.id'))
    table_id:Mapped[str]=mapped_column(ForeignKey('tables.id'))
    session_no:Mapped[int]=mapped_column(Integer)
    snapshot:Mapped[dict]=mapped_column(JSON)
    closed_at:Mapped[str]=mapped_column(String)

METHODS=('Dinheiro','Pix','Débito','Crédito')
def amount(value,zero=True):
    if type(value)!=int or value<0 or value>100000000 or (not zero and value==0):
        abort(400,description='Informe um valor válido em centavos.')
    return value

def active_cash(bar_id):
    return g.db.scalar(select(Cash).where(Cash.bar_id==bar_id,Cash.closed_at==None))

def tab_orders(table):
    return list(g.db.scalars(select(Order).where(Order.table_id==table.id,Order.session_no==table.session_no).order_by(Order.created_at)))

def tab_data(table):
    orders=tab_orders(table)
    assignment=g.db.get(Assignment,table.id)
    waiter=g.db.get(Waiter,assignment.waiter_id) if assignment else None
    return {'table_id':table.id,'table':table.name,'session':table.session_no,'open':table.opened,
            'opened_at':table.opened_at,'waiter_id':waiter.id if waiter else None,
            'waiter':waiter.name if waiter else 'Sem garçom','subtotal_cents':sum(o.total_cents for o in orders),
            'orders':[{'id':o.id,'name':o.customer_name,'items':o.items,'note':o.note,'total_cents':o.total_cents} for o in orders]}

def cash_summary(cash):
    by_method={method:0 for method in METHODS}; waiters=defaultdict(int); subtotal=0;service=0
    receipts=list(g.db.scalars(select(Receipt).where(Receipt.cash_id==cash.id)))
    for receipt in receipts:
        snap=receipt.snapshot;subtotal+=snap['subtotal_cents'];service+=snap['service_cents']
        waiters[snap['waiter']]+=snap['service_cents']
        for p in snap['payments']:by_method[p['method']]+=p['amount_cents']
    return {'id':cash.id,'opened_at':cash.opened_at,'closed_at':cash.closed_at,
            'opening_cents':cash.opening_cents,'methods':by_method,'subtotal_cents':subtotal,
            'service_cents':service,'waiters':dict(waiters),'received_cents':sum(by_method.values()),
            'expected_cash_cents':cash.opening_cents+by_method['Dinheiro'],'tabs':len(receipts),'closing':cash.closing}

def register_finance(app,access,require,data):
    def lock(bar_id):
        access(bar_id)
        g.db.scalar(select(Bar).where(Bar.id==bar_id).with_for_update())

    @app.get('/api/bars/<bar_id>/waiters')
    def waiters(bar_id):
        access(bar_id)
        return jsonify(waiters=[{'id':w.id,'name':w.name} for w in g.db.scalars(select(Waiter).where(Waiter.bar_id==bar_id).order_by(Waiter.name))])

    @app.post('/api/bars/<bar_id>/tables/batch')
    def batch_tables(bar_id):
        import secrets
        lock(bar_id);now=stamp();opened=active_cash(bar_id) is not None
        existing={t.name for t in g.db.scalars(select(Table).where(Table.bar_id==bar_id))}
        for number in range(1,51):
            if str(number) not in existing:
                g.db.add(Table(id=str(uuid.uuid4()),bar_id=bar_id,name=str(number),token=secrets.token_urlsafe(24),opened=opened,session_no=1 if opened else 0,opened_at=now if opened else None))
        g.db.commit();return jsonify(ok=True)

    @app.get('/api/bars/<bar_id>/qr.pdf')
    def qr_pdf(bar_id):
        access(bar_id)
        identifiers=request.args.getlist('table')
        if not 1<=len(identifiers)<=100:abort(400,description='Selecione entre 1 e 100 mesas.')
        tables=list(g.db.scalars(select(Table).where(Table.bar_id==bar_id,Table.id.in_(identifiers)).order_by(Table.name)))
        if len(tables)!=len(set(identifiers)):abort(404)
        tables.sort(key=lambda t:(not t.name.isdigit(),int(t.name) if t.name.isdigit() else t.name))
        from io import BytesIO
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics import renderPDF
        output=BytesIO();pdf=Canvas(output,pagesize=A4);width,height=A4
        bar=g.db.get(Bar,bar_id)
        for index,t in enumerate(tables):
            if index and index%6==0:pdf.showPage()
            position=index%6;x=30+(position%2)*270;y=height-35-(position//2)*260
            pdf.roundRect(x,y-242,250,230,10)
            pdf.setFont('Helvetica-Bold',16);pdf.drawCentredString(x+125,y-38,bar.name[:28])
            pdf.setFont('Helvetica-Bold',19);pdf.drawCentredString(x+125,y-64,'Mesa '+t.name[:20])
            qr=QrCodeWidget(request.host_url.rstrip('/')+'/?mesa='+t.token)
            bounds=qr.getBounds();size=150
            drawing=Drawing(size,size,transform=[size/(bounds[2]-bounds[0]),0,0,size/(bounds[3]-bounds[1]),0,0]);drawing.add(qr)
            renderPDF.draw(drawing,pdf,x+50,y-215)
            pdf.setFont('Helvetica',10);pdf.drawCentredString(x+125,y-230,'Aponte a câmera e faça seu pedido')
        pdf.save();output.seek(0)
        return send_file(output,mimetype='application/pdf',as_attachment=True,download_name='BarZap-mesas.pdf')

    @app.post('/api/bars/<bar_id>/waiters')
    def add_waiter(bar_id):
        lock(bar_id);w=Waiter(id=str(uuid.uuid4()),bar_id=bar_id,name=text(data(),'name',80))
        g.db.add(w);g.db.commit();return jsonify(id=w.id),201

    @app.post('/api/bars/<bar_id>/tables/<table_id>/waiter')
    def assign(bar_id,table_id):
        lock(bar_id);t=g.db.get(Table,table_id);w=g.db.get(Waiter,text(data(),'waiter_id'))
        if not t or t.bar_id!=bar_id or not w or w.bar_id!=bar_id:abort(404)
        a=g.db.get(Assignment,t.id)
        if a:a.waiter_id=w.id
        else:g.db.add(Assignment(table_id=t.id,waiter_id=w.id))
        g.db.commit();return jsonify(ok=True)

    @app.get('/api/bars/<bar_id>/cash')
    def cash_state(bar_id):
        access(bar_id);cash=active_cash(bar_id)
        return jsonify(cash=cash_summary(cash) if cash else None)

    @app.post('/api/bars/<bar_id>/cash/open')
    def cash_open(bar_id):
        lock(bar_id)
        if active_cash(bar_id):abort(409,description='O caixa já está aberto.')
        cash=Cash(id=str(uuid.uuid4()),bar_id=bar_id,opening_cents=amount(data().get('opening_cents')),opened_at=stamp())
        g.db.add(cash)
        for t in g.db.scalars(select(Table).where(Table.bar_id==bar_id,Table.opened==False)):
            t.opened=True;t.session_no+=1;t.opened_at=cash.opened_at
        g.db.commit();return jsonify(cash=cash_summary(cash)),201

    @app.get('/api/bars/<bar_id>/tabs')
    def tabs(bar_id):
        access(bar_id)
        return jsonify(tabs=[tab_data(t) for t in g.db.scalars(select(Table).where(Table.bar_id==bar_id,Table.opened==True).order_by(Table.name))])

    @app.post('/api/bars/<bar_id>/tables/<table_id>/open')
    def table_open(bar_id,table_id):
        lock(bar_id)
        if not active_cash(bar_id):abort(409,description='Abra o caixa primeiro.')
        t=g.db.get(Table,table_id)
        if not t or t.bar_id!=bar_id:abort(404)
        if not t.opened:t.opened=True;t.session_no+=1;t.opened_at=stamp()
        g.db.commit();return jsonify(ok=True)

    @app.post('/api/bars/<bar_id>/tables/<table_id>/settle')
    def settle(bar_id,table_id):
        lock(bar_id);t=g.db.scalar(select(Table).where(Table.id==table_id).with_for_update())
        if not t or t.bar_id!=bar_id:abort(404)
        cash=active_cash(bar_id)
        if not cash:abort(409,description='Abra o caixa antes de receber.')
        if not t.opened:abort(409,description='Esta comanda já foi fechada.')
        d=data()
        if d.get('session')!=t.session_no:abort(409,description='Comanda alterada. Atualize a tela.')
        snap=tab_data(t)
        if type(d.get('service'))!=bool:abort(400)
        snap['service_cents']=(snap['subtotal_cents']+5)//10 if d['service'] else 0
        if snap['service_cents'] and not snap['waiter_id']:abort(400,description='Selecione o garçom antes de cobrar os 10%.')
        snap['total_cents']=snap['subtotal_cents']+snap['service_cents']
        payments=d.get('payments')
        if not isinstance(payments,list) or len(payments)>100:abort(400)
        clean=[]
        for p in payments:
            if not isinstance(p,dict) or p.get('method') not in METHODS:abort(400)
            clean.append({'method':p['method'],'amount_cents':amount(p.get('amount_cents'),False),'person':str(p.get('person',''))[:80]})
        if sum(p['amount_cents'] for p in clean)!=snap['total_cents']:abort(400,description='Os pagamentos precisam somar exatamente o total da comanda.')
        snap.update(payments=clean,bar=g.db.get(Bar,bar_id).name,closed_at=stamp())
        receipt=Receipt(id=str(uuid.uuid4()),bar_id=bar_id,cash_id=cash.id,table_id=t.id,session_no=t.session_no,snapshot=snap,closed_at=snap['closed_at'])
        # Keep the table available for the next customer in a fresh session.
        # The receipt retains the old session and its complete snapshot.
        g.db.add(receipt);t.opened=True;t.session_no+=1;t.opened_at=stamp();g.db.commit()
        return jsonify(receipt={'id':receipt.id,**snap}),201

    @app.post('/api/bars/<bar_id>/cash/close')
    def cash_close(bar_id):
        lock(bar_id);cash=active_cash(bar_id)
        if not cash:abort(409,description='Não há caixa aberto.')
        list(g.db.scalars(select(Table).where(Table.bar_id==bar_id).with_for_update()))
        d=data();pending=[tab_data(t) for t in g.db.scalars(select(Table).where(Table.bar_id==bar_id,Table.opened==True))]
        pending=[t for t in pending if t['orders']]
        if pending:
            password=d.get('owner_password','')
            if not isinstance(password,str):abort(400)
            user=require()
            candidates=list(g.db.scalars(select(User).where(User.role=='owner')))
            candidates+=list(g.db.scalars(select(User).where(User.role=='bar',User.bar_id==bar_id)))
            # Throttling shared with the login limiter in this single-worker version.
            attempts=app.extensions['cash_auth_attempts'];import time
            key=(request.remote_addr,bar_id);recent=[at for at in attempts.get(key,[]) if time.monotonic()-at<300]
            if len(recent)>=5:abort(429,description='Aguarde cinco minutos para tentar a senha novamente.')
            approver=next((u for u in candidates if password and check_password_hash(u.password_hash,password)),None)
            if not approver:
                attempts[key]=recent+[time.monotonic()];abort(403,description='Há mesas pendentes. Informe a senha do dono do bar ou administrador.')
            attempts.pop(key,None)
            reason=text(d,'reason',300)
        else:reason='';user=require();approver=user
        summary=cash_summary(cash);counted=amount(d.get('counted_cash_cents'))
        cash.closing={'counted_cash_cents':counted,'difference_cents':counted-summary['expected_cash_cents'],
                      'pending':pending,'reason':reason,'authorized_by':approver.email,'performed_by':user.email}
        cash.closed_at=stamp()
        # Empty tables can close without an unpaid tab; pending tabs remain intact.
        for t in g.db.scalars(select(Table).where(Table.bar_id==bar_id,Table.opened==True)):
            if not tab_orders(t):t.opened=False
        g.db.commit();return jsonify(cash=cash_summary(cash))

    @app.get('/api/bars/<bar_id>/reports')
    def reports(bar_id):
        access(bar_id)
        start=request.args.get('start','');end=request.args.get('end','')
        try:
            if start:date.fromisoformat(start)
            if end:date.fromisoformat(end)
        except ValueError:abort(400,description='Data inválida.')
        from zoneinfo import ZoneInfo
        from datetime import datetime
        def matches(value):
            day=datetime.fromisoformat(value).astimezone(ZoneInfo('America/Sao_Paulo')).date().isoformat()
            return (not start or day>=start) and (not end or day<=end)
        return jsonify(receipts=[{'id':r.id,**r.snapshot} for r in g.db.scalars(select(Receipt).where(Receipt.bar_id==bar_id).order_by(Receipt.closed_at.desc())) if matches(r.closed_at)],
                       cash=[cash_summary(c) for c in g.db.scalars(select(Cash).where(Cash.bar_id==bar_id,Cash.closed_at!=None).order_by(Cash.closed_at.desc())) if matches(c.closed_at)])

    app.extensions['cash_auth_attempts']={}
