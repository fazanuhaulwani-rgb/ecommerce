# blueprints/cart.py
from flask import Blueprint, session, redirect, url_for, request, flash, render_template, current_app, jsonify
from supabase import create_client
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Konfigurasi Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Kunci API Xendit (diatur di .env)
XENDIT_API_KEY = os.getenv('XENDIT_API_KEY')

cart_bp = Blueprint('cart', __name__, url_prefix='/cart')

# -------------------------------
# Fungsi Pembantu: Dapatkan produk berdasarkan ID
# -------------------------------
def get_product_by_id(product_id):
    if not supabase:
        return None
    try:
        resp = supabase.table('products').select('*').eq('id', product_id).single().execute()
        return resp.data
    except Exception:
        return None

# -------------------------------
# Lihat Keranjang
# -------------------------------
@cart_bp.route('/')
def view_cart():
    cart = session.get('cart', {})
    cart_items = []
    subtotal = 0
    for product_id, item in cart.items():
        if isinstance(item, dict) and 'price' in item and 'quantity' in item:
            total_price = item['price'] * item['quantity']
            cart_items.append({
                'id': product_id,
                'name': item.get('name', ''),
                'description': item.get('description', ''),
                'price': item['price'],
                'quantity': item['quantity'],
                'image_url': item.get('image_url', ''),
                'total_price': total_price,
                'stock': item.get('stock', 100)
            })
            subtotal += total_price
    
    # Ambil voucher dari sesi
    applied_voucher = session.get('applied_voucher', None)
    discount = 0
    shipping_cost = 0 # Asumsi awal ada biaya pengiriman, nanti bisa diubah jadi gratis
    
    if applied_voucher:
        if applied_voucher['type'] == 'percentage':
            discount = subtotal * (applied_voucher['value'] / 100)
        elif applied_voucher['type'] == 'fixed_amount':
            discount = applied_voucher['value']
        elif applied_voucher['type'] == 'free_shipping':
            shipping_cost = 0 # Atau set ke nilai default jika ada
            flash('Voucher gratis ongkir diterapkan!', 'info')
            # Jika ada diskon lain, bisa digabungkan logikanya di sini
    
    total = subtotal - discount + shipping_cost # Sesuaikan perhitungan total
    
    return render_template('cart.html', cart_items=cart_items, subtotal=subtotal, discount=discount, total=total, applied_voucher=applied_voucher)

