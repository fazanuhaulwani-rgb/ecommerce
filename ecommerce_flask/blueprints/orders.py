from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = None

# Initialize Supabase only if credentials are provided
if supabase_url and supabase_key and supabase_url != 'your-supabase-url-here' and supabase_key != 'your-supabase-key-here':
    try:
        supabase = create_client(supabase_url, supabase_key)
        print("[OK] Supabase client initialized successfully in orders blueprint")
    except Exception as e:
        print(f"[ERROR] Error initializing Supabase client in orders blueprint: {e}")
        supabase = None
else:
    print("[WARNING] Supabase credentials not configured. Order features will be limited.")
    supabase = None

orders_bp = Blueprint('orders', __name__)

@orders_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user' not in session:
        flash('Please login to checkout', 'info')
        return redirect(url_for('auth.login'))
    
    cart = session.get('cart', [])
    if not cart:
        flash('Your cart is empty', 'info')
        return redirect(url_for('cart.view_cart'))

    # Ambil detail produk untuk setiap item di keranjang
    cart_items = []
    total = 0
    for item in cart:
        if supabase:
            response = supabase.table('products').select('*').eq('id', item['product_id']).execute()
            product_detail = response.data[0] if response.data else None
        else:
            product_detail = {
                'id': item['product_id'],
                'name': f'Sample Product {item["product_id"]}',
                'price': 100000,
                'stock': 10,
                'image_url': 'https://via.placeholder.com/300x200'
            }
        
        if product_detail:
            item_total = product_detail['price'] * item['quantity']
            total += item_total
            cart_items.append({
                'id': product_detail['id'],
                'name': product_detail['name'],
                'price': product_detail['price'],
                'stock': product_detail['stock'],
                'image_url': product_detail['image_url'],
                'quantity': item['quantity'],
                'total_price': item_total
            })

    if request.method == 'POST':
        shipping_address = request.form.get('shipping_address')
        if not shipping_address:
            flash('Shipping address is required', 'error')
            return render_template('checkout.html', user=session['user'], cart_items=cart_items, total=total)
        
        # Lanjutkan proses checkout seperti biasa
        # ...
    
    return render_template('checkout.html', user=session['user'], cart_items=cart_items, total=total)

@orders_bp.route('/confirmation/<int:order_id>')
def order_confirmation(order_id):
    """Order confirmation page"""
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Cek apakah Supabase terkonfigurasi
    if not supabase:
        flash('Database connection not available', 'error')
        return redirect(url_for('home'))
    
    try:
        # Ambil order dengan kolom baru
        response = supabase.table('orders').select('*, discount_amount, shipping_cost, voucher_code').eq('id', order_id).eq('user_id', session['user']['id']).single().execute()
        order = response.data
        
        if not order:
            flash('Order not found', 'error')
            return redirect(url_for('home'))
        
        # Ambil order_items untuk order ini
        try:
            order_items_response = supabase.table('order_items').select('*').eq('order_id', order['id']).execute()
            order_items = order_items_response.data if order_items_response.data else []
            
            # Ambil informasi produk untuk setiap item
            detailed_items = []
            for item in order_items:
                try:
                    product_response = supabase.table('products').select('*').eq('id', item['product_id']).execute()
                    product = product_response.data[0] if product_response.data else None
                    
                    detailed_items.append({
                        'quantity': item['quantity'],
                        'price': item['price'],
                        'total_price': item['quantity'] * item['price'],
                        'product': product
                    })
                except Exception as e:
                    print(f"❌ Error getting product info for item {item.get('product_id', 'unknown')}: {e}")
                    # Tambahkan item tanpa informasi produk jika gagal mengambil
                    detailed_items.append({
                        'quantity': item['quantity'],
                        'price': item['price'],
                        'total_price': item['quantity'] * item['price'],
                        'product': {'name': f'Product #{item.get("product_id", "unknown")}'}
                    })
            
            order['items'] = detailed_items
        except Exception as e:
            print(f"❌ Error getting items for order {order_id}: {e}")
            order['items'] = []
        
        return render_template('order_confirmation.html', order=order)
    except Exception as e:
        print("❌ Error loading order confirmation:", e)
        flash('Error loading order', 'error')
        return redirect(url_for('home'))

@orders_bp.route('/history')
def order_history():
    if 'user' not in session:
        flash("You must be logged in", "error")
        return redirect(url_for('auth.login'))

    user_id = session['user']['id']

    try:
        # Ambil order + order_items sekaligus, termasuk kolom voucher baru
        resp = supabase.table('orders').select('id, total, status, created_at, discount_amount, shipping_cost, voucher_code, order_items(product_id, quantity, price)').eq('user_id', user_id).order('created_at', desc=True).execute()
        orders = resp.data if resp.data else []

        # Ambil semua product info agar bisa tampil nama & gambar
        product_ids = [item['product_id'] for order in orders for item in order.get('order_items', [])]
        products = {}
        if product_ids:
            products_resp = supabase.table('products').select('id, name, image_url').in_('id', product_ids).execute()
            for p in products_resp.data:
                products[p['id']] = p

        # Tambahkan info produk ke tiap order_item
        for order in orders:
            for item in order.get('order_items', []):
                prod = products.get(item['product_id'])
                if prod:
                    item['name'] = prod['name']
                    item['image_url'] = prod.get('image_url')

        return render_template('order_history.html', orders=orders)

    except Exception as e:
        print("❌ Error loading order history:", e)
        flash("Error loading order history", "error")
        return render_template('order_history.html', orders=[])

@orders_bp.route('/admin/orders')
def admin_orders():
    """Admin order management"""
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Check if user is admin
    admin_emails = ['admin@4shoe.com', 'admin@example.com']
    if session['user']['email'] not in admin_emails:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    try:
        # Ambil order dengan kolom baru
        response = supabase.table('orders').select('*, discount_amount, shipping_cost, voucher_code').order('created_at', desc=True).execute()
        orders = response.data if response.data else []
        
        return render_template('admin_orders.html', orders=orders)
    except Exception as e:
        flash('Error loading orders', 'error')
        return render_template('admin_orders.html', orders=[])

@orders_bp.route('/admin/update_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    """Update order status (admin only)"""
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Check if user is admin
    admin_emails = ['admin@4shoe.com', 'admin@example.com']
    if session['user']['email'] not in admin_emails:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    status = request.form.get('status')
    
    try:
        supabase.table('orders').update({
            'status': status
        }).eq('id', order_id).execute()
        
        flash('Order status updated!', 'success')
    except Exception as e:
        flash('Error updating order status', 'error')
    
    return redirect(url_for('orders.admin_orders'))

