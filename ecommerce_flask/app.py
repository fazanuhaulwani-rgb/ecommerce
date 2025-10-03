from flask import Flask, render_template, redirect, url_for, session, flash, request
from flask_session import Session
from supabase import create_client, Client
import os
import sys


from flask import Blueprint, session, request, redirect, url_for, flash

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import configuration
try:
    from config import config
except ImportError:
    # Fallback configuration if config.py is not available
    class config:
        default = type('Config', (), {
            'SECRET_KEY': os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production'),
            'SESSION_TYPE': 'filesystem',
            'SESSION_FILE_DIR': 'flask_session',
            'GOOGLE_CLIENT_ID': os.getenv('GOOGLE_CLIENT_ID'),
            'GOOGLE_CLIENT_SECRET': os.getenv('GOOGLE_CLIENT_SECRET'),
            'GOOGLE_REDIRECT_URI': 'http://localhost:5000/auth/google/callback',
            'SUPABASE_URL': os.getenv('SUPABASE_URL'),
            'SUPABASE_KEY': os.getenv('SUPABASE_KEY')
        })()

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Environment variables may not be loaded.")

# Initialize Flask app with explicit template and static folders
app = Flask(__name__, 
           template_folder=os.path.join(current_dir, 'templates'),
           static_folder=os.path.join(current_dir, 'static'))

# Get configuration
config_class = config.get(os.getenv('FLASK_ENV', 'default'), config['default'])
app.config.from_object(config_class)

# Print debug information
print(f"App running from: {current_dir}")
print(f"Template folder: {app.template_folder}")
print(f"Static folder: {app.static_folder}")
print(f"Template exists: {os.path.exists(os.path.join(app.template_folder, 'base_simple.html'))}")

# Initialize Session
Session(app)

# Supabase configuration
supabase_url = app.config.get('SUPABASE_URL')
supabase_key = app.config.get('SUPABASE_KEY')
supabase: Client = None

# Initialize Supabase only if credentials are provided and valid
def is_valid_supabase_credentials(url, key):
    """Check if Supabase credentials are valid (not placeholders)"""
    if not url or not key:
        return False
    
    # Check for various placeholder patterns
    placeholders = [
        'your-supabase-url-here',
        'your-supabase-key-here',
        'your-project-id',
        'placeholder',
        'your-'
    ]
    
    url_lower = url.lower()
    key_lower = key.lower()
    
    for placeholder in placeholders:
        if placeholder in url_lower or placeholder in key_lower:
            return False
    
    return True

if is_valid_supabase_credentials(supabase_url, supabase_key):
    try:
        supabase = create_client(supabase_url, supabase_key)
        # Test the connection by making a simple query
        test_response = supabase.table('users').select('count', count='exact').execute()
        print("[OK] Supabase client initialized successfully")
        print("[OK] Supabase connection tested successfully")
    except Exception as e:
        print(f"[ERROR] Error initializing Supabase client: {e}")
        print("[WARNING] Database features will be disabled.")
        supabase = None
else:
    print("[WARNING] Supabase credentials not configured or using placeholders. Database features will be disabled.")
    print("[WARNING] Please update your .env file with valid Supabase credentials.")
    supabase = None

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.products import products_bp
from blueprints.cart import cart_bp
from blueprints.orders import orders_bp

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(products_bp, url_prefix='/products')
app.register_blueprint(cart_bp, url_prefix='/cart')
app.register_blueprint(orders_bp, url_prefix='/orders')


products_bp = Blueprint('products', __name__)

@products_bp.route('/set_size', methods=['POST'])
def set_size():
    size = request.form.get('size')
    if size:
        session['preferred_size'] = size
        flash(f"Size {size} berhasil disimpan!", "success")
    else:
        flash("Pilih size terlebih dahulu!", "warning")
    return redirect(request.referrer or url_for('main.home'))


@app.route('/')
def home():
    """Home page with product catalog"""
    category = request.args.get('category')
    
    # Jika ada parameter kategori, redirect ke route list_products
    if category:
        return redirect(url_for('products.list_products', category=category))
    
    try:
        if supabase:
            try:
                response = supabase.table('products').select('*').execute()
                products = response.data if response.data else []
                
                # Debug: tampilkan jumlah dan kategori produk yang dikembalikan
                print(f"Home page - Total products: {len(products)}")
                print(f"Product categories: {[p.get('category', 'NO_CATEGORY') for p in products]}")
            except Exception as e:
                print("❌ Error loading products:", e)
                products = []
        else:
            # Sample products for demo when database is not configured
            products = [
                {
                    'id': 1,
                    'name': 'Sample Product 1',
                    'description': 'This is a sample product for demonstration',
                    'price': 100000,
                    'stock': 10,
                    'image_url': 'https://via.placeholder.com/300x200'
                },
                {
                    'id': 2,
                    'name': 'Sample Product 2',
                    'description': 'Another sample product for demonstration',
                    'price': 150000,
                    'stock': 5,
                    'image_url': 'https://via.placeholder.com/300x200'
                }
            ]
        return render_template('home.html', products=products)
    except Exception as e:
        flash('Error loading products', 'error')
        return render_template('home.html', products=[])



