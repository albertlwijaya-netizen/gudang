from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'sembako_key_secret'

# --- KONFIGURASI DATABASE TIDB ---
db_config = {
    'host': 'gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com',
    'port': 4000,
    'user': '44GVr8AhWzxoo75.root',
    'password': 'wWoNZ7dC4jKc3d5L',
    'database': 'gudang_sembako',
    'cursorclass': pymysql.cursors.DictCursor,
    'ssl': {'ca': ''} 
}

def get_db():
    return pymysql.connect(**db_config)

# --- MIDDLEWARE / DECORATORS ---
@app.context_processor
def inject_user():
    return dict(session_user=session.get('username'), session_role=session.get('role'))

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Silakan login terlebih dahulu', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Akses ditolak! Hanya Admin yang diijinkan.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper

# --- ROUTES: AUTENTIKASI ---

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'logged_in' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
                user = cur.fetchone()
                if user:
                    session.update({
                        'logged_in': True,
                        'username': user['username'],
                        'role': user['role']
                    })
                    flash(f'Selamat datang, {user["username"]}!', 'success')
                    return redirect(url_for('dashboard'))
                flash('Username atau password salah', 'danger')
        finally:
            db.close()
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah keluar', 'info')
    return redirect(url_for('login'))

# --- ROUTES: DASHBOARD ---

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) as t FROM barang")
            t_barang = cur.fetchone()['t']
            cur.execute("SELECT COUNT(*) as t FROM supplier")
            t_supplier = cur.fetchone()['t']
            cur.execute("SELECT SUM(jumlah) as t FROM barang_masuk")
            t_masuk = cur.fetchone()['t'] or 0
            cur.execute("SELECT SUM(jumlah) as t FROM barang_keluar")
            t_keluar = cur.fetchone()['t'] or 0
            cur.execute("SELECT SUM(stok) as t FROM barang")
            t_stok = cur.fetchone()['t'] or 0
            
            return render_template('dashboard.html', t_barang=t_barang, t_supplier=t_supplier,
                                   t_masuk=t_masuk, t_keluar=t_keluar, t_stok=t_stok)
    finally:
        db.close()

# --- ROUTES: MANAJEMEN BARANG ---

@app.route('/barang')
@login_required
def barang():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM barang")
            return render_template('barang/index.html', barang=cur.fetchall())
    finally:
        db.close()

