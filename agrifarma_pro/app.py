import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta, timezone
from flask import abort
import re


# ----------------- CONFIGURATION -----------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agrifarma.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-secret-key-for-dev-only')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 

db = SQLAlchemy(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ----------------- DATABASE MODELS -----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    mobile = db.Column(db.String(20))
    location = db.Column(db.String(200))
    profession = db.Column(db.String(50))
    expertise = db.Column(db.String(50))
    profile_picture = db.Column(db.String(200))
    join_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_consultant = db.Column(db.Boolean, default=False)
    consultant_category = db.Column(db.String(100))
    consultant_approved = db.Column(db.Boolean, default=False)
    
    products = db.relationship('Product', backref='owner', lazy=True, cascade='all, delete-orphan')
    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='customer', lazy=True, cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='user', lazy=True, cascade='all, delete-orphan')
    consultations_requested = db.relationship('Consultation', foreign_keys='Consultation.user_id', backref='client', lazy=True)
    consultations_received = db.relationship('Consultation', foreign_keys='Consultation.consultant_id', backref='consultant', lazy=True)
    consultations_requested = db.relationship('Consultation', foreign_keys='Consultation.user_id', backref='client', lazy=True)
consultations_received = db.relationship('Consultation', foreign_keys='Consultation.consultant_id', backref='consultant', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    type = db.Column(db.String(50))
    
    # Relationships
    posts = db.relationship('Post', backref='category', lazy=True)
    products = db.relationship('Product', backref='product_category', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(100), nullable=False)
    subcategory = db.Column(db.String(100))
    featured = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    stock_quantity = db.Column(db.Integer, default=1)
    created_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    
    # Relationships
    orders = db.relationship('Order', backref='product', lazy=True, cascade='all, delete-orphan')
    cart_items = db.relationship('CartItem', backref='product', lazy=True, cascade='all, delete-orphan')
    posts = db.relationship('Post', backref='product', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    post_type = db.Column(db.String(50))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='SET NULL'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    created_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    tags = db.Column(db.String(200))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'))
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    shipping_address = db.Column(db.Text)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'))
    quantity = db.Column(db.Integer, default=1)
    added_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    consultant_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    scheduled_date = db.Column(db.DateTime, nullable=True)
    consultation_fee = db.Column(db.Float, default=0)

# ----------------- HELPER FUNCTIONS -----------------

def save_file(file):
    """Save uploaded file and return filename"""
    if file and file.filename:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        return unique_filename
    return None

def get_cart_items_count(user_id):
    """Get count of items in user's cart"""
    return CartItem.query.filter_by(user_id=user_id).count()

def get_cart_items(user_id):
    """Get all cart items for user"""
    return CartItem.query.filter_by(user_id=user_id).all()

def get_cart_total(user_id):
    """Calculate total price of items in cart"""
    cart_items = get_cart_items(user_id)
    total = 0
    for item in cart_items:
        if item.product:  # Add null check
            total += item.product.price * item.quantity
    return total

def clear_cart(user_id):
    """Clear user's cart"""
    CartItem.query.filter_by(user_id=user_id).delete()
    db.session.commit()

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_price(price):
    try:
        return float(price) > 0
    except (ValueError, TypeError):
        return False

# ----------------- ROUTES -----------------
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@app.route('/')
def index():
    try:
        featured_products = Product.query.filter_by(featured=True, active=True).limit(4).all()
        latest_posts = Post.query.order_by(Post.created_date.desc()).limit(3).all()
        return render_template('index.html', 
                             featured_products=featured_products, 
                             latest_posts=latest_posts)
    except Exception as e:
        flash(f"Error loading homepage: {str(e)}", "danger")
        return render_template('index.html', featured_products=[], latest_posts=[])

# --- User Registration ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('register'))
        
        if not validate_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        mobile = request.form.get('mobile')
        location = request.form.get('location')
        profession = request.form.get('profession')
        expertise = request.form.get('expertise')

        profile_picture = None
        if 'profile_picture' in request.files:
            profile_picture = save_file(request.files['profile_picture'])

        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            mobile=mobile,
            location=location,
            profession=profession,
            expertise=expertise,
            profile_picture=profile_picture
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash("Email or username already exists!", "warning")
            return redirect(url_for('register'))
        except Exception as e:
            db.session.rollback()
            flash(f"Registration failed: {str(e)}", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

# --- User Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session['user'] = user.username
            session['user_id'] = user.id
            session['is_consultant'] = user.is_consultant
            session.permanent = True
            flash("Login successful!", "success")
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials!", "danger")

    return render_template('login.html')

# --- User Dashboard ---
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash("Please login to access dashboard.", "warning")
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['user']).first()
    if not user:
        flash("User not found. Please login again.", "danger")
        return redirect(url_for('logout'))

    try:
        user_products = Product.query.filter_by(user_id=user.id).all()
        user_posts = Post.query.filter_by(user_id=user.id).all()
        user_orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_date.desc()).limit(5).all()
        return render_template('dashboard.html', user=user, products=user_products, posts=user_posts, orders=user_orders)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return render_template('dashboard.html', user=user, products=[], posts=[], orders=[])

# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# --- Add Product ---
@app.route('/add', methods=['GET', 'POST'])
def add_product():
    if 'user' not in session:
        flash("Please login to add products.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description')
        category = request.form.get('category')

        if not name or not price or not description or not category:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('add_product'))

        try:
            price = float(price)
            if price <= 0:
                flash("Price must be greater than 0.", "danger")
                return redirect(url_for('add_product'))
        except ValueError:
            flash("Invalid price format.", "danger")
            return redirect(url_for('add_product'))

        subcategory = request.form.get('subcategory')
        stock_quantity = request.form.get('stock_quantity', 1)
        try:
            stock_quantity = int(stock_quantity)
            if stock_quantity < 0:
                flash("Stock quantity cannot be negative.", "danger")
                return redirect(url_for('add_product'))
        except ValueError:
            flash("Invalid stock quantity format.", "danger")
            return redirect(url_for('add_product'))

        featured = 'featured' in request.form

        image_file = request.files.get('image')
        filename = save_file(image_file) if image_file else None

        new_product = Product(
            name=name,
            price=price,
            description=description,
            image=filename,
            category=category,
            subcategory=subcategory,
            stock_quantity=stock_quantity,
            featured=featured,
            user_id=session['user_id']
        )

        try:
            db.session.add(new_product)
            db.session.commit()
            flash("Product added successfully!", "success")
            return redirect(url_for('products'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding product: {str(e)}", "danger")
            return redirect(url_for('add_product'))

    return render_template('add_product.html')

# --- Product List ---
@app.route('/products')
def products():
    try:
        category = request.args.get('category', '')
        search = request.args.get('search', '')

        query = Product.query.filter_by(active=True)

        if category:
            query = query.filter_by(category=category)
        if search:
            query = query.filter(Product.name.contains(search) | Product.description.contains(search))

        all_products = query.all()
        categories = db.session.query(Product.category).distinct().all()

        return render_template('products.html', products=all_products, categories=categories, selected_category=category, search_query=search)
    except Exception as e:
        flash(f"Error loading products: {str(e)}", "danger")
        return render_template('products.html', products=[], categories=[], selected_category='', search_query='')

# --- Product Detail ---
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    try:
        product = Product.query.get_or_404(product_id)
        return render_template('product_detail.html', product=product)
    except Exception as e:
        flash(f"Error loading product: {str(e)}", "danger")
        return redirect(url_for('products'))

# --- Discussion Forum ---
@app.route('/forum')
def forum():
    try:
        posts = Post.query.filter_by(post_type='forum').order_by(Post.created_date.desc()).all()
        return render_template('forum.html', posts=posts)
    except Exception as e:
        flash(f"Error loading forum: {str(e)}", "danger")
        return render_template('forum.html', posts=[])

@app.route('/forum/new', methods=['GET', 'POST'])
def new_forum_post():
    if 'user' not in session:
        flash("Please login to create a post.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if not title or not content:
            flash("Please fill both title and content.", "danger")
            return redirect(url_for('new_forum_post'))

        tags = request.form.get('tags', '')
        category_id = request.form.get('category_id')

        try:
            if category_id:
                category_id = int(category_id)
        except (ValueError, TypeError):
            category_id = None

        new_post = Post(
            title=title,
            content=content,
            post_type='forum',
            user_id=session['user_id'],
            tags=tags,
            category_id=category_id
        )

        try:
            db.session.add(new_post)
            db.session.commit()
            flash("Post created successfully!", "success")
            return redirect(url_for('forum'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating post: {str(e)}", "danger")
            return redirect(url_for('new_forum_post'))

    return render_template('new_post.html')

# --- Blog ---
@app.route('/blog')
def blog():
    try:
        posts = Post.query.filter_by(post_type='blog').order_by(Post.created_date.desc()).all()
        return render_template('blog.html', posts=posts)
    except Exception as e:
        flash(f"Error loading blog: {str(e)}", "danger")
        return render_template('blog.html', posts=[])

# --- Consultancy Services ---
@app.route('/consultants')
def consultants():
    try:
        consultants = User.query.filter_by(is_consultant=True, consultant_approved=True).all()
        return render_template('consultants.html', consultants=consultants)
    except Exception as e:
        flash(f"Error loading consultants: {str(e)}", "danger")
        return render_template('consultants.html', consultants=[])

@app.route('/become_consultant', methods=['GET', 'POST'])
def become_consultant():
    if 'user' not in session:
        flash("Please login to become a consultant.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        category = request.form.get('category')
        experience = request.form.get('experience')
        expertise = request.form.get('expertise')
        summary = request.form.get('summary')
        
        if not all([category, experience, expertise]):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('become_consultant'))

        user = User.query.get(session['user_id'])
        user.is_consultant = True
        user.consultant_category = category
        user.expertise = expertise  # Update user expertise
        user.consultant_approved = False

        try:
            db.session.commit()
            flash("Application submitted! Waiting for admin approval.", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error submitting application: {str(e)}", "danger")
            return redirect(url_for('become_consultant'))

    return render_template('become_consultant.html')

@app.route('/book_consultation/<int:consultant_id>', methods=['GET', 'POST'])
def book_consultation(consultant_id):
    if 'user' not in session:
        flash("Please login to book consultation.", "warning")
        return redirect(url_for('login'))
    
    consultant = User.query.get_or_404(consultant_id)
    
    if not consultant.is_consultant or not consultant.consultant_approved:
        flash("This user is not an approved consultant.", "danger")
        return redirect(url_for('consultants'))
    
    if request.method == 'POST':
        category = request.form.get('category')
        description = request.form.get('description')
        scheduled_date = request.form.get('scheduled_date')
        
        if not all([category, description]):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('book_consultation', consultant_id=consultant_id))
        
        try:
            scheduled_datetime = None
            if scheduled_date:
                scheduled_datetime = datetime.strptime(scheduled_date, '%Y-%m-%dT%H:%M')
                
            consultation = Consultation(
                user_id=session['user_id'],
                consultant_id=consultant_id,
                category=category,
                description=description,
                scheduled_date=scheduled_datetime
            )
            
            db.session.add(consultation)
            db.session.commit()
            flash("Consultation request sent successfully!", "success")
            return redirect(url_for('consultants'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error booking consultation: {str(e)}", "danger")
            return redirect(url_for('book_consultation', consultant_id=consultant_id))
    
    return render_template('book_consultation.html', consultant=consultant)

# --- Shopping Cart ---
@app.before_request
def make_session_permanent():
    session.permanent = True
    if 'user_id' in session:
        session['cart_count'] = get_cart_items_count(session['user_id'])

@app.route('/cart')
def cart():
    if 'user' not in session:
        flash("Please login to view cart.", "warning")
        return redirect(url_for('login'))
    
    try:
        cart_items = get_cart_items(session['user_id'])
        total = get_cart_total(session['user_id'])
        return render_template('cart.html', cart_items=cart_items, total=total)
    except Exception as e:
        flash(f"Error loading cart: {str(e)}", "danger")
        return render_template('cart.html', cart_items=[], total=0)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user' not in session:
        flash("Please login to add items to cart.", "warning")
        return redirect(url_for('login'))

    try:
        product = Product.query.get_or_404(product_id)
        
        if product.stock_quantity <= 0:
            flash("This product is out of stock.", "warning")
            return redirect(url_for('product_detail', product_id=product_id))
        
        existing_item = CartItem.query.filter_by(
            user_id=session['user_id'], 
            product_id=product_id
        ).first()
        
        if existing_item:
            if existing_item.quantity >= product.stock_quantity:
                flash("Cannot add more items than available in stock.", "warning")
                return redirect(url_for('product_detail', product_id=product_id))
            existing_item.quantity += 1
        else:
            new_cart_item = CartItem(
                user_id=session['user_id'],
                product_id=product_id,
                quantity=1
            )
            db.session.add(new_cart_item)
        
        db.session.commit()
        flash(f"{product.name} added to cart!", "success")
        return redirect(url_for('product_detail', product_id=product_id))
    except Exception as e:
        db.session.rollback()
        flash(f"Error adding product to cart: {str(e)}", "danger")
        return redirect(url_for('products'))

@app.route('/cart/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    if 'user' not in session:
        return jsonify({'error': 'Please login'}), 401
    
    try:
        quantity = request.json.get('quantity', 1)
        cart_item = CartItem.query.filter_by(
            user_id=session['user_id'], 
            product_id=product_id
        ).first()
        
        if cart_item:
            product = Product.query.get(product_id)
            if quantity > product.stock_quantity:
                return jsonify({'error': f'Only {product.stock_quantity} items available'}), 400
                
            if quantity <= 0:
                db.session.delete(cart_item)
            else:
                cart_item.quantity = quantity
            db.session.commit()
            
        cart_items = get_cart_items(session['user_id'])
        total = get_cart_total(session['user_id'])
        
        return jsonify({
            'success': True, 
            'total': total,
            'item_count': len(cart_items)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/cart/remove/<int:product_id>')
def remove_from_cart(product_id):
    if 'user' not in session:
        flash("Please login to manage cart.", "warning")
        return redirect(url_for('login'))
    
    try:
        cart_item = CartItem.query.filter_by(
            user_id=session['user_id'], 
            product_id=product_id
        ).first()
        
        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
            flash("Item removed from cart.", "success")
        else:
            flash("Item not found in cart.", "warning")
            
        return redirect(url_for('cart'))
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing item from cart: {str(e)}", "danger")
        return redirect(url_for('cart'))

# --- Checkout and Orders ---
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user' not in session:
        flash("Please login to checkout.", "warning")
        return redirect(url_for('login'))
    
    cart_items = get_cart_items(session['user_id'])
    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for('cart'))
    
    total = get_cart_total(session['user_id'])
    
    if request.method == 'POST':
        shipping_address = request.form.get('shipping_address')
        
        if not shipping_address:
            flash("Please provide a shipping address.", "danger")
            return redirect(url_for('checkout'))
        
        try:
            # Check stock availability for all items first
            for cart_item in cart_items:
                if cart_item.product.stock_quantity < cart_item.quantity:
                    flash(f"Not enough stock for {cart_item.product.name}. Only {cart_item.product.stock_quantity} available.", "danger")
                    return redirect(url_for('cart'))
            
            # Create orders for each cart item
            for cart_item in cart_items:
                # Create order
                order = Order(
                    user_id=session['user_id'],
                    product_id=cart_item.product_id,
                    quantity=cart_item.quantity,
                    total_price=cart_item.product.price * cart_item.quantity,
                    shipping_address=shipping_address,
                    status='confirmed'
                )
                db.session.add(order)
                
                # Update product stock
                cart_item.product.stock_quantity -= cart_item.quantity
            
            # Clear cart after successful order
            clear_cart(session['user_id'])
            db.session.commit()
            
            flash("Order placed successfully!", "success")
            return redirect(url_for('order_confirmation'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error processing order: {str(e)}", "danger")
            return redirect(url_for('checkout'))
    
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/order_confirmation')
def order_confirmation():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Get the latest order for confirmation
    latest_order = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_date.desc()).first()
    if not latest_order:
        flash("No recent orders found.", "warning")
        return redirect(url_for('user_orders'))
    return render_template('order_confirmation.html', order=latest_order)

@app.route('/orders')
def user_orders():
    if 'user' not in session:
        flash("Please login to view orders.", "warning")
        return redirect(url_for('login'))
    
    try:
        orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_date.desc()).all()
        return render_template('orders.html', orders=orders)
    except Exception as e:
        flash(f"Error loading orders: {str(e)}", "danger")
        return render_template('orders.html', orders=[])

# --- Password Reset ---
@app.route('/reset_request', methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash("Please enter your email address.", "danger")
            return redirect(url_for('reset_request'))
            
        if not validate_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for('reset_request'))

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("No account found with that email.", "warning")
            return redirect(url_for('reset_request'))

        token = s.dumps(email, salt='password-reset')
        reset_link = url_for('reset_password', token=token, _external=True)
        flash(f"Password reset link (simulated): {reset_link}", "info")
        return redirect(url_for('login'))

    return render_template('reset_request.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset', max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for('reset_request'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not password:
            flash("Please enter a new password.", "danger")
            return redirect(url_for('reset_password', token=token))
        
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return redirect(url_for('reset_password', token=token))
        
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('reset_password', token=token))

        new_password = generate_password_hash(password)
        user = User.query.filter_by(email=email).first()

        if user:
            user.password = new_password
            db.session.commit()
            flash("Your password has been reset. Please log in.", "success")
            return redirect(url_for('login'))
        else:
            flash("User not found.", "danger")
            return redirect(url_for('reset_request'))

    return render_template('reset_password.html')

# ----------------- MAIN -----------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)