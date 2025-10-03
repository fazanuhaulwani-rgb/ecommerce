from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = None

# Initialize Supabase only if credentials are provided
if supabase_url and supabase_key and supabase_url != 'your-supabase-url-here' and supabase_key != 'your-supabase-key-here':
    try:
        supabase = create_client(supabase_url, supabase_key)
        print("[OK] Supabase client initialized successfully in products blueprint")
    except Exception as e:
        print(f"[ERROR] Error initializing Supabase client in products blueprint: {e}")
        supabase = None
else:
    print("[WARNING] Supabase credentials not configured. Product features will be limited.")
    supabase = None

products_bp = Blueprint('products', __name__)

@products_bp.route('/list')
def list_products():
    """List all products"""
    try:
        category = request.args.get('category')  # ambil query param

        query = supabase.table('products').select('*')

        if category:  # filter hanya jika kategori ada
            query = query.eq('category', category.lower())  # pastikan lowercase sesuai DB

        try:
            response = query.execute()
            products = response.data if response.data else []
            
            # Debug: tampilkan kategori produk yang dikembalikan query
            print("Query returned:", [p.get('category', 'NO_CATEGORY') for p in response.data])
        except Exception as e:
            print("❌ Error loading products:", e)
            products = []

        if not supabase:
            print("❌ Supabase client not initialized")
            flash('Database connection not available', 'error')
            return render_template('products.html', products=[], active_category=category)

        return render_template('products.html', products=products, active_category=category)
    except Exception as e:
        print("❌ Error loading products:", e)
        flash('Error loading products', 'error')
        return render_template('products.html', products=[], active_category=category)

    # MultipleFiles/products.py

    # ... (kode yang sudah ada di atas) ...

@products_bp.route('/product/<int:product_id>')
def view_product(product_id):
    """Product detail page"""
    try:
        product_detail = None
        related_products = [] # Pastikan ini diinisialisasi

        if supabase:
            response = supabase.table('products').select('*').eq('id', product_id).execute()
            product_detail = response.data[0] if response.data else None
        else:
            # sample product for demo - TAMBAHKAN KATEGORI DI SINI
            product_detail = {
                'id': product_id,
                'name': f'Sample Product {product_id}',
                'description': 'This is a sample product description.',
                'price': 100000,
                'stock': 10,
                'image_url': 'https://via.placeholder.com/300x200',
                'category': 'man' # <--- TAMBAHKAN INI
            }

        if not product_detail:
            flash('Product not found', 'error')
            return redirect(url_for('home'))
            
        # --- LOGIKA BARU: Ambil produk terkait ---
        if supabase and product_detail.get('category'):
            try:
                # Ambil produk lain dengan kategori yang sama, kecuali produk saat ini
                related_response = supabase.table('products').select('*') \
                                            .eq('category', product_detail['category']) \
                                            .neq('id', product_id) \
                                            .limit(4) \
                                            .execute()
                related_products = related_response.data if related_response.data else []
            except Exception as e:
                print(f"❌ Error loading related products: {e}")
                related_products = []
        elif not supabase:
            # Produk sampel terkait jika Supabase tidak terhubung
            related_products = [
                {
                    'id': product_id + 1,
                    'name': f'Related Product {product_id + 1}',
                    'price': 90000,
                    'image_url': 'https://picsum.photos/seed/related1/200/200.jpg',
                    'category': product_detail.get('category', 'man')
                },
                {
                    'id': product_id + 2,
                    'name': f'Related Product {product_id + 2}',
                    'price': 110000,
                    'image_url': 'https://picsum.photos/seed/related2/200/200.jpg',
                    'category': product_detail.get('category', 'man')
                }
            ]
         # --- AKHIR LOGIKA BARU ---

        # Hitung nilai maksimum kuantitas (menghindari penggunaan min() di template)
        # Kita ingin range dari 1 sampai minimum antara stok produk dan 10
        stock_value = product_detail.get('stock', 0)  # Gunakan .get() untuk nilai default
        if stock_value > 0:
            max_stock = min(stock_value, 10)
        else:
            max_stock = 1  # Minimal 1 jika stok nol atau negatif, tapi tombol add to cart akan dinonaktifkan
        max_quantity = max_stock + 1  # Ditambah 1 karena range() tidak menyertakan batas atas
            
        # Render the correct template - KIRIM related_products DI SINI
        return render_template('product_detail.html', product=product_detail, max_quantity=max_quantity, related_products=related_products) # <--- TAMBAHKAN related_products

    except Exception as e:
        flash(f'Error loading product: {e}', 'error')
        return redirect(url_for('home'))

    
    
@products_bp.route('/add', methods=['GET', 'POST'])
def add_product():
    """Add new product (admin only)"""
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Check if user is admin
    admin_emails = ['admin@4shoe.com', 'admin@example.com']
    if session['user']['email'] not in admin_emails:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        image_url = request.form.get('image_url')
        stock = int(request.form.get('stock'))
        category = request.form.get('category')
        
        try:
            if not supabase:
                print("❌ Supabase client not initialized")
                flash('Database connection not available', 'error')
                return redirect(url_for('admin'))
                
            supabase.table('products').insert({
                'name': name,
                'description': description,
                'price': price,
                'image_url': image_url,
                'stock': stock,
                'category': category
            }).execute()
            
            flash('Product added successfully!', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            print("❌ Error adding product:", e)
            flash('Error adding product', 'error')
    
    return render_template('add_product.html')

@products_bp.route('/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """Edit product (admin only)"""
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Check if user is admin
    admin_emails = ['admin@4shoe.com', 'admin@example.com']
    if session['user']['email'] not in admin_emails:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        image_url = request.form.get('image_url')
        stock = int(request.form.get('stock'))
        category = request.form.get('category')
        
        try:
            if not supabase:
                print("❌ Supabase client not initialized")
                flash('Database connection not available', 'error')
                return redirect(url_for('admin'))
                
            supabase.table('products').update({
                'name': name,
                'description': description,
                'price': price,
                'image_url': image_url,
                'stock': stock,
                'category': category
            }).eq('id', product_id).execute()
            
            flash('Product updated successfully!', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            print("❌ Error updating product:", e)
            flash('Error updating product', 'error')
    
    # GET request - show edit form
    try:
        if not supabase:
            print("❌ Supabase client not initialized")
            flash('Database connection not available', 'error')
            return redirect(url_for('admin'))
        
        response = supabase.table('products').select('*').eq('id', product_id).execute()
        product = response.data
        if not product or len(product) == 0:
            flash('Product not found', 'error')
            return redirect(url_for('admin'))
        
        # Since Supabase returns a list even for single records, take the first item
        product = product[0]
        
        return render_template('edit_product.html', product=product)
    except Exception as e:
        print("❌ Error loading product:", e)
        flash('Error loading product', 'error')
        return redirect(url_for('admin'))

@products_bp.route('/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """Delete product (admin only)"""
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    
    # Check if user is admin
    admin_emails = ['admin@4shoe.com', 'admin@example.com']
    if session['user']['email'] not in admin_emails:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    try:
        if not supabase:
            print("❌ Supabase client not initialized")
            flash('Database connection not available', 'error')
            return redirect(url_for('admin'))
            
        supabase.table('products').delete().eq('id', product_id).execute()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        print("❌ Error deleting product:", e)
        flash('Error deleting product', 'error')
    
    return redirect(url_for('admin'))