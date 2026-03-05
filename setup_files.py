"""
Run this once from your project root to write all source files correctly.
    python setup_files.py
"""
import os

files = {}

files['extensions.py'] = '''from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
'''

files['app.py'] = '''import os
from flask import Flask
from dotenv import load_dotenv
from extensions import db, login_manager

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///phdlens.db')
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access your dashboard.'
    login_manager.login_message_category = 'info'

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.settings import settings_bp
    from routes.articles import articles_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(articles_bp)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False') == 'True')
'''

files['models.py'] = '''from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json


class User(UserMixin, db.Model):
    __tablename__ = \'users\'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    openai_api_key = db.Column(db.String(256), nullable=True)

    profile = db.relationship(\'ResearchProfile\', backref=\'user\', uselist=False, cascade=\'all, delete-orphan\')
    articles = db.relationship(\'Article\', backref=\'user\', cascade=\'all, delete-orphan\')
    digests = db.relationship(\'DailyDigest\', backref=\'user\', cascade=\'all, delete-orphan\')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ResearchProfile(db.Model):
    __tablename__ = \'research_profiles\'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(\'users.id\'), nullable=False)

    main_topic = db.Column(db.String(500), nullable=False, default=\'\')
    keywords = db.Column(db.Text, default=\'\')
    must_include = db.Column(db.Text, default=\'\')
    exclude_terms = db.Column(db.Text, default=\'\')
    focus_areas = db.Column(db.Text, default=\'\')

    platforms = db.Column(db.Text, default=\'["arxiv", "semantic_scholar"]\')
    articles_per_day = db.Column(db.Integer, default=5)

    include_blogs = db.Column(db.Boolean, default=True)
    selected_blogs = db.Column(db.Text, default=\'["openai_blog", "google_ai", "deepmind", "anthropic"]\')

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_platforms(self):
        try:
            return json.loads(self.platforms)
        except:
            return [\'arxiv\', \'semantic_scholar\']

    def set_platforms(self, lst):
        self.platforms = json.dumps(lst)

    def get_selected_blogs(self):
        try:
            return json.loads(self.selected_blogs)
        except:
            return [\'openai_blog\', \'google_ai\', \'deepmind\', \'anthropic\']

    def set_selected_blogs(self, lst):
        self.selected_blogs = json.dumps(lst)


class Article(db.Model):
    __tablename__ = \'articles\'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(\'users.id\'), nullable=False)

    title = db.Column(db.String(1000), nullable=False)
    authors = db.Column(db.Text, default=\'\')
    abstract = db.Column(db.Text, default=\'\')
    url = db.Column(db.String(2000), default=\'\')
    source_platform = db.Column(db.String(100), default=\'\')
    published_date = db.Column(db.String(50), default=\'\')
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_blog_post = db.Column(db.Boolean, default=False)

    summary_highlights = db.Column(db.Text, default=\'\')
    summary_methodology = db.Column(db.Text, default=\'\')
    summary_datasets = db.Column(db.Text, default=\'\')
    summary_models = db.Column(db.Text, default=\'\')
    summary_results = db.Column(db.Text, default=\'\')
    summary_soul = db.Column(db.Text, default=\'\')

    detail_approach = db.Column(db.Text, default=\'\')
    detail_methodology = db.Column(db.Text, default=\'\')
    detail_results = db.Column(db.Text, default=\'\')
    detail_figures = db.Column(db.Text, default=\'\')
    detail_writeup_summary = db.Column(db.Text, default=\'\')

    relevance_score = db.Column(db.Float, default=0.0)
    digest_id = db.Column(db.Integer, db.ForeignKey(\'daily_digests.id\'), nullable=True)


class DailyDigest(db.Model):
    __tablename__ = \'daily_digests\'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(\'users.id\'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    date_label = db.Column(db.String(50), default=\'\')
    status = db.Column(db.String(50), default=\'pending\')
    error_message = db.Column(db.Text, default=\'\')
    total_articles = db.Column(db.Integer, default=0)
    new_articles_count = db.Column(db.Integer, default=0)
    regenerated = db.Column(db.Boolean, default=False)

    articles = db.relationship(\'Article\', backref=\'digest\', lazy=True,
                                foreign_keys=\'Article.digest_id\')
'''

files['routes/__init__.py'] = ''

