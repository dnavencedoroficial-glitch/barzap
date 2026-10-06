"""Per-bar stock counts, purchase suggestions and audited movements."""
import uuid
from flask import g,jsonify,abort,session
from sqlalchemy import select,ForeignKey,String,Integer,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from server import Base,Bar,Product,stamp,text
class Stock(Base):
 __tablename__='product_stock'
 product_id:Mapped[str]=mapped_column(ForeignKey('products.id'),primary_key=True)
 quantity:Mapped[int]=mapped_column(Integer)
class StockMovement(Base):
 __tablename__='stock_movements'
 __table_args__=(UniqueConstraint('order_id','product_id'),)
 id:Mapped[str]=mapped_column(String,primary_key=True)
 bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
 product_id:Mapped[str]=mapped_column(ForeignKey('products.id'))
 order_id:Mapped[str|None]=mapped_column(ForeignKey('orders.id'),nullable=True)
 change:Mapped[int]=mapped_column(Integer)
 balance:Mapped[int]=mapped_column(Integer)
 kind:Mapped[str]=mapped_column(String(30))
 reason:Mapped[str]=mapped_column(String(200))
 actor:Mapped[str|None]=mapped_column(String,nullable=True)
 created_at:Mapped[str]=mapped_column(String)
def lock_bar(db,bar_id):db.scalar(select(Bar).where(Bar.id==bar_id).with_for_update())
def sale(db,order):
 quantities={}
 for line in order.items:quantities[line['id']]=quantities.get(line['id'],0)+line['quantity']
 for pid,quantity in quantities.items():
  stock=db.get(Stock,pid)
  if stock is None:continue
  stock.quantity-=quantity
  db.add(StockMovement(id=str(uuid.uuid4()),bar_id=order.bar_id,product_id=pid,order_id=order.id,change=-quantity,balance=stock.quantity,kind='Pedido',reason='Baixa automática do pedido',actor=None,created_at=stamp()))
def register_inventory(app,access,data):
 @app.get('/api/bars/<bar_id>/stock')
 def inventory(bar_id):
  access(bar_id);items=[];suggestions=[]
  for p in g.db.scalars(select(Product).where(Product.bar_id==bar_id,Product.enabled==True).order_by(Product.category,Product.name)):
   stock=g.db.get(Stock,p.id);quantity=stock.quantity if stock else None
   item={'id':p.id,'name':p.name,'category':p.category,'quantity':quantity,'buy_quantity':max(0,6-quantity) if quantity is not None else None}
   items.append(item)
   if quantity is not None and quantity<6:suggestions.append(item)
  movements=[]
  for m in g.db.scalars(select(StockMovement).where(StockMovement.bar_id==bar_id).order_by(StockMovement.created_at.desc()).limit(100)):
   p=g.db.get(Product,m.product_id)
   movements.append({'name':p.name,'change':m.change,'balance':m.balance,'kind':m.kind,'reason':m.reason,'created_at':m.created_at})
  return jsonify(items=items,suggestions=suggestions,movements=movements)
 @app.post('/api/bars/<bar_id>/stock/<product_id>')
 def change_stock(bar_id,product_id):
  access(bar_id);lock_bar(g.db,bar_id);p=g.db.get(Product,product_id)
  if not p or p.bar_id!=bar_id or not p.enabled:abort(404)
  d=data();mode=d.get('mode');quantity=d.get('quantity')
  if mode not in ('count','entry') or type(quantity)!=int or quantity<0 or quantity>1000000 or (mode=='entry' and quantity==0):abort(400,description='Informe uma quantidade inteira válida.')
  reason=text(d,'reason',200);stock=g.db.get(Stock,product_id)
  if stock is None:
   if mode=='entry':abort(409,description='Informe primeiro a quantidade atual do produto.')
   stock=Stock(product_id=product_id,quantity=0);g.db.add(stock)
  balance=stock.quantity+quantity if mode=='entry' else quantity
  if balance>1000000:abort(400,description='Quantidade acima do limite.')
  delta=balance-stock.quantity;stock.quantity=balance
  g.db.add(StockMovement(id=str(uuid.uuid4()),bar_id=bar_id,product_id=product_id,order_id=None,change=delta,balance=balance,kind='Entrada' if mode=='entry' else 'Contagem',reason=reason,actor=session.get('user'),created_at=stamp()))
  g.db.commit();return jsonify(quantity=balance,buy_quantity=max(0,6-balance))
