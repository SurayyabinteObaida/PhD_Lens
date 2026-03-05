from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import Article
from extensions import db

articles_bp = Blueprint('articles', __name__, url_prefix='/articles')


@articles_bp.route('/')
@login_required
def library():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '')
    source = request.args.get('source', '')
    sort_by = request.args.get('sort', 'relevance')

    query = Article.query.filter_by(user_id=current_user.id)

    if search:
        query = query.filter(
            db.or_(
                Article.title.ilike(f'%{search}%'),
                Article.abstract.ilike(f'%{search}%'),
                Article.authors.ilike(f'%{search}%')
            )
        )
    if source:
        query = query.filter(Article.source_platform == source)

    if sort_by == 'relevance':
        query = query.order_by(Article.relevance_score.desc())
    elif sort_by == 'date':
        query = query.order_by(Article.fetched_at.desc())
    elif sort_by == 'title':
        query = query.order_by(Article.title.asc())

    articles = query.paginate(page=page, per_page=15, error_out=False)

    sources = db.session.query(Article.source_platform).filter_by(
        user_id=current_user.id
    ).distinct().all()
    sources = [s[0] for s in sources if s[0]]

    return render_template('library.html', articles=articles, search=search,
                           source=source, sort_by=sort_by, sources=sources)