# -------------------------------
# Tambah ke Keranjang
# -------------------------------
@cart_bp.route('/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}
    product = get_product_by_id(product_id)
    if not product:
        flash('Produk tidak ditemukan', 'error')
        return redirect(url_for('cart.view_cart'))
    key = str(product_id)
    if key in cart:
        cart[key]['quantity'] += quantity
    else:
        cart[key] = {
            'name': product['name'],
            'description': product.get('description', ''),
            'price': float(product['price']),
            'quantity': quantity,
            'image_url': product.get('image_url', ''),
            'stock': product.get('stock', 100)
        }
    session['cart'] = cart
    flash('Produk ditambahkan ke keranjang', 'success')
    return redirect(url_for('cart.view_cart'))

# -------------------------------
# Perbarui jumlah di keranjang
# -------------------------------
@cart_bp.route('/update/<int:product_id>', methods=['POST'])
def update_quantity(product_id):
    action = request.form.get('action')
    new_quantity = request.form.get('quantity')
    cart = session.get('cart', {})
    product_id_str = str(product_id)

    if product_id_str not in cart:
        flash('Item tidak ditemukan di keranjang', 'error')
        return redirect(url_for('cart.view_cart'))

    if action == 'increase':
        cart[product_id_str]['quantity'] += 1
    elif action == 'decrease':
        if cart[product_id_str]['quantity'] > 1:
            cart[product_id_str]['quantity'] -= 1
    elif new_quantity:
        try:
            new_quantity = int(new_quantity)
            if new_quantity > 0:
                cart[product_id_str]['quantity'] = new_quantity
            else:
                flash('Jumlah harus lebih besar dari 0', 'error')
        except ValueError:
            flash('Nilai jumlah tidak valid', 'error')
    
    session['cart'] = cart
    flash('Jumlah diperbarui', 'success')
    return redirect(url_for('cart.view_cart'))

# -------------------------------
# Hapus dari Keranjang
# -------------------------------
@cart_bp.route('/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    key = str(product_id)
    cart = session.get('cart', {})

    if not isinstance(cart, dict):
        cart = {}
        session['cart'] = cart

    if key in cart:
        cart.pop(key)
        session['cart'] = cart
        # Hapus voucher jika keranjang kosong setelah penghapusan
        if not cart:
            session.pop('applied_voucher', None)
        flash('Produk dihapus dari keranjang', 'success')
    return redirect(url_for('cart.view_cart'))

# -------------------------------
# Rute baru untuk menerapkan voucher
# -------------------------------
@cart_bp.route('/apply_voucher', methods=['POST'])
def apply_voucher():
    voucher_code = request.form.get('voucher_code', '').strip().upper()
    
    # Daftar voucher yang tersedia (contoh sederhana)
    available_vouchers = {
        'ONGKIRGRATIS': {'type': 'free_shipping', 'value': 0, 'description': 'Gratis Ongkir'},
        'DISKON10': {'type': 'percentage', 'value': 10, 'description': 'Diskon 10%'},
        'HEMAT50RB': {'type': 'fixed_amount', 'value': 50000, 'description': 'Diskon Rp 50.000'}
    }

    if voucher_code in available_vouchers:
      # Tambahan: Copy dict voucher dan tambah key 'code' untuk referensi
      voucher_data = available_vouchers[voucher_code].copy()  # Baris baru: Copy untuk hindari modifikasi asli
      voucher_data['code'] = voucher_code  # Baris baru: Tambah key 'code' dengan nilai kode input
      session['applied_voucher'] = voucher_data  # Ganti: Simpan voucher_data (bukan langsung dari available_vouchers)
      flash(f'Voucher "{voucher_code}" berhasil diterapkan!', 'success')
  
    else:
        session.pop('applied_voucher', None) # Hapus voucher yang mungkin sudah ada
        flash('Kode voucher tidak valid atau sudah tidak berlaku.', 'error')
    
    return redirect(url_for('cart.view_cart'))

# -------------------------------
# Rute baru untuk menghapus voucher
# -------------------------------
@cart_bp.route('/remove_voucher', methods=['POST'])
def remove_voucher():
    session.pop('applied_voucher', None)
    removed_code = session.get('applied_voucher', {}).get('code', 'Unknown') if session.get('applied_voucher') else None
    session.pop('applied_voucher', None)
    if removed_code and removed_code != 'Unknown':
      flash(f'Voucher "{removed_code}" berhasil dihapus.', 'info')
    else:
      flash('Voucher berhasil dihapus.', 'info')
  
    return redirect(url_for('cart.view_cart'))


# -------------------------------
# Formulir Checkout (pengiriman)
# -------------------------------
@cart_bp.route('/checkout/form', methods=['GET', 'POST'])
def checkout_form():
    if 'user' not in session:
        flash('Anda harus login untuk checkout', 'error')
        return redirect(url_for('auth.login'))
    cart = session.get('cart', {})
    if not cart:
        flash('Keranjang Anda kosong', 'error')
        return redirect(url_for('cart.view_cart'))
    
    cart_items = []
    subtotal = 0
    total_quantity = 0  # <-- Tambahkan ini: inisialisasi total quantity
    
    for product_id, item in cart.items():
        if isinstance(item, dict) and 'price' in item and 'quantity' in item:
            total_price = item['price'] * item['quantity']
            cart_items.append({
                'id': product_id,
                'name': item.get('name', ''),
                'price': item['price'],
                'quantity': item['quantity'],
                'image_url': item.get('image_url', ''),
                'total_price': total_price,
                'stock': item.get('stock', 100)
            })
            subtotal += total_price
            total_quantity += item['quantity']  # <-- Tambahkan ini: akumulasi quantity dari setiap item
    
    # Hitung diskon dan biaya pengiriman berdasarkan voucher
    applied_voucher = session.get('applied_voucher', None)
    discount = 0
    shipping_cost = 0  # Default shipping cost, adjust as needed
    
    if applied_voucher:
        if applied_voucher['type'] == 'percentage':
            discount = subtotal * (applied_voucher['value'] / 100)
        elif applied_voucher['type'] == 'fixed_amount':
            discount = applied_voucher['value']
        elif applied_voucher['type'] == 'free_shipping':
            shipping_cost = 0  # Gratis ongkir
            
    total = subtotal - discount + shipping_cost

    if request.method == 'POST':
        shipping_info = {
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name'),
            'mobile_phone': request.form.get('mobile_phone'),
            'address': request.form.get('address'),
            'province': request.form.get('province'),
            'city': request.form.get('city'),
            'district': request.form.get('district'),
            'zip_code': request.form.get('zip_code')
        }
        session['shipping_info'] = shipping_info
        return redirect(url_for('cart.checkout_finalize'))
    
    return render_template('checkout_form.html', 
                           cart_items=cart_items, 
                           subtotal=subtotal, 
                           discount=discount, 
                           shipping_cost=shipping_cost,  # Kirim biaya pengiriman
                           total=total,
                           applied_voucher=applied_voucher,
                           total_quantity=total_quantity)  # <-- Tambahkan ini: pass total_quantity ke template


# -------------------------------
# Finalisasi Checkout (buat pesanan + buat invoice Xendit)
# -------------------------------
@cart_bp.route('/checkout/finalize', methods=['GET', 'POST'])
def checkout_finalize():
    if 'user' not in session:
        flash('Anda harus login untuk checkout', 'error')
        return redirect(url_for('auth.login'))

    cart = session.get('cart', {})
    shipping_info = session.get('shipping_info', {})

    if not cart or not shipping_info:
        flash('Keranjang atau informasi pengiriman tidak ada', 'error')
        return redirect(url_for('cart.view_cart'))

    # siapkan item keranjang untuk ditampilkan
    cart_items = []
    subtotal = 0
    for product_id, item in cart.items():
        if isinstance(item, dict) and 'price' in item and 'quantity' in item:
            total_price = item['price'] * item['quantity']
            cart_items.append({
                'id': product_id,
                'name': item.get('name', ''),
                'price': item['price'],
                'quantity': item['quantity'],
                'image_url': item.get('image_url', ''),
                'total_price': total_price,
                'stock': item.get('stock', 100)
            })
            subtotal += total_price

    # Hitung diskon dan biaya pengiriman berdasarkan voucher
    applied_voucher = session.get('applied_voucher', None)
    discount = 0
    shipping_cost = 0 # Default shipping cost, adjust as needed
    
    if applied_voucher:
        if applied_voucher['type'] == 'percentage':
            discount = subtotal * (applied_voucher['value'] / 100)
        elif applied_voucher['type'] == 'fixed_amount':
            discount = applied_voucher['value']
        elif applied_voucher['type'] == 'free_shipping':
            shipping_cost = 0 # Gratis ongkir
            
    total = subtotal - discount + shipping_cost
    total_int = int(round(total))

    if request.method == 'POST':
        # validasi id pengguna di sesi (integer)
        user_id = session['user'].get('id')
        if not isinstance(user_id, int):
            flash('Sesi pengguna tidak valid. Silakan login kembali.', 'error')
            return redirect(url_for('auth.login'))

        if not cart_items:
            flash('Keranjang kosong atau tidak valid.', 'error')
            return redirect(url_for('cart.view_cart'))
        
        #Pengurangan Stok
        #Periksa stok sebelum membuat pesanan
        for item in cart_items:
            product_id = int(item['id'])
            quantity_ordered = item['quantity']

            product_db = get_product_by_id(product_id)
            if not product_db or product_db['stock'] < quantity_ordered:
                flash(f"Stok untuk produk '{item['name']}' tidak mencukupi. Tersedia: {product_db['stock'] if product_db else 0}, Diminta: {quantity_ordered}", 'error')
                return redirect(url_for('cart.view_cart'))

        # buat pesanan di supabase
        try:
            order_resp = supabase.table('orders').insert({
                'user_id': user_id,
                'total': total_int,
                'status': 'pending',
                'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'discount_amount': int(round(discount)), # Simpan jumlah diskon
                'shipping_cost': int(round(shipping_cost)), # Simpan biaya pengiriman
                'voucher_code': applied_voucher.get('code') if applied_voucher else None  # Ganti: Simpan kode (misalnya 'DISKON10') ke kolom DB
            }).execute()

            if not order_resp.data or len(order_resp.data) == 0:
                flash('Gagal membuat pesanan', 'error')
                return redirect(url_for('cart.view_cart'))

            order_id = order_resp.data[0]['id']

            # masukkan order_items
            order_items = []
            for pid, item in cart.items():
                try:
                    product_id_int = int(pid)
                except Exception:
                    continue
                order_items.append({
                    'order_id': order_id,
                    'product_id': product_id_int,
                    'quantity': item['quantity'],
                    'price': int(round(item['price']))
                })
            if order_items:
                supabase.table('order_items').insert(order_items).execute()

            #Pengurangan stok
            for item in cart_items:
                product_id = int(item['id'])
                quantity_ordered = item['quantity']

                product_db = get_product_by_id(product_id)
                if product_db:
                    new_stock = product_db['stock'] - quantity_ordered
                    supabase.table('products').update({'stock': new_stock}).eq('id', product_id).execute()
                else:
                    print(f"Warning: Product {product_id} not found during stock update.")

            # lampirkan informasi pengiriman ke pesanan (opsional) - jika tabel pesanan Anda memiliki kolom json pengiriman, Anda dapat memperbaruinya
            # mis., supabase.table('orders').update({'shipping': shipping_info}).eq('id', order_id).execute()

            # buat invoice Xendit
            if not XENDIT_API_KEY:
                flash('Layanan pembayaran tidak dikonfigurasi. Pesanan dibuat sebagai tertunda (demo).', 'info')
                session.pop('cart', None)
                session.pop('shipping_info', None)
                session.pop('applied_voucher', None) # Hapus voucher setelah pesanan dibuat
                return redirect(url_for('orders.order_history'))

            invoice_payload = {
                "external_id": f"order-{order_id}",
                "amount": total_int,
                "payer_email": session['user'].get('email'),
                "description": f"Pembayaran untuk pesanan #{order_id}",
                "success_redirect_url": url_for('cart.payment_success', order_id=order_id, _external=True),
                "failure_redirect_url": url_for('cart.payment_failed', order_id=order_id, _external=True)
            }

            resp = requests.post(
                "https://api.xendit.co/v2/invoices",
                auth=(XENDIT_API_KEY, ""),
                json=invoice_payload,
                timeout=15
            )

            try:
                invoice = resp.json()
            except Exception:
                invoice = None

            if resp.status_code in (200, 201) and invoice and invoice.get('invoice_url'):
                # perbarui pesanan dengan info invoice
                supabase.table('orders').update({
                    'invoice_id': invoice.get('id'),
                    'invoice_url': invoice.get('invoice_url')
                }).eq('id', order_id).execute()

                # Redirect langsung ke halaman invoice Xendit
                # Jangan hapus cart dan shipping_info di sini
                session.pop('applied_voucher', None) # Hapus voucher setelah pembayaran dimulai
                return redirect(invoice.get('invoice_url'))
            else:
                # pembuatan invoice gagal — simpan pesanan, tetapi informasikan pengguna
                print("Kesalahan invoice Xendit:", resp.status_code, resp.text)
                flash('Gagal membuat invoice pembayaran. Silakan hubungi admin.', 'error')
                return redirect(url_for('orders.order_history'))

        except Exception as e:
            print("❌ Kesalahan checkout:", e)
            flash(f'Kesalahan memproses pesanan: {e}', 'error')
            return redirect(url_for('cart.view_cart'))

    # GET -> tampilkan halaman finalisasi
    return render_template('checkout_finalize.html', 
                           cart=cart_items, 
                           shipping=shipping_info, 
                           subtotal=subtotal, 
                           discount=discount, 
                           shipping_cost=shipping_cost, # Kirim biaya pengiriman
                           total=total,
                           applied_voucher=applied_voucher)

# -------------------------------
# Halaman redirect Pembayaran memiliki: tautan ke Xendit + Tombol Simulasi
# -------------------------------
# Template 'payment_redirect.html' harus:
# - menampilkan invoice_url dengan tombol "Lanjutkan ke Pembayaran Xendit"
# - menampilkan tombol "Simulasikan Pembayaran (Demo)" yang mengarah ke /cart/payment/simulate/<order_id>
#
# Contoh: formulir POST ke payment/simulate atau anchor ke invoice_url target="_blank"

# -------------------------------
# Simulasi Pembayaran (demo) - tandai pesanan sebagai dibayar
# -------------------------------
@cart_bp.route('/payment/simulate/<int:order_id>', methods=['GET', 'POST'])
def payment_simulate(order_id):
    # Simulasikan konfirmasi (demo)
    if 'user' not in session:
        flash('Silakan login', 'error')
        return redirect(url_for('auth.login'))

    # Konfirmasi bahwa pesanan milik pengguna (opsional)
    try:
        resp = supabase.table('orders').select('*').eq('id', order_id).single().execute()
        order = resp.data
        if not order:
            flash('Pesanan tidak ditemukan', 'error')
            return redirect(url_for('orders.order_history'))
        # perbarui status
        supabase.table('orders').update({'status': 'success'}).eq('id', order_id).execute()
        
        # Hapus cart dan shipping_info setelah pembayaran berhasil (simulasi)
        session.pop('cart', None)
        session.pop('shipping_info', None)
        session.pop('applied_voucher', None) # Hapus voucher setelah pembayaran berhasil

        flash('Pesanan berhasil dibayar (disimulasikan).', 'success')
        return redirect(url_for('orders.order_history'))
    except Exception as e:
        print("Kesalahan simulasi pembayaran:", e)
        flash('Kesalahan simulasi', 'error')
        return redirect(url_for('orders.order_history'))

# -------------------------------
# Penangan redirect untuk Xendit
# -------------------------------
@cart_bp.route('/payment/success/<int:order_id>')
def payment_success(order_id):
    try:
        supabase.table('orders').update({'status': 'success'}).eq('id', order_id).execute()
        
        # Hapus cart dan shipping_info setelah pembayaran berhasil
        session.pop('cart', None)
        session.pop('shipping_info', None)
        session.pop('applied_voucher', None) # Hapus voucher setelah pembayaran berhasil

        flash('Pesanan berhasil dibayar!', 'success')
    except Exception as e:
        print("Kesalahan penangan sukses pembayaran:", e)
        flash('Pembayaran berhasil tetapi tidak dapat memperbarui pesanan. Hubungi admin.', 'error')
    return redirect(url_for('orders.order_history'))

@cart_bp.route('/payment/failed/<int:order_id>')
def payment_failed(order_id):
    try:
        # Perbarui status order menjadi 'failed'
        supabase.table('orders').update({'status': 'failed'}).eq('id', order_id).execute()
        # Jangan hapus cart dan shipping_info di sini, biarkan pengguna kembali ke checkout_finalize
        # Voucher tetap dipertahankan agar pengguna bisa mencoba lagi dengan voucher yang sama
    except Exception as e:
        print("Kesalahan penangan gagal pembayaran:", e)
    flash('Pembayaran gagal atau dibatalkan. Silakan coba lagi.', 'error')
    # Arahkan kembali ke halaman checkout_finalize
    return redirect(url_for('cart.checkout_finalize'))

# -------------------------------
# Webhook - Xendit akan POST event invoice di sini
# -------------------------------
@cart_bp.route('/payment/webhook', methods=['POST'])
def payment_webhook():
    try:
        payload = request.get_json(force=True)
        # Xendit mengirimkan notifikasi dengan field 'external_id' dan 'status' (dan 'id')
        external_id = payload.get('external_id') or (payload.get('data') or {}).get('external_id')
        status = payload.get('status') or (payload.get('data') or {}).get('status')
        invoice_id = payload.get('id') or (payload.get('data') or {}).get('id')

        if external_id:
            # format external_id yang diharapkan: "order-<order_id>"
            try:
                order_id = int(str(external_id).split('-')[1])
            except Exception:
                order_id = None
        else:
            order_id = None

        new_status = None
        if status:
            # Petakan status Xendit ke status kita
            s = status.lower()
            if s in ('paid', 'PAID'.lower()):
                new_status = 'success'
            elif s in ('pending',):
                new_status = 'pending'
            elif s in ('expired', 'failed', 'VOID'):
                new_status = 'failed'

        if order_id and new_status:
            supabase.table('orders').update({'status': new_status, 'invoice_id': invoice_id}).eq('id', order_id).execute()
            # Jika pembayaran berhasil melalui webhook, hapus cart dan shipping_info
            if new_status == 'success':
                session.pop('cart', None)
                session.pop('shipping_info', None)
                session.pop('applied_voucher', None) # Hapus voucher setelah pembayaran berhasil
        elif invoice_id and new_status:
            # fallback: coba temukan pesanan berdasarkan invoice_id
            sup = supabase.table('orders').select('*').eq('invoice_id', invoice_id).execute()
            if sup.data:
                supabase.table('orders').update({'status': new_status}).eq('invoice_id', invoice_id).execute()
                # Jika pembayaran berhasil melalui webhook, hapus cart dan shipping_info
                if new_status == 'success':
                    session.pop('cart', None)
                    session.pop('shipping_info', None)
                    session.pop('applied_voucher', None) # Hapus voucher setelah pembayaran berhasil

    except Exception as e:
        print("Kesalahan penanganan webhook:", e)
    return jsonify({'status': 'ok'}), 200

# -------------------------------
# Opsional: rute /payment/create langsung jika Anda lebih suka alur terpisah
# -------------------------------
@cart_bp.route('/payment/create/<int:order_id>', methods=['POST'])
def create_xendit_invoice_explicit(order_id):
    """
    Endpoint eksplisit alternatif untuk membuat invoice untuk pesanan yang sudah ada dan mengarahkan ke invoice_url.
    """
    if 'user' not in session:
        flash('Silakan login', 'error')
        return redirect(url_for('auth.login'))
    # ambil pesanan
    resp = supabase.table('orders').select('*').eq('id', order_id).single().execute()
    order = resp.data
    if not order:
        flash('Pesanan tidak ditemukan', 'error')
        return redirect(url_for('orders.order_history'))

    if not XENDIT_API_KEY:
        flash('Layanan pembayaran tidak dikonfigurasi', 'error')
        return redirect(url_for('orders.order_history'))

    payload = {
        "external_id": f"order-{order_id}",
        "amount": int(order['total']),
        "payer_email": session['user'].get('email'),
        "description": f"Pembayaran untuk pesanan #{order_id}",
        "success_redirect_url": url_for('cart.payment_success', order_id=order_id, _external=True),
        "failure_redirect_url": url_for('cart.payment_failed', order_id=order_id, _external=True)
    }

    try:
        r = requests.post("https://api.xendit.co/v2/invoices", auth=(XENDIT_API_KEY, ""), json=payload, timeout=15)
        invoice = r.json()
        if r.status_code in (200, 201) and invoice.get('invoice_url'):
            supabase.table('orders').update({'invoice_id': invoice.get('id'), 'invoice_url': invoice.get('invoice_url')}).eq('id', order_id).execute()
            # Jangan hapus cart dan shipping_info di sini
            session.pop('applied_voucher', None) # Hapus voucher setelah pembayaran dimulai
            return redirect(invoice.get('invoice_url'))
        else:
            print("Kesalahan eksplisit pembuatan Xendit:", r.status_code, r.text)
            flash('Gagal membuat invoice', 'error')
            return redirect(url_for('orders.order_history'))
    except Exception as e:
        print("Kesalahan pembuatan invoice:", e)
        flash('Kesalahan layanan pembayaran', 'error')
        return redirect(url_for('orders.order_history'))

# -------------------------------
# Rute baru untuk menangani pembayaran dari riwayat pesanan
# -------------------------------
@cart_bp.route('/checkout/finalize_from_history/<int:order_id>', methods=['POST'])
def checkout_finalize_from_history(order_id):
    if 'user' not in session:
        flash('Anda harus login untuk melanjutkan pembayaran', 'error')
        return redirect(url_for('auth.login'))

    try:
        # Ambil detail pesanan
        order_resp = supabase.table('orders').select('*').eq('id', order_id).eq('user_id', session['user']['id']).single().execute()
        order = order_resp.data

        if not order:
            flash('Pesanan tidak ditemukan atau bukan milik Anda.', 'error')
            return redirect(url_for('orders.order_history'))

        if order['status'] != 'pending':
            flash(f'Status pesanan adalah {order["status"]}. Tidak dapat melanjutkan pembayaran.', 'error')
            return redirect(url_for('orders.order_history'))

        # Ambil item pesanan untuk merekonstruksi keranjang untuk ditampilkan jika diperlukan, meskipun tidak terlalu penting untuk payload Xendit
        # Ini penting jika checkout_finalize digunakan untuk merender halaman sebelum mengarahkan ke Xendit
        # Untuk saat ini, kita akan langsung membuat invoice Xendit.
        
        if not XENDIT_API_KEY:
            flash('Layanan pembayaran tidak dikonfigurasi. Pesanan tetap tertunda (demo).', 'info')
            return redirect(url_for('orders.order_history'))

        invoice_payload = {
            "external_id": f"order-{order_id}",
            "amount": int(order['total']),
            "payer_email": session['user'].get('email'),
            "description": f"Pembayaran untuk pesanan #{order_id}",
            "success_redirect_url": url_for('cart.payment_success', order_id=order_id, _external=True),
            "failure_redirect_url": url_for('cart.payment_failed', order_id=order_id, _external=True)
        }

        resp = requests.post(
            "https://api.xendit.co/v2/invoices",
            auth=(XENDIT_API_KEY, ""),
            json=invoice_payload,
            timeout=15
        )

        try:
            invoice = resp.json()
        except Exception:
            invoice = None

        if resp.status_code in (200, 201) and invoice and invoice.get('invoice_url'):
            # Perbarui pesanan dengan info invoice
            supabase.table('orders').update({
                'invoice_id': invoice.get('id'),
                'invoice_url': invoice.get('invoice_url')
            }).eq('id', order_id).execute()

            # Redirect langsung ke halaman invoice Xendit
            session.pop('applied_voucher', None) # Hapus voucher setelah pembayaran dimulai
            return redirect(invoice.get('invoice_url'))
        else:
            print("Kesalahan invoice Xendit dari riwayat:", resp.status_code, resp.text)
            flash('Gagal membuat invoice pembayaran. Silakan hubungi admin.', 'error')
            return redirect(url_for('orders.order_history'))

    except Exception as e:
        print("❌ Kesalahan checkout dari riwayat:", e)
        flash(f'Kesalahan memproses pembayaran: {e}', 'error')
        return redirect(url_for('orders.order_history'))