@app.route('/barang/tambah', methods=['POST'])
@login_required
@admin_only
def barang_tambah():
    d = request.form
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""INSERT INTO barang (kode_barang, nama_barang, kategori, satuan, stok, stok_minimum, harga_beli, harga_jual) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", 
                        (d['kode'], d['nama'], d['kategori'], d['satuan'], d['stok'], d['stok_min'], d['harga_beli'], d['harga_jual']))
            db.commit()
            flash('Barang berhasil ditambahkan', 'success')
    except Exception as e:
        flash(f'Gagal: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('barang'))

@app.route('/barang/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_only
def barang_edit(id):
    db = get_db()
    try:
        with db.cursor() as cur:
            if request.method == 'POST':
                d = request.form
                cur.execute("""UPDATE barang SET kode_barang=%s, nama_barang=%s, kategori=%s, 
                               satuan=%s, stok_minimum=%s, harga_beli=%s, harga_jual=%s WHERE id_barang=%s""", 
                            (d['kode'], d['nama'], d['kategori'], d['satuan'], d['stok_min'], d['harga_beli'], d['harga_jual'], id))
                db.commit()
                flash('Data barang diperbarui', 'success')
                return redirect(url_for('barang'))
            
            cur.execute("SELECT * FROM barang WHERE id_barang = %s", (id,))
            return render_template('barang/edit.html', item=cur.fetchone())
    finally:
        db.close()

@app.route('/barang/hapus/<int:id>')
@login_required
@admin_only
def barang_hapus(id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM barang WHERE id_barang = %s", (id,))
            db.commit()
            flash('Barang telah dihapus', 'info')
    finally:
        db.close()
    return redirect(url_for('barang'))

# --- ROUTES: MANAJEMEN SUPPLIER ---

@app.route('/supplier')
@login_required
def supplier():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM supplier")
            return render_template('supplier/index.html', supplier=cur.fetchall())
    finally:
        db.close()

@app.route('/supplier/tambah', methods=['POST'])
@login_required
@admin_only
def supplier_tambah():
    d = request.form
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("INSERT INTO supplier (nama_supplier, alamat, nomor_telepon, email) VALUES (%s, %s, %s, %s)",
                        (d['nama'], d['alamat'], d['telp'], d['email']))
            db.commit()
            flash('Supplier ditambahkan', 'success')
    finally:
        db.close()
    return redirect(url_for('supplier'))

@app.route('/supplier/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_only
def supplier_edit(id):
    db = get_db()
    try:
        with db.cursor() as cur:
            if request.method == 'POST':
                d = request.form
                cur.execute("UPDATE supplier SET nama_supplier=%s, alamat=%s, nomor_telepon=%s, email=%s WHERE id_supplier=%s",
                            (d['nama'], d['alamat'], d['telp'], d['email'], id))
                db.commit()
                flash('Data supplier diperbarui', 'success')
                return redirect(url_for('supplier'))
            
            cur.execute("SELECT * FROM supplier WHERE id_supplier = %s", (id,))
            return render_template('supplier/edit.html', s=cur.fetchone())
    finally:
        db.close()

# --- ROUTES: TRANSAKSI ---

@app.route('/transaksi/masuk', methods=['GET', 'POST'])
@login_required
def transaksi_masuk():
    db = get_db()
    try:
        with db.cursor() as cur:
            if request.method == 'POST':
                f = request.form
                cur.execute("INSERT INTO barang_masuk (id_barang, id_supplier, jumlah, tanggal, keterangan) VALUES (%s, %s, %s, %s, %s)",
                            (f['id_barang'], f['id_supplier'], f['jumlah'], f['tanggal'], f['keterangan']))
                cur.execute("UPDATE barang SET stok = stok + %s WHERE id_barang = %s", (f['jumlah'], f['id_barang']))
                db.commit()
                flash('Barang masuk berhasil dicatat', 'success')
                return redirect(url_for('transaksi_masuk'))

            cur.execute("SELECT id_barang, nama_barang FROM barang")
            b = cur.fetchall()
            cur.execute("SELECT id_supplier, nama_supplier FROM supplier")
            s = cur.fetchall()
            return render_template('transaksi/masuk.html', barangs=b, suppliers=s)
    finally:
        db.close()

@app.route('/transaksi/keluar', methods=['GET', 'POST'])
@login_required
def transaksi_keluar():
    db = get_db()
    try:
        with db.cursor() as cur:
            if request.method == 'POST':
                f = request.form
                cur.execute("SELECT stok FROM barang WHERE id_barang = %s", (f['id_barang'],))
                stok_skrg = cur.fetchone()['stok']
                
                if int(f['jumlah']) > stok_skrg:
                    flash('Gagal! Stok tidak mencukupi.', 'danger')
                else:
                    cur.execute("INSERT INTO barang_keluar (id_barang, jumlah, tanggal, tujuan, keterangan) VALUES (%s, %s, %s, %s, %s)",
                                (f['id_barang'], f['jumlah'], f['tanggal'], f['tujuan'], f['keterangan']))
                    cur.execute("UPDATE barang SET stok = stok - %s WHERE id_barang = %s", (f['jumlah'], f['id_barang']))
                    db.commit()
                    flash('Barang keluar berhasil dicatat', 'success')
                return redirect(url_for('transaksi_keluar'))

            cur.execute("SELECT id_barang, nama_barang FROM barang")
            return render_template('transaksi/keluar.html', barangs=cur.fetchall())
    finally:
        db.close()

# --- ROUTES: MONITORING & LAPORAN ---

@app.route('/monitoring')
@login_required
def monitoring():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM barang")
            return render_template('monitoring/stok.html', barang=cur.fetchall())
    finally:
        db.close()

@app.route('/laporan/masuk', methods=['GET', 'POST'])
@login_required
def laporan_masuk():
    data = []
    if request.method == 'POST':
        db = get_db()
        try:
            with db.cursor() as cur:
                query = """SELECT m.*, b.nama_barang, s.nama_supplier FROM barang_masuk m 
                           JOIN barang b ON m.id_barang = b.id_barang 
                           JOIN supplier s ON m.id_supplier = s.id_supplier
                           WHERE m.tanggal BETWEEN %s AND %s"""
                cur.execute(query, (request.form['tgl_awal'], request.form['tgl_akhir']))
                data = cur.fetchall()
        finally:
            db.close()
    return render_template('laporan/masuk.html', laporan=data)

@app.route('/laporan/keluar', methods=['GET', 'POST'])
@login_required
def laporan_keluar():
    data = []
    if request.method == 'POST':
        db = get_db()
        try:
            with db.cursor() as cur:
                query = """SELECT k.*, b.nama_barang FROM barang_keluar k 
                           JOIN barang b ON k.id_barang = b.id_barang 
                           WHERE k.tanggal BETWEEN %s AND %s"""
                cur.execute(query, (request.form['tgl_awal'], request.form['tgl_akhir']))
                data = cur.fetchall()
        finally:
            db.close()
    return render_template('laporan/keluar.html', laporan=data)

if __name__ == '__main__':
    app.run(debug=True)