from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    openai_api_key = db.Column(db.String(256), nullable=True)

    profile = db.relationship('ResearchProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    articles = db.relationship('Article', backref='user', cascade='all, delete-orphan')
    digests = db.relationship('DailyDigest', backref='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ResearchProfile(db.Model):
    __tablename__ = 'research_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    main_topic = db.Column(db.String(500), nullable=False, default='')
    keywords = db.Column(db.Text, default='')
    must_include = db.Column(db.Text, default='')
    exclude_terms = db.Column(db.Text, default='')
    focus_areas = db.Column(db.Text, default='')

    platforms = db.Column(db.Text, default='["arxiv", "semantic_scholar"]')
    articles_per_day = db.Column(db.Integer, default=5)

    include_blogs = db.Column(db.Boolean, default=True)
    selected_blogs = db.Column(db.Text, default='["openai_blog", "google_ai", "deepmind", "anthropic"]')

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_platforms(self):
        try:
            return json.loads(self.platforms)
        except:
            return ['arxiv', 'semantic_scholar']

    def set_platforms(self, lst):
        self.platforms = json.dumps(lst)

    def get_selected_blogs(self):
        try:
            return json.loads(self.selected_blogs)
        except:
            return ['openai_blog', 'google_ai', 'deepmind', 'anthropic']

    def set_selected_blogs(self, lst):
        self.selected_blogs = json.dumps(lst)


class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    title = db.Column(db.String(1000), nullable=False)
    authors = db.Column(db.Text, default='')
    abstract = db.Column(db.Text, default='')
    url = db.Column(db.String(2000), default='')
    source_platform = db.Column(db.String(100), default='')
    published_date = db.Column(db.String(50), default='')
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_blog_post = db.Column(db.Boolean, default=False)

    summary_highlights = db.Column(db.Text, default='')
    summary_methodology = db.Column(db.Text, default='')
    summary_datasets = db.Column(db.Text, default='')
    summary_models = db.Column(db.Text, default='')
    summary_results = db.Column(db.Text, default='')
    summary_soul = db.Column(db.Text, default='')

    detail_approach = db.Column(db.Text, default='')
    detail_methodology = db.Column(db.Text, default='')
    detail_results = db.Column(db.Text, default='')
    detail_figures = db.Column(db.Text, default='')
    detail_writeup_summary = db.Column(db.Text, default='')

    relevance_score = db.Column(db.Float, default=0.0)
    digest_id = db.Column(db.Integer, db.ForeignKey('daily_digests.id'), nullable=True)


class DailyDigest(db.Model):
    __tablename__ = 'daily_digests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    date_label = db.Column(db.String(50), default='')
    status = db.Column(db.String(50), default='pending')
    error_message = db.Column(db.Text, default='')
    total_articles = db.Column(db.Integer, default=0)
    new_articles_count = db.Column(db.Integer, default=0)
    regenerated = db.Column(db.Boolean, default=False)

    articles = db.relationship('Article', backref='digest', lazy=True,
                                foreign_keys='Article.digest_id')
