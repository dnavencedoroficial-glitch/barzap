import os,secrets,hmac,uuid,re,time
from menu_images import product_data,FILES,image_for
from auto_images import find_photo,uploaded_photo
import starter_catalog
from datetime import datetime,date,timedelta,timezone
from decimal import Decimal,InvalidOperation
from functools import wraps
from zoneinfo import ZoneInfo
from flask import Flask,request,session,jsonify,abort,g,send_from_directory,Response
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.exceptions import HTTPException
class SubscriptionRequired(HTTPException):
    code=402
    description="Assinatura vencida."
from sqlalchemy import create_engine,select,event,ForeignKey,UniqueConstraint
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column,Session
from sqlalchemy import String,Integer,Boolean,Date,JSON,LargeBinary

class Base(DeclarativeBase):pass
class Bar(Base):
    __tablename__='bars'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    name:Mapped[str]=mapped_column(String(100))
    start:Mapped[date]=mapped_column(Date)
    due:Mapped[date]=mapped_column(Date)
    release:Mapped[int]=mapped_column(Integer,unique=True)
class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    email:Mapped[str]=mapped_column(String(200),unique=True)
    password_hash:Mapped[str]=mapped_column(String(300))
    role:Mapped[str]=mapped_column(String(20))
    bar_id:Mapped[str|None]=mapped_column(ForeignKey('bars.id'),nullable=True)
class Table(Base):
    __tablename__='tables'
    __table_args__=(UniqueConstraint('bar_id','name'),)
    id:Mapped[str]=mapped_column(String,primary_key=True)
    bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
    name:Mapped[str]=mapped_column(String(60))
    token:Mapped[str]=mapped_column(String,unique=True)
    opened:Mapped[bool]=mapped_column(Boolean,default=False)
    session_no:Mapped[int]=mapped_column(Integer,default=0)
    opened_at:Mapped[str|None]=mapped_column(String,nullable=True)
class Product(Base):
    __tablename__='products'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
    category:Mapped[str]=mapped_column(String(60))
    name:Mapped[str]=mapped_column(String(100))
    price_cents:Mapped[int]=mapped_column(Integer)
    enabled:Mapped[bool]=mapped_column(Boolean,default=True)
class ProductPreset(Base):
    __tablename__='product_presets'
    __table_args__=(UniqueConstraint('bar_id','preset_key'),)
    id:Mapped[str]=mapped_column(String,primary_key=True)
    bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
    preset_key:Mapped[str]=mapped_column(String(80))
    product_id:Mapped[str]=mapped_column(ForeignKey('products.id'))

class ProductPhoto(Base):
    __tablename__='product_photos'
    product_id:Mapped[str]=mapped_column(ForeignKey('products.id'),primary_key=True)
    token:Mapped[str]=mapped_column(String)
    content:Mapped[bytes]=mapped_column(LargeBinary)
    details:Mapped[dict]=mapped_column(JSON)

class Order(Base):
    __tablename__='orders'
    __table_args__=(UniqueConstraint('bar_id','request_id'),)
    id:Mapped[str]=mapped_column(String,primary_key=True)
    bar_id:Mapped[str]=mapped_column(ForeignKey('bars.id'))
    table_id:Mapped[str]=mapped_column(ForeignKey('tables.id'))
    session_no:Mapped[int]=mapped_column(Integer)
    customer_name:Mapped[str]=mapped_column(String(80))
    phone:Mapped[str]=mapped_column(String(20))
    items:Mapped[list]=mapped_column(JSON)
    total_cents:Mapped[int]=mapped_column(Integer)
    note:Mapped[str]=mapped_column(String(500))
    status:Mapped[str]=mapped_column(String(20),default='Recebido')
    created_at:Mapped[str]=mapped_column(String)
    request_id:Mapped[str]=mapped_column(String(80))