files['routes/auth.py'] = '''from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, ResearchProfile

auth_bp = Blueprint(\'auth\', __name__)


@auth_bp.route(\'/\')
def index():
    if current_user.is_authenticated:
        return redirect(url_for(\'dashboard.home\'))
    return render_template(\'landing.html\')


@auth_bp.route(\'/register\', methods=[\'GET\', \'POST\'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(\'dashboard.home\'))
    if request.method == \'POST\':
        name = request.form.get(\'name\', \'\').strip()
        email = request.form.get(\'email\', \'\').strip().lower()
        password = request.form.get(\'password\', \'\')
        confirm = request.form.get(\'confirm_password\', \'\')
        openai_key = request.form.get(\'openai_api_key\', \'\').strip()

        if not name or not email or not password:
            flash(\'All fields are required.\', \'error\')
            return render_template(\'register.html\')
        if password != confirm:
            flash(\'Passwords do not match.\', \'error\')
            return render_template(\'register.html\')
        if len(password) < 8:
            flash(\'Password must be at least 8 characters.\', \'error\')
            return render_template(\'register.html\')
        if User.query.filter_by(email=email).first():
            flash(\'An account with this email already exists.\', \'error\')
            return render_template(\'register.html\')

        user = User(name=name, email=email, openai_api_key=openai_key if openai_key else None)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        profile = ResearchProfile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()

        login_user(user)
        flash("Account created. Let\'s set up your research profile.", \'success\')
        return redirect(url_for(\'settings.research_profile\'))

    return render_template(\'register.html\')


@auth_bp.route(\'/login\', methods=[\'GET\', \'POST\'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(\'dashboard.home\'))
    if request.method == \'POST\':
        email = request.form.get(\'email\', \'\').strip().lower()
        password = request.form.get(\'password\', \'\')
        remember = request.form.get(\'remember\') == \'on\'

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get(\'next\')
            return redirect(next_page or url_for(\'dashboard.home\'))
        flash(\'Invalid email or password.\', \'error\')

    return render_template(\'login.html\')


@auth_bp.route(\'/logout\')
@login_required
def logout():
    logout_user()
    return redirect(url_for(\'auth.login\'))
'''

files['routes/dashboard.py'] = '''from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
import threading
from extensions import db
from models import DailyDigest, Article

dashboard_bp = Blueprint(\'dashboard\', __name__)


def run_digest_thread(app, user_id, digest_id):
    with app.app_context():
        from models import User, DailyDigest
        from fetcher import run_digest
        user = User.query.get(user_id)
        digest = DailyDigest.query.get(digest_id)
        if user and digest:
            run_digest(user, digest)


@dashboard_bp.route(\'/dashboard\')
@login_required
def home():
    profile = current_user.profile
    latest_digest = DailyDigest.query.filter_by(
        user_id=current_user.id
    ).order_by(DailyDigest.created_at.desc()).first()

    articles = []
    if latest_digest and latest_digest.status == \'ready\':
        articles = Article.query.filter_by(
            digest_id=latest_digest.id
        ).order_by(Article.relevance_score.desc()).all()

    all_digests = DailyDigest.query.filter_by(
        user_id=current_user.id
    ).order_by(DailyDigest.created_at.desc()).limit(10).all()

    return render_template(\'dashboard.html\',
                           profile=profile,
                           latest_digest=latest_digest,
                           articles=articles,
                           all_digests=all_digests)


@dashboard_bp.route(\'/digest/start\', methods=[\'POST\'])
@login_required
def start_digest():
    from flask import current_app

    processing = DailyDigest.query.filter_by(
        user_id=current_user.id,
        status=\'processing\'
    ).first()
    if processing:
        return jsonify({\'status\': \'already_processing\', \'digest_id\': processing.id})

    profile = current_user.profile
    if not profile or not profile.main_topic:
        return jsonify({\'status\': \'error\', \'message\': \'Please configure your research profile first.\'})

    if not current_user.openai_api_key:
        return jsonify({\'status\': \'error\', \'message\': \'Please add your OpenAI API key in Settings.\'})

    today = datetime.utcnow().strftime(\'%B %d, %Y\')
    digest = DailyDigest(user_id=current_user.id, date_label=today, status=\'pending\')
    db.session.add(digest)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=run_digest_thread, args=(app, current_user.id, digest.id), daemon=True)
    thread.start()

    return jsonify({\'status\': \'started\', \'digest_id\': digest.id})


@dashboard_bp.route(\'/digest/<int:digest_id>/status\')
@login_required
def digest_status(digest_id):
    digest = DailyDigest.query.filter_by(id=digest_id, user_id=current_user.id).first_or_404()
    return jsonify({
        \'status\': digest.status,
        \'total_articles\': digest.total_articles,
        \'new_articles_count\': digest.new_articles_count,
        \'regenerated\': digest.regenerated,
        \'error_message\': digest.error_message
    })


@dashboard_bp.route(\'/digest/<int:digest_id>\')
@login_required
def view_digest(digest_id):
    digest = DailyDigest.query.filter_by(id=digest_id, user_id=current_user.id).first_or_404()
    articles = Article.query.filter_by(digest_id=digest.id).order_by(Article.relevance_score.desc()).all()
    return render_template(\'digest_view.html\', digest=digest, articles=articles)


@dashboard_bp.route(\'/article/<int:article_id>\')
@login_required
def view_article(article_id):
    article = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()
    view_mode = request.args.get(\'view\', \'summary\')
    return render_template(\'article_view.html\', article=article, view_mode=view_mode)
'''