@app.route('/admin')
def admin():
    """Admin dashboard"""
    if 'user' not in session:
        flash('Please login to access admin panel', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user is admin (for demo purposes, we'll use a simple check)
    # In production, this should be stored in the database
    admin_emails = ['admin@4shoe.com', 'admin@example.com']
    if session['user']['email'] not in admin_emails:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('home'))
    
    try:
        if supabase:
            response = supabase.table('products').select('*').execute()
            products = response.data if response.data else []
        else:
            # Sample products for demo when database is not configured
            products = [
                {
                    'id': 1,
                    'name': 'Sample Product 1',
                    'description': 'This is a sample product for demonstration',
                    'price': 100000,
                    'stock': 10,
                    'image_url': 'https://via.placeholder.com/300x200'
                },
                {
                    'id': 2,
                    'name': 'Sample Product 2',
                    'description': 'Another sample product for demonstration',
                    'price': 150000,
                    'stock': 5,
                    'image_url': 'https://via.placeholder.com/300x200'
                }
            ]
        return render_template('admin.html', products=products)
    except Exception as e:
        flash('Error loading products', 'error')
        return render_template('admin.html', products=[])

@app.route('/login')
def login():
    """Login page"""
    return redirect(url_for('auth.login'))

@app.route('/register')
def register():
    """Register page"""
    return redirect(url_for('auth.register'))

@app.route('/logout')
def logout():
    """Logout page"""
    return redirect(url_for('auth.logout'))

@app.context_processor
def inject_category():
    """Fungsi untuk mengirimkan kategori aktif ke semua template"""
    return dict(active_category=request.args.get('category'))

@app.route("/shop-by-size")
def shop_by_size():
    sizes = {
        "MEN FOOTWEAR": [
            {"id": "39", "us": "6"},
            {"id": "40", "us": "7"},
            {"id": "40.5", "us": "7.5"},
            {"id": "41.5", "us": "8.5"},
            {"id": "42", "us": "9"},
            {"id": "42.5", "us": "9.5"},
            {"id": "43", "us": "10"},
            {"id": "44", "us": "10.5"},
            {"id": "44.5", "us": "11"},
            {"id": "45", "us": "11.5"},
            {"id": "45.5", "us": "12"},
            {"id": "46", "us": "12.5"},
        ],
        "WOMEN FOOTWEAR": [
            {"id": "35", "us": "5"},
            {"id": "36", "us": "6"},
            {"id": "36.5", "us": "6.5"},
            {"id": "37", "us": "6.5"},
            {"id": "37.5", "us": "7"},
            {"id": "38", "us": "7.5"},
            {"id": "39", "us": "8"},
            {"id": "40", "us": "9"},
            {"id": "40.5", "us": "9.5"},
            {"id": "41", "us": "10"},
            {"id": "41.5", "us": "10.5"},
            {"id": "43", "us": "11.5"},
        ],
        "KIDS FOOTWEAR": [
            {"id": "16", "us": "1C"},
            {"id": "16.5", "us": "2C"},
            {"id": "17", "us": "2C"},
            {"id": "18", "us": "3C"},
            {"id": "18.5", "us": "3.5C"},
            {"id": "20", "us": "4.5C"},
            {"id": "21", "us": "5C"},
            {"id": "22.5", "us": "6C"},
            {"id": "23.5", "us": "7C"},
            {"id": "25", "us": "8C"},
            {"id": "26", "us": "9C"},
            {"id": "27.5", "us": "10C"},
        ]
    }
    return render_template("shop_by_size.html", sizes=sizes)


app.secret_key = 'your_secret_key'

# Dummy data brand
brand_list = [
    {'name': 'Nike', 'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/a/a6/Logo_NIKE.svg', 'slug': 'nike'},
    {'name': 'Adidas', 'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/2/20/Adidas_Logo.svg', 'slug': 'adidas'},
    {'name': 'Puma', 'logo_url': 'https://www.svgrepo.com/show/303470/puma-logo-logo.svg', 'slug': 'puma'},
    {'name': 'Reebok', 'logo_url': 'https://upload.wikimedia.org/wikipedia/commons/5/53/Reebok_2019_logo.svg', 'slug': 'reebok'},
    {'name': 'Converse', 'logo_url': 'https://wallpapers.com/images/hd/white-2007-converse-logo-f9eskkopzvb311gm.jpg', 'slug': 'converse'},
    {'name': 'Specs', 'logo_url': 'https://2.bp.blogspot.com/-EcYgWHarEUs/VuYo9G8nuNI/AAAAAAAACEQ/JiIZWu9pH7IE0GAAU1B6H2K3HGQhe4gng/s1600/specs.png', 'slug': 'specs'},
    {'name': 'Ellesse', 'logo_url': 'https://logos-world.net/wp-content/uploads/2022/06/Ellesse-Logo.jpg', 'slug': 'ellesse'},
    {'name': 'Diadora', 'logo_url': 'https://cdn.freebiesupply.com/logos/thumbs/2x/diadora-logo.png', 'slug': 'diadora'},
]

# Route: All brands
@app.route('/brands')
def brands_all():
    return render_template('brands.html', brand_list=brand_list)


@app.route('/brands/<slug>')
def brand_detail(slug):
    # Cari brand berdasarkan slug di daftar brand_list
    brand = next((b for b in brand_list if b['slug'] == slug), None)
    if not brand:
        return "Brand tidak ditemukan", 404

    products = []
    try:
        if supabase:
            # Ambil produk yang namanya ada keyword brand (case-insensitive)
            response = supabase.table('products').select('*') \
                .ilike('name', f'%{brand["name"]}%').execute()
            products = response.data if response.data else []
        else:
            # Dummy data jika Supabase tidak aktif
            products = [
                {
                    'id': 1,
                    'name': f'{brand["name"]} Air Max',
                    'description': f'Sepatu {brand["name"]} terbaru dengan desain modern',
                    'price': 1200000,
                    'stock': 5,
                    'image_url': 'https://via.placeholder.com/300x200'
                },
                {
                    'id': 2,
                    'name': f'{brand["name"]} Runner',
                    'description': f'Sepatu lari {brand["name"]} dengan kenyamanan maksimal',
                    'price': 950000,
                    'stock': 8,
                    'image_url': 'https://via.placeholder.com/300x200'
                }
            ]
    except Exception as e:
        print(f"❌ Error ambil produk brand {brand['name']}: {e}")
        products = []

    return render_template(
        'products.html',   # pakai template produk umum
        products=products,
        active_category=brand["name"],
        brand=brand
    )


# Dummy data sports
sports_list = [
    {
        "name": "Running", 
        "slug": "running", 
        "img_url": "https://img.icons8.com/color/96/running.png"
    },
    {
        "name": "Training", 
        "slug": "training", 
        "img_url": "https://img.freepik.com/premium-vector/silhouette-young-man-training-football-logo-design-vector-graphic-symbol-icon-sign-illustration_15473-9327.jpg?w=2000"
    },
    {
        "name": "Outdoor", 
        "slug": "outdoor", 
        "img_url": "https://img.icons8.com/color/96/mountain.png"
    },
]

# Route: All sports
@app.route("/sports")
def sports_all():
    return render_template("sports_all.html", sports_list=sports_list)

@app.route("/sports/<slug>")
def sport_detail(slug):
    # Cari sport berdasarkan slug
    sport = next((s for s in sports_list if s['slug'] == slug), None)
    if not sport:
        return "Sport tidak ditemukan", 404

    products = []

    try:
        if supabase:
            # Filter produk di DB berdasarkan slug
            response = supabase.table('products').select('*') \
                .eq('sport', sport['slug']).execute()
            products = response.data if response.data else []
        else:
            # Dummy produk jika DB tidak aktif
            products = [
                {
                    'id': 1,
                    'name': f'{sport["name"]} Shoes Pro',
                    'description': f'Sepatu {sport["name"]} premium untuk performa maksimal',
                    'price': 1500000,
                    'stock': 10,
                    'img_url': 'https://via.placeholder.com/300x200',
                    'sport': sport['slug']
                },
                {
                    'id': 2,
                    'name': f'{sport["name"]} Flex',
                    'description': f'Sepatu {sport["name"]} dengan desain ringan dan nyaman',
                    'price': 1100000,
                    'stock': 7,
                    'img_url': 'https://via.placeholder.com/300x200',
                    'sport': sport['slug']
                }
            ]
    except Exception as e:
        print(f"❌ Error ambil produk sport {sport['name']}: {e}")
        products = []

    return render_template(
        "sport_detail.html",
        sport=sport,
        products=products
    )

    


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000)) 
        app.run(host="0.0.0.0", port=port, debug=True)
