"""Ruh Al Quran Academy V4: dependency-free Python web app."""
import os, json, sqlite3, secrets, hashlib, hmac, time, re, html, smtplib, ssl
from email.message import EmailMessage
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=os.environ.get('DATABASE_PATH',str(ROOT/'admissions.sqlite3'))
PORT=int(os.environ.get('PORT','8000'))
ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD','')
SECRET=os.environ.get('SESSION_SECRET','')
SECURE=os.environ.get('COOKIE_SECURE','0')=='1'
SESSION_TTL=8*3600
MAX_BODY=12000
RATE={}
STATUSES=['New','Contacted','Trial Scheduled','Enrolled','Closed']

def db():
    c=sqlite3.connect(DB,timeout=10)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    return c

def setup():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL DEFAULT (datetime('now')),name TEXT NOT NULL,email TEXT NOT NULL,course TEXT NOT NULL,age TEXT,phone TEXT,timezone TEXT,message TEXT,status TEXT NOT NULL DEFAULT 'New')''')

def sign(payload):
    return hmac.new(SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()

def safe(v,limit=300):
    return str(v or '').strip()[:limit]

def notify(data):
    if not all(os.environ.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','NOTIFY_EMAIL')):return
    try:
        msg=EmailMessage();msg['Subject']='New Quran Academy admission inquiry';msg['From']=os.environ['SMTP_USER'];msg['To']=os.environ['NOTIFY_EMAIL']
        msg.set_content('\n'.join(f'{k}: {v}' for k,v in data.items()))
        with smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.environ.get('SMTP_PORT','465')),context=ssl.create_default_context(),timeout=8) as s:
            s.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);s.send_message(msg)
    except Exception as exc: print('Notification failed:',type(exc).__name__,flush=True)

class Handler(BaseHTTPRequestHandler):
    def send(self,code,body,ctype='application/json',headers=None):
        if isinstance(body,(dict,list)):body=json.dumps(body).encode()
        elif isinstance(body,str):body=body.encode()
        self.send_response(code);self.send_header('Content-Type',ctype+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('X-Frame-Options','DENY');self.send_header('Cache-Control','no-store' if self.path.startswith('/api/') or self.path.startswith('/admin') else 'public, max-age=300')
        if headers:
            for k,v in headers.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(body)
    def data(self):
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n<=0 or n>MAX_BODY:return None
            return json.loads(self.rfile.read(n))
        except (ValueError,UnicodeDecodeError):return None
    def cookie(self,name):
        try:
            c=SimpleCookie();c.load(self.headers.get('Cookie',''));return c[name].value if name in c else ''
        except Exception:return ''
    def auth(self):
        token=self.cookie('academy_session');parts=token.split('.')
        if len(parts)!=2:return False
        payload,sig=parts
        if not hmac.compare_digest(sign(payload),sig):return False
        try:return time.time()-int(payload.split(':')[0])<SESSION_TTL and time.time()>=int(payload.split(':')[0])
        except (ValueError,IndexError):return False
    def csrf(self):
        return self.auth() and hmac.compare_digest(self.headers.get('X-CSRF-Token',''),sign('csrf:'+self.cookie('academy_session')))
    def origin_ok(self):
        origin=self.headers.get('Origin')
        if not origin:return True
        host=self.headers.get('Host','')
        return origin in ('https://'+host,'http://'+host)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/' or path=='/index.html':return self.send(200,(ROOT/'index.html').read_bytes(),'text/html')
        if path=='/admin':return self.send(200,(ROOT/'admin.html').read_bytes(),'text/html')
        if path=='/health':return self.send(200,{'ok':True})
        if path=='/api/session':return self.send(200,{'authenticated':self.auth(),'csrf':sign('csrf:'+self.cookie('academy_session')) if self.auth() else None})
        if path=='/api/applications':
            if not self.auth():return self.send(401,{'error':'Login required'})
            with db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM applications ORDER BY id DESC LIMIT 1000')]
            return self.send(200,{'applications':rows})
        return self.send(404,{'error':'Not found'})
    def do_POST(self):
        path=urlparse(self.path).path
        if not self.origin_ok():return self.send(403,{'error':'Invalid origin'})
        d=self.data()
        if not isinstance(d,dict):return self.send(400,{'error':'Invalid request'})
        if path=='/api/apply':
            ip=self.client_address[0];now=time.time();RATE[ip]=[t for t in RATE.get(ip,[]) if now-t<3600]
            if len(RATE[ip])>=8:return self.send(429,{'error':'Too many inquiries. Please try again later.'})
            if d.get('website'):return self.send(200,{'ok':True})
            name=safe(d.get('name'),100);email=safe(d.get('email'),200);course=safe(d.get('course'),100)
            if not (2<=len(name)<=100 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) and course in ['Noorani Qaida','Quran Reading','Tajweed','Quran Memorization','Islamic Studies','Personalized Learning']):return self.send(400,{'error':'Please check name, email, and course.'})
            row={'name':name,'email':email,'course':course,'age':safe(d.get('age'),30),'phone':safe(d.get('phone'),50),'timezone':safe(d.get('timezone'),100),'message':safe(d.get('message'),2000)}
            with db() as c:c.execute('INSERT INTO applications(name,email,course,age,phone,timezone,message) VALUES(:name,:email,:course,:age,:phone,:timezone,:message)',row)
            RATE[ip].append(now);notify(row)
            return self.send(201,{'ok':True,'message':'Your inquiry has been received. Our admissions team will contact you.'})
        if path=='/api/login':
            ip=self.client_address[0];now=time.time();key='login:'+ip;RATE[key]=[t for t in RATE.get(key,[]) if now-t<900]
            if len(RATE[key])>=10:return self.send(429,{'error':'Too many login attempts. Try again later.'})
            RATE[key].append(now)
            if not ADMIN_PASSWORD or not hmac.compare_digest(str(d.get('password','')),ADMIN_PASSWORD):return self.send(401,{'error':'Invalid password'})
            payload=f'{int(now)}:{secrets.token_hex(16)}';token=payload+'.'+sign(payload)
            cookie='academy_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+str(SESSION_TTL)+('; Secure' if SECURE else '')
            return self.send(200,{'ok':True},headers={'Set-Cookie':cookie})
        if path=='/api/logout':
            return self.send(200,{'ok':True},headers={'Set-Cookie':'academy_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+('; Secure' if SECURE else '')})
        if path=='/api/status':
            if not self.csrf():return self.send(403,{'error':'Unauthorized or invalid session token'})
            try:app_id=int(d.get('id'))
            except (ValueError,TypeError):return self.send(400,{'error':'Invalid ID'})
            status=d.get('status')
            if status not in STATUSES:return self.send(400,{'error':'Invalid status'})
            with db() as c:cur=c.execute('UPDATE applications SET status=? WHERE id=?',(status,app_id))
            return self.send(200 if cur.rowcount else 404,{'ok':bool(cur.rowcount)})
        return self.send(404,{'error':'Not found'})

if __name__=='__main__':
    if not ADMIN_PASSWORD or not SECRET or len(SECRET)<32:raise SystemExit('Set ADMIN_PASSWORD and SESSION_SECRET (32+ characters) before starting.')
    setup();print(f'Listening on port {PORT}',flush=True);ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