files['routes/settings.py'] = '''import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import ResearchProfile

settings_bp = Blueprint(\'settings\', __name__, url_prefix=\'/settings\')

PLATFORM_OPTIONS = [
    (\'arxiv\', \'arXiv\'),
    (\'semantic_scholar\', \'Semantic Scholar\'),
    (\'pubmed\', \'PubMed\'),
    (\'crossref\', \'CrossRef\'),
]

BLOG_OPTIONS = [
    (\'openai_blog\', \'OpenAI Research Blog\'),
    (\'google_ai\', \'Google AI Blog\'),
    (\'deepmind\', \'DeepMind Blog\'),
    (\'anthropic\', \'Anthropic Blog\'),
    (\'microsoft_research\', \'Microsoft Research Blog\'),
    (\'sebastian_ruder\', "Sebastian Ruder\'s Blog"),
    (\'distill\', \'Distill.pub\'),
    (\'towards_data_science\', \'Towards Data Science\'),
]


@settings_bp.route(\'/profile\', methods=[\'GET\', \'POST\'])
@login_required
def research_profile():
    profile = current_user.profile
    if not profile:
        profile = ResearchProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == \'POST\':
        profile.main_topic = request.form.get(\'main_topic\', \'\').strip()
        profile.keywords = request.form.get(\'keywords\', \'\').strip()
        profile.must_include = request.form.get(\'must_include\', \'\').strip()
        profile.exclude_terms = request.form.get(\'exclude_terms\', \'\').strip()
        profile.focus_areas = request.form.get(\'focus_areas\', \'\').strip()

        selected_platforms = request.form.getlist(\'platforms\')
        if not selected_platforms:
            selected_platforms = [\'arxiv\']
        profile.set_platforms(selected_platforms)

        try:
            apd = int(request.form.get(\'articles_per_day\', 5))
            profile.articles_per_day = max(1, min(20, apd))
        except:
            profile.articles_per_day = 5

        profile.include_blogs = \'include_blogs\' in request.form
        selected_blogs = request.form.getlist(\'blogs\')
        profile.set_selected_blogs(selected_blogs)

        openai_key = request.form.get(\'openai_api_key\', \'\').strip()
        if openai_key:
            current_user.openai_api_key = openai_key

        db.session.commit()
        flash(\'Research profile updated successfully.\', \'success\')
        return redirect(url_for(\'dashboard.home\'))

    return render_template(\'settings.html\', profile=profile,
                           platform_options=PLATFORM_OPTIONS, blog_options=BLOG_OPTIONS)


@settings_bp.route(\'/account\', methods=[\'GET\', \'POST\'])
@login_required
def account():
    if request.method == \'POST\':
        name = request.form.get(\'name\', \'\').strip()
        openai_key = request.form.get(\'openai_api_key\', \'\').strip()
        current_password = request.form.get(\'current_password\', \'\')
        new_password = request.form.get(\'new_password\', \'\')
        confirm_password = request.form.get(\'confirm_password\', \'\')

        if name:
            current_user.name = name
        if openai_key:
            current_user.openai_api_key = openai_key

        if current_password and new_password:
            if not current_user.check_password(current_password):
                flash(\'Current password is incorrect.\', \'error\')
                return render_template(\'account.html\')
            if new_password != confirm_password:
                flash(\'New passwords do not match.\', \'error\')
                return render_template(\'account.html\')
            if len(new_password) < 8:
                flash(\'Password must be at least 8 characters.\', \'error\')
                return render_template(\'account.html\')
            current_user.set_password(new_password)

        db.session.commit()
        flash(\'Account updated successfully.\', \'success\')

    return render_template(\'account.html\')
'''

files['routes/articles.py'] = '''from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import Article
from extensions import db

articles_bp = Blueprint(\'articles\', __name__, url_prefix=\'/articles\')


@articles_bp.route(\'/\')
@login_required
def library():
    page = request.args.get(\'page\', 1, type=int)
    search = request.args.get(\'q\', \'\')
    source = request.args.get(\'source\', \'\')
    sort_by = request.args.get(\'sort\', \'relevance\')

    query = Article.query.filter_by(user_id=current_user.id)

    if search:
        query = query.filter(
            db.or_(
                Article.title.ilike(f\'%{search}%\'),
                Article.abstract.ilike(f\'%{search}%\'),
                Article.authors.ilike(f\'%{search}%\')
            )
        )
    if source:
        query = query.filter(Article.source_platform == source)

    if sort_by == \'relevance\':
        query = query.order_by(Article.relevance_score.desc())
    elif sort_by == \'date\':
        query = query.order_by(Article.fetched_at.desc())
    elif sort_by == \'title\':
        query = query.order_by(Article.title.asc())

    articles = query.paginate(page=page, per_page=15, error_out=False)

    sources = db.session.query(Article.source_platform).filter_by(
        user_id=current_user.id
    ).distinct().all()
    sources = [s[0] for s in sources if s[0]]

    return render_template(\'library.html\', articles=articles, search=search,
                           source=source, sort_by=sort_by, sources=sources)
'''


# Write all files
for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Written: {path}')

print('\nAll files written. Run: python app.py')