def seed_catalog(db,bar_id):
    db.scalar(select(Bar).where(Bar.id==bar_id).with_for_update())
    existing=list(db.scalars(select(Product).where(Product.bar_id==bar_id)))
    imported=set(db.scalars(select(ProductPreset.preset_key).where(ProductPreset.bar_id==bar_id)))
    for preset in starter_catalog.CATALOG:
        if preset['key'] in imported:
            link=db.scalar(select(ProductPreset).where(ProductPreset.bar_id==bar_id,ProductPreset.preset_key==preset['key']))
            seeded=db.get(Product,link.product_id)
            match=next((p for p in existing if p.id!=seeded.id and p.price_cents>0 and starter_catalog.matches(p,preset)),None)
            if seeded.enabled and seeded.price_cents==0 and match is not None:
                seeded.enabled=False;link.product_id=match.id
            continue
        product=next((p for p in existing if starter_catalog.matches(p,preset)),None)
        if product is None:
            product=Product(id=str(uuid.uuid4()),bar_id=bar_id,name=preset['name'],category=preset['category'],price_cents=0,enabled=True)
            db.add(product);db.flush();existing.append(product)
        db.add(ProductPreset(id=str(uuid.uuid4()),bar_id=bar_id,preset_key=preset['key'],product_id=product.id))
    db.flush()

def today():return datetime.now(ZoneInfo('America/Sao_Paulo')).date()
def stamp():return datetime.now(timezone.utc).isoformat()
def text(data,key,limit=100):
    value=data.get(key)
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:abort(400,description='Campo inválido: '+key)
    return value.strip()
def cents(value):
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number<=0 or number>100000 or number.as_tuple().exponent < -2:raise ValueError()
        return int(number*100)
    except (InvalidOperation,ValueError,TypeError):abort(400,description='Valor inválido')
def subscription(bar):
    block=bar.due+timedelta(days=5)
    return {'start':bar.start.isoformat(),'due':bar.due.isoformat(),'block':block.isoformat(),'status':'Bloqueada' if today()>=block else 'Em tolerância' if today()>=bar.due else 'Ativa'}
def bar_data(bar):return {'id':bar.id,'name':bar.name,'release':bar.release,**subscription(bar)}

