from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
import threading
from extensions import db
from models import DailyDigest, Article

dashboard_bp = Blueprint('dashboard', __name__)


def run_digest_thread(app, user_id, digest_id):
    with app.app_context():
        from models import User, DailyDigest
        from fetcher import run_digest
        user = User.query.get(user_id)
        digest = DailyDigest.query.get(digest_id)
        if user and digest:
            run_digest(user, digest)


@dashboard_bp.route('/dashboard')
@login_required
def home():
    profile = current_user.profile
    latest_digest = DailyDigest.query.filter_by(
        user_id=current_user.id
    ).order_by(DailyDigest.created_at.desc()).first()

    articles = []
    if latest_digest and latest_digest.status == 'ready':
        articles = Article.query.filter_by(
            digest_id=latest_digest.id
        ).order_by(Article.relevance_score.desc()).all()

    all_digests = DailyDigest.query.filter_by(
        user_id=current_user.id
    ).order_by(DailyDigest.created_at.desc()).limit(10).all()

    return render_template('dashboard.html',
                           profile=profile,
                           latest_digest=latest_digest,
                           articles=articles,
                           all_digests=all_digests)


@dashboard_bp.route('/digest/start', methods=['POST'])
@login_required
def start_digest():
    from flask import current_app

    processing = DailyDigest.query.filter_by(
        user_id=current_user.id,
        status='processing'
    ).first()
    if processing:
        return jsonify({'status': 'already_processing', 'digest_id': processing.id})

    profile = current_user.profile
    if not profile or not profile.main_topic:
        return jsonify({'status': 'error', 'message': 'Please configure your research profile first.'})

    if not current_user.openai_api_key:
        return jsonify({'status': 'error', 'message': 'Please add your OpenAI API key in Settings.'})

    today = datetime.utcnow().strftime('%B %d, %Y')
    digest = DailyDigest(user_id=current_user.id, date_label=today, status='pending')
    db.session.add(digest)
    db.session.commit()

    app = current_app._get_current_object()
    thread = threading.Thread(target=run_digest_thread, args=(app, current_user.id, digest.id), daemon=True)
    thread.start()

    return jsonify({'status': 'started', 'digest_id': digest.id})


@dashboard_bp.route('/digest/<int:digest_id>/status')
@login_required
def digest_status(digest_id):
    digest = DailyDigest.query.filter_by(id=digest_id, user_id=current_user.id).first_or_404()
    return jsonify({
        'status': digest.status,
        'total_articles': digest.total_articles,
        'new_articles_count': digest.new_articles_count,
        'regenerated': digest.regenerated,
        'error_message': digest.error_message
    })


@dashboard_bp.route('/digest/<int:digest_id>')
@login_required
def view_digest(digest_id):
    digest = DailyDigest.query.filter_by(id=digest_id, user_id=current_user.id).first_or_404()
    articles = Article.query.filter_by(digest_id=digest.id).order_by(Article.relevance_score.desc()).all()
    return render_template('digest_view.html', digest=digest, articles=articles)


@dashboard_bp.route('/article/<int:article_id>')
@login_required
def view_article(article_id):
    article = Article.query.filter_by(id=article_id, user_id=current_user.id).first_or_404()
    view_mode = request.args.get('view', 'summary')
    return render_template('article_view.html', article=article, view_mode=view_mode)