def create_app(config=None):
    from finance import register_finance,active_cash,Assignment,Waiter
    from inventory import register_inventory,lock_bar,sale
    app=Flask(__name__,static_folder=None)
    app.aborter.mapping[402]=SubscriptionRequired
    secret=os.environ.get('SECRET_KEY')
    if not secret and not config:raise RuntimeError('Configure SECRET_KEY com uma chave aleatória antes de iniciar.')
    if os.environ.get('APP_ENV')=='production' and (not secret or len(secret)<32 or not os.environ.get('DATABASE_URL')) and not config:raise RuntimeError('Produção exige SECRET_KEY forte e DATABASE_URL do PostgreSQL.')
    app.config.update(SECRET_KEY=secret,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('APP_ENV')=='production',PERMANENT_SESSION_LIFETIME=timedelta(hours=12),MAX_CONTENT_LENGTH=3000000)
    if config:app.config.update(config)
    hosts=os.environ.get('TRUSTED_HOSTS','')
    if hosts:app.config['TRUSTED_HOSTS']=[host.strip() for host in hosts.split(',') if host.strip()]
    url=app.config.get('DATABASE_URL') or os.environ.get('DATABASE_URL','sqlite:///barzap.sqlite3')
    if os.environ.get('APP_ENV')=='production' and url.startswith('sqlite:'):raise RuntimeError('Use PostgreSQL para esta configuração de produção.')
    if url.startswith('postgres://'):url='postgresql+psycopg://'+url[len('postgres://'):]
    if url.startswith('postgresql://'):url='postgresql+psycopg://'+url[len('postgresql://'):]
    engine=create_engine(url,pool_pre_ping=True)
    if url.startswith('sqlite:'):
        @event.listens_for(engine,'connect')
        def sqlite_fk(dbapi,record):dbapi.execute('PRAGMA foreign_keys=ON')
    with engine.begin() as schema_connection:
        if engine.dialect.name=='postgresql':schema_connection.exec_driver_sql('SELECT pg_advisory_xact_lock(287419550)')
        Base.metadata.create_all(schema_connection)
    app.extensions['engine']=engine
    catalog_enabled=app.config.get('STARTER_CATALOG',not app.config.get('TESTING',False))
    if catalog_enabled:
        with Session(engine) as catalog_db:
            for catalog_bar in catalog_db.scalars(select(Bar).order_by(Bar.id)):
                seed_catalog(catalog_db,catalog_bar.id)
            catalog_db.commit()
    attempts={}
    @app.before_request
    def before():
        g.db=Session(engine)
        if request.method in ('POST','PUT','PATCH','DELETE'):
            value=request.headers.get('X-CSRF-Token','')
            if not value or not hmac.compare_digest(value,session.get('csrf','')):abort(403,description='Atualize a página antes de enviar.')
    @app.teardown_request
    def after(error):
        if hasattr(g,'db'):g.db.close()
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        if request.path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        return response
    @app.errorhandler(Exception)
    def error(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc,HTTPException):return jsonify(error=exc.description),exc.code
        g.db.rollback();app.logger.exception('Falha na requisição');return jsonify(error='Não foi possível concluir a operação.'),500
    def require(owner=False):
        user=g.db.get(User,session.get('user')) if session.get('user') else None
        if not user:abort(401,description='Faça login.')
        if owner and user.role!='owner':abort(403,description='Acesso exclusivo ao administrador.')
        return user
    def access(bar_id,allow_expired=False):
        user=require();bar=g.db.get(Bar,bar_id)
        if not bar or (user.role!='owner' and user.bar_id!=bar_id):abort(404)
        if not allow_expired and user.role!='owner' and subscription(bar)['status']=='Bloqueada':abort(402,description='Assinatura vencida após 5 dias de tolerância.')
        return bar
    def data():
        result=request.get_json(silent=True)
        if not isinstance(result,dict):abort(400)
        return result
    def product_view(product):
        result=product_data(product)
        preset=g.db.scalar(select(ProductPreset).where(ProductPreset.product_id==product.id))
        if preset:result['image']=starter_catalog.metadata(starter_catalog.BY_KEY[preset.preset_key])
        result['price_pending']=product.price_cents<=0
        photo=g.db.get(ProductPhoto,product.id)
        if photo:result['image']={**photo.details,'url':'/media/products/'+product.id+'/'+photo.token+'.jpg'}
        return result
    def save_photo(product,value=None):
        if value:
            try:content=uploaded_photo(value)
            except ValueError as exc:abort(400,description=str(exc))
            details={'alt':product.name,'credit':'Foto fornecida pelo bar','source':None,'license':None,'kind':'food','origin':'bar'}
        elif image_for(product):return 'catalog'
        else:
            found=(app.config.get('IMAGE_LOOKUP') or find_photo)(product.name,product.category) if not app.config.get('TESTING') or app.config.get('IMAGE_LOOKUP') else None
            if not found:return 'missing'
            content,details=found
        photo=g.db.get(ProductPhoto,product.id)
        if not photo:photo=ProductPhoto(product_id=product.id);g.db.add(photo)
        photo.token=secrets.token_urlsafe(24);photo.content=content;photo.details=details;g.db.commit()
        return 'found'
    register_finance(app,access,require,data)
    register_inventory(app,access,data)
    @app.get('/')
    def home():return send_from_directory(app.root_path,'index.html')
    @app.get('/static/<name>')
    def public_asset(name):
        if name not in ('app.js','finance.js','inventory.js','style.css') and name not in FILES and name not in starter_catalog.STATIC_FILES:abort(404)
        return send_from_directory(app.root_path,name)
    @app.get('/health')
    def health():return jsonify(status='ok')
    @app.get('/api/session')
    def identity():
        session.setdefault('csrf',secrets.token_urlsafe(32))
        u=g.db.get(User,session.get('user')) if session.get('user') else None
        return jsonify(csrf=session['csrf'],user={'email':u.email,'role':u.role,'bar_id':u.bar_id} if u else None)
    @app.post('/api/login')
    def login():
        d=data();email=text(d,'email',200).lower();password=text(d,'password',200);key=(request.remote_addr,email);recent=[t for t in attempts.get(key,[]) if time.monotonic()-t<300]
        if len(recent)>=10:abort(429,description='Aguarde alguns minutos para tentar novamente.')
        u=g.db.scalar(select(User).where(User.email==email))
        if not u or not check_password_hash(u.password_hash,password):attempts[key]=recent+[time.monotonic()];abort(401,description='E-mail ou senha incorretos.')
        attempts.pop(key,None);session.clear();session.update(user=u.id,csrf=secrets.token_urlsafe(32));session.permanent=True
        return jsonify(csrf=session['csrf'],user={'email':u.email,'role':u.role,'bar_id':u.bar_id})
    @app.post('/api/logout')
    def logout():session.clear();return jsonify(ok=True)
    @app.get('/api/bars')
    def bars():
        u=require();q=select(Bar).order_by(Bar.release)
        if u.role!='owner':q=q.where(Bar.id==u.bar_id)
        return jsonify(bars=[bar_data(b) for b in g.db.scalars(q)])
    @app.post('/api/bars')
    def new_bar():
        require(True);d=data();name=text(d,'name');email=text(d,'email',200).lower();password=text(d,'password',200)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(password)<8:abort(400,description='Informe e-mail válido e senha com ao menos 8 caracteres.')
        if g.db.scalar(select(User).where(User.email==email)):abort(409,description='E-mail já cadastrado.')
        last=g.db.scalar(select(Bar.release).order_by(Bar.release.desc()).limit(1)) or 0
        bar=Bar(id=str(uuid.uuid4()),name=name,start=today(),due=today()+timedelta(days=30),release=last+1);g.db.add(bar);g.db.flush();g.db.add(User(id=str(uuid.uuid4()),email=email,password_hash=generate_password_hash(password),role='bar',bar_id=bar.id));
        if catalog_enabled:seed_catalog(g.db,bar.id)
        g.db.commit();return jsonify(bar=bar_data(bar)),201
    @app.post('/api/bars/<bar_id>/renew')
    def renew(bar_id):
        require(True);bar=access(bar_id,True);bar.start=max(today(),bar.due);bar.due=bar.start+timedelta(days=30);g.db.commit();return jsonify(bar=bar_data(bar))
    @app.get('/api/bars/<bar_id>/products')
    def products(bar_id):
        access(bar_id);return jsonify(products=[product_view(p) for p in g.db.scalars(select(Product).where(Product.bar_id==bar_id,Product.enabled==True))])
    @app.post('/api/bars/<bar_id>/products')
    def new_product(bar_id):
        access(bar_id);d=data();p=Product(id=str(uuid.uuid4()),bar_id=bar_id,category=text(d,'category',60),name=text(d,'name'),price_cents=cents(d.get('price')));g.db.add(p)
        # Validate an optional supplied photo before committing the product.
        if d.get('photo'):
            try:uploaded_photo(d['photo'])
            except ValueError as exc:abort(400,description=str(exc))
        g.db.commit();state=save_photo(p,d.get('photo'));return jsonify(id=p.id,image_state=state),201
    @app.patch('/api/bars/<bar_id>/products/<product_id>')
    def edit_product(bar_id,product_id):
        access(bar_id);product=g.db.get(Product,product_id)
        if not product or product.bar_id!=bar_id or not product.enabled:abort(404)
        d=data();name=text(d,'name');category=text(d,'category',60)
        price=d.get('price')
        if price in (None,''):
            if product.price_cents>0:abort(400,description='Informe o preço do produto.')
            value=0
        else:value=cents(price)
        product.name=name;product.category=category;product.price_cents=value;g.db.commit()
        return jsonify(product=product_view(product))
    @app.post('/api/bars/<bar_id>/products/<product_id>/price')
    def product_price(bar_id,product_id):
        access(bar_id);product=g.db.get(Product,product_id)
        if not product or product.bar_id!=bar_id or not product.enabled:abort(404)
        product.price_cents=cents(data().get('price'));g.db.commit()
        return jsonify(product=product_view(product))
    @app.post('/api/bars/<bar_id>/products/<product_id>/image')
    def replace_product_photo(bar_id,product_id):
        access(bar_id);product=g.db.get(Product,product_id)
        if not product or product.bar_id!=bar_id or not product.enabled:abort(404)
        d=data();state=save_photo(product,d.get('photo'));return jsonify(image_state=state,product=product_view(product))
    @app.get('/media/products/<product_id>/<photo_token>.jpg')
    def stored_product_photo(product_id,photo_token):
        photo=g.db.get(ProductPhoto,product_id);product=g.db.get(Product,product_id)
        if not photo or not product or not product.enabled or not hmac.compare_digest(photo.token,photo_token):abort(404)
        response=Response(photo.content,mimetype='image/jpeg')
        response.headers['Cache-Control']='public, max-age=86400'
        return response
    @app.delete('/api/bars/<bar_id>/products/<product_id>')
    def remove_product(bar_id,product_id):
        access(bar_id);p=g.db.get(Product,product_id)
        if not p or p.bar_id!=bar_id:abort(404)
        p.enabled=False;g.db.commit();return jsonify(ok=True)
    @app.get('/api/bars/<bar_id>/tables')
    def tables(bar_id):
        access(bar_id);return jsonify(tables=[{'id':t.id,'name':t.name,'open':t.opened,'opened_at':t.opened_at,'token':t.token,'link':'/?mesa='+t.token} for t in g.db.scalars(select(Table).where(Table.bar_id==bar_id).order_by(Table.name))])
    @app.post('/api/bars/<bar_id>/tables')
    def new_table(bar_id):
        access(bar_id);name=text(data(),'name',60)
        if g.db.scalar(select(Table).where(Table.bar_id==bar_id,Table.name==name)):abort(409,description='Mesa já cadastrada.')
        t=Table(id=str(uuid.uuid4()),bar_id=bar_id,name=name,token=secrets.token_urlsafe(24));
        if active_cash(bar_id):t.opened=True;t.session_no=1;t.opened_at=stamp()
        g.db.add(t);g.db.commit();return jsonify(id=t.id),201
    @app.post('/api/bars/<bar_id>/tables/open')
    def open_tables(bar_id):
        access(bar_id)
        if not active_cash(bar_id):abort(409,description='Abra o caixa primeiro.')
        for t in g.db.scalars(select(Table).where(Table.bar_id==bar_id,Table.opened==False)):
            t.opened=True;t.session_no+=1;t.opened_at=stamp()
        g.db.commit();return jsonify(ok=True)
    def public_table(token,lock=False):
        q=select(Table).where(Table.token==token)
        if lock:q=q.with_for_update()
        t=g.db.scalar(q)
        if not t:abort(404)
        bar=g.db.get(Bar,t.bar_id)
        if subscription(bar)['status']=='Bloqueada':abort(402,description='Atendimento temporariamente indisponível.')
        return t,bar
    @app.get('/api/public/<token>')
    def menu(token):
        t,b=public_table(token);return jsonify(bar=b.name,table=t.name,open=t.opened and active_cash(b.id) is not None,session=t.session_no,waiter=(g.db.get(Waiter,g.db.get(Assignment,t.id).waiter_id).name if g.db.get(Assignment,t.id) else 'Sem garçom'),products=[product_view(p) for p in g.db.scalars(select(Product).where(Product.bar_id==b.id,Product.enabled==True,Product.price_cents>0))])
    @app.post('/api/public/<token>/orders')
    def order(token):
        t,b=public_table(token)
        lock_bar(g.db,b.id)
        g.db.expire(t)
        t,b=public_table(token,True)
        if not t.opened or not active_cash(b.id):abort(409,description='Mesa ou caixa fechado. Solicite a abertura à equipe.')
        d=data();name=text(d,'name',80);phone=re.sub(r'\D','',text(d,'phone',20));rid=text(d,'request_id',80)
        if len(phone)==13 and phone.startswith('55'):phone=phone[2:]
        if not re.fullmatch(r'[1-9][0-9]9[0-9]{8}',phone):abort(400,description='Celular inválido.')
        previous=g.db.scalar(select(Order).where(Order.bar_id==b.id,Order.request_id==rid))
        if previous:
            if previous.table_id!=t.id or previous.session_no!=t.session_no:abort(409)
            return jsonify(id=previous.id,total_cents=previous.total_cents),200
        lines=d.get('items')
        if not isinstance(lines,list) or not 1<=len(lines)<=100:abort(400)
        snapshots=[];total=0
        for line in lines:
            if not isinstance(line,dict):abort(400)
            if not isinstance(line.get('id'),str):abort(400)
            p=g.db.get(Product,line.get('id'));qty=line.get('quantity')
            if not p or p.bar_id!=b.id or not p.enabled or p.price_cents<=0 or type(qty)!=int or not 1<=qty<=100:abort(400,description='Produto ou quantidade inválida.')
            snapshots.append({'id':p.id,'name':p.name,'quantity':qty,'unit_cents':p.price_cents});total+=p.price_cents*qty
        note=d.get('note','')
        if not isinstance(note,str) or len(note)>500:abort(400)
        o=Order(id=str(uuid.uuid4()),bar_id=b.id,table_id=t.id,session_no=t.session_no,customer_name=name,phone=phone,items=snapshots,total_cents=total,note=note,status='Recebido',created_at=stamp(),request_id=rid);g.db.add(o);g.db.flush();sale(g.db,o);g.db.commit();return jsonify(id=o.id,total_cents=total),201
    @app.get('/api/bars/<bar_id>/orders')
    def orders(bar_id):
        access(bar_id);return jsonify(orders=[{'id':o.id,'table':g.db.get(Table,o.table_id).name,'name':o.customer_name,'phone':o.phone,'items':o.items,'total_cents':o.total_cents,'status':o.status,'created_at':o.created_at} for o in g.db.scalars(select(Order).join(Table,Order.table_id==Table.id).where(Order.bar_id==bar_id,Table.opened==True,Order.session_no==Table.session_no).order_by(Order.created_at.desc()).limit(500))])
    @app.post('/api/bars/<bar_id>/orders/<order_id>/advance')
    def advance(bar_id,order_id):
        access(bar_id);o=g.db.get(Order,order_id)
        if not o or o.bar_id!=bar_id:abort(404)
        o.status={'Recebido':'Em preparo','Em preparo':'Entregue','Entregue':'Entregue'}[o.status];g.db.commit();return jsonify(status=o.status)
    @app.cli.command('create-admin')
    def create_admin():
        email=os.environ.get('ADMIN_EMAIL','').strip().lower();password=os.environ.get('ADMIN_PASSWORD','')
        if not email or len(password)<10:raise RuntimeError('Configure ADMIN_EMAIL e ADMIN_PASSWORD (ao menos 10 caracteres).')
        with Session(engine) as db:
            if db.scalar(select(User).where(User.email==email)):raise RuntimeError('Usuário já existe; não sobrescrito.')
            db.add(User(id=str(uuid.uuid4()),email=email,password_hash=generate_password_hash(password),role='owner'));db.commit()
        print('Administrador criado. A senha não foi gravada no código.')
    return app


